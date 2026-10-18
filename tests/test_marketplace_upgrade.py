"""Import the new server over an actual pre-workspace SQLite database."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import accounts

class UpgradeExistingDatabase(unittest.TestCase):
    def test_script_entrypoint_can_register_and_publish_in_one_transaction(self):
        with tempfile.TemporaryDirectory() as directory:
            code="""
import accounts,http.server,json,os,runpy,sqlite3,sys
from pathlib import Path
from types import SimpleNamespace
conn=sqlite3.connect(Path(os.environ['NEXO_DATA_DIR'])/'nexo.sqlite3');conn.row_factory=sqlite3.Row
accounts.initialize(conn);accounts.create_user(conn,{'name':'Gerencia','username':'admin','password':'entrypoint-test-password'},'admin','2026-10-18');conn.commit();conn.close()
class FakeHTTP:
 def __init__(self,*args):pass
 def serve_forever(self):
  app=sys.modules['__main__']
  with app.LOCK,app.db() as c:
   user=app.marketplace.register(c,{'name':'Asesor','username':'entrypoint.advisor','password':'entrypoint-test-password','accountType':'independent','email':'qa@example.test','phone':'59170000000','acceptTerms':True})
   p={'id':'entrypoint-property','title':'Departamento','zone':'Centro','type':'Departamento','operation':'Venta','currency':'USD','price':85000,'status':'Disponible','workspaceId':user['workspaceId']}
   app.put(c,'properties',p)
   c.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?)',('photo',p['id'],'photo.jpg','image/jpeg',100,'photo.jpg','2026-10-18'))
   h=SimpleNamespace(current_user=user,get_record=lambda conn,rid,kind:app.record(conn,rid,kind))
   result=app.marketplace.save_publication(h,c,{'propertyId':p['id'],'latitude':-17.39,'longitude':-66.16,'city':'Cochabamba','contactPhone':'59170000000','photoIds':['photo'],'status':'published','confirmPublication':True})
   print(json.dumps({'status':result['status'],'total':app.marketplace.public_search(c,{})['total']}))
http.server.ThreadingHTTPServer=FakeHTTP
runpy.run_path('server.py',run_name='__main__')
"""
            env={**os.environ,'NEXO_DATA_DIR':directory,'HOST':'127.0.0.1','NEXO_DEPLOYMENT':'0'}
            result=subprocess.check_output([sys.executable,'-c',code],cwd=Path(__file__).resolve().parents[1],env=env,text=True,timeout=20)
            self.assertEqual(json.loads(result.splitlines()[-1]),{'status':'published','total':1})

    def test_existing_admin_session_and_private_records_survive_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            conn=sqlite3.connect(Path(directory)/'nexo.sqlite3')
            conn.executescript('''CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT UNIQUE,name TEXT,role TEXT,password_hash TEXT,salt TEXT,active INTEGER,created TEXT);
                CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,user_id TEXT,expires INTEGER);
                CREATE TABLE records(id TEXT PRIMARY KEY,kind TEXT,body TEXT,updated TEXT);''')
            digest,salt=accounts.password_values('upgrade-test-password')
            conn.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?,?)',('old-admin','admin','Gerencia existente','admin',digest,salt,1,'2026-10-15'))
            conn.execute('INSERT INTO sessions VALUES(?,?,?)',(accounts.token_hash('legacy-token'),'old-admin',int(time.time())+3600))
            conn.execute('INSERT INTO records VALUES(?,?,?,?)',('old-client','clients',json.dumps({'id':'old-client','name':'Cliente guardado','notes':'Información privada'}),'2026-10-15'))
            conn.commit();conn.close()
            code="""import json,server,accounts
with server.db() as c:
 u=accounts.current_user(c,{'Cookie':'nexo_session=legacy-token'})
 print(json.dumps({'user':u,'record':server.record(c,'old-client'),'publications':c.execute('SELECT count(*) FROM publications').fetchone()[0]}))
"""
            environment={**os.environ,'NEXO_DATA_DIR':directory}
            root=Path(__file__).resolve().parents[1]
            for _ in range(2): # A second startup must not overwrite the migrated space.
                output=subprocess.check_output([sys.executable,'-c',code],cwd=root,env=environment,text=True,timeout=15)
                result=json.loads(output)
                self.assertEqual(result['user']['name'],'Gerencia existente')
                self.assertTrue(result['user']['platformAdmin'])
                self.assertEqual(result['user']['workspaceId'],'legacy')
                self.assertEqual(result['record']['notes'],'Información privada')
                self.assertEqual(result['record']['workspaceId'],'legacy')
                self.assertEqual(result['publications'],0)

if __name__=='__main__':unittest.main()
