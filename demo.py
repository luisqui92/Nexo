"""Optional, explicitly loaded fictional data for trying the workflow."""
from datetime import datetime, timedelta

def demo_records():
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    tomorrow = (now + timedelta(days=1)).strftime('%Y-%m-%d')
    clients = [
        {'id':'c-demo-1','name':'Lucía Mendoza','role':'Comprador','phone':'','email':'','intent':'Venta','budget':95000,'currency':'USD','zones':['Queru Queru','Cala Cala'],'propertyType':'Departamento','bedrooms':2,'needs':['Dos dormitorios y estacionamiento','Cerca de colegios'],'notes':'Primera vivienda. Prefiere visitar por la tarde.'},
        {'id':'c-demo-2','name':'Mateo Vargas','role':'Inquilino','phone':'','email':'','intent':'Alquiler','budget':450,'currency':'USD','zones':['Cala Cala'],'propertyType':'Departamento','bedrooms':2,'needs':['Luminoso','Estacionamiento'],'notes':'Busca mudarse el próximo mes.'},
        {'id':'c-demo-3','name':'Valeria Rojas','role':'Propietario','phone':'','email':'','intent':'Venta','budget':0,'currency':'USD','zones':[],'needs':[],'notes':'Propietaria del departamento de Queru Queru.'},
        {'id':'c-demo-4','name':'Diego Salinas','role':'Comprador','phone':'','email':'','intent':'Venta','budget':180000,'currency':'USD','zones':['Tiquipaya'],'propertyType':'Casa','bedrooms':3,'needs':['Jardín','Espacio para trabajar desde casa'],'notes':'Busca una casa para su familia.'}
    ]
    properties = [
        {'id':'p-demo-1','code':'INM-001','title':'Un nuevo comienzo en Queru Queru','type':'Departamento','operation':'Venta','price':89000,'currency':'USD','zone':'Queru Queru','address':'Cochabamba · dirección de ejemplo','area':112,'bedrooms':2,'bathrooms':2,'parking':1,'status':'Disponible','ownerId':'c-demo-3','description':'Departamento luminoso con balcón, cocina abierta y estacionamiento.','features':['Balcón','Ascensor','Estacionamiento'],'art':'apartment'},
        {'id':'p-demo-2','code':'INM-002','title':'Casa con jardín en Tiquipaya','type':'Casa','operation':'Venta','price':165000,'currency':'USD','zone':'Tiquipaya','address':'Cochabamba · dirección de ejemplo','area':240,'bedrooms':3,'bathrooms':3,'parking':2,'status':'Disponible','ownerId':None,'description':'Casa familiar con jardín, terraza y ambiente para oficina.','features':['Jardín','Terraza','Oficina'],'art':'house'},
        {'id':'p-demo-3','code':'INM-003','title':'Luz y espacio en Cala Cala','type':'Departamento','operation':'Alquiler','price':420,'currency':'USD','zone':'Cala Cala','address':'Cochabamba · dirección de ejemplo','area':95,'bedrooms':2,'bathrooms':2,'parking':1,'status':'Disponible','ownerId':None,'description':'Ambientes amplios, buena iluminación y parqueo cubierto.','features':['Estacionamiento','Ascensor'],'art':'interior'},
        {'id':'p-demo-4','code':'INM-004','title':'Tu próximo espacio de trabajo','type':'Oficina','operation':'Alquiler','price':600,'currency':'USD','zone':'Centro','address':'Cochabamba · dirección de ejemplo','area':78,'bedrooms':0,'bathrooms':1,'parking':0,'status':'Disponible','ownerId':None,'description':'Oficina para un equipo pequeño, cerca de servicios y transporte.','features':['Recepción','Seguridad'],'art':'office'}
    ]
    visits = [
        {'id':'v-demo-1','clientId':'c-demo-1','propertyId':'p-demo-1','advisor':'Equipo Nexo','date':today+'T10:30','status':'Confirmada','transcript':'Lucía busca un departamento con dos dormitorios y estacionamiento. Su presupuesto es hasta 95 mil dólares. Le gustó la ubicación y el balcón, pero quiere confirmar los gastos comunes. Acordamos enviar el detalle de expensas y coordinar una segunda visita mañana.','sheet':{'summary':'Lucía valoró la ubicación y el balcón. Quiere confirmar las expensas antes de una segunda visita.','needs':['Dos dormitorios y estacionamiento'],'budget':95000,'currency':'USD','zones':['Queru Queru'],'likes':['Ubicación','Balcón'],'objections':['Necesita confirmar los gastos comunes'],'questions':['¿Cuánto se paga de expensas?'],'interest':'Alto','offer':None,'agreements':['Enviar detalle de expensas'],'nextStep':'Coordinar segunda visita','followUp':tomorrow},'confirmedAt':now.isoformat()}
    ]
    operations = [
        {'id':'o-demo-1','clientId':'c-demo-1','propertyId':'p-demo-1','stage':'Visita','value':89000,'currency':'USD','notes':'Segunda visita pendiente; confirmar expensas.'},
        {'id':'o-demo-2','clientId':'c-demo-2','propertyId':'p-demo-3','stage':'Contacto','value':420,'currency':'USD','notes':'Enviar horarios disponibles.'},
        {'id':'o-demo-3','clientId':'c-demo-4','propertyId':'p-demo-2','stage':'Negociación','value':165000,'currency':'USD','notes':'Revisar propuesta con el propietario.'}
    ]
    events = [
        {'id':'e-demo-1','title':'Segunda visita · Lucía','clientId':'c-demo-1','propertyId':'p-demo-1','date':today+'T16:30','type':'Visita','status':'Pendiente','notes':'Confirmar gastos comunes.'},
        {'id':'e-demo-2','title':'Enviar opciones · Mateo','clientId':'c-demo-2','propertyId':'p-demo-3','date':tomorrow+'T09:00','type':'Seguimiento','status':'Pendiente','notes':'Preparar opciones de alquiler.'}
    ]
    return {'clients':clients,'properties':properties,'visits':visits,'operations':operations,'events':events}
