"""Public deployment must require a private administrator and HTTPS sessions."""
import unittest
from unittest.mock import patch

import test_flows as flows
import accounts
import deployment
import server
from scripts.create_admin import create_first_admin


class DeploymentSecurity(unittest.TestCase):
    def setUp(self):
        with server.db() as conn:
            conn.execute('DELETE FROM sessions')
            conn.execute('DELETE FROM login_attempts')
            conn.execute('DELETE FROM users')
        self.environment = patch.dict('os.environ', {
            'NEXO_DEPLOYMENT': '1', 'NEXO_HTTPS': '1',
            'NEXO_DOMAIN': 'app.chatgo.ia.bo', 'NEXO_PRESENTATION': '0',
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_requires_admin_and_https_before_public_listener(self):
        with self.assertRaisesRegex(ValueError, 'administrador'):
            deployment.validate_startup('0.0.0.0', False)
        with patch.dict('os.environ', {'NEXO_HTTPS': '0'}):
            with self.assertRaisesRegex(ValueError, 'HTTPS'):
                deployment.validate_startup('0.0.0.0', True)
        with patch.dict('os.environ', {'NEXO_DOMAIN': 'https://app.chatgo.ia.bo/path'}):
            with self.assertRaisesRegex(ValueError, 'dominio'):
                deployment.validate_startup('0.0.0.0', True)
        deployment.validate_startup('0.0.0.0', True)

    def test_public_setup_cannot_take_over_empty_database(self):
        result = flows.request('POST', '/api/auth/setup', {
            'name': 'Attacker', 'username': 'attacker', 'password': 'arbitrary-password',
        }, cookie='', host='app.chatgo.ia.bo')
        self.assertEqual(result['status'], 403)
        with server.db() as conn:
            self.assertFalse(accounts.has_users(conn))

    def test_private_bootstrap_and_secure_login_persist(self):
        data = {'name': 'Gerencia', 'username': 'gerencia', 'password': 'private-test-password'}
        user = create_first_admin(data)
        self.assertEqual(user['role'], 'admin')
        self.assertNotIn('password_hash', user)
        with self.assertRaisesRegex(ValueError, 'Ya existen'):
            create_first_admin({**data, 'username': 'replacement'})
        result = flows.request('POST', '/api/auth/login', data, cookie='',
                               host='app.chatgo.ia.bo', origin='https://app.chatgo.ia.bo')
        self.assertEqual(result['status'], 200)
        cookie = next(value for name, value in result['headers'] if name == 'Set-Cookie')
        for flag in ('Secure', 'HttpOnly', 'SameSite=Strict'):
            self.assertIn(flag, cookie)
        reopened = flows.request('GET', '/api/auth/me', host='app.chatgo.ia.bo', cookie=cookie.split(';')[0])
        self.assertEqual(reopened['data']['user']['id'], user['id'])

    def test_wrong_host_and_insecure_origin_are_rejected(self):
        for host, origin in [('other.example', None), ('app.chatgo.ia.bo', 'http://app.chatgo.ia.bo'),
                             ('app.chatgo.ia.bo', 'https://evil.example')]:
            result = flows.request('POST', '/api/auth/login', cookie='', host=host, origin=origin)
            self.assertEqual(result['status'], 403)
        health = flows.request('GET', '/healthz', cookie='')
        self.assertEqual(health['data'], {'ok': True})

    def test_demo_database_cannot_be_exposed_by_deployment_flag(self):
        with patch.dict('os.environ', {'NEXO_PRESENTATION': '1'}):
            with self.assertRaisesRegex(ValueError, 'presentación'):
                deployment.validate_startup('0.0.0.0', True)

    def test_existing_local_external_password_guard_is_preserved(self):
        with patch.dict('os.environ', {'NEXO_DEPLOYMENT': '0', 'APP_PASSWORD': ''}):
            deployment.validate_startup('127.0.0.1', False)
            with self.assertRaisesRegex(ValueError, 'APP_PASSWORD'):
                deployment.validate_startup('0.0.0.0', True)


if __name__ == '__main__':
    unittest.main()
