import random
import requests
import ee
import urllib2 as urllib
import json

from flask import Flask, request, render_template, redirect, url_for
from flask_restful import Resource, Api, reqparse
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# from models import Record

from config import Config

from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired

app = Flask(__name__)

app.config.from_object(Config)
api = Api(app)
Bootstrap(app)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True)
    x = db.Column(db.Float)
    y = db.Column(db.Float)
    answer = db.Column(db.Integer)
    ref_modis_answer = db.Column(db.Integer)

    def __repr__(self):
        return '<record {}>: name {}, xy({}, {}), answer {}, ref_modis_answer {}'.format(
            self.id, self.username, self.x, self.y, self.answer, self.ref_modis_answer)

# PP token
pptoken = app.config['PPTOKEN']

# GEE service account
service_account = app.config['GEE_SERVICE']
credentials = ee.ServiceAccountCredentials(service_account, app.config['GEE_KEY'])
ee.Initialize(credentials)

# Data collection
modis = ee.ImageCollection('MODIS/006/MCD12Q1')

# discontinued data; don't use
# modis_meta = ee.ImageCollection('MODIS/051/MCD12Q1')

# create lookup for lc name, value and colour palette
metadata = modis.getInfo()
# metadata_vlookup = dict()

# # metadata changed in the data catalogue
# for lc_type in ['LC_Type_1', 'LC_Type_2', 'LC_Type_3', 'LC_Type_4', 'LC_Type_5']:
#     metadata_vlookup[lc_type] = {
#         'names':metadata['features'][0]['properties'][lc_type+'_class_names'],
#         'values':metadata['features'][0]['properties'][lc_type+'_class_values'],
#         'palette':metadata['features'][0]['properties'][lc_type+'_class_palette'],
#     }

# lc1_vlookup = metadata_vlookup['LC_Type_1']

meta_lc1 = {u'Color': u'05450a', u'Description': u'Evergreen Needleleaf Forests: dominated by evergreen conifer trees (canopy >2m). Tree cover >60%.', u'Value': u'1'}, {u'Color': u'086a10', u'Description': u'Evergreen Broadleaf Forests: dominated by evergreen broadleaf and palmate trees (canopy >2m). Tree cover >60%.', u'Value': u'2'}, {u'Color': u'54a708', u'Description': u'Deciduous Needleleaf Forests: dominated by deciduous needleleaf (larch) trees (canopy >2m). Tree cover >60%.', u'Value': u'3'}, {u'Color': u'78d203', u'Description': u'Deciduous Broadleaf Forests: dominated by deciduous broadleaf trees (canopy >2m). Tree cover >60%.', u'Value': u'4'}, {u'Color': u'009900', u'Description': u'Mixed Forests: dominated by neither deciduous nor evergreen (40-60% of each) tree type (canopy >2m). Tree cover >60%.', u'Value': u'5'}, {u'Color': u'c6b044', u'Description': u'Closed Shrublands: dominated by woody perennials (1-2m height) >60% cover.', u'Value': u'6'}, {u'Color': u'dcd159', u'Description': u'Open Shrublands: dominated by woody perennials (1-2m height) 10-60% cover.', u'Value': u'7'}, {u'Color': u'dade48', u'Description': u'Woody Savannas: tree cover 30-60% (canopy >2m).', u'Value': u'8'}, {u'Color': u'fbff13', u'Description': u'Savannas: tree cover 10-30% (canopy >2m).', u'Value': u'9'}, {u'Color': u'b6ff05', u'Description': u'Grasslands: dominated by herbaceous annuals (<2m).', u'Value': u'10'}, {u'Color': u'27ff87', u'Description': u'Permanent Wetlands: permanently inundated lands with 30-60% water cover and >10% vegetated cover.', u'Value': u'11'}, {u'Color': u'c24f44', u'Description': u'Croplands: at least 60% of area is cultivated cropland.', u'Value': u'12'}, {u'Color': u'a5a5a5', u'Description': u'Urban and Built-up Lands: at least 30% impervious surface area including building materials, asphalt and vehicles.', u'Value': u'13'}, {u'Color': u'ff6d4c', u'Description': u'Cropland/Natural Vegetation Mosaics: mosaics of small-scale cultivation 40-60% with natural tree, shrub, or herbaceous vegetation.', u'Value': u'14'}, {u'Color': u'69fff8', u'Description': u'Permanent Snow and Ice: at least 60% of area is covered by snow and ice for at least 10 months of the year.', u'Value': u'15'}, {u'Color': u'f9ffa4', u'Description': u'Barren: at least 60% of area is non-vegetated barren (sand, rock, soil) areas with less than 10% vegetation.', u'Value': u'16'}, {u'Color': u'1c0dff', u'Description': u'Water Bodies: at least 60% of area is covered by permanent water bodies.', u'Value': u'17'}

lc1_vlookup = {
    'names': [str(each['Description']) for each in meta_lc1],
    'values': [str(each['Value']) for each in meta_lc1],
    'palette': [str(each['Color']) for each in meta_lc1],
}

# default land cover; needs to be refactored if in the future other land cover types are required
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

    if year not in range(2002, 2018):
        raise Exception('Year must be in between 2000 and 2018')
        
    # internal ee.Image 'system:time_start' 'system:time_end' in miliseconds
    # all timestamps are '20xx-01-01'
    landcover_image = modis.filterDate(str(year)+'-01-01', str(year)+'-01-02').first()

    return landcover_image.select(classification)

def get_tile_layer_url(ee_image_object):
    map_id = ee.Image(ee_image_object).getMapId({'min':1.0, 'max': 17.0, 'palette':lc1_vlookup['palette']})
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
def _format_results(results):
    # use result['class'] values as index to find name

    stats = [{
    'lc_type': result['class'],
    'name': lc1_vlookup['names'][result['class']-1],
    'amount': result['sum'], 
    'palette': lc1_vlookup['palette'][result['class']-1]} for result in results]

    return stats

class Statistics(Resource):
    def post(self):
        geojson = request.get_json()

        if check_geojson(geojson):
            results = landcover_composition(geojson, get_modis_lc_by_year(2015))

            stats = _format_results(results)

            return stats

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

# == DEMO PAGES ==

@app.route('/demo')
def demo_index():
    return render_template('demo_index.html')

@app.route('/pa')
# === DEMO 1: land cover from all PAs from PPNET ===
def get_pa_list():
    # get page
    page = request.args.get('page')

    if not page:
        page = 1
    
    else:
        page = int(page)
        
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
        stats = _format_results(results)

        # AP: geojson format not well formed
        return render_template('pa.html', stats=stats, pa_name=pa_name, url=url, geojson=json.dumps(geojson))


# DEMO 2: land cover from an uploaded geometry
def arbitary_geom():
    return ''

# === DEMO 3: land cover guess game
class YourName(FlaskForm):
    name = StringField('name', validators=[DataRequired()])

@app.route('/guess-game', methods=['GET','POST'])
def guess_game():
    form = YourName()
    # if request.method == 'POST' and form.validate_on_submit():
    # if request.method == 'POST' and form.validate():
    if request.method == 'POST':
        return redirect(url_for('random_guess', username=form.name.data))
        # return "HIthere"
    return render_template('guess_game.html', form=form)

@app.route('/random-guess', methods=['GET', 'POST'])
def random_guess():
    # get page number
    # page = request.args.get('page') or 1
    # page = int(page)

    # a post message
    if request.method == 'POST':
        # return str()
        username = request.values.get('username') or 'anonymous'
        x = request.form.get('x')
        y = request.form.get('y')
        answer = request.form.get('landcover') or -1 # if no data is given - it's wrong
        ref = request.form.get('ref')
        page = int(request.form.get('page'))

        record = Record(username=username, x=x, y=y, answer=answer, ref_modis_answer=ref)
        db.session.add(record)
        db.session.commit()

        page += 1

        if page > 10:
            # complete
            return redirect(url_for('index'))
    # get
    else:
        page = 1
    
    # if page > 10:
    #     return redirect(url_for('index'))

    # random geojson
    x, y = random_xy_generator()
    random_geojson = geojson_generator((x,y))

    # call api
    url = 'http://localhost:5000/api/stats'
    response = requests.post(url, json=random_geojson)
    stats = response.json()

    # options
    options = zip(lc1_vlookup['values'], lc1_vlookup['names'])

    # get user name
    username = request.args.get('username') or 'anonymous'

    # get ref data
    if not stats:
        # need to handle this? refresh?
        lc_type = 0

    else:
        # saving result
        max_amount = max([stat['amount'] for stat in stats])

        for stat in stats:
            if stat['amount'] == max_amount:
                lc_type = stat['lc_type']

    # renders
    return render_template('random.html', 
    geojson=json.dumps(random_geojson), 
    stats=stats, 
    options=options, 
    x=x,
    y=y,
    page=page, 
    username=username,
    ref=lc_type)

# this function currently generates (x,y) in England
def random_xy_generator():
    lats = [50.951356, 53.30052]
    lons = [-3.509831, 0.15538]

    return (random.uniform(*lats), random.uniform(*lons))

def geojson_generator(pt, offset=0.001):
    # offset 0.001 translate roughly to 100 m at equator - 200 m is roughly the resolution of modis
    lat, lon = pt
    poly = dict()
    poly['type'] = 'Feature'
    poly['geometry'] = {
        'type': 'Polygon',
        'coordinates': [
            [[lon-offset, lat-offset], [lon+offset, lat-offset], [lon+offset, lat+offset], [lon-offset, lat+offset], [lon-offset, lat-offset]]
        ]
    }
    poly['properties'] = {
        "fill-opacity": 0.7,
        "stroke-width": 0.05,
        "stroke": "#40541b",
        "fill": "#83ad35",
        "marker-color": "#2B3146"
    }

    # dictionary output, needs `json.dumps() to convert to string for viewing`
    return poly

# DEMO 4: land cover image for up uploaded geometry
def land_cover_image():
    return ''

api.add_resource(Status, '/api/')
api.add_resource(Metadata, '/api/metadata')
api.add_resource(Statistics, '/api/stats')
# api.add_resource()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')