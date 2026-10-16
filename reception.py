"""Shared reservation logic for WhatsApp and Vapi. External services remain opt-in."""
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def functions():
    import server
    return server

def local_now(): return datetime.now(ZoneInfo(os.environ.get('NEXO_TIMEZONE','America/La_Paz'))).replace(tzinfo=None)
def available(conn, property_id=None):
    app=functions()
    if property_id:
        p=app.record(conn,property_id,'properties')
        if p.get('status')!='Disponible':return []
    events=app.list_records(conn,'events')
    current=local_now()
    options=[]
    start_hour=int(os.environ.get('BOOKING_START_HOUR','9'))
    end_hour=int(os.environ.get('BOOKING_END_HOUR','18'))
    for day in range(1,15):
        date=current+timedelta(days=day)
        if date.weekday()>4:continue
        slot=date.replace(hour=start_hour,minute=0,second=0,microsecond=0)
        while slot.hour<end_hour:
            end=slot+timedelta(minutes=45)
            if end.hour>end_hour or (end.hour==end_hour and end.minute>0):break
            blocked=False
            for event in events:
                if event.get('status')!='Pendiente':continue
                beginning=datetime.fromisoformat(event['date']).replace(tzinfo=None)
                if beginning<end and beginning+timedelta(minutes=45)>slot:blocked=True;break
            if not blocked:options.append(slot.isoformat(timespec='minutes'))
            if len(options)>=8:return options
            slot+=timedelta(minutes=45)
    return options

def book(conn,property_id,date,name,phone):
    app=functions();phone=re.sub(r'\D','',phone)
    if not 8<=len(phone)<=15 or len(name.strip())<2:raise ValueError('Hace falta nombre completo y teléfono internacional válido.')
    if date not in available(conn,property_id):raise ValueError('Ese horario ya no está disponible. Consultá otras opciones.')
    p=app.record(conn,property_id,'properties')
    clients=app.list_records(conn,'clients')
    c=next((c for c in clients if re.sub(r'\D','',c.get('phone',''))==phone),None)
    if not c:
        c={'id':str(uuid.uuid4()),'name':name.strip(),'phone':phone,'role':'Inquilino' if p['operation']=='Alquiler' else 'Comprador','intent':p['operation'],'currency':p['currency'],'needs':[],'zones':[],'createdAt':app.now()}
        app.validate(conn,'clients',c);app.put(conn,'clients',c)
    event={'id':str(uuid.uuid4()),'clientId':c['id'],'propertyId':property_id,'title':'Visita · '+c['name'],'date':date,'type':'Visita','status':'Pendiente','notes':'Reserva confirmada por recepción','createdAt':app.now()}
    app.validate(conn,'events',event);app.put(conn,'events',event)
    return event

def cancel(conn,event_id,phone):
    app=functions();event=app.record(conn,event_id,'events');c=app.record(conn,event.get('clientId'),'clients')
    if re.sub(r'\D','',c.get('phone',''))!=re.sub(r'\D','',phone):raise ValueError('La visita no corresponde a este contacto.')
    if event.get('status')!='Pendiente':raise ValueError('La visita ya no está pendiente.')
    event['status']='Cancelada';app.put(conn,'events',event)
    return event

def handle_voice(conn,tool,args):
    app=functions()
    if tool=='listar_inmuebles':
        ps=[p for p in app.list_records(conn,'properties') if p.get('status')=='Disponible']
        return json.dumps([{'propertyId':p['id'],'title':p['title'],'zone':p['zone'],'operation':p['operation'],'price':p['price'],'currency':p['currency']} for p in ps],ensure_ascii=False)
    if tool=='consultar_disponibilidad':return json.dumps(available(conn,args.get('propertyId')),ensure_ascii=False)
    if tool=='agendar_visita':
        event=book(conn,args.get('propertyId'),args.get('date'),str(args.get('name','')),str(args.get('phone','')))
        return 'Visita confirmada para '+event['date']+'.'
    if tool=='consultar_mis_visitas':
        phone=re.sub(r'\D','',args.get('phone',''))
        if not phone:raise ValueError('Indicá el teléfono de contacto.')
        ids={c['id'] for c in app.list_records(conn,'clients') if re.sub(r'\D','',c.get('phone',''))==phone}
        return json.dumps([{'eventId':e['id'],'date':e['date'],'title':e['title']} for e in app.list_records(conn,'events') if e.get('clientId') in ids and e.get('status')=='Pendiente'],ensure_ascii=False)
    if tool=='cancelar_visita':
        event=cancel(conn,args.get('eventId'),str(args.get('phone','')))
        return 'Visita del '+event['date']+' cancelada.'
    raise ValueError('Herramienta desconocida.')

def handle_whatsapp(conn,phone,text,message_id=''):
    app=functions();phone=re.sub(r'\D','',phone)
    if not 8<=len(phone)<=15:return None
    if message_id:
        mid='message-'+hashlib.sha256(message_id.encode()).hexdigest()
        if conn.execute('SELECT id FROM records WHERE id=?',(mid,)).fetchone():return None
        app.put(conn,'wa_seen',{'id':mid})
    sid='wa-'+hashlib.sha256(phone.encode()).hexdigest()
    try:session=app.record(conn,sid,'wa_session')
    except ValueError:session={'id':sid,'step':'start'}
    if session.get('updatedAt') and datetime.fromisoformat(session['updatedAt'])<datetime.now()-timedelta(minutes=15):session={'id':sid,'step':'start'}
    t=text.strip().lower()
    if t in ('inicio','reiniciar'):session={'id':sid,'step':'start'}
    if t=='cancelar':
        ids={c['id'] for c in app.list_records(conn,'clients') if re.sub(r'\D','',c.get('phone',''))==phone}
        events=sorted([e for e in app.list_records(conn,'events') if e.get('clientId') in ids and e.get('status')=='Pendiente'],key=lambda e:e['date'])
        if not events:return 'No encontré una visita pendiente a tu nombre. Escribí inicio para reservar una.'
        session={'id':sid,'step':'cancel','eventId':events[0]['id']};app.put(conn,'wa_session',session)
        return '¿Confirmás cancelar tu visita del '+events[0]['date'].replace('T',' a las ')+'? Respondé sí o no.'
    if session['step']=='cancel':
        if t in ('sí','si'):cancel(conn,session['eventId'],phone);reply='Tu visita quedó cancelada.'
        elif t=='no':reply='Conservamos tu visita.'
        else:return 'Respondé sí para cancelar o no para conservar tu visita.'
        app.put(conn,'wa_session',{'id':sid,'step':'start'});return reply
    if session['step']=='start':
        ps=[p for p in app.list_records(conn,'properties') if p.get('status')=='Disponible'][:8]
        if not ps:return 'Por ahora no hay inmuebles disponibles. Contactá al equipo para coordinar.'
        session.update(step='property',options=[p['id'] for p in ps]);app.put(conn,'wa_session',session)
        return '¡Hola! ¿Qué inmueble querés visitar? Respondé con su número:\n'+ '\n'.join(f"{i+1}. {p['title']} · {p['zone']}" for i,p in enumerate(ps))
    if session['step']=='property':
        if not t.isdigit() or not 1<=int(t)<=len(session['options']):return 'Elegí un número de la lista, o escribí inicio para volver a comenzar.'
        session['propertyId']=session['options'][int(t)-1];options=available(conn,session['propertyId'])[:5]
        if not options:return 'No hay horarios disponibles para ese inmueble. Escribí inicio para ver otras opciones.'
        session.update(step='slot',options=options);app.put(conn,'wa_session',session)
        return 'Elegí el horario de tu visita:\n'+'\n'.join(f'{i+1}. '+slot.replace('T',' a las ') for i,slot in enumerate(options))
    if session['step']=='slot':
        if not t.isdigit() or not 1<=int(t)<=len(session['options']):return 'Elegí uno de los números de horario.'
        session.update(step='name',date=session['options'][int(t)-1]);app.put(conn,'wa_session',session)
        return '¿Cuál es tu nombre completo?'
    if session['step']=='name':
        if len(text.strip())<2:return 'Necesito tu nombre para la visita.'
        session.update(step='confirm',name=text.strip()[:120]);app.put(conn,'wa_session',session)
        return 'Visita para '+session['name']+' el '+session['date'].replace('T',' a las ')+'. ¿Confirmás? Respondé sí o no.'
    if session['step']=='confirm':
        if t in ('sí','si'):
            try:event=book(conn,session['propertyId'],session['date'],session['name'],phone);reply='¡Listo! Tu visita quedó confirmada para '+event['date'].replace('T',' a las ')+'. Para cancelarla, escribí cancelar.'
            except ValueError as e:reply=str(e)+' Escribí inicio para elegir otro horario.'
        elif t=='no':reply='No reservamos la visita. Escribí inicio para ver otras opciones.'
        else:return 'Respondé sí para confirmar o no para volver a empezar.'
        app.put(conn,'wa_session',{'id':sid,'step':'start'});return reply
    return 'Escribí inicio para coordinar una visita.'
