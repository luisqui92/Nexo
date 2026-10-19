"""The example map is readable without accounts and cannot create real leads."""
import unittest
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
import test_flows as flows
from test_flows import request
import portal_examples
import server

class PublicExampleHouses(unittest.TestCase):
    def setUp(self):flows.VisitFlow.setUp(self)

    def snapshot(self):
        with server.db() as conn:
            return {table:[tuple(row) for row in conn.execute('SELECT * FROM '+table+' ORDER BY 1')] for table in ('users','records','files','publications','inquiries','publication_reports')}

    def test_six_houses_are_read_only_and_separate_from_actual_offers(self):
        before=self.snapshot()
        result=request('GET','/api/public/examples',cookie='')
        self.assertEqual(result['status'],200,result)
        self.assertEqual(result['data']['total'],6)
        self.assertTrue(result['data']['exampleMode'])
        houses=result['data']['listings']
        self.assertEqual(len({p['id'] for p in houses}),6)
        for house in houses:
            self.assertTrue(house['isExample'])
            self.assertEqual(house['type'],'Casa')
            self.assertEqual(house['locationPrecision'],'illustrative')
            self.assertNotIn('phone',house['publisher'])
            self.assertIn('ficticia',house['description'])
        self.assertEqual(request('GET','/api/public/listings',cookie='')['data']['total'],0)
        self.assertEqual(before,self.snapshot())

    def test_example_filters_prices_currency_city_bounds_and_pagination(self):
        scenarios=[({'operation':'Alquiler'},2),({'currency':'BOB'},2),({'q':'queru'},1),({'city':'Cochabamba'},4),({'bedrooms':4},2),({'type':'Departamento'},0),({'currency':'BOB','maxPrice':5000},1),({'south':-17.38,'north':-17.36,'west':-66.18,'east':-66.14},2)]
        for params,total in scenarios:
            result=request('GET','/api/public/examples?'+urlencode(params),cookie='');self.assertEqual(result['status'],200,result);self.assertEqual(result['data']['total'],total,params)
        self.assertEqual(request('GET','/api/public/examples?maxPrice=5000',cookie='')['status'],400)
        second=request('GET','/api/public/examples?page=2&limit=2',cookie='')['data']
        self.assertEqual(second['total'],6);self.assertEqual(len(second['listings']),2)
        self.assertEqual(second['listings'][0]['id'],'ejemplo-casa-sarco')

    def test_detail_and_illustrations_are_available_without_login(self):
        for house in portal_examples.listings():
            result=request('GET','/api/public/examples/'+house['id'],cookie='')
            self.assertEqual(result['status'],200,result)
            self.assertTrue(result['data']['isExample'])
            image=request('GET',house['photos'][0],cookie='')
            self.assertEqual(image['status'],200,image)
            self.assertIn('image/svg+xml',image['mime'])
            root=ET.fromstring(image['data'])
            self.assertNotIn('script',[node.tag.rsplit('}',1)[-1] for node in root.iter()])
            self.assertIn('SIN OFERTA REAL',image['data'].decode())
        self.assertEqual(request('GET','/api/public/examples/not-a-house',cookie='')['status'],404)

    def test_interior_gallery_and_spherical_panorama_are_public_demo_media(self):
        for house in portal_examples.listings():
            detail=request('GET','/api/public/examples/'+house['id'],cookie='')['data']
            self.assertEqual(len(detail['photos']),3)
            self.assertEqual(len(detail['photoLabels']),3)
            self.assertIn('IA',detail['mediaNotice'])
            self.assertEqual(detail['panorama']['projection'],'equirectangular')
            for url in detail['photos'][1:]+[detail['panorama']['url']]:
                result=request('GET',url,cookie='')
                self.assertEqual(result['status'],200,result)
                self.assertIn('image/webp',result['mime'])
                self.assertTrue(result['data'].startswith(b'RIFF'))
                self.assertEqual(result['data'][8:12],b'WEBP')
                self.assertLess(len(result['data']),350000)
        for path in ('/panorama.js','/portal.js'):
            self.assertEqual(request('GET',path,cookie='')['status'],200)

    def test_examples_cannot_receive_contacts_reports_or_be_saved_as_a_real_property(self):
        before=self.snapshot();pid='ejemplo-casa-cala-cala'
        for action in ('inquiries','report'):
            result=request('POST','/api/public/examples/'+pid+'/'+action,{'name':'Persona','phone':'59170000000','consent':True},cookie='')
            self.assertEqual(result['status'],405,result)
            self.assertEqual(request('POST','/api/public/listings/'+pid+'/'+action,{},cookie='')['status'],404)
        self.assertEqual(request('PATCH','/api/public/examples/'+pid,{'price':1})['status'],405)
        self.assertEqual(request('POST','/api/publications',{'propertyId':pid})['status'],400)
        self.assertEqual(before,self.snapshot())

    def test_real_private_properties_are_unchanged_when_examples_are_used(self):
        prop=request('POST','/api/properties',{'title':'Casa privada real','zone':'Centro','type':'Casa','operation':'Venta','status':'Disponible','price':210000,'currency':'USD'})
        self.assertEqual(prop['status'],201,prop)
        before=self.snapshot()
        request('GET','/api/public/examples',cookie='')
        request('GET','/api/public/examples/ejemplo-casa-sarco',cookie='')
        self.assertEqual(before,self.snapshot())
        self.assertEqual(request('GET','/api/public/listings',cookie='')['data']['total'],0)
        self.assertEqual(request('GET','/api/properties/'+prop['data']['id'])['data']['title'],'Casa privada real')

if __name__=='__main__':unittest.main()
