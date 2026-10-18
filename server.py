#!/usr/bin/env python3
"""Nexo: standalone SQLite application. Run python server.py (Python >=3.10)."""
import base64
import hashlib
import hmac
import json
import mimetypes
import math
import os
import re
import secrets
import sqlite3
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from logic import extract_visit, matching, clean
from demo import demo_records
import accounts
import ai_services
import deployment
import marketplace
from concurrent.futures import ThreadPoolExecutor

# Helpers importing `server` must share the running app's lock and database.
# Without this alias, `python server.py` could initialize a second app mid-write.
if __name__ == '__main__':
    sys.modules.setdefault('server',sys.modules[__name__])

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('NEXO_DATA_DIR', ROOT / 'data')).resolve()
UPLOADS = DATA / 'uploads'
DATA.mkdir(parents=True, exist_ok=True)
UPLOADS.mkdir(exist_ok=True)
DBPATH = DATA / 'nexo.sqlite3'
KINDS = ('clients', 'properties', 'visits', 'operations', 'events')
STAGES = ('Contacto', 'Visita', 'Oferta', 'Negociación', 'Cierre', 'Descartada')
SESSION = secrets.token_urlsafe(32)
LOCK = threading.RLock()
TRANSCRIPTION_SETTINGS = DATA / 'transcription-settings.json'
TRANSCRIPTION_POOL = ThreadPoolExecutor(max_workers=2,thread_name_prefix='nexo-audio')
ACTIVE_TRANSCRIPTIONS = set()

def transcription_key():
    if os.environ.get('ASSEMBLYAI_API_KEY'):
        return os.environ['ASSEMBLYAI_API_KEY']
    try:
        return clean(json.loads(TRANSCRIPTION_SETTINGS.read_text()).get('assemblyai_key'))
    except (OSError,ValueError):
        return ''

def save_transcription_key(value):
    value=clean(value)
    if value and (len(value)<16 or len(value)>256 or re.search(r'\s',value)):
        raise ValueError('La clave debe tener entre 16 y 256 caracteres, sin espacios')
    temporary=TRANSCRIPTION_SETTINGS.with_suffix('.tmp')
    temporary.write_text(json.dumps({'assemblyai_key':value}))
    temporary.chmod(0o600)
    os.replace(temporary,TRANSCRIPTION_SETTINGS)

def db():
    conn = sqlite3.connect(DBPATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

with db() as conn:
    conn.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL, updated TEXT NOT NULL)')
    conn.execute('CREATE INDEX IF NOT EXISTS records_kind ON records(kind)')
    conn.execute('CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY, record_id TEXT NOT NULL REFERENCES records(id), filename TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL, storage TEXT NOT NULL, created TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, action TEXT NOT NULL, record_id TEXT, created TEXT NOT NULL)')
    accounts.initialize(conn)
    if 'workspace_id' not in {r[1] for r in conn.execute('PRAGMA table_info(records)')}:
        conn.execute("ALTER TABLE records ADD COLUMN workspace_id TEXT NOT NULL DEFAULT 'legacy'")
    conn.execute('CREATE INDEX IF NOT EXISTS records_workspace ON records(workspace_id,kind,updated)')
    marketplace.initialize(conn)

def now(): return datetime.now().isoformat(timespec='seconds')
def openai_key(): return ai_services.openai_key(DATA)
def transcription_provider(): return ai_services.provider(DATA,transcription_key())
def transcription_ready(): return ai_services.configured(DATA,transcription_key())

def process_openai_job(jid, key):
    try:
        with LOCK,db() as conn:
            job=record(conn,jid,'transcription_jobs')
            f=conn.execute('SELECT * FROM files WHERE id=?',(job['fileId'],)).fetchone()
            if not f: raise ValueError('Audio no encontrado')
            audio=(UPLOADS/f['storage']).read_bytes()
            job['status']='processing';put(conn,'transcription_jobs',job)
        text=ai_services.transcribe(audio,f['filename'],f['mime'],key,job['model'])
        with LOCK,db() as conn:
            job=record(conn,jid,'transcription_jobs')
            job.update(status='completed',text=text,completedAt=now());put(conn,'transcription_jobs',job)
    except Exception as error:
        message=str(error) if isinstance(error,ValueError) else ('OpenAI rechazó la solicitud ('+str(error.code)+'). Revisá tu clave, saldo y permisos.' if isinstance(error,urllib.error.HTTPError) else 'No se pudo completar la transcripción. El audio se conserva; comprobá la conexión y volvé a intentar.')
        with LOCK,db() as conn:
            job=record(conn,jid,'transcription_jobs');job.update(status='error',error=message);put(conn,'transcription_jobs',job)
    finally:
        with LOCK: ACTIVE_TRANSCRIPTIONS.discard(jid)

def list_records(conn, kind, workspace_id=accounts.LEGACY_WORKSPACE):
    return [{**json.loads(r['body']),'workspaceId':workspace_id} for r in conn.execute('SELECT body FROM records WHERE kind=? AND workspace_id=? ORDER BY updated DESC', (kind,workspace_id))]
def record(conn, rid, kind=None):
    row = conn.execute('SELECT kind,body,workspace_id FROM records WHERE id=?', (rid,)).fetchone()
    if not row or (kind and row['kind'] != kind): raise ValueError('Registro no encontrado')
    return {**json.loads(row['body']),'workspaceId':row['workspace_id']}
def put(conn, kind, obj):
    obj['updatedAt'] = now()
    obj.setdefault('workspaceId',accounts.LEGACY_WORKSPACE)
    result=conn.execute('INSERT INTO records(id,kind,body,updated,workspace_id) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body, updated=excluded.updated WHERE records.workspace_id=excluded.workspace_id', (obj['id'],kind,json.dumps(obj, ensure_ascii=False), obj['updatedAt'],obj['workspaceId']))
    if not result.rowcount: raise ValueError('El registro pertenece a otro espacio')
    conn.execute('INSERT INTO audit(action,record_id,created) VALUES(?,?,?)', ('save_'+kind,obj['id'],now()))
def valid_date(value):
    try: datetime.fromisoformat(value)
    except (ValueError, TypeError): raise ValueError('Fecha inválida')

def assign_client(conn, client, uid):
    accounts.advisor(conn, uid, client.get('workspaceId',accounts.LEGACY_WORKSPACE))
    client['advisorId'] = uid or None
    put(conn, 'clients', client)
    # Transfer responsibility, preserving who recorded/confirmed the original sheet.
    for kind in ('visits','operations','events'):
        for obj in list_records(conn, kind, client.get('workspaceId',accounts.LEGACY_WORKSPACE)):
            if obj.get('clientId') != client['id']: continue
            obj['advisorId'] = uid or None
            put(conn, kind, obj)
            if uid and obj.get('propertyId'):
                p = record(conn, obj['propertyId'], 'properties')
                if uid not in p.get('advisorIds', []):
                    p['advisorIds'] = list(dict.fromkeys(p.get('advisorIds', []) + [uid]))
                    put(conn, 'properties', p)

def assign_property(conn, obj, ids):
    if not isinstance(ids, list) or len(ids)>100: raise ValueError('Seleccioná los asesores del inmueble')
    for uid in ids: accounts.advisor(conn, uid, obj.get('workspaceId',accounts.LEGACY_WORKSPACE))
    ids = list(dict.fromkeys(ids))
    required = {r.get('advisorId') for kind in ('visits','operations','events') for r in list_records(conn,kind,obj.get('workspaceId',accounts.LEGACY_WORKSPACE)) if r.get('propertyId')==obj['id'] and r.get('advisorId')}
    if required - set(ids): raise ValueError('El inmueble tiene historial o actividades de ese asesor. Reasigná primero sus clientes o actividades.')
    obj['advisorIds'] = ids
    put(conn, 'properties', obj)

def validate(conn, kind, obj):
    if kind == 'clients':
        if not clean(obj.get('name')): raise ValueError('El cliente necesita un nombre')
        if obj.get('role') not in ('Comprador','Propietario','Inquilino','Inversor'): raise ValueError('Tipo de cliente inválido')
    if kind == 'properties':
        if not clean(obj.get('title')) or not clean(obj.get('zone')): raise ValueError('Completá título y zona')
        if obj.get('operation') not in ('Venta','Alquiler'): raise ValueError('Operación inválida')
        if obj.get('ownerId'): record(conn,obj['ownerId'],'clients')
        if obj.get('status') not in ('Disponible','Reservado','Vendido','Alquilado','Pausado'): raise ValueError('Estado inválido')
        if 'latitude' in obj: marketplace.number(obj['latitude'],'la latitud',-90,90)
        if 'longitude' in obj: marketplace.number(obj['longitude'],'la longitud',-180,180)
    for field in ('budget','price','value','area','bedrooms','bathrooms','parking'):
        if field in obj and obj[field] is not None:
            value = float(obj[field])
            if not math.isfinite(value) or value < 0 or value > 1e12: raise ValueError('Valor numérico inválido')
    if kind in ('clients','properties','operations') and obj.get('currency') not in ('USD','BOB'): raise ValueError('Moneda inválida')
    for field in ('needs','zones','features'):
        if field in obj and (not isinstance(obj[field],list) or len(obj[field]) > 100): raise ValueError('Lista inválida')
    if kind in ('visits','operations','events'):
        for field, target in [('clientId','clients'), ('propertyId','properties')]:
            if obj.get(field): record(conn,obj[field],target)
            elif kind != 'events': raise ValueError('Elegí cliente e inmueble')
    if kind == 'operations' and obj.get('stage') not in STAGES: raise ValueError('Etapa inválida')
    if kind in ('visits','events'):
        valid_date(obj.get('date'))
        if kind == 'events' and not clean(obj.get('title')): raise ValueError('La actividad necesita un título')

def external_json(url, payload, headers):
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json', **headers})
    with urllib.request.urlopen(request,timeout=60) as response: return json.load(response)

def analyse(text):
    key = openai_key()
    if not key: return {'sheet':extract_visit(text),'method':'automatic','source':'text'}
    prompt = 'Extrae una hoja de visita inmobiliaria. Devuelve JSON: summary(string), needs/zones/likes/objections/questions/agreements(arrays de strings), budget/offer(números o null), currency(USD/BOB o null), interest(Alto/Medio/Bajo o null), nextStep(string o null), followUp(YYYY-MM-DD o null). Solo lo dicho explícitamente; no inventes hechos, interés, monedas, fechas, acuerdos ni datos legales. Hoy: '+datetime.now().strftime('%Y-%m-%d')
    result = external_json('https://api.openai.com/v1/chat/completions', {'model':ai_services.text_model(DATA),'response_format':{'type':'json_object'},'messages':[{'role':'system','content':prompt},{'role':'user','content':text}],'temperature':0.1}, {'Authorization':'Bearer '+key})
    sheet = json.loads(result['choices'][0]['message']['content'])
    baseline = extract_visit('')
    for key in baseline:
        val = sheet.get(key)
        if isinstance(baseline[key],list): baseline[key] = [str(x)[:1000] for x in (val if isinstance(val,list) else [])][:30]
        elif key in ('budget','offer'): baseline[key] = float(val) if isinstance(val,(int,float)) and 0<val<1e12 else None
        else: baseline[key] = str(val)[:2000] if val is not None else None
    if baseline['interest'] not in ('Alto','Medio','Bajo'): baseline['interest'] = None
    if baseline['currency'] not in ('USD','BOB'): baseline['currency'] = None
    if baseline['followUp']:
        try: valid_date(baseline['followUp'])
        except ValueError: baseline['followUp'] = None
    return {'sheet':baseline,'method':'ai','source':'text'}

class Handler(BaseHTTPRequestHandler):
    server_version = 'Nexo/2.1'
    def log_message(self, *args): pass
    def reply(self, status, data, mime='application/json; charset=utf-8'):
        content = json.dumps(data,ensure_ascii=False).encode() if mime.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(content)))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
        self.send_header('Cache-Control','no-store' if self.path.startswith('/api') else 'no-cache')
        for key,value in getattr(self,'response_headers',[]): self.send_header(key,value)
        self.end_headers()
        self.wfile.write(content)
    def authorized(self):
        password = os.environ.get('APP_PASSWORD')
        if not password: return True
        token = self.headers.get('Authorization','')
        try:
            supplied = base64.b64decode(token.removeprefix('Basic ')).decode().split(':',1)[1]
            return token.startswith('Basic ') and hmac.compare_digest(password,supplied)
        except Exception: return False
    def body(self, raw=False, limit=10*1024*1024):
        length = int(self.headers.get('Content-Length','0'))
        if length < 0 or length > limit: raise ValueError('Archivo demasiado grande')
        content = self.rfile.read(length)
        return content if raw else json.loads(content or '{}')
    def do_GET(self): self.route('GET')
    def do_POST(self): self.route('POST')
    def do_PATCH(self): self.route('PATCH')
    def do_DELETE(self): self.route('DELETE')
    def get_record(self, conn, rid, kind=None):
        obj = record(conn,rid,kind)
        actual_kind = kind or conn.execute('SELECT kind FROM records WHERE id=?',(rid,)).fetchone()['kind']
        if not accounts.can_access(conn,self.current_user,actual_kind,obj):
            raise accounts.AccessError('Registro no encontrado',404)
        return obj
    def list_records(self, conn, kind):
        return [obj for obj in list_records(conn,kind,self.current_user['workspaceId']) if accounts.can_access(conn,self.current_user,kind,obj)]
    def ai_allowed(self,conn):
        return bool(conn.execute('SELECT ai_enabled FROM workspaces WHERE id=?',(self.current_user['workspaceId'],)).fetchone()['ai_enabled'])
    def prepare_record(self, conn, kind, obj, old=None):
        user=self.current_user
        if 'workspaceId' in obj and obj['workspaceId']!=user['workspaceId']:
            raise accounts.AccessError('No podés cambiar el espacio de un registro')
        obj['workspaceId']=user['workspaceId']
        if kind=='properties' and obj.get('ownerId'): self.get_record(conn,obj['ownerId'],'clients')
        if user['role']=='advisor':
            if kind=='properties':
                accounts.require_property_manager(user)
                if obj.get('advisorIds') not in (None,[user['id']]): raise accounts.AccessError('Solo podés asignarte tus propios inmuebles')
                obj['advisorIds']=[user['id']]
            elif 'advisorIds' in obj: raise accounts.AccessError('Las asignaciones se administran desde el panel central')
            if obj.get('advisorId') not in (None,user['id']): raise accounts.AccessError('No podés asignar registros a otro asesor')
            obj['advisorId']=user['id']
            if kind=='visits': obj['advisor']=user['name'] if not old else old.get('advisor',user['name'])
        elif kind=='clients':
            accounts.advisor(conn,obj.get('advisorId'),user['workspaceId'])
            if old and obj.get('advisorId')!=old.get('advisorId'):
                raise ValueError('Usá Asignar asesor para transferir también su historial')
        elif kind=='properties':
            ids=obj.get('advisorIds',[])
            if not isinstance(ids,list) or len(ids)>100: raise ValueError('Lista de asesores inválida')
            for uid in ids: accounts.advisor(conn,uid,user['workspaceId'])
            if old and ids!=old.get('advisorIds',[]): raise ValueError('Usá Asignar asesores para cambiar el acceso al inmueble')
            obj['advisorIds']=list(dict.fromkeys(ids))
        if kind in ('visits','operations','events'):
            for field,target in (('clientId','clients'),('propertyId','properties')):
                if obj.get(field): self.get_record(conn,obj[field],target)
            linked_client=record(conn,obj['clientId'],'clients') if obj.get('clientId') else None
            responsible=linked_client.get('advisorId') if linked_client else obj.get('advisorId')
            if user['role']=='admin': obj['advisorId']=responsible or None
            accounts.advisor(conn,obj.get('advisorId'),user['workspaceId'])
            if obj.get('advisorId') and obj.get('propertyId'):
                p=record(conn,obj['propertyId'],'properties')
                if obj['advisorId'] not in p.get('advisorIds',[]):
                    raise ValueError('Asigná este inmueble al asesor responsable antes de vincularlo')
            if kind=='visits':
                obj['recordedById']=old.get('recordedById',old.get('createdById')) if old else user['id']
        obj['createdById']=old.get('createdById') if old else user['id']
        if old and old.get('confirmedById'): obj['confirmedById']=old['confirmedById']
        else: obj.pop('confirmedById',None)
        if kind=='properties' and obj.get('photoId'):
            f=conn.execute('SELECT record_id FROM files WHERE id=?',(obj['photoId'],)).fetchone()
            if not f or f['record_id']!=obj['id']: raise ValueError('La fotografía debe pertenecer a este inmueble')
        if kind=='visits':
            if obj.get('audioId'):
                f=conn.execute('SELECT record_id,mime FROM files WHERE id=?',(obj['audioId'],)).fetchone()
                if not f or f['record_id']!=obj['id'] or not f['mime'].startswith('audio/'): raise ValueError('El audio debe pertenecer a esta visita')
            if obj.get('transcriptionJobId'):
                job=self.get_record(conn,obj['transcriptionJobId'],'transcription_jobs')
                f=conn.execute('SELECT record_id FROM files WHERE id=?',(job.get('fileId'),)).fetchone()
                if not f or f['record_id']!=obj['id']: raise ValueError('La transcripción debe pertenecer a esta visita')
        validate(conn,kind,obj)
    def route(self, method):
        self.response_headers=[]
        if self.path == '/healthz' and method == 'GET':
            return self.reply(200, {'ok': True})
        if not deployment.request_allowed(self.headers, method):
            return self.reply(403, {'error': 'Usá el dominio HTTPS de Nexo.'})
        if self.path.split('?')[0] in ('/webhooks/whatsapp','/webhooks/vapi'):
            return self.webhook(method)
        if not self.authorized():
            self.send_response(401); self.send_header('WWW-Authenticate','Basic realm="Nexo"'); self.end_headers(); return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path.startswith('/api') and method != 'GET':
                origin = self.headers.get('Origin')
                if origin and urllib.parse.urlparse(origin).netloc != self.headers.get('Host'): return self.reply(403,{'error':'Origen no autorizado'})
            with LOCK, db() as conn:
                self.current_user=accounts.current_user(conn,self.headers)
                if marketplace.route(self,conn,method,path,query): return
                if path=='/api/auth/me' and method=='GET':
                    return self.reply(200,{'initialized':accounts.has_users(conn),'user':self.current_user,'teamSupported':True})
                if path in ('/api/auth/setup','/api/auth/login') and method=='POST':
                    body=self.body()
                    if not isinstance(body,dict): raise ValueError('Datos inválidos')
                    if path.endswith('/setup'):
                        if deployment.enabled(): return self.reply(403,{'error':'El administrador se crea desde la consola del servidor.'})
                        if accounts.has_users(conn): return self.reply(409,{'error':'El administrador ya está creado. Iniciá sesión.'})
                        address=getattr(self,'client_address',('127.0.0.1',0))[0]
                        if address not in ('127.0.0.1','::1'): return self.reply(403,{'error':'Creá el administrador desde el servidor local antes de compartir el acceso.'})
                        user=accounts.create_user(conn,body,'admin',now())
                    else:
                        user,error,status=accounts.login(conn,body,getattr(self,'client_address',('127.0.0.1',0))[0])
                        if error: return self.reply(status,{'error':error})
                    token=accounts.session(conn,user['id'])
                    self.response_headers.append(('Set-Cookie',accounts.cookie(token,os.environ.get('NEXO_HTTPS')=='1')))
                    return self.reply(201 if path.endswith('/setup') else 200,{'user':user})
                if path=='/api/auth/logout' and method=='POST':
                    conn.execute('DELETE FROM sessions WHERE token_hash=?',(accounts.token_hash(accounts.token_from(self.headers)),))
                    self.response_headers.append(('Set-Cookie',accounts.cookie('',os.environ.get('NEXO_HTTPS')=='1')))
                    return self.reply(200,{'ok':True})
                if path.startswith('/api') and not self.current_user:
                    return self.reply(401,{'error':'Iniciá sesión para abrir tu panel.'})
                if path=='/api/account' and method in ('GET','PATCH'):
                    user = self.current_user if method=='GET' else accounts.update_profile(conn,self.current_user['id'],self.body(limit=4096))
                    return self.reply(200,{'user':user})
                if path=='/api/account/avatar' and method in ('GET','POST','DELETE'):
                    uid=self.current_user['id']
                    if method=='GET':
                        avatar=conn.execute('SELECT mime,body FROM user_avatars WHERE user_id=?',(uid,)).fetchone()
                        if not avatar: return self.reply(404,{'error':'Todavía no agregaste una foto'})
                        return self.reply(200,avatar['body'],avatar['mime'])
                    if method=='POST':
                        accounts.save_avatar(conn,uid,self.body(raw=True,limit=256*1024),self.headers.get('Content-Type','').split(';')[0])
                    else:
                        conn.execute('DELETE FROM user_avatars WHERE user_id=?',(uid,))
                        conn.execute("UPDATE users SET avatar_updated='' WHERE id=?",(uid,))
                    return self.reply(200,{'user':accounts.public_user(conn.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())})
                if path=='/api/account/password' and method=='POST':
                    body=self.body(limit=4096)
                    if not isinstance(body,dict): raise ValueError('Datos inválidos')
                    digest,salt=accounts.password_values(body.get('newPassword'))
                    user,error,status=accounts.login(conn,{'username':self.current_user['username'],'password':body.get('currentPassword')},getattr(self,'client_address',('127.0.0.1',0))[0])
                    if error: return self.reply(429 if status==429 else 400,{'error':error if status==429 else 'La contraseña actual no es correcta.'})
                    conn.execute('UPDATE users SET password_hash=?,salt=? WHERE id=?',(digest,salt,user['id']))
                    conn.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
                    token=accounts.session(conn,user['id'])
                    self.response_headers.append(('Set-Cookie',accounts.cookie(token,os.environ.get('NEXO_HTTPS')=='1')))
                    conn.execute('INSERT INTO audit(action,record_id,created) VALUES(?,?,?)',('password_changed',user['id'],now()))
                    return self.reply(200,{'ok':True})
                if path=='/api/users' and method=='GET':
                    accounts.require_admin(self.current_user)
                    return self.reply(200,{'users':[accounts.public_user(r) for r in conn.execute('SELECT * FROM users WHERE workspace_id=? ORDER BY role,name',(self.current_user['workspaceId'],))]})
                if path=='/api/users' and method=='POST':
                    accounts.require_admin(self.current_user)
                    return self.reply(201,accounts.create_user(conn,self.body(),'advisor',now(),self.current_user['workspaceId']))
                user_match=re.fullmatch(r'/api/users/([^/]+)',path)
                if user_match and method=='PATCH':
                    accounts.require_admin(self.current_user)
                    body=self.body(); row=conn.execute('SELECT * FROM users WHERE id=? AND workspace_id=?',(user_match[1],self.current_user['workspaceId'])).fetchone()
                    if not row: raise ValueError('Usuario no encontrado')
                    if row['role']=='admin': raise ValueError('La cuenta del administrador se conserva activa')
                    if 'role' in body or 'id' in body or 'username' in body: raise ValueError('El rol y el usuario no se cambian')
                    if 'name' in body:
                        if not isinstance(body['name'],str) or not 1<=len(body['name'].strip())<=120: raise ValueError('Nombre inválido')
                        conn.execute('UPDATE users SET name=? WHERE id=?',(body['name'].strip(),row['id']))
                    if 'active' in body:
                        if not isinstance(body['active'],bool): raise ValueError('Estado inválido')
                        conn.execute('UPDATE users SET active=? WHERE id=?',(int(body['active']),row['id']))
                    if 'password' in body:
                        digest,salt=accounts.password_values(body['password'])
                        conn.execute('UPDATE users SET password_hash=?,salt=? WHERE id=?',(digest,salt,row['id']))
                    if 'password' in body or body.get('active') is False:
                        conn.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],))
                    conn.execute('INSERT INTO audit(action,record_id,created) VALUES(?,?,?)',('account_updated',row['id'],now()))
                    return self.reply(200,accounts.public_user(conn.execute('SELECT * FROM users WHERE id=?',(row['id'],)).fetchone()))
                if path=='/api/assign' and method=='POST':
                    accounts.require_admin(self.current_user)
                    body=self.body();kind=body.get('kind')
                    if kind not in ('clients','properties'): raise ValueError('Asignación inválida')
                    obj=self.get_record(conn,body.get('id'),kind)
                    if kind=='clients': assign_client(conn,obj,body.get('advisorId'))
                    else: assign_property(conn,obj,body.get('advisorIds'))
                    return self.reply(200,obj)
                if path == '/api/state' and method == 'GET':
                    state = {kind:self.list_records(conn,kind) for kind in KINDS}
                    visible={obj['id'] for rows in state.values() for obj in rows}
                    state['files'] = [dict(r) for r in conn.execute('SELECT id,record_id,filename,mime,size,created FROM files') if r['record_id'] in visible]
                    return self.reply(200,state)
                if path == '/api/config' and method == 'GET':
                    allowed=self.ai_allowed(conn)
                    legacy=self.current_user['workspaceId']==accounts.LEGACY_WORKSPACE
                    workspace=conn.execute('SELECT name FROM workspaces WHERE id=?',(self.current_user['workspaceId'],)).fetchone()
                    return self.reply(200,{'brand':'Nexo','ai':allowed and bool(openai_key()),'transcription':allowed and transcription_ready(),'aiEnabled':allowed,'workspaceName':workspace['name'],'transcriptionProvider':transcription_provider(),'audioModel':ai_services.audio_model(DATA),'openaiConfigured':allowed and bool(openai_key()),'assemblyaiConfigured':allowed and bool(transcription_key()),'presentation':os.environ.get('NEXO_PRESENTATION')=='1','transcriptionSetup':'local' if self.current_user['platformAdmin'] else None,'whatsapp':legacy and bool(os.environ.get('WHATSAPP_TOKEN') and os.environ.get('WHATSAPP_PHONE_NUMBER_ID')),'voice':legacy and bool(os.environ.get('VAPI_SERVER_SECRET')),'calendar':legacy and bool(os.environ.get('GOOGLE_CALENDAR_TOKEN') and os.environ.get('GOOGLE_CALENDAR_ID')),'storage':'server','user':self.current_user['name'],'role':self.current_user['role'],'profile':self.current_user,'teamSupported':True,'marketplace':True})
                if path=='/api/readiness' and method=='GET':
                    accounts.require_admin(self.current_user)
                    return self.reply(200,{'presentation':os.environ.get('NEXO_PRESENTATION')=='1','accounts':conn.execute("SELECT count(*) FROM users WHERE role='advisor' AND active=1 AND workspace_id=?",(self.current_user['workspaceId'],)).fetchone()[0],'clients':len(self.list_records(conn,'clients')),'properties':len(self.list_records(conn,'properties')),'visits':len(self.list_records(conn,'visits')),'storage':os.access(DATA,os.W_OK) and os.access(UPLOADS,os.W_OK),'transcription':self.ai_allowed(conn) and transcription_ready(),'ai':self.ai_allowed(conn) and bool(openai_key()),'provider':transcription_provider()})
                if path=='/api/ai-settings' and method=='POST':
                    accounts.require_platform(self.current_user)
                    body=self.body()
                    if not isinstance(body,dict): raise ValueError('Datos inválidos')
                    ai_services.save(DATA,body,save_transcription_key)
                    return self.reply(200,{'configured':transcription_ready(),'provider':transcription_provider()})
                if path=='/api/ai-check' and method=='POST':
                    accounts.require_platform(self.current_user)
                    if not openai_key(): raise ValueError('Configurá primero la clave de OpenAI')
                    external_json('https://api.openai.com/v1/chat/completions',{'model':ai_services.text_model(DATA),'messages':[{'role':'user','content':'Respondé solamente OK.'}],'max_tokens':5},{'Authorization':'Bearer '+openai_key()})
                    return self.reply(200,{'ok':True,'message':'OpenAI respondió. Antes de presentar, probá también una grabación real.'})
                if path == '/api/transcription-settings' and method=='POST':
                    accounts.require_platform(self.current_user)
                    value=self.body().get('key')
                    if not isinstance(value,str): raise ValueError('Ingresá una clave de transcripción')
                    if os.environ.get('ASSEMBLYAI_API_KEY'):
                        return self.reply(409,{'error':'La conexión está definida en el entorno del servidor. Modificala allí.'})
                    save_transcription_key(value)
                    return self.reply(200,{'configured':bool(transcription_key())})
                if path == '/api/demo' and method == 'POST':
                    accounts.require_platform(self.current_user)
                    if conn.execute('SELECT count(*) FROM records').fetchone()[0]: raise ValueError('La demo solo se carga en un espacio vacío')
                    for kind,records in demo_records().items():
                        for obj in records: obj['demo']=True; put(conn,kind,obj)
                    return self.reply(201,{'ok':True})
                if path == '/api/analyse' and method == 'POST':
                    body=self.body();text = clean(body.get('text'))
                    if len(text) < 15 or len(text)>150000: raise ValueError('Agregá una transcripción de entre 15 y 150000 caracteres')
                    if body.get('local') is not True and not self.ai_allowed(conn): return self.reply(403,{'error':'La IA no está habilitada para tu espacio. Podés organizar el texto sin IA.'})
                    if body.get('local') is True: return self.reply(200,{'sheet':extract_visit(text),'method':'automatic','source':'text'})
                    return self.reply(200,analyse(text))
                if path == '/api/ask' and method == 'POST':
                    body = self.body(); client = self.get_record(conn,body.get('clientId'),'clients')
                    visits = [v for v in self.list_records(conn,'visits') if v.get('clientId')==client['id'] and v.get('status')=='Confirmada']
                    question = clean(body.get('question'))
                    if not question or len(question)>1000: raise ValueError('Escribí una pregunta de hasta 1000 caracteres')
                    key = openai_key() if self.ai_allowed(conn) else ''
                    context = json.dumps({'client':client,'visits':visits},ensure_ascii=False)
                    if key:
                        r = external_json('https://api.openai.com/v1/chat/completions',{'model':ai_services.text_model(DATA),'messages':[{'role':'system','content':'Responde en español solo con la información del historial dado. Si no está registrado, dilo. Cita fechas. No inventes compromisos ni datos legales.'},{'role':'user','content':context+'\nPregunta: '+question}],'temperature':0.1}, {'Authorization':'Bearer '+key})
                        answer = r['choices'][0]['message']['content']
                    else:
                        low = question.lower()
                        field = 'objections' if re.search('descart|objec|no le gust|rechaz|por qu',low) else 'budget' if 'presupuesto' in low else 'likes' if 'gust' in low else 'nextStep' if re.search('pendiente|pr[oó]ximo|seguimiento|acuerd',low) else 'summary'
                        fragments = []
                        for v in sorted(visits,key=lambda x:x['date'],reverse=True):
                            content = v.get('sheet',{}).get(field)
                            if content: fragments.append(v['date'][:10]+': '+ ('; '.join(content) if isinstance(content,list) else str(content)))
                        answer = '\n'.join(fragments[:8]) or ('Presupuesto registrado: '+str(client.get('budget'))+' '+client.get('currency','') if field=='budget' and client.get('budget') else 'No hay información sobre eso en las hojas de visita confirmadas.')
                    return self.reply(200,{'answer':answer})
                match = re.fullmatch(r'/api/matches/([^/]+)',path)
                if match and method == 'GET': return self.reply(200,{'matches':matching(self.get_record(conn,match[1],'clients'), self.list_records(conn,'properties'))})
                match = re.fullmatch(r'/api/visits/([^/]+)/confirm',path)
                if match and method=='POST':
                    visit = self.get_record(conn,match[1],'visits')
                    if visit.get('status')=='Confirmada': return self.reply(409,{'error':'La visita ya fue confirmada'})
                    if visit.get('transcriptionJobId'):
                        job=self.get_record(conn,visit['transcriptionJobId'],'transcription_jobs')
                        if job.get('provider')=='openai' and job.get('status') in ('queued','processing'):
                            return self.reply(409,{'error':'Esperá a que termine la transcripción antes de confirmar la hoja.'})
                    body = self.body(); sheet=body.get('sheet')
                    if not isinstance(sheet,dict): raise ValueError('Revisá la hoja antes de confirmar')
                    for k in ('needs','zones','likes','objections','questions','agreements'):
                        if not isinstance(sheet.get(k,[]),list): raise ValueError('Campos de la hoja inválidos')
                    if sheet.get('budget') is not None and float(sheet['budget'])<=0: raise ValueError('Presupuesto inválido')
                    if body.get('updateClient'):
                        client = self.get_record(conn,visit['clientId'],'clients')
                        for k in ('needs','zones'): client[k]=list(dict.fromkeys(client.get(k,[])+sheet.get(k,[])))
                        for k in ('budget','currency'):
                            if sheet.get(k): client[k]=sheet[k]
                        validate(conn,'clients',client); put(conn,'clients',client)
                    if body.get('createFollowUp') and sheet.get('nextStep'):
                        date = clean(sheet.get('followUp'))
                        if not date: raise ValueError('Elegí una fecha para el seguimiento')
                        valid_date(date)
                        event={'id':str(uuid.uuid4()),'title':sheet['nextStep'],'date':date+'T09:00' if len(date)==10 else date,'type':'Seguimiento','status':'Pendiente','clientId':visit['clientId'],'propertyId':visit['propertyId'],'notes':'Desde hoja de visita','visitId':visit['id'],'advisorId':visit.get('advisorId'),'createdById':self.current_user['id'],'workspaceId':self.current_user['workspaceId']}
                        validate(conn,'events',event); put(conn,'events',event)
                    visit.update({'sheet':sheet,'status':'Confirmada','confirmedAt':now(),'confirmedById':self.current_user['id']});put(conn,'visits',visit)
                    return self.reply(200,visit)
                match = re.fullmatch(r'/api/files/([^/]+)',path)
                if match and method=='GET':
                    f = conn.execute('SELECT * FROM files WHERE id=?',(match[1],)).fetchone()
                    if not f: return self.reply(404,{'error':'Archivo no encontrado'})
                    self.get_record(conn,f['record_id'])
                    return self.reply(200,(UPLOADS/f['storage']).read_bytes(),f['mime'])
                if path == '/api/files' and method=='POST':
                    rid=query.get('recordId',[''])[0]; self.get_record(conn,rid)
                    parent_kind=conn.execute('SELECT kind FROM records WHERE id=?',(rid,)).fetchone()['kind']
                    if parent_kind=='properties': accounts.require_property_manager(self.current_user)
                    raw=self.body(raw=True,limit=80*1024*1024)
                    mime=self.headers.get('Content-Type','application/octet-stream').split(';')[0]
                    if not raw: raise ValueError('El archivo está vacío')
                    if not (mime.startswith('audio/') or mime in ('application/pdf','image/jpeg','image/png','image/webp','image/gif','text/plain')): raise ValueError('Formato no permitido: usá imagen, PDF o audio')
                    fid=str(uuid.uuid4());storage=fid+(mimetypes.guess_extension(mime) or '.bin')
                    filename=Path(query.get('name',['archivo'])[0]).name[:180]
                    (UPLOADS/storage).write_bytes(raw)
                    conn.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?)',(fid,rid,filename,mime,len(raw),storage,now()))
                    return self.reply(201,{'id':fid,'filename':filename,'record_id':rid,'mime':mime})
                if path == '/api/transcribe' and method=='POST':
                    if not self.ai_allowed(conn): return self.reply(403,{'error':'La transcripción con IA no está habilitada para tu espacio.'})
                    body=self.body();fid=body.get('fileId')
                    f=conn.execute('SELECT * FROM files WHERE id=?',(fid,)).fetchone()
                    if not f or not f['mime'].startswith('audio/'): raise ValueError('Elegí una grabación de audio')
                    self.get_record(conn,f['record_id'])
                    if transcription_provider()=='openai':
                        key=openai_key()
                        if not key: return self.reply(503,{'error':'El administrador debe conectar OpenAI para transcribir el audio.'})
                        if f['size']>ai_services.MAX_OPENAI_AUDIO: raise ValueError('OpenAI admite hasta 25 MB por audio. Dividí el archivo en grabaciones más cortas.')
                        if f['mime'] not in ('audio/webm','audio/mp4','audio/mpeg','audio/mp3','audio/wav','audio/x-wav','audio/m4a','audio/x-m4a'):
                            raise ValueError('Para OpenAI usá WebM, MP3, M4A, MP4 o WAV.')
                        for existing in self.list_records(conn,'transcription_jobs'):
                            if existing.get('provider')=='openai' and existing.get('fileId')==fid and existing.get('status') in ('queued','processing','completed'):
                                if existing.get('status')=='completed' or existing['id'] in ACTIVE_TRANSCRIPTIONS:
                                    return self.reply(202,{'jobId':existing['id']})
                        jid='oa-'+str(uuid.uuid4())
                        put(conn,'transcription_jobs',{'id':jid,'fileId':fid,'provider':'openai','model':ai_services.audio_model(DATA),'status':'queued','createdAt':now(),'workspaceId':self.current_user['workspaceId']})
                        ACTIVE_TRANSCRIPTIONS.add(jid)
                        try: TRANSCRIPTION_POOL.submit(process_openai_job,jid,key)
                        except Exception: ACTIVE_TRANSCRIPTIONS.discard(jid);raise
                        return self.reply(202,{'jobId':jid})
                    key=transcription_key()
                    if not key: return self.reply(503,{'error':'La transcripción de archivos necesita ASSEMBLYAI_API_KEY. Podés usar el texto capturado en vivo o pegar una transcripción.'})
                    request=urllib.request.Request('https://api.assemblyai.com/v2/upload',data=(UPLOADS/f['storage']).read_bytes(),headers={'Authorization':key,'Content-Type':'application/octet-stream'})
                    with urllib.request.urlopen(request,timeout=90) as r: uploaded=json.load(r)
                    r=external_json('https://api.assemblyai.com/v2/transcript',{'audio_url':uploaded['upload_url'],'language_code':'es','speaker_labels':True},{'Authorization':key})
                    put(conn,'transcription_jobs',{'id':r['id'],'fileId':fid,'workspaceId':self.current_user['workspaceId']})
                    return self.reply(202,{'jobId':r['id']})
                if path.startswith('/api/transcribe/') and method=='GET':
                    jid=path.rsplit('/',1)[-1]
                    if not re.fullmatch(r'[\w-]+',jid): raise ValueError('Identificador inválido')
                    job=self.get_record(conn,jid,'transcription_jobs')
                    if job.get('provider')=='openai':
                        if job.get('status') in ('queued','processing') and jid not in ACTIVE_TRANSCRIPTIONS:
                            job.update(status='error',error='El servidor se reinició durante el procesamiento. El audio se conserva; volvé a transcribirlo.')
                            put(conn,'transcription_jobs',job)
                        return self.reply(200,{'status':job['status'],'text':job.get('text',''),'error':job.get('error')})
                    key=transcription_key()
                    if not key: return self.reply(503,{'error':'Servicio no configurado'})
                    request=urllib.request.Request('https://api.assemblyai.com/v2/transcript/'+jid,headers={'Authorization':key})
                    with urllib.request.urlopen(request,timeout=30) as r: result=json.load(r)
                    return self.reply(200,{'status':result['status'],'text':result.get('text',''),'error':result.get('error')})
                if path == '/api/whatsapp' and method=='POST':
                    if self.current_user['workspaceId']!=accounts.LEGACY_WORKSPACE: raise accounts.AccessError('Esta integración pertenece a otro espacio de trabajo')
                    b=self.body(); client=self.get_record(conn,b.get('clientId'),'clients');message=clean(b.get('message'))
                    token=os.environ.get('WHATSAPP_TOKEN');phoneid=os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
                    if not token or not phoneid: return self.reply(503,{'error':'WhatsApp no está conectado. Podés abrir el mensaje para enviarlo personalmente.'})
                    if not re.fullmatch(r'\d{8,15}',client.get('phone','')) or not message: raise ValueError('Completá teléfono internacional y mensaje')
                    r=external_json('https://graph.facebook.com/v21.0/'+phoneid+'/messages',{'messaging_product':'whatsapp','to':client['phone'],'type':'text','text':{'body':message}},{'Authorization':'Bearer '+token})
                    conn.execute('INSERT INTO audit(action,record_id,created) VALUES(?,?,?)',('whatsapp_sent',client['id'],now()))
                    return self.reply(200,{'ok':True,'messageId':r.get('messages',[{}])[0].get('id')})
                if path == '/api/calendar' and method=='POST':
                    if self.current_user['workspaceId']!=accounts.LEGACY_WORKSPACE: raise accounts.AccessError('Esta integración pertenece a otro espacio de trabajo')
                    event=self.get_record(conn,self.body().get('eventId'),'events')
                    token=os.environ.get('GOOGLE_CALENDAR_TOKEN');cal=os.environ.get('GOOGLE_CALENDAR_ID')
                    if not token or not cal: return self.reply(503,{'error':'Google Calendar no está conectado. Podés descargar el archivo de calendario.'})
                    if event.get('googleEventId'): return self.reply(409,{'error':'Esta actividad ya fue enviada al calendario'})
                    start=datetime.fromisoformat(event['date'])
                    r=external_json('https://www.googleapis.com/calendar/v3/calendars/'+urllib.parse.quote(cal,safe='')+'/events',{'summary':event['title'],'description':event.get('notes',''),'start':{'dateTime':start.isoformat(),'timeZone':os.environ.get('NEXO_TIMEZONE','America/La_Paz')},'end':{'dateTime':(start+timedelta(minutes=45)).isoformat(),'timeZone':os.environ.get('NEXO_TIMEZONE','America/La_Paz')}},{'Authorization':'Bearer '+token})
                    event['googleEventId']=r['id'];put(conn,'events',event)
                    return self.reply(200,{'ok':True})
                if path == '/api/export' and method=='GET':
                    accounts.require_property_manager(self.current_user)
                    return self.reply(200,{'version':2,'exportedAt':now(),'records':{kind:self.list_records(conn,kind) for kind in KINDS},'team':[accounts.public_user(r) for r in conn.execute('SELECT * FROM users WHERE workspace_id=?',(self.current_user['workspaceId'],))]})
                match = re.fullmatch(r'/api/(clients|properties|visits|operations|events)(?:/([^/]+))?',path)
                if match:
                    kind,rid=match.groups()
                    if method=='GET': return self.reply(200,self.get_record(conn,rid,kind) if rid else self.list_records(conn,kind))
                    if method in ('POST','PATCH'):
                        old=None
                        obj=self.body()
                        if not isinstance(obj,dict): raise ValueError('Datos inválidos')
                        if method=='PATCH':
                            if not rid: raise ValueError('Falta el registro')
                            old=self.get_record(conn,rid,kind)
                            if kind=='visits' and old.get('status')=='Confirmada': return self.reply(409,{'error':'La hoja confirmada es de solo lectura'})
                            obj={**old,**obj,'id':rid}
                        else:
                            obj['id']=str(uuid.uuid4());obj['createdAt']=now()
                            if kind=='visits': obj['status']='Borrador'
                        if kind=='visits': obj['status']='Borrador';obj.pop('confirmedAt',None)
                        self.prepare_record(conn,kind,obj,old);put(conn,kind,obj)
                        return self.reply(201 if method=='POST' else 200,obj)
                    if method=='DELETE':
                        accounts.require_property_manager(self.current_user)
                        old=self.get_record(conn,rid,kind)
                        if kind=='visits' and old.get('status')=='Confirmada': return self.reply(409,{'error':'Conservá el historial de las visitas confirmadas'})
                        for k in KINDS:
                            if k in ('clients','properties'): continue
                            if any(x.get('clientId')==rid or x.get('propertyId')==rid for x in self.list_records(conn,k)): return self.reply(409,{'error':'Tiene visitas, operaciones o actividades vinculadas. Conservá su historial.'})
                        if kind=='clients' and any(p.get('ownerId')==rid for p in self.list_records(conn,'properties')): return self.reply(409,{'error':'Es propietario de un inmueble registrado'})
                        for f in conn.execute('SELECT storage FROM files WHERE record_id=?',(rid,)).fetchall(): (UPLOADS/f['storage']).unlink(missing_ok=True)
                        conn.execute('DELETE FROM files WHERE record_id=?',(rid,));conn.execute('DELETE FROM records WHERE id=?',(rid,))
                        return self.reply(200,{'ok':True})
            if method=='GET' and not path.startswith('/api'):
                filename='portal.html' if path in ('/explorar','/explorar/') or path.startswith(('/inmueble/','/asesor/')) else 'registro.html' if path in ('/registro','/registro/') else 'index.html' if path in ('/','/index.html','/app') else path.lstrip('/')
                target=(ROOT/'public'/filename).resolve()
                if not target.is_relative_to(ROOT/'public') or not target.is_file(): return self.reply(404,b'No encontrado','text/plain')
                return self.reply(200,target.read_bytes(),mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
            return self.reply(404,{'error':'Ruta no encontrada'})
        except accounts.AccessError as e: self.reply(e.status,{'error':str(e)})
        except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e: self.reply(400,{'error':str(e)})
        except urllib.error.HTTPError as e: self.reply(502,{'error':'El servicio externo rechazó la solicitud ('+str(e.code)+'). Revisá sus credenciales y permisos.'})
        except Exception as e:
            print('Request failed:',type(e).__name__,flush=True)
            self.reply(500,{'error':'No se pudo completar la operación. Los datos ya guardados se conservan.'})

    def webhook(self, method):
        try:
            from reception import handle_voice, handle_whatsapp
            path=urllib.parse.urlparse(self.path).path
            query=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if path=='/webhooks/vapi':
                secret=os.environ.get('VAPI_SERVER_SECRET','')
                supplied=self.headers.get('x-vapi-secret') or self.headers.get('Authorization','').removeprefix('Bearer ')
                if not secret or not hmac.compare_digest(secret,supplied): return self.reply(401,{'error':'No autorizado'})
                if method!='POST': return self.reply(405,{'error':'Método no permitido'})
                body=self.body()
                with LOCK,db() as conn:
                    msg=body.get('message',{})
                    if msg.get('type')!='tool-calls': return self.reply(200,{'ok':True})
                    results=[]
                    for call in msg.get('toolCallList',[])[:10]:
                        args=call.get('arguments',{})
                        if isinstance(args,str):args=json.loads(args)
                        if not args.get('phone'):args['phone']=msg.get('call',{}).get('customer',{}).get('number','')
                        try: result=handle_voice(conn,call.get('name'),args)
                        except ValueError as e: result=str(e)
                        results.append({'toolCallId':call.get('id'),'result':result})
                return self.reply(200,{'results':results})
            token=os.environ.get('WHATSAPP_VERIFY_TOKEN','')
            if method=='GET':
                supplied=query.get('hub.verify_token',[''])[0]
                if token and hmac.compare_digest(token,supplied): return self.reply(200,query.get('hub.challenge',[''])[0].encode(),'text/plain')
                return self.reply(403,{'error':'Verificación inválida'})
            if method!='POST':return self.reply(405,{'error':'Método no permitido'})
            raw=self.body(raw=True)
            appsecret=os.environ.get('META_APP_SECRET','')
            signature=self.headers.get('X-Hub-Signature-256','')
            expected='sha256='+hmac.new(appsecret.encode(),raw,hashlib.sha256).hexdigest()
            if not appsecret or not hmac.compare_digest(signature,expected): return self.reply(401,{'error':'Firma inválida'})
            body=json.loads(raw)
            value=body.get('entry',[{}])[0].get('changes',[{}])[0].get('value',{})
            for message in value.get('messages',[])[:10]:
                if message.get('type')!='text': continue
                with LOCK,db() as conn:
                    response=handle_whatsapp(conn,message.get('from',''),message.get('text',{}).get('body',''),message.get('id',''))
                if response and os.environ.get('WHATSAPP_TOKEN') and os.environ.get('WHATSAPP_PHONE_NUMBER_ID'):
                    external_json('https://graph.facebook.com/v21.0/'+os.environ['WHATSAPP_PHONE_NUMBER_ID']+'/messages',{'messaging_product':'whatsapp','to':message['from'],'type':'text','text':{'body':response}},{'Authorization':'Bearer '+os.environ['WHATSAPP_TOKEN']})
            return self.reply(200,{'ok':True})
        except (ValueError,KeyError,IndexError,TypeError) as e: return self.reply(400,{'error':'Solicitud inválida'})
        except Exception as e:
            print('Webhook failed:',type(e).__name__,flush=True)
            return self.reply(502,{'error':'No se pudo procesar el servicio externo'})

if __name__ == '__main__':
    host=os.environ.get('HOST','127.0.0.1');port=int(os.environ.get('PORT','8080'))
    with db() as conn:
        has_admin=bool(conn.execute("SELECT 1 FROM users WHERE role='admin' AND active=1 LIMIT 1").fetchone())
    try: deployment.validate_startup(host,has_admin)
    except ValueError as error: raise SystemExit(str(error))
    print(f'Nexo disponible en http://{host}:{port}',flush=True)
    ThreadingHTTPServer((host,port),Handler).serve_forever()
