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
LEGACY_WORKSPACE = 'legacy'

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
    # Additive migration: existing accounts, passwords and sessions are preserved.
    columns = {r[1] for r in conn.execute('PRAGMA table_info(users)')}
    migrated_workspace = 'workspace_id' not in columns
    for column, default in (('email', ''), ('phone', ''), ('title', ''), ('avatar_color', '#164d45'), ('avatar_updated', ''), ('workspace_id', LEGACY_WORKSPACE), ('workspace_kind', 'agency'), ('platform_admin', '0')):
        if column not in columns:
            conn.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT NOT NULL DEFAULT '{default}'")
    conn.execute('''CREATE TABLE IF NOT EXISTS user_avatars (
        user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        mime TEXT NOT NULL, body BLOB NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS workspaces (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1, ai_enabled INTEGER NOT NULL DEFAULT 0,
        created TEXT NOT NULL
    )''')
    conn.execute("INSERT OR IGNORE INTO workspaces VALUES(?,'Mi inmobiliaria','agency',1,1,'legacy')", (LEGACY_WORKSPACE,))
    if migrated_workspace:
        conn.execute("UPDATE users SET platform_admin='1' WHERE role='admin' AND workspace_id=?", (LEGACY_WORKSPACE,))
    conn.execute('CREATE INDEX IF NOT EXISTS users_workspace ON users(workspace_id)')

def public_user(row):
    user = {key: row[key] for key in ('id', 'username', 'name', 'role', 'active', 'created', 'email', 'phone', 'title')}
    user.update(avatarColor=row['avatar_color'], avatarUpdated=row['avatar_updated'])
    user.update(workspaceId=row['workspace_id'], workspaceKind=row['workspace_kind'], platformAdmin=str(row['platform_admin'])=='1')
    return user

def update_profile(conn, user_id, data):
    allowed = {'name', 'email', 'phone', 'title', 'avatarColor'}
    if not isinstance(data, dict) or not data or set(data) - allowed:
        raise ValueError('Solo podés editar tus datos de perfil')
    clean = {}
    for key, value in data.items():
        limit = {'name':120, 'email':254, 'phone':40, 'title':100, 'avatarColor':7}[key]
        if not isinstance(value, str) or len(value.strip()) > limit or any(ord(c)<32 for c in value):
            raise ValueError('Revisá los datos del perfil')
        value = value.strip()
        if key == 'name' and not value: raise ValueError('Ingresá tu nombre')
        if key == 'email' and value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Ingresá un correo válido')
        if key == 'avatarColor' and not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise ValueError('Elegí un color válido')
        clean['avatar_color' if key == 'avatarColor' else key] = value
    conn.execute('UPDATE users SET '+','.join(key+'=?' for key in clean)+' WHERE id=?', (*clean.values(), user_id))
    row=conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if row['workspace_kind']=='independent' and 'name' in clean:
        conn.execute('UPDATE workspaces SET name=? WHERE id=?',(clean['name'],row['workspace_id']))
    return public_user(row)

def save_avatar(conn, user_id, body, mime):
    if mime not in ('image/jpeg', 'image/png', 'image/webp') or not 12 <= len(body) <= 256*1024:
        raise ValueError('Usá una foto JPG, PNG o WebP de hasta 256 KB')
    valid = ((mime == 'image/jpeg' and body.startswith(b'\xff\xd8\xff') and body.endswith(b'\xff\xd9')) or
             (mime == 'image/png' and body.startswith(b'\x89PNG\r\n\x1a\n')) or
             (mime == 'image/webp' and body[:4] == b'RIFF' and body[8:12] == b'WEBP'))
    if not valid: raise ValueError('El archivo no corresponde a una imagen compatible')
    conn.execute('INSERT INTO user_avatars VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET mime=excluded.mime,body=excluded.body', (user_id, mime, body))
    conn.execute('UPDATE users SET avatar_updated=? WHERE id=?', (secrets.token_hex(12), user_id))

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

def create_user(conn, data, role, created, workspace_id=LEGACY_WORKSPACE, workspace_kind='agency'):
    if not isinstance(data, dict): raise ValueError('Datos inválidos')
    name = data.get('name')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
        raise ValueError('Ingresá el nombre, hasta 120 caracteres')
    login = username(data.get('username'))
    if conn.execute('SELECT 1 FROM users WHERE username=?', (login,)).fetchone():
        raise ValueError('Ese nombre de usuario ya está registrado')
    digest, salt = password_values(data.get('password'))
    uid = str(uuid.uuid4())
    conn.execute('INSERT INTO users(id,username,name,role,password_hash,salt,active,created,workspace_id,workspace_kind,platform_admin) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (uid, login, name.strip(), role, digest, salt, 1, created, workspace_id, workspace_kind, '1' if role=='admin' and workspace_id==LEGACY_WORKSPACE else '0'))
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
    row = conn.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id JOIN workspaces w ON w.id=u.workspace_id WHERE s.token_hash=? AND s.expires>? AND u.active=1 AND w.active=1', (token_hash(token), int(time.time()))).fetchone()
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
    workspace = conn.execute('SELECT active FROM workspaces WHERE id=?', (row['workspace_id'],)).fetchone() if row else None
    if not row or not valid or not row['active'] or not workspace or not workspace['active']:
        failures = attempt['failures'] + 1 if attempt and attempt['reset_at'] > timestamp else 1
        reset = attempt['reset_at'] if attempt and attempt['reset_at'] > timestamp else timestamp + 15*60
        conn.execute('INSERT INTO login_attempts VALUES(?,?,?) ON CONFLICT(attempt_key) DO UPDATE SET failures=excluded.failures,reset_at=excluded.reset_at', (key, failures, reset))
        return None, 'Usuario o contraseña incorrectos.', 401
    conn.execute('DELETE FROM login_attempts WHERE attempt_key=?', (key,))
    return public_user(row), None, 200

def require_admin(user):
    if user['role'] != 'admin': raise AccessError('Esta acción corresponde al panel central')

def require_platform(user):
    if not user.get('platformAdmin'): raise AccessError('Esta acción corresponde a la administración de Nexo')

def manages_properties(user):
    return user['role']=='admin' or user.get('workspaceKind')=='independent'

def require_property_manager(user):
    if not manages_properties(user): raise AccessError('Los inmuebles se administran desde la inmobiliaria')

def advisor(conn, uid, workspace_id=LEGACY_WORKSPACE):
    if not uid: return None
    row = conn.execute("SELECT * FROM users WHERE id=? AND role='advisor' AND active=1 AND workspace_id=?", (uid,workspace_id)).fetchone()
    if not row: raise ValueError('Elegí un asesor activo')
    return public_user(row)

def can_access(conn, user, kind, obj):
    if obj.get('workspaceId', LEGACY_WORKSPACE) != user.get('workspaceId', LEGACY_WORKSPACE): return False
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
