"""Account isolation, credential rotation, image handling and legacy migration."""
import sqlite3
import unittest

import accounts
import test_flows as flows
from test_flows import request
import server

class AccountSettings(unittest.TestCase):
    def setUp(self):
        flows.VisitFlow.setUp(self)
        self.advisor=request('POST','/api/users',{'name':'Ana','username':'ana','password':'advisor-test-password'})['data']
        self.cookie=self.login()

    def login(self, password='advisor-test-password'):
        result=request('POST','/api/auth/login',{'username':'ana','password':password},cookie='')
        self.assertEqual(result['status'],200,result)
        return next(v.split(';')[0] for k,v in result['headers'] if k=='Set-Cookie')

    def test_edit_own_profile_and_keep_permissions(self):
        result=request('PATCH','/api/account',{'name':'Ana Pérez','email':'ana@example.test','phone':'+591 70000000','title':'Ventas','avatarColor':'#572d73'},cookie=self.cookie)
        self.assertEqual(result['status'],200,result)
        self.assertEqual(result['data']['user']['name'],'Ana Pérez')
        self.assertEqual(result['data']['user']['role'],'advisor')
        self.assertNotIn('password_hash',result['data']['user'])
        self.assertNotIn('salt',result['data']['user'])
        config=request('GET','/api/config',cookie=self.cookie)['data']
        self.assertEqual(config['user'],'Ana Pérez')
        self.assertEqual(config['profile']['email'],'ana@example.test')
        admin=request('GET','/api/account')['data']['user']
        self.assertEqual(admin['name'],'Administrador QA')
        for data in ({'role':'admin'},{'id':admin['id'],'name':'Impostor'},{'username':'admin'},{'active':False},{'email':'invalid'},{'avatarColor':'red;display:none'},{'name':''}):
            self.assertEqual(request('PATCH','/api/account',data,cookie=self.cookie)['status'],400,data)
        self.assertEqual(request('GET','/api/users',cookie=self.cookie)['status'],403)
        self.assertEqual(request('GET','/api/account',cookie='')['status'],401)

    def test_password_change_rotates_all_sessions_but_keeps_this_browser(self):
        other_cookie=self.login()
        wrong=request('POST','/api/account/password',{'currentPassword':'incorrect','newPassword':'new-advisor-password'},cookie=self.cookie)
        self.assertEqual(wrong['status'],400)
        self.assertEqual(request('GET','/api/account',cookie=self.cookie)['status'],200)
        short=request('POST','/api/account/password',{'currentPassword':'advisor-test-password','newPassword':'short'},cookie=self.cookie)
        self.assertEqual(short['status'],400)
        result=request('POST','/api/account/password',{'currentPassword':'advisor-test-password','newPassword':'new-advisor-password'},cookie=self.cookie)
        self.assertEqual(result['status'],200,result)
        replacement=next(v.split(';')[0] for k,v in result['headers'] if k=='Set-Cookie')
        for old in (self.cookie,other_cookie):
            self.assertEqual(request('GET','/api/account',cookie=old)['status'],401)
        self.assertEqual(request('GET','/api/account',cookie=replacement)['status'],200)
        self.assertEqual(request('GET','/api/account')['status'],200) # Other users are unaffected.
        self.assertEqual(request('POST','/api/auth/login',{'username':'ana','password':'advisor-test-password'},cookie='')['status'],401)
        self.login('new-advisor-password')

    def test_wrong_current_password_is_rate_limited_without_closing_session(self):
        for _ in range(8):
            self.assertEqual(request('POST','/api/account/password',{'currentPassword':'wrong','newPassword':'new-advisor-password'},cookie=self.cookie)['status'],400)
        self.assertEqual(request('POST','/api/account/password',{'currentPassword':'advisor-test-password','newPassword':'new-advisor-password'},cookie=self.cookie)['status'],429)
        self.assertEqual(request('GET','/api/account',cookie=self.cookie)['status'],200)

    def test_private_photo_upload_validation_and_removal(self):
        photo=b'\xff\xd8\xff'+b'example-image-bytes'+b'\xff\xd9'
        uploaded=request('POST','/api/account/avatar',raw=photo,mime='image/jpeg',cookie=self.cookie)
        self.assertEqual(uploaded['status'],200,uploaded)
        self.assertTrue(uploaded['data']['user']['avatarUpdated'])
        read=request('GET','/api/account/avatar',cookie=self.cookie)
        self.assertEqual(read['data'],photo)
        self.assertEqual(read['mime'],'image/jpeg')
        self.assertEqual(request('GET','/api/account/avatar')['status'],404)
        self.assertEqual(request('GET','/api/account/avatar',cookie='')['status'],401)
        for content,mime in ((b'<svg onload="alert(1)"></svg>','image/svg+xml'),(b'<html>not a photo</html>','image/png'),(b'x'*262145,'image/jpeg')):
            self.assertEqual(request('POST','/api/account/avatar',raw=content,mime=mime,cookie=self.cookie)['status'],400)
        self.assertEqual(request('GET','/api/account/avatar',cookie=self.cookie)['data'],photo)
        removed=request('DELETE','/api/account/avatar',cookie=self.cookie)
        self.assertEqual(removed['data']['user']['avatarUpdated'],'')
        self.assertEqual(request('GET','/api/account/avatar',cookie=self.cookie)['status'],404)

    def test_administrator_can_personalize_own_account(self):
        self.assertEqual(request('PATCH','/api/account',{'name':'Gerencia Nexo','title':'Gerente'})['status'],200)
        result=request('POST','/api/account/password',{'currentPassword':'admin-test-password','newPassword':'admin-new-password'})
        self.assertEqual(result['status'],200,result)

class LegacyMigration(unittest.TestCase):
    def test_old_database_keeps_passwords_sessions_and_can_create_new_users(self):
        conn=sqlite3.connect(':memory:');self.addCleanup(conn.close);conn.row_factory=sqlite3.Row
        conn.execute('CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT UNIQUE,name TEXT,role TEXT,password_hash TEXT,salt TEXT,active INTEGER,created TEXT)')
        digest,salt=accounts.password_values('legacy-test-password')
        conn.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?,?)',('legacy','legacy','Usuario existente','advisor',digest,salt,1,'2026-10-15'))
        accounts.initialize(conn)
        token=accounts.session(conn,'legacy')
        accounts.initialize(conn)
        user=accounts.current_user(conn,{'Cookie':accounts.cookie(token)})
        self.assertEqual(user['name'],'Usuario existente')
        self.assertEqual(user['avatarUpdated'],'')
        self.assertEqual(accounts.login(conn,{'username':'legacy','password':'legacy-test-password'},'test')[2],200)
        new=accounts.create_user(conn,{'name':'Nueva','username':'nueva','password':'new-test-password'},'advisor','2026-10-16')
        self.assertEqual(new['email'],'')
        self.assertEqual(conn.execute('SELECT count(*) FROM users').fetchone()[0],2)

if __name__=='__main__': unittest.main()
