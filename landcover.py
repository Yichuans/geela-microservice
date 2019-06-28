from flask import Flask, request, render_template
from flask_restful import Resource, Api, reqparse
from flask_bootstrap import Bootstrap
import ee
import urllib2 as urllib
import json
from config import pptoken

app = Flask(__name__)
api = Api(app)
Bootstrap(app)

# GEE service account
service_account = 'gee-landcover@prototype-landcover-gee.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, './gs_private_key.json')
ee.Initialize(credentials)

# Data collection
modis = ee.ImageCollection('MODIS/006/MCD12Q1')

# create lookup for lc name, value and colour palette
metadata = modis.getInfo()
metadata_vlookup = dict()

for lc_type in ['LC_Type1', 'LC_Type2', 'LC_Type3', 'LC_Type4', 'LC_Type5']:
    metadata_vlookup[lc_type] = {
        'names':metadata['features'][0]['properties'][lc_type+'_class_names'],
        'values':metadata['features'][0]['properties'][lc_type+'_class_values'],
        'palette':metadata['features'][0]['properties'][lc_type+'_class_palette'],
    }

lc1_vlookup = metadata_vlookup['LC_Type1']

# default land cover
LC_TYPE = 'LC_Type1'

# ----- Utility  -----
PPNET_API_URL = 'https://api.protectedplanet.net/v3/'

# construct for get request PPAPI
def ppapi_geom_url(wdpaid, token):
    url = PPNET_API_URL + "/protected_areas/{}?token={}".format(wdpaid, token)
    return url

def ppapi_pa_list_url(token, page=1, per_page=50):
    url = PPNET_API_URL + "/protected_areas?token={}&page={}&per_page={}".format(
        token, page, per_page
    )
    return url

# load url and get wdpa data PPPI
def get_ppapi_json(url):

    # UNSAFE! https://stackoverflow.com/questions/27835619/urllib-and-ssl-certificate-verify-failed-error
    import ssl
    gcontext = ssl._create_unverified_context()

    try:
        response = urllib.urlopen(url, context=gcontext)
        result_dict = json.loads(response.read())
        # result_dict as a python dictionary
        return result_dict

    # AP: need to cath exact exception
    except:
        return

# wrapper if only geometry in geojson
def get_pa_json(wdpaid, token):
    url = ppapi_geom_url(wdpaid, token)
    data = get_ppapi_json(url)
    
    if not data:
        return

    if 'protected_area' not in data.keys():
        raise Exception('no protected area in json')
        
    else:
        return data['protected_area']

# ----- GEE functions -----
def get_modis_lc_by_year(year, classification=LC_TYPE):
    # returns a ee.image based on year and classification

    if year not in range(2000, 2017):
        raise Exception('Year must be in between 2000 and 2016')
        
    # internal ee.Image 'system:time_start' 'system:time_end' in miliseconds
    landcover_image = modis.filterDate(str(year)+'-01-01', str(year)+'-12-31').first()

    return landcover_image.select(classification)

def get_tile_layer_url(ee_image_object):
    map_id = ee.Image(ee_image_object).getMapId()
    tile_url_template = "https://earthengine.googleapis.com/map/{mapid}/{{z}}/{{x}}/{{y}}?token={token}"
    return tile_url_template.format(**map_id)

def landcover_composition(geom, ee_landcover, scale=250):
    """<geojson>, <ee.Image>, <scale=250"""
    # `ee.Image`, `ee.Feature`, scale
    # compose a two band image 0: area 1: land cover classes
    # reduced based on the geometry

    ee_feature = ee.Feature(geom)
    landcover_composite = ee.Image.pixelArea().addBands(ee_landcover)
    
    # reduce group
    result = landcover_composite.reduceRegion(
    reducer = ee.Reducer.sum().group(
        groupField=1,
        groupName='class'
    ),
    geometry=ee_feature.geometry(),
    scale=scale,
    maxPixels=1e9
    ).getInfo()
    
    return result['groups']

# AP: check geojson is valid
def check_geojson(input_geojson):
    return True

# ----- API -----

class Statistics(Resource):
    def post(self):
        geojson = request.get_json()

        if check_geojson(geojson):
            return landcover_composition(geojson, get_modis_lc_by_year(2015))
        else:
            return {"error": "Bad geojson"}

class Metadata(Resource):
    def get(self):
        return modis.getInfo()

class Status(Resource):
    def get(self):
        if modis:
            return {'status': 'Okay'}
        else:
            return {'status': 'Error'}

# ----- Controller -----
@app.route('/')
def index():
    # return 'Welcome to the GEELA (Google Earth Engine Land cover API) microservice, under construction!'
    return render_template('index.html')

# == demo page ==
@app.route('/pa/<wdpaid>')
def protected_area(wdpaid):
    # web service to get PA json, including geometry
    data = get_pa_json(wdpaid, pptoken)
    if not data:
        return 'No PA can be found with WDPAID {}'.format(wdpaid)

    # get map tiles
    url = get_tile_layer_url(get_modis_lc_by_year(2015))

    # get name
    pa_name = data['name']

    # geometry
    if 'geojson' not in data.keys():
        raise Exception('no geometry in json')

    else:
        geojson = data['geojson']

        results = landcover_composition(geojson, get_modis_lc_by_year(2015))

        # use result['class'] values as index to find name
        lcs = [{'name': lc1_vlookup['names'][result['class']-1],
         'amount': result['sum'], 
         'palette': lc1_vlookup['palette'][result['class']-1]} for result in results]

        # AP: geojson format not well formed
        return render_template('pa.html', lcs=lcs, pa_name=pa_name, url=url, geojson=json.dumps(geojson))

@app.route('/pa')
# === DEMO 1: land cover from all PAs from PPNET ===
def get_pa_list():
    # get page
    page = int(request.args.get('page'))

    if not page:
        page = 1
    url = ppapi_pa_list_url(pptoken, page)

    next_page = page + 1
    last_page = page - 1

    # get list
    result = get_ppapi_json(url)

    # if exist 
    if result and 'protected_areas' in result.keys():
        return render_template('pa_list.html', pas=result['protected_areas'], 
        next_page=next_page, last_page=last_page)
    
    return None
    # return str(url)

def protected_area_index():
    return 'index page for protected areas'

# DEMO 2: land cover from an uploaded geometry
def arbitary_geom():
    return ''

# DEMO 3: land cover guess game
def guess_game():
    return ''

# DEMO 4: land cover image for up uploaded geometry
def land_cover_image():
    return ''

api.add_resource(Status, '/api/')
api.add_resource(Metadata, '/api/metadata')
api.add_resource(Statistics, '/api/stats')
# api.add_resource()

if __name__ == '__main__':
    app.run(debug=True)