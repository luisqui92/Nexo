"""Public listings contain an explicit whitelist; CRM data stays workspace-scoped."""
import hashlib
import ipaddress
import json
import math
import os
import re
import time
import uuid
from datetime import datetime
from urllib.parse import urlsplit
import accounts
import portal_examples

def initialize(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS publications (
            id TEXT PRIMARY KEY, property_id TEXT NOT NULL UNIQUE REFERENCES records(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL, publisher_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status TEXT NOT NULL, blocked INTEGER NOT NULL DEFAULT 0, body TEXT NOT NULL,
            created TEXT NOT NULL, updated TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS publications_workspace ON publications(workspace_id,status);
        CREATE INDEX IF NOT EXISTS publications_publisher ON publications(publisher_id,status,updated);
        CREATE TABLE IF NOT EXISTS inquiries (
            id TEXT PRIMARY KEY, publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL, publisher_id TEXT NOT NULL, body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Nueva', created TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS inquiries_workspace ON inquiries(workspace_id,created);
        CREATE TABLE IF NOT EXISTS publication_reports (
            id TEXT PRIMARY KEY, publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
            reason TEXT NOT NULL, details TEXT NOT NULL, resolved INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS api_rate_limits (
            rate_key TEXT PRIMARY KEY, count INTEGER NOT NULL, reset_at INTEGER NOT NULL
        );
    ''')

def timestamp(): return datetime.now().isoformat(timespec='seconds')

def text(value, label, limit=120, required=False):
    if not isinstance(value,str) or len(value.strip())>limit or any(ord(c)<32 and c not in '\n\r\t' for c in value):
        raise ValueError('Revisá '+label)
    value=value.strip()
    if required and not value: raise ValueError('Completá '+label)
    return value

def phone(value):
    value=text(value,'el teléfono',40,True)
    if not re.fullmatch(r'[+\d ()-]+',value): raise ValueError('Ingresá un teléfono con código de país')
    digits=re.sub(r'\D','',value)
    if not 8<=len(digits)<=15: raise ValueError('Ingresá un teléfono con código de país')
    return digits

def number(value, label, low, high):
    if isinstance(value,bool): raise ValueError('Revisá '+label)
    try: result=float(value)
    except (TypeError,ValueError): raise ValueError('Revisá '+label)
    if not math.isfinite(result) or not low<=result<=high: raise ValueError('Revisá '+label)
    return result

def client_ip(handler):
    value=getattr(handler,'client_address',('127.0.0.1',0))[0]
    # In deployment the backend is reachable only through Caddy, which overwrites XFF.
    if os.environ.get('NEXO_DEPLOYMENT')=='1':
        forwarded=handler.headers.get('X-Forwarded-For','').split(',')[-1].strip()
        try: value=str(ipaddress.ip_address(forwarded))
        except ValueError: pass
    return value

def limited(conn, handler, scope, maximum, seconds=3600):
    key=hashlib.sha256((scope+'|'+client_ip(handler)).encode()).hexdigest()
    now=int(time.time());row=conn.execute('SELECT * FROM api_rate_limits WHERE rate_key=?',(key,)).fetchone()
    if row and row['reset_at']>now and row['count']>=maximum: return True
    count=row['count']+1 if row and row['reset_at']>now else 1
    reset=row['reset_at'] if row and row['reset_at']>now else now+seconds
    conn.execute('DELETE FROM api_rate_limits WHERE reset_at<=?',(now,))
    conn.execute('INSERT INTO api_rate_limits VALUES(?,?,?) ON CONFLICT(rate_key) DO UPDATE SET count=excluded.count,reset_at=excluded.reset_at',(key,count,reset))
    return False

def register(conn, data):
    if not isinstance(data,dict) or set(data)-{'name','username','password','email','phone','accountType','agencyName','website','acceptTerms'}:
        raise ValueError('Datos de registro inválidos')
    if data.get('website'): raise ValueError('No se pudo completar el registro')
    if data.get('acceptTerms') is not True: raise ValueError('Aceptá las condiciones de publicación')
    if data.get('accountType') not in ('independent','agency'): raise ValueError('Elegí tu tipo de cuenta')
    if not conn.execute("SELECT 1 FROM users WHERE platform_admin='1' AND active=1").fetchone():
        raise accounts.AccessError('El registro estará disponible cuando Nexo complete la configuración inicial.',503)
    name=text(data.get('name'),'tu nombre',120,True)
    email=text(data.get('email'),'el correo electrónico',254,True)
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise ValueError('Ingresá un correo válido')
    contact=phone(data.get('phone'))
    wid=str(uuid.uuid4());kind=data['accountType']
    company=text(data.get('agencyName',''),'el nombre de la inmobiliaria',120,kind=='agency') if kind=='agency' else name
    conn.execute('INSERT INTO workspaces VALUES(?,?,?,1,0,?)',(wid,company,kind,timestamp()))
    user=accounts.create_user(conn,data,'admin' if kind=='agency' else 'advisor',timestamp(),wid,kind)
    return accounts.update_profile(conn,user['id'],{'email':email,'phone':contact})

ACTIVE_SQL="""SELECT p.*, u.name AS publisher_name,u.title AS publisher_title,w.name AS company
    FROM publications p JOIN records r ON r.id=p.property_id
    JOIN users u ON u.id=p.publisher_id JOIN workspaces w ON w.id=p.workspace_id
    WHERE p.status='published' AND p.blocked=0 AND u.active=1 AND w.active=1
    AND json_extract(r.body,'$.status')='Disponible'"""

def active(conn, pid):
    row=conn.execute(ACTIVE_SQL+' AND p.id=?',(pid,)).fetchone()
    if not row: raise accounts.AccessError('La publicación no está disponible',404)
    return row

def public_listing(row):
    data=json.loads(row['body'])
    # Always build from safe fields, including when reading a previous schema.
    output={key:data.get(key) for key in ('title','zone','city','operation','type','price','currency','area','bedrooms','bathrooms','parking','description','features','latitude','longitude')}
    output.update(id=row['id'],locationPrecision='approximate',updatedAt=row['updated'])
    output['photos']=[f"/api/public/photos/{row['id']}/{fid}" for fid in data.get('photoIds',[])]
    output['publisher']={'id':row['publisher_id'],'name':row['publisher_name'],'title':row['publisher_title'],'company':row['company'],'phone':data['contactPhone']}
    return output

def search_parameters(query):
    get=lambda key:query.get(key,[''])[0]
    search=text(get('q'),'la búsqueda',120).casefold()
    currency=get('currency')
    if currency and currency not in ('USD','BOB'): raise ValueError('Moneda inválida')
    if (get('minPrice') or get('maxPrice')) and not currency: raise ValueError('Elegí la moneda para filtrar por precio')
    low=number(get('minPrice'),'el precio mínimo',0,1e12) if get('minPrice') else 0
    high=number(get('maxPrice'),'el precio máximo',0,1e12) if get('maxPrice') else 1e12
    if low>high: raise ValueError('El precio mínimo supera al máximo')
    rooms=number(get('bedrooms'),'los dormitorios',0,30) if get('bedrooms') else 0
    page=int(number(get('page') or 1,'la página',1,100000))
    limit=int(number(get('limit') or 48,'la cantidad',1,100))
    bounds=None
    if any(get(k) for k in ('south','north','west','east')):
        bounds=[number(get(k),'el área del mapa',-90 if k in ('south','north') else -180,90 if k in ('south','north') else 180) for k in ('south','north','west','east')]
        if bounds[0]>bounds[1] or bounds[2]>bounds[3]: raise ValueError('Área del mapa inválida')
    return search,currency,low,high,rooms,page,limit,bounds

def example_search(query):
    search,currency,low,high,rooms,page,limit,bounds=search_parameters(query)
    get=lambda key:query.get(key,[''])[0]
    matches=[]
    for house in portal_examples.listings():
        if search and search not in ' '.join(house[k] for k in ('title','zone','city')).casefold():continue
        if any(get(k) and get(k).casefold()!=house[k].casefold() for k in ('city','operation','type')):continue
        if currency and house['currency']!=currency:continue
        if get('publisher') and get('publisher')!=house['publisher']['id']:continue
        if not low<=house['price']<=high or house['bedrooms']<rooms:continue
        if bounds and not(bounds[0]<=house['latitude']<=bounds[1] and bounds[2]<=house['longitude']<=bounds[3]):continue
        matches.append(house)
    start=(page-1)*limit
    return {'listings':matches[start:start+limit],'total':len(matches),'page':page,'limit':limit,'exampleMode':True}

def public_search(conn, query):
    search,currency,low,high,rooms,page,limit,bounds=search_parameters(query)
    get=lambda key:query.get(key,[''])[0]
    conditions=[];values=[]
    if search:
        conditions.append("instr(json_extract(p.body,'$.searchText'),?)>0");values.append(search)
    for key in ('city','operation','type','currency'):
        value=currency if key=='currency' else get(key)
        if value:
            conditions.append(f"json_extract(p.body,'$.{key}')=? COLLATE NOCASE");values.append(value)
    if get('publisher'):conditions.append('p.publisher_id=?');values.append(get('publisher'))
    conditions.extend(["json_extract(p.body,'$.price') BETWEEN ? AND ?","json_extract(p.body,'$.bedrooms')>=?"])
    values.extend([low,high,rooms])
    if bounds:
        conditions.extend(["json_extract(p.body,'$.latitude') BETWEEN ? AND ?","json_extract(p.body,'$.longitude') BETWEEN ? AND ?"]);values.extend(bounds)
    sql=ACTIVE_SQL+' AND '+' AND '.join(conditions)
    total=conn.execute('SELECT count(*) '+sql[sql.index('FROM publications'):],values).fetchone()[0]
    rows=conn.execute(sql+' ORDER BY p.updated DESC,p.id LIMIT ? OFFSET ?',(*values,limit,(page-1)*limit)).fetchall()
    return {'listings':[public_listing(row) for row in rows],'total':total,'page':page,'limit':limit}

def own_publications(conn, user):
    rows=conn.execute('SELECT * FROM publications WHERE workspace_id=? ORDER BY updated DESC',(user['workspaceId'],)).fetchall()
    return [dict(row,body=json.loads(row['body'])) for row in rows if user['role']=='admin' or row['publisher_id']==user['id']]

def save_publication(handler, conn, data):
    user=handler.current_user;accounts.require_property_manager(user)
    allowed={'propertyId','latitude','longitude','city','contactPhone','photoIds','status','confirmPublication'}
    if not isinstance(data,dict) or set(data)-allowed: raise ValueError('Datos de publicación inválidos')
    prop=handler.get_record(conn,data.get('propertyId'),'properties')
    if prop.get('demo'): raise ValueError('Los inmuebles de demostración no se publican')
    status=data.get('status','draft')
    if status not in ('draft','published','paused'): raise ValueError('Estado de publicación inválido')
    if status=='published' and (data.get('confirmPublication') is not True or prop.get('status')!='Disponible'):
        raise ValueError('Confirmá la publicación de un inmueble disponible')
    lat=number(data.get('latitude'),'la ubicación (latitud)',-90,90)
    lon=number(data.get('longitude'),'la ubicación (longitud)',-180,180)
    city=text(data.get('city'),'la ciudad',100,True)
    contact=phone(data.get('contactPhone'))
    photos=data.get('photoIds',[])
    if not isinstance(photos,list) or len(photos)>10 or any(not isinstance(v,str) for v in photos): raise ValueError('Elegí hasta 10 fotos del inmueble')
    photos=list(dict.fromkeys(photos))
    if status=='published' and not photos: raise ValueError('Agregá al menos una foto del inmueble antes de publicarlo')
    for fid in photos:
        f=conn.execute('SELECT * FROM files WHERE id=? AND record_id=?',(fid,prop['id'])).fetchone()
        if not f or f['mime'] not in ('image/jpeg','image/png','image/webp') or f['size']>8*1024*1024: raise ValueError('Usá fotos JPG, PNG o WebP del inmueble, de hasta 8 MB cada una')
    old=conn.execute('SELECT * FROM publications WHERE property_id=?',(prop['id'],)).fetchone()
    if old and user['role']!='admin' and old['publisher_id']!=user['id']: raise accounts.AccessError('Esta publicación pertenece a otro asesor')
    body={k:text(str(prop.get(k) or ''),k,6000 if k=='description' else 180) for k in ('title','zone','operation','type','currency','description')}
    for k in ('price','area','bedrooms','bathrooms','parking'):body[k]=number(prop.get(k) or 0,k,0,1e12)
    if body['currency'] not in ('USD','BOB'):raise ValueError('Revisá la moneda del inmueble')
    body.update(city=city,latitude=round(lat,2),longitude=round(lon,2),contactPhone=contact,photoIds=photos,features=[text(v,'las características',200) for v in prop.get('features',[])][:100])
    body['searchText']=' '.join(body[k] for k in ('title','zone','city')).casefold()
    pid=old['id'] if old else str(uuid.uuid4());now=timestamp()
    conn.execute('''INSERT INTO publications(id,property_id,workspace_id,publisher_id,status,body,created,updated) VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET status=excluded.status,body=excluded.body,updated=excluded.updated''',(pid,prop['id'],user['workspaceId'],user['id'],status,json.dumps(body,ensure_ascii=False),now,now))
    # Exact coordinates stay exclusively on the private CRM record.
    import server
    prop.update(latitude=lat,longitude=lon,city=city);server.put(conn,'properties',prop)
    return {'id':pid,'status':status,'blocked':bool(old and old['blocked']),'url':'/inmueble/'+pid}

def route(h, conn, method, path, query):
    """Return True after replying; never bypass the main handler's host/origin checks."""
    def reply(status,data,mime='application/json; charset=utf-8'):
        h.reply(status,data,mime);return True
    if path=='/api/public/examples' and method=='GET':return reply(200,example_search(query))
    example_match=re.fullmatch(r'/api/public/examples/([\w-]+)(?:/(inquiries|report))?',path)
    if example_match:
        house=portal_examples.get(example_match[1])
        if not house:return reply(404,{'error':'No encontramos esta casa de ejemplo'})
        if method!='GET' or example_match[2]:return reply(405,{'error':'Es una casa ficticia de demostración; no admite consultas ni reservas.'})
        return reply(200,house)
    if path=='/api/public/config' and method=='GET':
        url=os.environ.get('NEXO_MAP_TILE_URL') or 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
        if urlsplit(url).scheme!='https' or not all(v in url for v in ('{z}','{x}','{y}')): raise ValueError('La configuración del proveedor de mapas es inválida')
        return reply(200,{'tileUrl':url,'tileProvider':(os.environ.get('NEXO_MAP_PROVIDER') or 'OpenStreetMap')[:80],'center':[-17.3895,-66.1568],'zoom':13})
    if path=='/api/public/register' and method=='POST':
        if limited(conn,h,'register',5): return reply(429,{'error':'Demasiados registros desde esta conexión. Probá más tarde.'})
        # Keep counters even when validation fails.
        try:
            conn.execute('SAVEPOINT registration')
            user=register(conn,h.body(limit=8192))
            conn.execute('RELEASE registration')
        except (ValueError,accounts.AccessError) as error:
            conn.execute('ROLLBACK TO registration');conn.execute('RELEASE registration')
            return reply(getattr(error,'status',400),{'error':str(error)})
        token=accounts.session(conn,user['id'])
        h.response_headers.append(('Set-Cookie',accounts.cookie(token,os.environ.get('NEXO_HTTPS')=='1')))
        return reply(201,{'user':user})
    if path=='/api/public/listings' and method=='GET': return reply(200,public_search(conn,query))
    match=re.fullmatch(r'/api/public/listings/([\w-]+)(?:/(inquiries|report))?',path)
    if match:
        pid,action=match.groups();row=active(conn,pid)
        if not action and method=='GET': return reply(200,public_listing(row))
        if action in ('inquiries','report') and method=='POST':
            if limited(conn,h,action,10): return reply(429,{'error':'Alcanzaste el límite de solicitudes. Probá más tarde.'})
            data=h.body(limit=8192)
            if not isinstance(data,dict) or data.get('website'): return reply(400,{'error':'Solicitud inválida'})
            try:
                if action=='inquiries':
                    name=text(data.get('name'),'tu nombre',120,True);contact=phone(data.get('phone'))
                    message=text(data.get('message',''),'el mensaje',2000)
                    date=text(data.get('preferredDate',''),'la fecha solicitada',16)
                    if date:
                        try:datetime.fromisoformat(date)
                        except ValueError:raise ValueError('Revisá la fecha solicitada')
                    if data.get('consent') is not True: raise ValueError('Autorizá compartir tus datos con el responsable del inmueble')
                    body={'name':name,'phone':contact,'message':message,'preferredDate':date,'propertyTitle':json.loads(row['body'])['title']}
                    conn.execute('INSERT INTO inquiries(id,publication_id,workspace_id,publisher_id,body,status,created) VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),pid,row['workspace_id'],row['publisher_id'],json.dumps(body,ensure_ascii=False),'Nueva',timestamp()))
                else:
                    reason=data.get('reason');details=text(data.get('details',''),'el detalle',1000)
                    if reason not in ('Información incorrecta','Posible fraude','Ya no está disponible','Otro'): raise ValueError('Elegí un motivo')
                    conn.execute('INSERT INTO publication_reports VALUES(?,?,?,?,0,?)',(str(uuid.uuid4()),pid,reason,details,timestamp()))
            except ValueError as error:return reply(400,{'error':str(error)})
            return reply(201,{'ok':True,'message':'Solicitud enviada. El asesor debe confirmar la disponibilidad y el horario.' if action=='inquiries' else 'Reporte recibido.'})
    match=re.fullmatch(r'/api/public/photos/([\w-]+)/([\w-]+)',path)
    if match and method=='GET':
        pid,fid=match.groups();row=active(conn,pid)
        if fid not in json.loads(row['body']).get('photoIds',[]): raise accounts.AccessError('Foto no encontrada',404)
        f=conn.execute('SELECT * FROM files WHERE id=? AND record_id=?',(fid,row['property_id'])).fetchone()
        if not f or f['mime'] not in ('image/jpeg','image/png','image/webp'): raise accounts.AccessError('Foto no encontrada',404)
        import server
        return reply(200,(server.UPLOADS/f['storage']).read_bytes(),f['mime'])
    # All other routes below require a session.
    if not path.startswith(('/api/publications','/api/inquiries','/api/platform','/api/workspace')):return False
    user=h.current_user
    if not user:return reply(401,{'error':'Iniciá sesión para abrir tu espacio.'})
    if path=='/api/workspace' and method=='PATCH':
        accounts.require_admin(user);data=h.body(limit=4096)
        if not isinstance(data,dict) or set(data)!={'name'}: raise ValueError('Solo podés modificar el nombre del espacio')
        name=text(data['name'],'el nombre del espacio',120,True)
        conn.execute('UPDATE workspaces SET name=? WHERE id=?',(name,user['workspaceId']))
        return reply(200,{'name':name})
    if path=='/api/publications' and method=='GET':
        accounts.require_property_manager(user)
        return reply(200,{'publications':own_publications(conn,user)})
    if path=='/api/publications' and method=='POST':return reply(200,save_publication(h,conn,h.body(limit=16384)))
    match=re.fullmatch(r'/api/publications/([\w-]+)',path)
    if match and method=='PATCH':
        accounts.require_property_manager(user);data=h.body(limit=1024)
        row=conn.execute('SELECT * FROM publications WHERE id=? AND workspace_id=?',(match[1],user['workspaceId'])).fetchone()
        if not row or (user['role']!='admin' and row['publisher_id']!=user['id']):raise accounts.AccessError('Publicación no encontrada',404)
        if not isinstance(data,dict) or data!={'status':'paused'}: raise ValueError('Para publicar o actualizar usá el formulario de publicación')
        conn.execute("UPDATE publications SET status='paused',updated=? WHERE id=?",(timestamp(),row['id']))
        return reply(200,{'ok':True})
    if path=='/api/inquiries' and method=='GET':
        rows=conn.execute('SELECT * FROM inquiries WHERE workspace_id=? ORDER BY created DESC',(user['workspaceId'],)).fetchall()
        return reply(200,{'inquiries':[dict(r,body=json.loads(r['body'])) for r in rows if user['role']=='admin' or r['publisher_id']==user['id']]})
    match=re.fullmatch(r'/api/inquiries/([\w-]+)',path)
    if match and method=='PATCH':
        row=conn.execute('SELECT * FROM inquiries WHERE id=? AND workspace_id=?',(match[1],user['workspaceId'])).fetchone()
        if not row or (user['role']!='admin' and row['publisher_id']!=user['id']):raise accounts.AccessError('Solicitud no encontrada',404)
        data=h.body(limit=1024)
        if not isinstance(data,dict) or set(data)!={'status'} or data['status'] not in ('Nueva','Contactada','Archivada'):raise ValueError('Estado inválido')
        conn.execute('UPDATE inquiries SET status=? WHERE id=?',(data['status'],row['id']))
        return reply(200,{'ok':True})
    if path.startswith('/api/platform'):
        accounts.require_platform(user)
        if path=='/api/platform' and method=='GET':
            return reply(200,{'workspaces':[dict(r) for r in conn.execute('SELECT * FROM workspaces ORDER BY created DESC')],
                'accounts':[dict(r) for r in conn.execute('SELECT id,name,username,workspace_id,role,active FROM users ORDER BY created DESC')],
                'publications':[{'id':r['id'],'status':r['status'],'blocked':bool(r['blocked']),'title':json.loads(r['body'])['title'],'workspaceId':r['workspace_id']} for r in conn.execute('SELECT * FROM publications ORDER BY updated DESC')],
                'reports':[dict(r) for r in conn.execute('SELECT * FROM publication_reports WHERE resolved=0 ORDER BY created DESC')]})
        match=re.fullmatch(r'/api/platform/(workspaces|publications|reports|accounts)/([\w-]+)',path)
        if match and method=='PATCH':
            kind,target=match.groups();data=h.body(limit=1024)
            if not isinstance(data,dict):raise ValueError('Datos inválidos')
            if kind=='workspaces':
                if target==accounts.LEGACY_WORKSPACE:raise ValueError('El espacio principal se conserva activo')
                if not data or set(data)-{'active','aiEnabled'} or any(not isinstance(v,bool) for v in data.values()):raise ValueError('Estado inválido')
                if 'active' in data:conn.execute('UPDATE workspaces SET active=? WHERE id=?',(int(data['active']),target))
                if 'aiEnabled' in data:conn.execute('UPDATE workspaces SET ai_enabled=? WHERE id=?',(int(data['aiEnabled']),target))
                if data.get('active') is False:conn.execute('DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE workspace_id=?)',(target,))
            elif kind=='publications':
                if set(data)!={'blocked'} or not isinstance(data['blocked'],bool):raise ValueError('Estado inválido')
                conn.execute('UPDATE publications SET blocked=? WHERE id=?',(int(data['blocked']),target))
            elif kind=='accounts':
                if set(data)!={'active'} or not isinstance(data['active'],bool):raise ValueError('Estado inválido')
                if conn.execute("SELECT 1 FROM users WHERE id=? AND platform_admin='1'",(target,)).fetchone():raise ValueError('La administración principal se conserva activa')
                conn.execute('UPDATE users SET active=? WHERE id=?',(int(data['active']),target))
                if not data['active']:conn.execute('DELETE FROM sessions WHERE user_id=?',(target,))
            else:
                if data!={'resolved':True}:raise ValueError('Estado inválido')
                conn.execute('UPDATE publication_reports SET resolved=1 WHERE id=?',(target,))
            return reply(200,{'ok':True})
    return reply(404,{'error':'Ruta no encontrada'})
