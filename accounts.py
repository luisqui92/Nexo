"""Local team accounts. Passwords and session tokens are never returned to clients."""
import hashlib
import hmac
import re
import secrets
import time
import uuid
from http.cookies import SimpleCookie

COOKIE = 'nexo_session'
SESSION_SECONDS = 12 * 60 * 60
ITERATIONS = 210000

class AccessError(Exception):
    def __init__(self, message, status=403):
        super().__init__(message)
        self.status = status

def initialize(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL, role TEXT NOT NULL,
            password_hash TEXT NOT NULL, salt TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            expires INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS login_attempts (
            attempt_key TEXT PRIMARY KEY, failures INTEGER NOT NULL, reset_at INTEGER NOT NULL
        );
    ''')

def public_user(row):
    return {key: row[key] for key in ('id', 'username', 'name', 'role', 'active', 'created')}

def has_users(conn):
    return bool(conn.execute('SELECT 1 FROM users LIMIT 1').fetchone())

def username(value):
    if not isinstance(value, str): raise ValueError('Ingresá un nombre de usuario')
    value = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9_.@+-]{3,60}', value):
        raise ValueError('El usuario debe tener entre 3 y 60 caracteres: letras sin acentos, números, punto o guion')
    return value

def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ITERATIONS).hex()

def password_values(password):
    if not isinstance(password, str) or not 10 <= len(password) <= 256:
        raise ValueError('La contraseña debe tener entre 10 y 256 caracteres')
    salt = secrets.token_hex(16)
    return password_hash(password, salt), salt

def create_user(conn, data, role, created):
    name = data.get('name')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
        raise ValueError('Ingresá el nombre, hasta 120 caracteres')
    login = username(data.get('username'))
    if conn.execute('SELECT 1 FROM users WHERE username=?', (login,)).fetchone():
        raise ValueError('Ese nombre de usuario ya está registrado')
    digest, salt = password_values(data.get('password'))
    uid = str(uuid.uuid4())
    conn.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?,?)', (uid, login, name.strip(), role, digest, salt, 1, created))
    return public_user(conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())

def token_from(headers):
    try:
        cookie = SimpleCookie()
        cookie.load(headers.get('Cookie', ''))
        return cookie[COOKIE].value if COOKIE in cookie else ''
    except Exception:
        return ''

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def current_user(conn, headers):
    token = token_from(headers)
    if not token: return None
    row = conn.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token_hash=? AND s.expires>? AND u.active=1', (token_hash(token), int(time.time()))).fetchone()
    return public_user(row) if row else None

def session(conn, user_id):
    token = secrets.token_urlsafe(32)
    conn.execute('DELETE FROM sessions WHERE expires<=?', (int(time.time()),))
    conn.execute('INSERT INTO sessions VALUES(?,?,?)', (token_hash(token), user_id, int(time.time()) + SESSION_SECONDS))
    return token

def cookie(token, secure=False):
    return f'{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_SECONDS if token else 0}' + ('; Secure' if secure else '')

def login(conn, data, address):
    login_name = str(data.get('username', '')).strip().lower()[:60]
    password = data.get('password')
    if not isinstance(password, str) or len(password)>256: password = ''
    key = hashlib.sha256((address + '|' + login_name).encode()).hexdigest()
    attempt = conn.execute('SELECT * FROM login_attempts WHERE attempt_key=?', (key,)).fetchone()
    timestamp = int(time.time())
    if attempt and attempt['reset_at'] > timestamp and attempt['failures'] >= 8:
        return None, 'Esperá unos minutos antes de volver a intentar.', 429
    row = conn.execute('SELECT * FROM users WHERE username=?', (login_name,)).fetchone()
    # Hash even unknown accounts, so the response does not reveal registered names.
    valid = hmac.compare_digest(password_hash(password, row['salt'] if row else '00'*16), row['password_hash'] if row else '0'*64)
    if not row or not valid or not row['active']:
        failures = attempt['failures'] + 1 if attempt and attempt['reset_at'] > timestamp else 1
        reset = attempt['reset_at'] if attempt and attempt['reset_at'] > timestamp else timestamp + 15*60
        conn.execute('INSERT INTO login_attempts VALUES(?,?,?) ON CONFLICT(attempt_key) DO UPDATE SET failures=excluded.failures,reset_at=excluded.reset_at', (key, failures, reset))
        return None, 'Usuario o contraseña incorrectos.', 401
    conn.execute('DELETE FROM login_attempts WHERE attempt_key=?', (key,))
    return public_user(row), None, 200

def require_admin(user):
    if user['role'] != 'admin': raise AccessError('Esta acción corresponde al panel central')

def advisor(conn, uid):
    if not uid: return None
    row = conn.execute("SELECT * FROM users WHERE id=? AND role='advisor' AND active=1", (uid,)).fetchone()
    if not row: raise ValueError('Elegí un asesor activo')
    return public_user(row)

def can_access(conn, user, kind, obj):
    if user['role'] == 'admin': return True
    uid = user['id']
    if kind == 'clients': return obj.get('advisorId') == uid
    if kind == 'properties': return uid in obj.get('advisorIds', [])
    if kind in ('visits','operations','events'): return obj.get('advisorId') == uid
    if kind == 'transcription_jobs':
        row = conn.execute('SELECT r.kind,r.body FROM files f JOIN records r ON r.id=f.record_id WHERE f.id=?', (obj.get('fileId'),)).fetchone()
        if not row: return False
        import json
        return can_access(conn, user, row['kind'], json.loads(row['body']))
    return False
