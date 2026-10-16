import json
import unittest
from unittest.mock import patch

import accounts
import server
import test_flows as flows
from test_flows import request

class TeamAccess(unittest.TestCase):
    def setUp(self):
        with server.db() as conn:
            for table in ('files','records','audit','sessions','users','login_attempts'):
                conn.execute('DELETE FROM '+table)
        flows.AUTH_COOKIE=''
        self.admin=self.setup_admin()
        self.a=self.create_advisor('ana','Ana Asesora')
        self.b=self.create_advisor('bruno','Bruno Asesor')
        self.ca=self.login('ana')
        self.cb=self.login('bruno')
        self.client=self.create('clients',{'name':'Cliente de Ana','role':'Comprador','currency':'USD','advisorId':self.a['id'],'needs':[],'zones':[]})
        self.property=self.create('properties',{'title':'Inmueble compartido','zone':'Centro','operation':'Venta','status':'Disponible','currency':'USD','price':80000,'advisorIds':[self.a['id'],self.b['id']]})
        self.private=self.create('properties',{'title':'Privado de Bruno','zone':'Norte','operation':'Venta','status':'Disponible','currency':'USD','price':90000,'advisorIds':[self.b['id']]})

    def setup_admin(self):
        r=request('POST','/api/auth/setup',{'username':'admin','name':'Administración','password':'unit-test-password'},cookie='')
        self.assertEqual(r['status'],201,r)
        flows.AUTH_COOKIE=self.cookie(r)
        return r['data']['user']
    def cookie(self,r): return next(v.split(';')[0] for k,v in r['headers'] if k=='Set-Cookie')
    def create_advisor(self,username,name):
        r=request('POST','/api/users',{'username':username,'name':name,'password':'unit-test-password','role':'admin'})
        self.assertEqual(r['status'],201,r)
        self.assertEqual(r['data']['role'],'advisor')
        return r['data']
    def login(self,username):
        r=request('POST','/api/auth/login',{'username':username,'password':'unit-test-password'},cookie='')
        self.assertEqual(r['status'],200,r)
        return self.cookie(r)
    def create(self,kind,data,cookie=None):
        r=request('POST','/api/'+kind,data,cookie=cookie)
        self.assertEqual(r['status'],201,r)
        return r['data']
    def visit(self):
        return self.create('visits',{'clientId':self.client['id'],'propertyId':self.property['id'],'date':'2026-10-13T10:00','advisor':'Forged name'},self.ca)

    def test_first_setup_session_cookie_password_storage_and_legacy_data(self):
        self.assertEqual(request('GET','/api/state',cookie='')['status'],401)
        me=request('GET','/api/auth/me',cookie='')['data']
        self.assertTrue(me['initialized']);self.assertIsNone(me['user'])
        self.assertEqual(request('POST','/api/auth/setup',{'username':'other','password':'unit-test-password','name':'Other'},cookie='')['status'],409)
        user=request('GET','/api/auth/me',cookie=self.ca)['data']['user']
        self.assertEqual(user['role'],'advisor')
        self.assertNotIn('password_hash',json.dumps(user))
        self.assertNotIn('salt',json.dumps(request('GET','/api/users')['data']))
        with server.db() as conn:
            row=conn.execute('SELECT * FROM users WHERE id=?',(self.a['id'],)).fetchone()
            self.assertNotEqual(row['password_hash'],'unit-test-password')
            # Legacy records remain central-only until assigned; there is no destructive migration.
            server.put(conn,'clients',{'id':'legacy','name':'Cliente anterior','role':'Comprador','currency':'USD'})
        self.assertEqual(request('GET','/api/clients/legacy')['status'],200)
        self.assertEqual(request('GET','/api/clients/legacy',cookie=self.ca)['status'],404)
        request('POST','/api/assign',{'kind':'clients','id':'legacy','advisorId':self.a['id']})
        self.assertEqual(request('GET','/api/clients/legacy',cookie=self.ca)['status'],200)
        login=request('POST','/api/auth/login',{'username':'ana','password':'unit-test-password'},cookie='')
        cookie_header=next(v for k,v in login['headers'] if k=='Set-Cookie')
        self.assertIn('HttpOnly',cookie_header);self.assertIn('SameSite=Strict',cookie_header)
        request('POST','/api/auth/logout',cookie=self.ca)
        self.assertEqual(request('GET','/api/state',cookie=self.ca)['status'],401)

    def test_scoped_lists_direct_reads_and_protected_files(self):
        v=self.visit()
        f=request('POST',f"/api/files?recordId={v['id']}&name=visit.webm",raw=b'unit-test-audio',mime='audio/webm',cookie=self.ca)['data']
        state=request('GET','/api/state',cookie=self.ca)['data']
        self.assertEqual([c['id'] for c in state['clients']],[self.client['id']])
        self.assertEqual([p['id'] for p in state['properties']],[self.property['id']])
        self.assertEqual(len(state['files']),1)
        other=request('GET','/api/state',cookie=self.cb)['data']
        self.assertEqual(other['clients'],[]);self.assertEqual(other['visits'],[]);self.assertEqual(other['files'],[])
        for path in ('/api/clients/'+self.client['id'],'/api/visits/'+v['id'],'/api/files/'+f['id'],'/api/matches/'+self.client['id']):
            self.assertEqual(request('GET',path,cookie=self.cb)['status'],404,path)
        self.assertEqual(request('POST','/api/ask',{'clientId':self.client['id'],'question':'Resumen'},cookie=self.cb)['status'],404)
        self.assertEqual(request('PATCH','/api/clients/'+self.client['id'],{'notes':'Forbidden'},cookie=self.cb)['status'],404)
        self.assertEqual(request('POST','/api/files?recordId='+self.client['id'],raw=b'test',mime='text/plain',cookie=self.cb)['status'],404)
        with server.db() as conn: server.put(conn,'transcription_jobs',{'id':'job-private','fileId':f['id']})
        self.assertEqual(request('GET','/api/transcribe/job-private',cookie=self.cb)['status'],404)
        self.assertEqual(request('POST','/api/transcribe',{'fileId':f['id']},cookie=self.cb)['status'],404)
        matches=request('GET','/api/matches/'+self.client['id'],cookie=self.ca)['data']['matches']
        self.assertEqual([m['property']['id'] for m in matches],[self.property['id']])

    def test_advisor_cannot_escalate_reassign_or_change_settings(self):
        actions=[('GET','/api/users',{}),('POST','/api/users',{'username':'evil','password':'unit-test-password','name':'Evil'}),('POST','/api/assign',{'kind':'clients','id':self.client['id'],'advisorId':self.b['id']}),('POST','/api/transcription-settings',{'key':'test-provider-key-never-used'}),('GET','/api/export',{}),('POST','/api/demo',{}),('PATCH','/api/properties/'+self.property['id'],{'price':1}),('DELETE','/api/clients/'+self.client['id'],{})]
        for method,path,body in actions:
            self.assertEqual(request(method,path,body,cookie=self.ca)['status'],403,path)
        self.assertEqual(request('PATCH','/api/clients/'+self.client['id'],{'advisorId':self.b['id']},cookie=self.ca)['status'],403)
        self.assertEqual(request('POST','/api/visits',{'clientId':self.client['id'],'propertyId':self.private['id'],'date':'2026-10-13T10:00'},cookie=self.ca)['status'],404)
        own=self.create('clients',{'name':'Nuevo cliente','role':'Comprador','currency':'USD','createdById':self.b['id']},self.ca)
        self.assertEqual(own['advisorId'],self.a['id']);self.assertEqual(own['createdById'],self.a['id'])
        cfg=request('GET','/api/config',cookie=self.ca)['data']
        self.assertEqual(cfg['role'],'advisor');self.assertIsNone(cfg['transcriptionSetup'])
        self.assertEqual(request('POST','/api/files?recordId='+self.property['id'],raw=b'doc',mime='text/plain',cookie=self.ca)['status'],403)

    def test_visit_confirmation_and_transfer_preserve_authorship(self):
        v=self.visit()
        self.assertEqual(v['advisor'],'Ana Asesora');self.assertEqual(v['recordedById'],self.a['id'])
        sheet={'summary':'Busca dos dormitorios','needs':['Dos dormitorios'],'zones':[],'likes':[],'objections':[],'questions':[],'agreements':[],'nextStep':'Llamar al cliente','followUp':'2026-10-14','budget':85000,'currency':'USD'}
        confirmed=request('POST',f"/api/visits/{v['id']}/confirm",{'sheet':sheet,'updateClient':True,'createFollowUp':True},cookie=self.ca)
        self.assertEqual(confirmed['status'],200,confirmed)
        self.assertEqual(confirmed['data']['confirmedById'],self.a['id'])
        event=request('GET','/api/state',cookie=self.ca)['data']['events'][0]
        self.assertEqual(event['advisorId'],self.a['id'])
        self.assertEqual(request('GET','/api/state')['data']['visits'][0]['status'],'Confirmada')
        self.assertEqual(request('POST','/api/assign',{'kind':'properties','id':self.property['id'],'advisorIds':[self.b['id']]})['status'],400)
        transfer=request('POST','/api/assign',{'kind':'clients','id':self.client['id'],'advisorId':self.b['id']})
        self.assertEqual(transfer['status'],200,transfer)
        self.assertEqual(request('GET','/api/visits/'+v['id'],cookie=self.ca)['status'],404)
        moved=request('GET','/api/visits/'+v['id'],cookie=self.cb)['data']
        self.assertEqual(moved['advisorId'],self.b['id'])
        self.assertEqual(moved['advisor'],'Ana Asesora')
        self.assertEqual(moved['recordedById'],self.a['id'])
        self.assertEqual(moved['confirmedById'],self.a['id'])
        self.assertEqual(request('GET','/api/events/'+event['id'],cookie=self.cb)['data']['advisorId'],self.b['id'])

    def test_disable_reset_expiration_and_csrf(self):
        self.assertEqual(request('POST','/api/users',{},origin='https://evil.test')['status'],403)
        self.assertEqual(request('POST','/api/auth/login',{},cookie='',origin='https://evil.test')['status'],403)
        r=request('PATCH','/api/users/'+self.a['id'],{'active':False})
        self.assertEqual(r['status'],200,r)
        self.assertEqual(request('GET','/api/state',cookie=self.ca)['status'],401)
        self.assertEqual(request('POST','/api/auth/login',{'username':'ana','password':'unit-test-password'},cookie='')['status'],401)
        request('PATCH','/api/users/'+self.a['id'],{'active':True,'password':'changed-test-password'})
        self.assertEqual(request('POST','/api/auth/login',{'username':'ana','password':'unit-test-password'},cookie='')['status'],401)
        self.assertEqual(request('POST','/api/auth/login',{'username':'ana','password':'changed-test-password'},cookie='')['status'],200)
        with patch('accounts.time.time',return_value=9999999999):
            self.assertEqual(request('GET','/api/state',cookie=self.cb)['status'],401)
        for _ in range(8): request('POST','/api/auth/login',{'username':'unknown','password':'bad'},cookie='')
        self.assertEqual(request('POST','/api/auth/login',{'username':'unknown','password':'bad'},cookie='')['status'],429)

    def test_transfer_grants_required_property_and_blocks_forged_audio_links(self):
        request('POST','/api/assign',{'kind':'properties','id':self.property['id'],'advisorIds':[self.a['id']]})
        v=self.visit()
        request('POST','/api/assign',{'kind':'clients','id':self.client['id'],'advisorId':self.b['id']})
        p=request('GET','/api/properties/'+self.property['id'],cookie=self.cb)
        self.assertEqual(p['status'],200)
        self.assertIn(self.b['id'],p['data']['advisorIds'])
        other=self.create('visits',{'clientId':self.client['id'],'propertyId':self.property['id'],'date':'2026-10-14T10:00'},self.cb)
        f=request('POST',f"/api/files?recordId={other['id']}",raw=b'audio',mime='audio/webm',cookie=self.cb)['data']
        self.assertEqual(request('PATCH','/api/visits/'+v['id'],{'audioId':f['id']},cookie=self.cb)['status'],400)

if __name__=='__main__': unittest.main()
