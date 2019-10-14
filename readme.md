# Land cover API

A proof-of-concept micro API, implemented with Python, Flask, and the Google Earth Engine for easily retrieving land cover information with a 'cookie-cutter', i.e. a spatially explicit geometry.

The idea is to try a different approach towards making knowledge product that is powerful, useful but at the same time scalable, less need for maintenance and can be re-purposed, built-upon and further integrated into other products. More specifically, this would allow: 1) easy engineering of products 2) shifts towards a valued added model, compared to the traditional data reselling model.

## Quick start docker

Create the docker image from the current folder

```bash
docker build -t lc:1.0 .
```

Mount the volume with source code, and run the container

```bash
docker run --name "lc" -it -p 5000:5000 -v ~/Documents/git/land-cover-micro-api:/app lc:1.0
```

You can then use

```bash
docker start lc
```

to resume your docker container.

## Quick start

It is currently a one file application.

Install libraries and run the Flask app.

```python
pip install -r requirements.txt
python landcover.py
```

Ask me for `config.py`, where the GEE service and its key `gs_private_key.json` (earth engine service account private key) as well as the protected planet api token live.

On my own computer, an existing conda environment `flask27` can be activated by

```bash
conda activate flask27
```

## done

- `GET /api/status` status of the API

- `POST /stats/` content-application geojson

- `GET /pa/{wdpaid}` stats of land

- dockerise environment

## to-do list

In no specific order

- check SSL when calling PPAPI

- geojson validation

- caching/avoid repeat expensive calls to GEE

- parser for arguments

- refractor to separate different logics

- view templates

- expose hard coded variables `year`, `classifcation` in the API

- test cases

- documentation

- demos
