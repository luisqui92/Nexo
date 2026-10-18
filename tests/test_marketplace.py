"""Exercise anonymous browsing and hostile requests across independent workspaces."""
import json
import sqlite3
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
import test_flows as flows
from test_flows import request
import accounts
import server
from reception import handle_voice, cancel

class MarketplaceFlow(unittest.TestCase):
    def setUp(self):
        flows.VisitFlow.setUp(self)
        with server.db() as conn:
            conn.execute('DELETE FROM api_rate_limits')
            conn.execute("DELETE FROM workspaces WHERE id!='legacy'")
        self.admin_cookie=flows.AUTH_COOKIE
        self.ind,self.ic=self.signup('independiente')
        self.agency,self.ac=self.signup('agencia','agency')
        self.other,self.oc=self.signup('otro')
        self.prop=self.create('properties',{'title':'Departamento luminoso','zone':'Cala Cala','type':'Departamento','operation':'Venta','price':89000,'currency':'USD','status':'Disponible','area':112,'bedrooms':3,'bathrooms':2,'parking':1,'description':'Balcón y vista abierta.','address':'Dirección privada 123','notes':'Nota interna confidencial','features':['Balcón']},self.ic)
        self.photo=self.upload(self.prop['id'],b'\xff\xd8\xffphoto-test\xff\xd9','image/jpeg',self.ic)
        self.pdf=self.upload(self.prop['id'],b'%PDF documento privado','application/pdf',self.ic)
        self.payload={'propertyId':self.prop['id'],'latitude':-17.366129,'longitude':-66.161489,'city':'Cochabamba','contactPhone':'59170000000','photoIds':[self.photo['id']],'status':'published','confirmPublication':True}

    def signup(self,username,kind='independent',**extra):
        body={'name':'Nombre '+username,'username':username,'password':'marketplace-test-password','accountType':kind,'agencyName':'Inmobiliaria '+username,'email':username+'@example.test','phone':'+59170000000','acceptTerms':True,**extra}
        result=request('POST','/api/public/register',body,cookie='')
        self.assertEqual(result['status'],201,result)
        return result['data']['user'],next(v.split(';')[0] for k,v in result['headers'] if k=='Set-Cookie')
    def create(self,kind,data,cookie):
        r=request('POST','/api/'+kind,data,cookie=cookie);self.assertEqual(r['status'],201,r);return r['data']
    def upload(self,rid,raw,mime,cookie):
        r=request('POST','/api/files?recordId='+rid,raw=raw,mime=mime,cookie=cookie);self.assertEqual(r['status'],201,r);return r['data']
    def publish(self,**changes):
        r=request('POST','/api/publications',{**self.payload,**changes},cookie=self.ic);self.assertEqual(r['status'],200,r);return r['data']

    def test_registration_assigns_own_space_and_never_platform_privileges(self):
        self.assertEqual(self.ind['role'],'advisor');self.assertEqual(self.ind['workspaceKind'],'independent');self.assertFalse(self.ind['platformAdmin'])
        self.assertEqual(self.agency['role'],'admin');self.assertFalse(self.agency['platformAdmin'])
        self.assertNotEqual(self.ind['workspaceId'],self.agency['workspaceId'])
        for cookie in (self.ic,self.ac):
            self.assertEqual(request('GET','/api/platform',cookie=cookie)['status'],403)
            self.assertEqual(request('POST','/api/ai-settings',{'provider':'openai','key':'secret-never-used'},cookie=cookie)['status'],403)
        with server.db() as conn:conn.execute('DELETE FROM api_rate_limits')
        for forged in ({'platformAdmin':True},{'workspaceId':'legacy'},{'role':'admin'}):
            r=request('POST','/api/public/register',{'username':'forged',**forged},cookie='');self.assertEqual(r['status'],400)
        config=request('GET','/api/config',cookie=self.ic)['data'];self.assertFalse(config['ai']);self.assertFalse(config['transcription']);self.assertFalse(config['aiEnabled'])

    def test_crm_lists_direct_reads_files_and_assignments_stay_in_workspace(self):
        customer=self.create('clients',{'name':'Cliente privado','role':'Comprador','currency':'USD'},self.ic)
        visit=self.create('visits',{'clientId':customer['id'],'propertyId':self.prop['id'],'date':'2026-10-18T10:00'},self.ic)
        for cookie in (self.ac,self.oc,self.admin_cookie):
            for kind,obj in (('properties',self.prop),('clients',customer),('visits',visit)):
                self.assertEqual(request('GET',f"/api/{kind}/{obj['id']}",cookie=cookie)['status'],404)
                ids=[r['id'] for r in request('GET','/api/'+kind,cookie=cookie)['data']];self.assertNotIn(obj['id'],ids)
            self.assertEqual(request('GET','/api/files/'+self.photo['id'],cookie=cookie)['status'],404)
        self.assertEqual(request('PATCH','/api/properties/'+self.prop['id'],{'workspaceId':'legacy'},cookie=self.ic)['status'],403)
        self.assertEqual(request('PATCH','/api/properties/'+self.prop['id'],{'ownerId':self.other['id']},cookie=self.ic)['status'],400)
        forged=self.create('properties',{'title':'Propiedad de agencia','zone':'Centro','operation':'Venta','price':100,'currency':'USD','status':'Disponible'},self.ac)
        cross=request('POST','/api/assign',{'kind':'properties','id':forged['id'],'advisorIds':[self.ind['id']]},cookie=self.ac)
        self.assertEqual(cross['status'],400)
        teammate=request('POST','/api/users',{'name':'Equipo','username':'equipo.agencia','password':'agency-test-password','workspaceId':'legacy'},cookie=self.ac)['data']
        self.assertEqual(teammate['workspaceId'],self.agency['workspaceId'])
        visible=request('GET','/api/users',cookie=self.ac)['data']['users'];self.assertEqual({u['id'] for u in visible},{self.agency['id'],teammate['id']})
        export=request('GET','/api/export',cookie=self.ac)['data'];self.assertNotIn(self.prop['id'],json.dumps(export));self.assertNotIn(self.ind['id'],json.dumps(export))

    def test_only_explicit_publications_are_visible_and_private_fields_are_omitted(self):
        self.assertEqual(request('GET','/api/public/listings',cookie='')['data']['total'],0)
        publication=self.publish()
        listing=request('GET','/api/public/listings/'+publication['id'],cookie='')['data']
        self.assertEqual(listing['title'],self.prop['title']);self.assertEqual(listing['latitude'],-17.37);self.assertEqual(listing['longitude'],-66.16)
        raw=json.dumps(listing)
        for private in ('Dirección privada','Nota interna','workspaceId','advisorIds','ownerId','createdById','password_hash','salt','example.test',self.prop['id'],self.pdf['id']):self.assertNotIn(private,raw)
        self.assertEqual(request('GET',listing['photos'][0],cookie='')['data'],b'\xff\xd8\xffphoto-test\xff\xd9')
        self.assertEqual(request('GET',f"/api/public/photos/{publication['id']}/{self.pdf['id']}",cookie='')['status'],404)
        self.assertEqual(request('GET','/api/properties/'+self.prop['id'],cookie='')['status'],401)
        self.assertEqual(request('POST','/api/publications',self.payload,cookie=self.oc)['status'],404)
        self.assertEqual(request('PATCH','/api/publications/'+publication['id'],{'status':'paused'},cookie=self.ac)['status'],404)

    def test_publication_validation_rejects_documents_invalid_locations_and_unconsented_uploads(self):
        for changes in ({'photoIds':[self.pdf['id']]},{'latitude':float('nan')},{'longitude':181},{'latitude':True},{'photoIds':[]},{'confirmPublication':False},{'publisherId':self.other['id']}):
            result=request('POST','/api/publications',{**self.payload,**changes},cookie=self.ic);self.assertEqual(result['status'],400,result)
        self.publish(status='draft',photoIds=[],confirmPublication=False)
        self.assertEqual(request('GET','/api/public/listings',cookie='')['data']['total'],0)
        request('PATCH','/api/properties/'+self.prop['id'],{'demo':True},cookie=self.ic)
        self.assertEqual(request('POST','/api/publications',self.payload,cookie=self.ic)['status'],400)

    def test_pause_sale_block_and_suspension_remove_both_listing_and_public_photo(self):
        publication=self.publish();pid=publication['id'];photo=f"/api/public/photos/{pid}/{self.photo['id']}"
        request('PATCH','/api/publications/'+pid,{'status':'paused'},cookie=self.ic)
        self.assertEqual(request('GET',photo,cookie='')['status'],404)
        self.publish()
        request('PATCH','/api/properties/'+self.prop['id'],{'status':'Vendido'},cookie=self.ic)
        self.assertEqual(request('GET','/api/public/listings/'+pid,cookie='')['status'],404)
        request('PATCH','/api/properties/'+self.prop['id'],{'status':'Disponible'},cookie=self.ic)
        request('PATCH','/api/platform/publications/'+pid,{'blocked':True})
        self.publish() # Owner cannot remove a moderation block by republishing.
        self.assertEqual(request('GET',photo,cookie='')['status'],404)
        request('PATCH','/api/platform/publications/'+pid,{'blocked':False})
        self.assertEqual(request('GET',photo,cookie='')['status'],200)
        request('PATCH','/api/platform/workspaces/'+self.ind['workspaceId'],{'active':False})
        self.assertEqual(request('GET',photo,cookie='')['status'],404)
        self.assertEqual(request('GET','/api/state',cookie=self.ic)['status'],401)

    def test_search_price_currency_area_pagination_and_publisher(self):
        self.publish()
        for params,expected in (({'q':'cala'},1),({'currency':'BOB'},0),({'maxPrice':'90000','currency':'USD'},1),({'maxPrice':'80000','currency':'USD'},0),({'publisher':self.ind['id']},1),({'publisher':self.other['id']},0),({'bedrooms':4},0),({'south':-17.38,'north':-17.36,'west':-66.17,'east':-66.15},1),({'city':'La Paz'},0)):
            result=request('GET','/api/public/listings?'+urlencode(params),cookie='');self.assertEqual(result['status'],200,result);self.assertEqual(result['data']['total'],expected,params)
        self.assertEqual(request('GET','/api/public/listings?maxPrice=90000',cookie='')['status'],400)
        self.assertEqual(request('GET','/api/public/listings?limit=1000',cookie='')['status'],400)
        result=request('GET','/api/public/listings?page=2&limit=1',cookie='')['data'];self.assertEqual(result['total'],1);self.assertEqual(result['listings'],[])

    def test_inquiry_is_stored_privately_and_never_confirms_a_booking(self):
        publication=self.publish();path='/api/public/listings/'+publication['id']+'/inquiries'
        data={'name':'Persona interesada','phone':'59171111111','message':'Quiero visitar','preferredDate':'2026-10-20T10:00','consent':True}
        self.assertEqual(request('POST',path,{**data,'consent':False},cookie='')['status'],400)
        result=request('POST',path,data,cookie='');self.assertEqual(result['status'],201,result)
        self.assertIn('confirmar',result['data']['message'])
        own=request('GET','/api/inquiries',cookie=self.ic)['data']['inquiries'];self.assertEqual(len(own),1);self.assertEqual(own[0]['body']['phone'],'59171111111')
        for cookie in (self.ac,self.oc,self.admin_cookie):
            self.assertEqual(request('GET','/api/inquiries',cookie=cookie)['data']['inquiries'],[])
            self.assertEqual(request('PATCH','/api/inquiries/'+own[0]['id'],{'status':'Contactada'},cookie=cookie)['status'],404)
        self.assertEqual(request('PATCH','/api/inquiries/'+own[0]['id'],{'status':'Contactada'},cookie=self.ic)['status'],200)
        state=request('GET','/api/state',cookie=self.ic)['data'];self.assertEqual(state['events'],[]);self.assertEqual(state['clients'],[])
        request('POST','/api/public/listings/'+publication['id']+'/report',{'reason':'Información incorrecta','details':'Revisar precio'},cookie='')
        reports=request('GET','/api/platform')['data']['reports'];self.assertEqual(len(reports),1)
        self.assertEqual(request('GET','/api/platform',cookie=self.ic)['status'],403)
        request('PATCH','/api/platform/reports/'+reports[0]['id'],{'resolved':True})
        self.assertEqual(request('GET','/api/platform')['data']['reports'],[])

    def test_rate_limits_csrf_and_signup_rollback(self):
        # Three accounts were registered in setUp; two invalid attempts also count.
        for _ in range(2):self.assertEqual(request('POST','/api/public/register',{},cookie='')['status'],400)
        self.assertEqual(request('POST','/api/public/register',{},cookie='')['status'],429)
        self.assertEqual(request('POST','/api/publications',self.payload,cookie=self.ic,origin='https://evil.example')['status'],403)
        with server.db() as conn:self.assertEqual(conn.execute('SELECT count(*) FROM workspaces WHERE name=?',('Inmobiliaria agencia',)).fetchone()[0],1)

    def test_disabled_ai_cannot_spend_shared_key_and_can_be_enabled_by_nexo(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':'never-sent-test-key'}),patch('server.external_json') as external:
            self.assertEqual(request('POST','/api/analyse',{'text':'Busca un departamento con dos dormitorios.'},cookie=self.ic)['status'],403)
            self.assertEqual(request('POST','/api/transcribe',{'fileId':'anything'},cookie=self.ic)['status'],403)
            external.assert_not_called()
            self.assertEqual(request('POST','/api/analyse',{'text':'Busca un departamento con dos dormitorios.','local':True},cookie=self.ic)['status'],200)
            request('PATCH','/api/platform/workspaces/'+self.ind['workspaceId'],{'aiEnabled':True})
            self.assertTrue(request('GET','/api/config',cookie=self.ic)['data']['aiEnabled'])

    def test_private_audio_and_follow_up_remain_inside_independent_workspace(self):
        client=self.create('clients',{'name':'Cliente propio','role':'Comprador','currency':'USD'},self.ic)
        visit=self.create('visits',{'clientId':client['id'],'propertyId':self.prop['id'],'date':'2026-10-18T10:00'},self.ic)
        audio=self.upload(visit['id'],b'audio','audio/webm',self.ic)
        request('PATCH','/api/visits/'+visit['id'],{'audioId':audio['id']},cookie=self.ic)
        confirm=request('POST','/api/visits/'+visit['id']+'/confirm',{'sheet':{'nextStep':'Llamar al cliente','followUp':'2026-10-20'},'createFollowUp':True},cookie=self.ic)
        self.assertEqual(confirm['status'],200,confirm)
        own=request('GET','/api/state',cookie=self.ic)['data'];self.assertEqual(len(own['events']),1);self.assertEqual(own['events'][0]['workspaceId'],self.ind['workspaceId'])
        self.assertNotIn(audio['id'],json.dumps(request('GET','/api/state')['data']))
        with server.db() as conn:
            self.assertNotIn(self.prop['id'],handle_voice(conn,'listar_inmuebles',{}))
            with self.assertRaises(ValueError):handle_voice(conn,'consultar_disponibilidad',{'propertyId':self.prop['id']})
            with self.assertRaises(ValueError):cancel(conn,own['events'][0]['id'],'59170000000')

    def test_public_pages_are_served_without_login(self):
        for path in ('/explorar','/registro','/inmueble/example','/asesor/example','/condiciones.html'):
            r=request('GET',path,cookie='');self.assertEqual(r['status'],200,r);self.assertIn('text/html',r['mime'])
        with patch.dict('os.environ',{'NEXO_DEPLOYMENT':'1','NEXO_HTTPS':'1','NEXO_DOMAIN':'app.chatgo.ia.bo'}):
            self.assertEqual(request('GET','/api/public/listings',cookie='',host='app.chatgo.ia.bo')['status'],200)

if __name__=='__main__':unittest.main()
