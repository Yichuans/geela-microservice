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

# parser for in-built validation
# parser = reqparse.RequestParser()

# ----- Utility  -----

# construct for get request PPAPI
def get_ppnet_url(wdpaid, token):
    url = "https://api.protectedplanet.net/v3/protected_areas/{}?token={}".format(wdpaid, token)
    return url

# load url and get wdpa data PPPI
def get_pa_geojson(url):

    # UNSAFE! https://stackoverflow.com/questions/27835619/urllib-and-ssl-certificate-verify-failed-error
    import ssl
    gcontext = ssl._create_unverified_context()

    try:
        response = urllib.urlopen(url, context=gcontext)
        geojson = json.loads(response.read())
        return geojson

    # AP: need to cath exact exception
    except:
        return


# wrapper if only geometry in geojson
def get_pa(wdpaid, token):
    url = get_ppnet_url(wdpaid, token)
    data = get_pa_geojson(url)
    
    if not data:
        return

    if 'protected_area' not in data.keys():
        raise Exception('no protected area in json')
        
    else:
        data = data['protected_area']
        
        if 'geojson' not in data.keys():
            raise Exception('no geometry in json')
        else:
            return data['geojson']

# ----- GEE functions -----
def get_modis_lc_by_year(year, classification='LC_Type1'):
    # returns a ee.image based on year and classification

    if year not in range(2000, 2017):
        raise Exception('Year must be in between 2000 and 2016')
        
    # internal ee.Image 'system:time_start' 'system:time_end' in miliseconds
    landcover_image = modis.filterDate(str(year)+'-01-01', str(year)+'-12-31').first()

    return landcover_image.select(classification)

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

@app.route('/pa/<wdpaid>')
def protected_area(wdpaid):
    geojson = get_pa(wdpaid, pptoken)
    if geojson:
        return str(landcover_composition(geojson, get_modis_lc_by_year(2015)))
    else:
        return "No PA found"

api.add_resource(Status, '/api/')
api.add_resource(Metadata, '/api/metadata')
api.add_resource(Statistics, '/api/stats')
# api.add_resource()

if __name__ == '__main__':
    app.run(debug=True)