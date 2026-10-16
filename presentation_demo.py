"""Create a fictional, isolated workspace for presentations. No real records."""
import json
import secrets
from datetime import datetime, timedelta

def prepare_demo(server):
    credentials_path=server.DATA/'accesos-demo.json'
    with server.LOCK,server.db() as conn:
        if server.accounts.has_users(conn):
            if not credentials_path.is_file():
                raise ValueError('Este espacio ya tiene cuentas. Conservá sus datos y usá sus accesos existentes.')
            return json.loads(credentials_path.read_text())
        if conn.execute('SELECT COUNT(*) FROM records').fetchone()[0]:
            raise ValueError('El espacio no está vacío. La preparación nunca reemplaza registros existentes.')
        accounts=[]
        for username,name,role in [('gerencia.demo','Gerencia · Demo','admin'),('ana.demo','Ana · Demo','advisor'),('bruno.demo','Bruno · Demo','advisor')]:
            password=secrets.token_urlsafe(12)
            data={'username':username,'name':name,'password':password}
            user=server.accounts.create_user(conn,data,role,server.now())
            accounts.append({**user,'password':password})
        admin,ana,bruno=accounts
        records=server.demo_records()
        owners={'c-demo-1':ana['id'],'c-demo-2':bruno['id'],'c-demo-3':ana['id'],'c-demo-4':bruno['id']}
        shared={'p-demo-1':[ana['id']],'p-demo-2':[bruno['id']],'p-demo-3':[ana['id'],bruno['id']],'p-demo-4':[bruno['id']]}
        for kind,rows in records.items():
            for obj in rows:
                obj.update(demo=True,createdById=admin['id'])
                if kind=='clients': obj['advisorId']=owners[obj['id']]
                elif kind=='properties': obj['advisorIds']=shared[obj['id']]
                else: obj['advisorId']=owners[obj['clientId']]
                if kind=='visits':
                    obj.update(advisor=ana['name'],recordedById=ana['id'],confirmedById=ana['id'])
                server.validate(conn,kind,obj)
                server.put(conn,kind,obj)
        # A second confirmed visit lets the audience compare separate portfolios.
        date=(datetime.now()-timedelta(days=1)).isoformat(timespec='minutes')
        text='Mateo busca un departamento de dos dormitorios y estacionamiento en Cala Cala. Su presupuesto es hasta 450 dólares al mes. Le gustó la luz natural. Necesita confirmar si se permiten mascotas. Acordamos consultar ese requisito y llamarlo mañana.'
        sheet=server.extract_visit(text)
        server.put(conn,'visits',{'id':'v-demo-2','demo':True,'createdById':bruno['id'],'recordedById':bruno['id'],'confirmedById':bruno['id'],'advisorId':bruno['id'],'advisor':bruno['name'],'clientId':'c-demo-2','propertyId':'p-demo-3','date':date,'status':'Confirmada','confirmedAt':date,'transcript':text,'sheet':sheet})
        server.put(conn,'visits',{'id':'v-demo-borrador','demo':True,'createdById':ana['id'],'recordedById':ana['id'],'advisorId':ana['id'],'advisor':ana['name'],'clientId':'c-demo-1','propertyId':'p-demo-1','date':server.now()[:16],'status':'Borrador','transcript':'','sheet':None})
        credentials={'createdAt':server.now(),'workspace':'Presentación — solo datos ficticios','accounts':accounts}
        temporary=credentials_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(credentials,ensure_ascii=False,indent=2))
        temporary.chmod(0o600)
        temporary.replace(credentials_path)
        return credentials
