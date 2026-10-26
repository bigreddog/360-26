"""Independent source/GPX/graph assertions for the published official course."""
from pathlib import Path
import json,hashlib,xml.etree.ElementTree as E
import numpy as np
from pyproj import Geod
from lxml import etree
R=Path(__file__).resolve().parents[1];d=json.loads((R/'data/roadbook_data.json').read_text());checks=[]
def check(name,value):
 assert value,name
 checks.append(name)
raw=E.parse(R/'360_2026_Total.gpx');original=np.array([[float(p.get('lon')),float(p.get('lat')),float(p.findtext('{*}ele'))] for p in raw.findall('.//{*}trkpt')]);keep=np.r_[True,np.any(original[1:,:2]!=original[:-1,:2],axis=1)]
path=R/d['gpx_file'];track=E.parse(path);pts=track.findall('.//{*}trkpt');actual=np.array([[float(p.get('lon')),float(p.get('lat')),float(p.findtext('{*}ele'))] for p in pts]);wps=track.findall('.//{*}wpt')
check('canonical GPX preserves every nonduplicate source coordinate and height',np.array_equal(actual,original[keep]))
check('exactly the reported zero-length duplicates are removed',len(original)-len(actual)==1116)
check('one continuous track and all twenty-nine waypoints',len(track.findall('.//{*}trkseg'))==1 and len(wps)==29)
schema=etree.XMLSchema(etree.parse(str(R/'vendor/gpx-1.1.xsd')));check('combined GPX validates against GPX 1.1 schema',schema.validate(etree.parse(str(path))))
check('canonical hash is the built data identity',hashlib.sha256(path.read_bytes()).hexdigest()==d['gpx_sha256'])
g=Geod(ellps='WGS84');steps=g.inv(actual[:-1,0],actual[:-1,1],actual[1:,0],actual[1:,1])[2];axis=np.r_[0,np.cumsum(steps)]/1000
check('full preview axis aligns independently with canonical GPX chainage',len(axis)==len(d['track_km']) and np.allclose(axis,d['track_km'],atol=1e-8))
check('official measured distance is not silently scaled to PDF target',abs(axis[-1]-249.37268507008)<1e-9 and d['published_distance_km']==254.11)
check('no hidden long source gaps',steps.max()<201 and np.all(steps>0))
check('display polyline chainage is ordered and shares full source endpoints',len(d['route'])==len(d['route_km']) and np.all(np.diff(d['route_km'])>0) and d['route_km'][0]==0 and abs(d['route_km'][-1]-axis[-1])<1e-8)
source_wps=E.parse(R/'360_2026_Waypoints.gpx').findall('.//{*}wpt');source_coords={(float(w.get('lat')),float(w.get('lon'))) for w in source_wps};published_coords={(w['lat'],w['lon']) for w in d['waypoints']}
check('source waypoint geography retained',source_coords==published_coords)
check('all PDF numbers, text and source pages are retained',[w['number'] for w in d['waypoints']]==list(range(1,30)) and all(w['instruction'] and 2<=w['page']<=5 for w in d['waypoints']))
check('all cut-offs are present and ordered',len([w for w in d['checkpoints'] if w.get('cutoff')])==9 and all(a['km']<b['km'] for a,b in zip(d['checkpoints'],d['checkpoints'][1:])))
artenara=next(w for w in d['checkpoints'] if w['name']=='Artenara');check('Artenara is an aid checkpoint without sleep',artenara['type']=='aid' and artenara['sleeping_lifebase'] is False and artenara['cutoff']=='2026-11-04T19:55:00Z')
check('only four lifebases',sum(w['type']=='lifebase' for w in d['checkpoints'])==4)
check('every leg has a consecutive index and matches its neighbours',all(s['id']==i for i,s in enumerate(d['sections'])) and all(a['to_km']==b['from_km'] for a,b in zip(d['sections'],d['sections'][1:])))
network=np.load(R/'data/routing/approach_graph.npz',allow_pickle=False);node_ids=network['node_ids'];edges={tuple(sorted((int(node_ids[a]),int(node_ids[b])))):int(w) for a,b,w in zip(network['a'],network['b'],network['way_ids'])}
for p in d['pois']:
 assert p['attachment_offset_m']<=3 and p['entrance_snap_m']<=100 and p['walk_oneway_m']<=1600
 assert len(p['detour_coords'])==len(p['detour_osm_nodes']) and len(p['detour_osm_ways'])==len(p['detour_osm_nodes'])-1
 for a,b,w in zip(p['detour_osm_nodes'],p['detour_osm_nodes'][1:],p['detour_osm_ways']):assert edges[tuple(sorted((a,b)))]==w
check('every resupply approach uses consecutive real graph edges with recorded offsets',True)
report={'passed':len(checks),'checks':checks};(R/'docs/official-data-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
