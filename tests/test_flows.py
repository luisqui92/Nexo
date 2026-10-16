"""Exercises real HTTP handler routes without opening sockets in restricted runtimes."""
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
TMP=tempfile.TemporaryDirectory()
os.environ['NEXO_DATA_DIR']=TMP.name
import server
from reception import available, handle_voice, handle_whatsapp
from logic import amount, extract_visit, matching

AUTH_COOKIE=''
def request(method,path,body=None,raw=None,mime='application/json',cookie=None,origin=None,host='localhost'):
    h=object.__new__(server.Handler)
    payload=raw if raw is not None else json.dumps(body or {}).encode()
    h.path=path
    h.headers={'Content-Length':str(len(payload)),'Content-Type':mime,'Host':host}
    if cookie is None: cookie=AUTH_COOKIE
    if cookie: h.headers['Cookie']=cookie
    if origin: h.headers['Origin']=origin
    h.rfile=io.BytesIO(payload)
    result={}
    h.reply=lambda status,data,mime='application/json':result.update(status=status,data=data,mime=mime)
    h.route(method)
    result['headers']=h.response_headers
    return result

class VisitFlow(unittest.TestCase):
    def setUp(self):
        global AUTH_COOKIE
        server.TRANSCRIPTION_SETTINGS.unlink(missing_ok=True)
        (server.DATA/'ai-settings.json').unlink(missing_ok=True)
        with server.db() as c:
            c.execute('DELETE FROM files');c.execute('DELETE FROM records');c.execute('DELETE FROM audit')
            c.execute('DELETE FROM sessions');c.execute('DELETE FROM users');c.execute('DELETE FROM login_attempts')
        AUTH_COOKIE=''
        setup=request('POST','/api/auth/setup',{'name':'Administrador QA','username':'admin','password':'admin-test-password'},cookie='')
        self.assertEqual(setup['status'],201,setup)
        AUTH_COOKIE=next(v.split(';')[0] for k,v in setup['headers'] if k=='Set-Cookie')
    def create(self,kind,data):
        r=request('POST','/api/'+kind,data)
        self.assertEqual(r['status'],201,r)
        return r['data']
    def fixtures(self):
        c=self.create('clients',{'name':'Cliente de prueba','role':'Comprador','currency':'USD','intent':'Venta','needs':[],'zones':[]})
        p=self.create('properties',{'title':'Departamento','zone':'Cala Cala','operation':'Venta','status':'Disponible','currency':'USD','price':85000,'parking':1,'bedrooms':2,'type':'Departamento'})
        return c,p
    def test_full_visit_confirmation_is_atomic_and_idempotent(self):
        c,p=self.fixtures()
        text='Busca estacionamiento. Su presupuesto es hasta 90 mil dólares. Le gustó la luz natural. Acordamos llamar mañana para coordinar otra visita.'
        analysed=request('POST','/api/analyse',{'text':text})
        self.assertEqual(analysed['status'],200)
        v=self.create('visits',{'clientId':c['id'],'propertyId':p['id'],'date':'2026-10-12T10:00','transcript':text,'sheet':analysed['data']['sheet']})
        confirm={'sheet':analysed['data']['sheet'],'updateClient':True,'createFollowUp':True}
        confirm['sheet']['followUp']='bad-date'
        invalid=request('POST',f"/api/visits/{v['id']}/confirm",confirm)
        self.assertEqual(invalid['status'],400)
        untouched=request('GET','/api/clients/'+c['id'])['data']
        self.assertFalse(untouched.get('budget'))
        confirm['sheet']['followUp']='2026-10-13'
        saved=request('POST',f"/api/visits/{v['id']}/confirm",confirm)
        self.assertEqual(saved['status'],200,saved)
        self.assertEqual(saved['data']['status'],'Confirmada')
        state=request('GET','/api/state')['data']
        self.assertEqual(len(state['events']),1)
        self.assertEqual(state['clients'][0]['budget'],90000)
        again=request('POST',f"/api/visits/{v['id']}/confirm",confirm)
        self.assertEqual(again['status'],409)
        self.assertEqual(len(request('GET','/api/state')['data']['events']),1)
        edit=request('PATCH','/api/visits/'+v['id'],{'transcript':'Changed'})
        self.assertEqual(edit['status'],409)
    def test_no_cross_kind_links_and_preserved_history(self):
        c,p=self.fixtures()
        invalid=request('POST','/api/visits',{'clientId':p['id'],'propertyId':c['id'],'date':'2026-10-12T10:00'})
        self.assertEqual(invalid['status'],400)
        self.create('visits',{'clientId':c['id'],'propertyId':p['id'],'date':'2026-10-12T10:00'})
        self.assertEqual(request('DELETE','/api/clients/'+c['id'])['status'],409)
        self.assertEqual(request('DELETE','/api/properties/'+p['id'])['status'],409)
    def test_upload_and_export(self):
        c,p=self.fixtures()
        v=self.create('visits',{'clientId':c['id'],'propertyId':p['id'],'date':'2026-10-12T10:00'})
        r=request('POST',f"/api/files?recordId={v['id']}&name=visit.webm",raw=b'audio-test',mime='audio/webm')
        self.assertEqual(r['status'],201,r)
        f=request('GET','/api/files/'+r['data']['id'])
        self.assertEqual(f['data'],b'audio-test')
        self.assertEqual(f['mime'],'audio/webm')
        self.assertEqual(request('POST',f"/api/files?recordId={v['id']}&name=bad.html",raw=b'<script>',mime='text/html')['status'],400)
        export=request('GET','/api/export')['data']
        self.assertEqual(len(export['records']['visits']),1)
    def test_demo_never_overwrites_real_records(self):
        self.fixtures()
        self.assertEqual(request('POST','/api/demo')['status'],400)
        self.assertEqual(len(request('GET','/api/state')['data']['clients']),1)
    def test_missing_external_services_are_explicit(self):
        self.assertFalse(request('GET','/api/config')['data']['ai'])
        self.assertFalse(request('GET','/api/config')['data']['whatsapp'])
        self.assertFalse(request('GET','/api/config')['data']['calendar'])

    def test_voice_booking_revalidates_slots_and_cancel_verifies_contact(self):
        c,p=self.fixtures()
        with server.db() as conn:
            slots=available(conn,p['id'])
            self.assertTrue(slots)
            result=handle_voice(conn,'agendar_visita',{'propertyId':p['id'],'date':slots[0],'name':'Persona de prueba','phone':'59170000123'})
            self.assertIn('confirmada',result)
            with self.assertRaises(ValueError):handle_voice(conn,'agendar_visita',{'propertyId':p['id'],'date':slots[0],'name':'Otra persona','phone':'59170000124'})
            events=server.list_records(conn,'events')
            with self.assertRaises(ValueError):handle_voice(conn,'cancelar_visita',{'eventId':events[0]['id'],'phone':'59170000124'})
            result=handle_voice(conn,'cancelar_visita',{'eventId':events[0]['id'],'phone':'59170000123'})
            self.assertIn('cancelada',result)

    def test_whatsapp_requires_confirmation_and_deduplicates_messages(self):
        c,p=self.fixtures()
        phone='59170000125'
        with server.db() as conn:
            self.assertIn('inmueble',handle_whatsapp(conn,phone,'Hola','m1'))
            self.assertIsNone(handle_whatsapp(conn,phone,'Hola','m1'))
            self.assertIn('horario',handle_whatsapp(conn,phone,'1','m2'))
            self.assertIn('nombre',handle_whatsapp(conn,phone,'1','m3'))
            self.assertIn('Confirmás',handle_whatsapp(conn,phone,'Cliente nuevo','m4'))
            self.assertEqual(len(server.list_records(conn,'events')),0)
            self.assertIn('confirmada',handle_whatsapp(conn,phone,'sí','m5'))
            self.assertEqual(len(server.list_records(conn,'events')),1)

    def test_transcription_connection_keeps_the_key_server_side(self):
        fake_key='fictional-key-for-unit-tests-only'
        result=request('POST','/api/transcription-settings',{'key':fake_key})
        self.assertEqual(result['status'],200)
        cfg=request('GET','/api/config')['data']
        self.assertTrue(cfg['transcription'])
        self.assertEqual(cfg['transcriptionSetup'],'local')
        self.assertNotIn(fake_key,json.dumps(cfg))
        self.assertEqual(server.transcription_key(),fake_key)
        self.assertEqual(request('POST','/api/transcription-settings',{'key':'short'})['status'],400)
        request('POST','/api/transcription-settings',{'key':''})
        self.assertFalse(request('GET','/api/config')['data']['transcription'])

    def test_saved_audio_can_be_transcribed_and_job_is_tracked(self):
        c,p=self.fixtures()
        v=self.create('visits',{'clientId':c['id'],'propertyId':p['id'],'date':'2026-10-12T10:00'})
        f=request('POST',f"/api/files?recordId={v['id']}&name=visit.webm",raw=b'audio-test',mime='audio/webm')['data']
        self.assertEqual(request('POST','/api/transcribe',{'fileId':f['id']})['status'],503)
        server.save_transcription_key('fictional-key-for-unit-tests-only')
        text='Busca dos dormitorios. Su presupuesto es hasta 90 mil dólares.'
        upload=io.BytesIO(json.dumps({'upload_url':'https://example.invalid/unit-test-audio'}).encode())
        completed=io.BytesIO(json.dumps({'status':'completed','text':text}).encode())
        with patch('server.urllib.request.urlopen',side_effect=[upload,completed]) as upstream, patch('server.external_json',return_value={'id':'test-transcription-job'}) as create:
            job=request('POST','/api/transcribe',{'fileId':f['id']})
            self.assertEqual(job['status'],202)
            self.assertEqual(upstream.call_args.args[0].data,b'audio-test')
            result=request('GET','/api/transcribe/test-transcription-job')
            self.assertEqual(result['data']['text'],text)
            self.assertTrue(create.call_args.args[1]['speaker_labels'])
        self.assertEqual(request('GET','/api/transcribe/unknown-job')['status'],400)
        with server.db() as conn:
            self.assertEqual(server.record(conn,'test-transcription-job','transcription_jobs')['fileId'],f['id'])

class Extraction(unittest.TestCase):
    def test_spanish_amounts(self):
        for text,n in [('90 mil dólares',90000),('95.000 dólares',95000),('1,5 millones de dólares',1500000),('420 dólares',420),('165000',165000)]:
            self.assertEqual(amount(text),n,text)
    def test_absent_fields_and_negative_interest_not_invented(self):
        result=extract_visit('No le gustó el departamento. Tiene demasiado ruido.',datetime(2026,10,12))
        self.assertEqual(result['likes'],[])
        self.assertIsNone(result['budget'])
        self.assertIsNone(result['interest'])
        self.assertIsNone(result['followUp'])
        self.assertTrue(result['objections'])
    def test_tomorrow_and_budget_are_extracted(self):
        r=extract_visit('Busca estacionamiento. Presupuesto hasta 90 mil dólares. Acordamos llamar mañana.',datetime(2026,10,12))
        self.assertEqual(r['budget'],90000)
        self.assertEqual(r['followUp'],'2026-10-13')
        self.assertEqual(r['currency'],'USD')
    def test_matches_explain_missing_and_do_not_mix_currencies(self):
        c={'intent':'Venta','budget':90000,'currency':'USD','needs':['Necesita estacionamiento'],'zones':['Cala Cala'],'propertyType':'Departamento','bedrooms':2}
        properties=[{'id':'good','status':'Disponible','operation':'Venta','price':85000,'currency':'USD','parking':1,'zone':'Cala Cala','type':'Departamento','bedrooms':2},{'id':'bad','status':'Disponible','operation':'Venta','price':500000,'currency':'BOB','parking':0,'zone':'Otra','type':'Casa','bedrooms':1},{'id':'sold','status':'Vendido'}]
        ms=matching(c,properties)
        self.assertEqual(len(ms),2)
        self.assertEqual(ms[0]['property']['id'],'good')
        self.assertEqual(ms[0]['score'],100)
        self.assertIn('Moneda distinta; requiere conversión',ms[1]['missing'])

if __name__=='__main__': unittest.main()
