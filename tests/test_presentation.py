import io
import json
import threading
import unittest
import urllib.error
from unittest.mock import patch

import ai_services
import server
import test_flows as flows
from test_flows import request
from presentation_demo import prepare_demo

class PresentationFlow(unittest.TestCase):
    def setUp(self):
        flows.VisitFlow.setUp(self)
        (server.DATA/'accesos-demo.json').unlink(missing_ok=True)
        server.ACTIVE_TRANSCRIPTIONS.clear()
    def create(self,kind,body): return flows.VisitFlow.create(self,kind,body)
    def fixtures(self): return flows.VisitFlow.fixtures(self)
    def audio(self):
        c,p=self.fixtures()
        v=self.create('visits',{'clientId':c['id'],'propertyId':p['id'],'date':'2026-10-19T10:00'})
        f=request('POST',f"/api/files?recordId={v['id']}&name=visita.webm",raw=b'unit-test-audio',mime='audio/webm')['data']
        return v,f
    def configure(self):
        result=request('POST','/api/ai-settings',{'provider':'openai','key':'fictional-openai-key-for-tests-only','audioModel':'gpt-4o-mini-transcribe'})
        self.assertEqual(result['status'],200,result)
    def test_configuration_uses_one_key_without_exposing_it(self):
        self.configure()
        cfg=request('GET','/api/config')['data']
        self.assertTrue(cfg['ai']);self.assertTrue(cfg['transcription'])
        self.assertEqual(cfg['transcriptionProvider'],'openai')
        self.assertNotIn('fictional-openai-key',json.dumps(cfg))
        text='Busca dos dormitorios y estacionamiento. Presupuesto hasta 95 mil dólares.'
        response={'choices':[{'message':{'content':json.dumps(server.extract_visit(text))}}]}
        with patch('server.external_json',return_value=response) as upstream:
            analysed=request('POST','/api/analyse',{'text':text})
            self.assertEqual(analysed['data']['method'],'ai')
            self.assertEqual(upstream.call_args.args[1]['model'],'gpt-4.1-mini')
            self.assertEqual(upstream.call_args.args[2]['Authorization'],'Bearer fictional-openai-key-for-tests-only')
        with patch('server.external_json',return_value={'choices':[]}) as upstream:
            self.assertEqual(request('POST','/api/ai-check')['status'],200)
        self.assertEqual(request('POST','/api/ai-settings',{'provider':'openai','key':'short'})['status'],400)
        self.assertEqual(request('POST','/api/ai-settings',{'provider':'openai','audioModel':'untrusted-model'})['status'],400)
        with patch('server.external_json',side_effect=OSError('offline')) as upstream:
            offline=request('POST','/api/analyse',{'text':text,'local':True})
            self.assertEqual(offline['status'],200)
            self.assertEqual(offline['data']['method'],'automatic')
            self.assertEqual(offline['data']['sheet']['budget'],95000)
            upstream.assert_not_called()

    def test_openai_job_survives_polling_and_is_not_charged_twice(self):
        v,f=self.audio();self.configure()
        with patch.object(server.TRANSCRIPTION_POOL,'submit'):
            first=request('POST','/api/transcribe',{'fileId':f['id']})
            self.assertEqual(first['status'],202,first)
            jid=first['data']['jobId']
            self.assertEqual(request('POST','/api/transcribe',{'fileId':f['id']})['data']['jobId'],jid)
        text='Busca dos dormitorios. Su presupuesto es hasta 95 mil dólares.'
        with patch('ai_services.transcribe',return_value=text) as provider:
            server.process_openai_job(jid,server.openai_key())
            self.assertEqual(provider.call_count,1)
            self.assertEqual(provider.call_args.args[0],b'unit-test-audio')
        complete=request('GET','/api/transcribe/'+jid)
        self.assertEqual(complete['data']['status'],'completed');self.assertEqual(complete['data']['text'],text)
        with patch.object(server.TRANSCRIPTION_POOL,'submit') as submit:
            self.assertEqual(request('POST','/api/transcribe',{'fileId':f['id']})['data']['jobId'],jid)
            submit.assert_not_called()
        self.assertEqual(request('PATCH','/api/visits/'+v['id'],{'transcriptionJobId':jid,'audioId':f['id'],'transcript':text})['status'],200)

    def test_provider_request_does_not_block_other_advisors(self):
        v,f=self.audio();self.configure()
        started=threading.Event();release=threading.Event()
        def slow_provider(*args):
            started.set()
            if not release.wait(3): raise ValueError('Test timed out')
            return 'Conversación de prueba suficientemente extensa.'
        with patch('ai_services.transcribe',side_effect=slow_provider):
            result=request('POST','/api/transcribe',{'fileId':f['id']})
            self.assertEqual(result['status'],202)
            self.assertTrue(started.wait(2))
            try:
                self.assertEqual(request('GET','/api/state')['status'],200)
                self.assertEqual(request('GET','/api/transcribe/'+result['data']['jobId'])['data']['status'],'processing')
            finally: release.set()
            # Wait on the pool, not on an arbitrary sleep; the following task runs after this one.
            with server.LOCK: pass
            for jid in list(server.ACTIVE_TRANSCRIPTIONS):
                # A short explicit event tracks the completion before the test deletes records.
                done=threading.Event()
                original_put=server.put
                def observed_put(conn,kind,obj):
                    original_put(conn,kind,obj)
                    if kind=='transcription_jobs' and obj.get('status')=='completed': done.set()
                with patch('server.put',side_effect=observed_put):
                    if request('GET','/api/transcribe/'+jid)['data']['status']!='completed': self.assertTrue(done.wait(2))

    def test_errors_restart_and_large_files_keep_audio(self):
        v,f=self.audio();self.configure()
        with patch.object(server.TRANSCRIPTION_POOL,'submit'):
            jid=request('POST','/api/transcribe',{'fileId':f['id']})['data']['jobId']
        with patch('ai_services.transcribe',side_effect=urllib.error.HTTPError('https://api.openai.com',401,'Unauthorized',{},None)):
            server.process_openai_job(jid,server.openai_key())
        result=request('GET','/api/transcribe/'+jid)['data']
        self.assertEqual(result['status'],'error');self.assertIn('401',result['error'])
        self.assertNotIn('fictional-openai-key',result['error'])
        self.assertEqual(request('GET','/api/files/'+f['id'])['data'],b'unit-test-audio')
        with patch.object(server.TRANSCRIPTION_POOL,'submit'):
            restarted=request('POST','/api/transcribe',{'fileId':f['id']})['data']['jobId']
        server.ACTIVE_TRANSCRIPTIONS.discard(restarted)
        self.assertIn('reinició',request('GET','/api/transcribe/'+restarted)['data']['error'])
        with server.db() as conn: conn.execute('UPDATE files SET size=? WHERE id=?',(ai_services.MAX_OPENAI_AUDIO+1,f['id']))
        self.assertEqual(request('POST','/api/transcribe',{'fileId':f['id']})['status'],400)

    def test_multipart_spanish_request_and_speaker_model(self):
        for model,expected in [('gpt-4o-mini-transcribe',b'name="language"'),('gpt-transcribe',b'name="languages[]"'),('gpt-4o-transcribe-diarize',b'name="chunking_strategy"')]:
            with patch('ai_services.urllib.request.urlopen',return_value=io.BytesIO(json.dumps({'text':'Texto real de la respuesta de prueba.'}).encode())) as upstream:
                text=ai_services.transcribe(b'audio-bytes','visita.webm','audio/webm','unit-test-key',model)
                self.assertIn('Texto real',text)
                req=upstream.call_args.args[0]
                self.assertIn(expected,req.data);self.assertIn(b'audio-bytes',req.data)
                self.assertEqual(req.full_url,'https://api.openai.com/v1/audio/transcriptions')
                self.assertIn('multipart/form-data',req.get_header('Content-type'))

    def test_demo_is_fictional_assigned_idempotent_and_never_overwrites(self):
        with self.assertRaises(ValueError): prepare_demo(server)
        with server.db() as conn:
            conn.execute('DELETE FROM sessions');conn.execute('DELETE FROM users')
        first=prepare_demo(server);again=prepare_demo(server)
        self.assertEqual(first,again)
        self.assertEqual(len(first['accounts']),3)
        self.assertNotEqual(server.DATA,server.ROOT/'data')
        ana=first['accounts'][1]
        login=request('POST','/api/auth/login',{'username':ana['username'],'password':ana['password']},cookie='')
        cookie=next(v.split(';')[0] for k,v in login['headers'] if k=='Set-Cookie')
        state=request('GET','/api/state',cookie=cookie)['data']
        self.assertTrue(state['clients']);self.assertTrue(state['properties']);self.assertTrue(state['visits'])
        self.assertTrue(all(v['advisorId']==ana['id'] for v in state['visits']))
        self.assertTrue(all(c['demo'] for c in state['clients']))
        self.assertEqual(request('GET','/api/readiness',cookie=cookie)['status'],403)

if __name__=='__main__': unittest.main()
