"""Read-only illustrative houses for the public map; never insert CRM records."""
from copy import deepcopy

_HOUSES=(
    ('cala-cala','Casa con jardín en Cala Cala','Cala Cala','Cochabamba','Venta',145000,'USD',240,3,3,2,-17.370,-66.170,['Jardín','Patio','Sala de estar']),
    ('queru-queru','Casa familiar en Queru Queru','Queru Queru','Cochabamba','Venta',225000,'USD',350,5,4,3,-17.366,-66.147,['Terraza','Escritorio','Jardín']),
    ('sarco','Casa de dos plantas en Sarco','Sarco','Cochabamba','Venta',118000,'USD',190,3,2,1,-17.381,-66.187,['Patio','Balcón','Lavandería']),
    ('tiquipaya','Casa con patio en Tiquipaya','Tiquipaya','Tiquipaya','Venta',840000,'BOB',280,4,3,2,-17.337,-66.215,['Patio amplio','Parrillero','Jardín']),
    ('tupuraya','Casa en alquiler en Tupuraya','Tupuraya','Cochabamba','Alquiler',650,'USD',210,3,3,2,-17.373,-66.128,['Balcón','Terraza','Lavandería']),
    ('colcapirhua','Casa de una planta en Colcapirhua','Colcapirhua','Colcapirhua','Alquiler',3200,'BOB',150,2,2,1,-17.393,-66.239,['Patio','Cocina independiente','Jardín frontal']),
)

def listings():
    houses=[]
    for slug,title,zone,city,operation,price,currency,area,bedrooms,bathrooms,parking,lat,lon,features in _HOUSES:
        houses.append({'id':'ejemplo-casa-'+slug,'isExample':True,'title':title,'zone':zone,'city':city,
            'operation':operation,'type':'Casa','price':price,'currency':currency,'area':area,
            'bedrooms':bedrooms,'bathrooms':bathrooms,'parking':parking,'features':list(features),
            'description':'Casa ficticia para mostrar cómo funciona el mapa de Nexo. El precio, las características y el punto del mapa son ilustrativos. No corresponde a una oferta real.',
            'latitude':lat,'longitude':lon,'locationPrecision':'illustrative',
            'photos':['/examples/casa-'+slug+'.svg','/examples/interiores/dormitorio.webp','/examples/interiores/cocina.webp'],
            'photoLabels':['Fachada ilustrativa','Dormitorio ficticio','Cocina ficticia'],
            'panorama':{'url':'/examples/interiores/sala-360.webp','label':'Sala ficticia · Vista 360°','projection':'equirectangular'},
            'mediaNotice':'Ambientes generados con IA, compartidos entre las seis casas de ejemplo. No representan un inmueble real ni un recorrido completo de la casa.',
            'publisher':{'id':'nexo-ejemplos','name':'Nexo · Demostración','company':'Casa de ejemplo'}})
    return houses

def get(public_id):
    return next((deepcopy(house) for house in listings() if house['id']==public_id),None)
