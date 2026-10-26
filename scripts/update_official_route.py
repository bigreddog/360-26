"""Rebuild the official roadbook and compare it with the archived candidate.

Development dependencies: numpy, scipy, shapely>=2, pyproj. No browser runtime dependencies.
Uses the two root GPXs, reviewed PDF transcription, and versioned OSM approach/POI snapshots.
"""
from pathlib import Path
import copy,json,hashlib,html,xml.etree.ElementTree as ET
from bisect import bisect_right
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from pyproj import Geod,Transformer
from shapely import LineString,points,STRtree
R=Path(__file__).resolve().parents[1];GEOD=Geod(ellps='WGS84');PROJ=Transformer.from_crs(4326,32628,always_xy=True);NS='http://www.topografix.com/GPX/1/1';ET.register_namespace('',NS)
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n')
def axis(c):return np.r_[0,np.cumsum(GEOD.inv(c[:-1,0],c[:-1,1],c[1:,0],c[1:,1])[2])]
def geo(c):return np.array(PROJ.transform(c[:,0],c[:,1])).T

def merge_sources():
 # Merge waypoint elements before processing either geometry or checkpoint semantics.
 root=ET.parse(R/'360_2026_Total.gpx').getroot();track=root.findall('.//{*}trkseg');assert len(track)==1,'Disconnected input: do not flatten segments.'
 source_waypoints=ET.parse(R/'360_2026_Waypoints.gpx').getroot().findall('{*}wpt');assert len(source_waypoints)==29
 for w in source_waypoints:root.insert(0,copy.deepcopy(w))
 trkpts=root.findall('.//{*}trkpt');raw=np.array([[float(p.get('lon')),float(p.get('lat')),float(p.findtext('{*}ele'))] for p in trkpts]);assert np.isfinite(raw).all()
 keep=np.r_[True,np.any(raw[1:,:2]!=raw[:-1,:2],axis=1)];c=raw[keep];assert np.all(abs(c[:,0])<=180) and np.all(abs(c[:,1])<=90);dd=axis(c);assert np.diff(dd).max()<400,'Unverified track gap.'
 xy=geo(c);tree=cKDTree(xy);source=[]
 for w in root.findall('{*}wpt'):
  lon,lat=float(w.get('lon')),float(w.get('lat'));off,i=tree.query(PROJ.transform(lon,lat));source.append({'original_name':w.findtext('{*}name'),'lat':lat,'lon':lon,'km':float(dd[i]/1000),'track_index':int(i),'track_offset_m':round(float(off),1),'elevation_m':float(c[i,2])})
 source.sort(key=lambda w:w['km']);instructions=read(R/'data/official_waypoint_instructions.json')['waypoints'];assert len(instructions)==len(source)
 waypoints=[dict(w,name=instruction['title'],**instruction) for w,instruction in zip(source,instructions)]
 assert all(a['km']<b['km'] for a,b in zip(waypoints,waypoints[1:]))
 # Validate semantic correspondence independently of input file order.
 assert 'ARTENARA' in waypoints[3]['original_name'] and 'CERCADOS' in waypoints[9]['original_name'] and 'PARQUE' in waypoints[14]['original_name'] and 'SANTA LUC' in waypoints[19]['original_name'] and 'SANTA BR' in waypoints[25]['original_name']
 out=ET.Element('{'+NS+'}gpx',{'version':'1.1','creator':'Canarias 360 official route + organiser roadbook'})
 meta=ET.SubElement(out,'{'+NS+'}metadata');ET.SubElement(meta,'{'+NS+'}name').text='Canarias 360 2026 — official route and 29 roadbook waypoints'
 ET.SubElement(meta,'{'+NS+'}desc').text='Track geometry from 360_2026_Total.gpx; waypoints from 360_2026_Waypoints.gpx; numbered English instructions from the supplied official roadbook PDF. Consecutive zero-length duplicates removed; coordinates otherwise unchanged. Waypoint elevations sampled from the track, replacing source zero placeholders.'
 for w in waypoints:
  wp=ET.SubElement(out,'{'+NS+'}wpt',{'lat':str(w['lat']),'lon':str(w['lon'])});ET.SubElement(wp,'{'+NS+'}ele').text=str(w['elevation_m']);ET.SubElement(wp,'{'+NS+'}name').text=f"WP {w['number']:02d} · {w['title']}";ET.SubElement(wp,'{'+NS+'}desc').text=w['instruction']+' Original GPX label: '+w['original_name']
 trk=ET.SubElement(out,'{'+NS+'}trk');ET.SubElement(trk,'{'+NS+'}name').text='Canarias 360 2026 official';seg=ET.SubElement(trk,'{'+NS+'}trkseg')
 for lon,lat,z in c:
  p=ET.SubElement(seg,'{'+NS+'}trkpt',{'lat':str(lat),'lon':str(lon)});ET.SubElement(p,'{'+NS+'}ele').text=str(z)
 path=R/'routes/canarias360_official_2026.gpx';ET.ElementTree(out).write(path,encoding='utf-8',xml_declaration=True)
 return c,xy,dd,waypoints,{'original_points':len(raw),'canonical_points':len(c),'zero_length_duplicates_removed':int((~keep).sum()),'maximum_point_spacing_m':round(float(np.diff(dd).max()),3),'source_raw_3d_distance_km':float(np.hypot(np.diff(axis(raw)),np.diff(raw[:,2])).sum()/1000),'source_route_sha256':sha(R/'360_2026_Total.gpx'),'source_waypoints_sha256':sha(R/'360_2026_Waypoints.gpx'),'combined_gpx_sha256':sha(path)}

def simplified_indices(xy,tolerance):
 # RDP returns original vertices. Recover their chronological occurrences rather
 # than spatially snapping repeated coordinates to an earlier or later pass.
 occurrences={}
 for i,row in enumerate(xy):occurrences.setdefault(tuple(row),[]).append(i)
 result=[];previous=-1
 for row in LineString(xy).simplify(tolerance,preserve_topology=False).coords:
  choices=occurrences[tuple(row)];j=bisect_right(choices,previous);assert j<len(choices);previous=choices[j];result.append(previous)
 return np.unique(np.r_[0,result,len(xy)-1])

def terrain(c,dd):
 grid=np.r_[np.arange(0,dd[-1],25),dd[-1]];z=gaussian_filter1d(np.interp(grid,dd,c[:,2]),2,mode='nearest');delta=np.diff(z);up=np.r_[0,np.cumsum(np.maximum(delta,0))];down=np.r_[0,np.cumsum(np.maximum(-delta,0))];idx=np.unique(np.r_[np.arange(0,len(grid),4),len(grid)-1]);profile=[[float(grid[i]/1000),round(float(z[i]),2),round(float(up[i]),3),round(float(down[i]),3)] for i in idx];return grid,z,up,down,profile

def comparison(c,xy,dd,wps,up,down,profile,normalization):
 old=read(R/'data/candidate_roadbook_reference.json');oldxy=np.array(PROJ.transform(np.array(old['route'])[:,1],np.array(old['route'])[:,0])).T;oldaxis=np.array(old['route_km'])*1000
 def offsets(a,dist,b):
  samples=np.arange(0,dist[-1],25);p=points(np.interp(samples,dist,a[:,0]),np.interp(samples,dist,a[:,1]));chunks=[LineString(b[i:min(i+501,len(b))]) for i in range(0,len(b)-1,500)];_,d=STRtree(chunks).query_nearest(p,return_distance=True,all_matches=False);return {'sampling_m':25,'within_30m_percent':round(float(np.mean(d<=30)*100),2),'within_100m_percent':round(float(np.mean(d<=100)*100),2),'mean_offset_m':round(float(np.mean(d)),1),'median_offset_m':round(float(np.median(d)),1),'p95_offset_m':round(float(np.quantile(d,.95)),1)}
 record={'official':{'distance_km':float(dd[-1]/1000),'gain_m':round(float(up[-1])),'loss_m':round(float(down[-1]))},'candidate':{k:old[k] for k in ['distance_km','gain_m','loss_m']},'published_distance_km':254.11,'normalization':normalization,'official_to_candidate':offsets(xy,dd,oldxy),'candidate_to_official':offsets(oldxy,oldaxis,xy),'checkpoints':[{k:w[k] for k in ['number','title','km','type','cutoff','published_km'] if k in w} for w in wps if w['type'] in ['start','aid','control','lifebase','finish']],'method':'Horizontal WGS84 geodesic chainage; elevation sampled at 25m, Gaussian sigma 50m; overlap sampled by chainage every 25m and measured against full projected UTM28N polylines, separately in each direction. No distance rescaling or geographic snapping.','limitations':['Official PDF retains a 254.11km distance; the supplied official GPX measures shorter. Both are retained.','GPX metadata includes an old software timestamp; course authority follows the supplied 2026 filenames, organiser PDF and runner identification, not that timestamp.','The coastal alternative in rough seas is an instruction, not supplied alternate geometry.']}
 record['difference']={k:round(record['official'][k]-record['candidate'][k],3) for k in ['distance_km','gain_m','loss_m']};write(R/'docs/route-comparison.json',record)
 report=R/'docs/route-comparison.html';stats=''.join(f'<tr><th>{html.escape({'distance_km':'Horizontal distance (km)','gain_m':'Smoothed ascent (m)','loss_m':'Smoothed descent (m)'}[k])}</th><td>{record["candidate"][k]:,.2f}</td><td>{record["official"][k]:,.2f}</td><td>{record["difference"][k]:+,.2f}</td></tr>' for k in ['distance_km','gain_m','loss_m'])
 rows=''.join(f'<tr><td>{w["number"]}</td><td>{html.escape(w["title"])}</td><td>{w["type"]}</td><td>{w["km"]:.3f}</td><td>{w.get("published_km","—")}</td><td>{w.get("cutoff","—")}</td></tr>' for w in record['checkpoints'])
 i=simplified_indices(xy,2);official=[[float(c[j,1]),float(c[j,0])] for j in i]
 chart=lambda p,color:'<polyline fill="none" stroke="'+color+'" stroke-width="2" points="'+' '.join(f'{r[0]/max(old["distance_km"],dd[-1]/1000)*1000:.1f},{220-r[1]/1800*210:.1f}' for r in p)+'"/>'
 report.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Official course vs candidate · Canarias 360</title><style>'+ (R/'vendor/leaflet.css').read_text()+'body{font:18px/1.5 system-ui;color:#182f2a;background:#f3f0e8;margin:16px auto;max-width:1100px;padding:12px}h1{line-height:1.2}table{border-collapse:collapse;width:100%;font-size:16px}td,th{text-align:left;border-bottom:1px solid #aaa;padding:8px}section{background:#fffefa;padding:18px;border-radius:12px;margin:16px 0}.scroll{overflow:auto}#map{height:520px}.leaflet-control-layers{font-size:16px}.leaflet-control-layers label{display:flex;align-items:center;min-height:48px}.leaflet-control-layers input{width:22px;height:22px;margin-right:7px}button{font:inherit;padding:10px;margin:5px}svg{width:100%;height:240px}</style><h1>Official course vs candidate</h1><p><a href="../">Back to roadbook</a></p><section><strong>The supplied official GPX measures '+f'{dd[-1]/1000:.3f} km'+', compared with 254.11 km printed in the PDF.</strong><p>Distances are horizontal WGS84 geodesic chainage, measured from source coordinates and not stretched to match the publication. Raw elevation-adjusted 3D source length is approximately 253.956 km, so the distance convention matters; the organiser’s exact calculation is not supplied.</p><div class="scroll"><table><tr><th>Measure</th><th>Candidate</th><th>Official</th><th>Change</th></tr>'+stats+'</table></div><p>Official distance within 30 m of candidate: '+str(record['official_to_candidate']['within_30m_percent'])+'%. Candidate distance within 30 m of official: '+str(record['candidate_to_official']['within_30m_percent'])+'%.</p></section><section><h2>Course comparison</h2><p>Green: official. Orange: candidate. Select either or both layers. No online tiles required.</p><div id="map"></div></section><section><h2>Elevation vs actual distance</h2><svg viewBox="0 0 1000 240" role="img" aria-label="Green official and orange candidate elevation profiles on actual distance axes">'+chart(old['profile'],'#b76d25')+chart(profile,'#216b50')+'</svg><p>Same smoothing method for both. Peaks can shift because the route and distance axis differ.</p></section><section><h2>Official checkpoints and cut-offs</h2><p>Artenara is an aid station, without a sleeping lifebase. Controls are not confirmed food or sleep services. Cut-offs below are UTC / Canary time in November.</p><div class="scroll"><table><tr><th>WP</th><th>Place</th><th>Type</th><th>GPX km</th><th>Published km</th><th>Cut-off</th></tr>'+rows+'</table></div></section><section><h2>Method and provenance</h2><p>'+record['method']+'</p><p>Sources: <a href="../360_2026_Total.gpx">original track</a>, <a href="../360_2026_Waypoints.gpx">original waypoints</a>, <a href="evidence/ROAD_BOOK_2026_-ESP_ENG_FRA.pdf">official roadbook PDF</a>. <a href="route-comparison.json">Full comparison JSON</a>.</p><p>Only consecutive duplicate track positions are removed in the combined download; remaining coordinates and elevations are preserved. Waypoints retain their supplied locations; zero elevation placeholders are replaced with nearby track elevations. Preview/map simplification is for display only.</p></section><script>'+(R/'vendor/leaflet.js').read_text()+'</script><script>const map=L.map("map",{preferCanvas:true});const official=L.polyline('+json.dumps(official)+',{color:"#216b50",weight:4}).addTo(map),candidate=L.polyline('+json.dumps(old['route'])+',{color:"#b76d25",weight:3,opacity:.7}).addTo(map);map.fitBounds(official.getBounds().extend(candidate.getBounds()));L.control.layers(null,{"Official 2026":official,"Prior candidate":candidate},{collapsed:false}).addTo(map);</script></html>')
 return old,record

def resupply(c,xy,dd,old):
 graph_meta=read(R/'data/routing/source.json');assert graph_meta['graph_sha256']==sha(R/'data/routing/approach_graph.npz'),'Approach cache hash mismatch';assert graph_meta['route_source_sha256']==sha(R/'360_2026_Total.gpx'),'Approach cache was clipped to a different route: review or refresh graph coverage before processing';g=np.load(R/'data/routing/approach_graph.npz',allow_pickle=False);coords=g['coords'];node_ids=g['node_ids'];tree=cKDTree(xy);offset,near=tree.query(coords[:,3:5],workers=-1);src=np.flatnonzero(offset<=3);assert len(src)>100
 a,b=g['a'],g['b'];matrix=coo_matrix((np.r_[g['length'],g['length']],(np.r_[a,b],np.r_[b,a])),shape=(len(coords),len(coords))).tocsr();dist,pred,origin=dijkstra(matrix,directed=False,indices=src,min_only=True,return_predecessors=True,limit=1600);ntree=cKDTree(coords[:,3:5]);edge={tuple(sorted((int(u),int(v)))):int(w) for u,v,w in zip(a,b,g['way_ids'])};oldby={p['id']:p for p in old['pois']};excluded={p['id'] for p in old.get('source_decisions',[])};pois=[];seen=set();unmatched=0
 for name in ['owner_retail','retail','food','waterfuel']:
  for e in read(R/f'data/poi_sources/{name}.json')['elements']:
   ident=e['type']+'/'+str(e['id']);t=e.get('tags',{});loc=e.get('center',e)
   if ident in seen or ident in excluded or 'lat' not in loc:continue
   seen.add(ident);lat,lon=loc['lat'],loc['lon'];p=np.array(PROJ.transform(lon,lat));air,ti=tree.query(p)
   if air>650:continue
   snap,j=ntree.query(p);walk=dist[j]
   if not np.isfinite(walk) or walk>1500 or snap>100:unmatched+=1;continue
   source=int(origin[j]);path=[int(j)];cur=int(j)
   for _ in range(6000):
    if cur==source:break
    cur=int(pred[cur])
    if cur<0:break
    path.append(cur)
   if path[-1]!=source:continue
   path=path[::-1];detour=coords[path];rise=np.maximum(np.diff(detour[:,2]),0).sum();oneway=float(walk+snap)
   if oneway>1600:continue
   cat=t.get('shop') or t.get('amenity');name=t.get('name') or t.get('brand') or ('Mapped drinking-water point' if cat=='drinking_water' else 'Mapped '+cat.replace('_',' '));km=float(dd[near[source]]/1000)
   item={'id':ident,'name':name,'category':cat,'lat':lat,'lon':lon,'km':km,'anchor_index':int(near[source]),'air_m':round(float(air)),'walk_oneway_m':round(oneway),'network_oneway_m':round(float(walk)),'entrance_snap_m':round(float(snap)),'attachment_offset_m':round(float(offset[source]),2),'detour_minutes_oneway':round(oneway/50+float(rise)/10,1),'detour_coords':[[float(v[1]),float(v[0])] for v in detour],'detour_osm_nodes':[int(v) for v in node_ids[path]],'detour_osm_ways':[edge[tuple(sorted((u,v)))] for u,v in zip(path,path[1:])],'opening_hours':t.get('opening_hours',''),'phone':t.get('contact:phone',t.get('phone','')),'website':t.get('contact:website',t.get('website','')),'address':' '.join(str(t.get(k,'')) for k in ['addr:street','addr:housenumber','addr:city']).strip(),'hours_source':'https://www.openstreetmap.org/'+ident,'hours_evidence':'OSM weekly hours' if t.get('opening_hours') else 'Hours unknown','food':cat not in {'drinking_water','fuel'},'water':cat in {'drinking_water','supermarket','convenience'},'retail':bool(t.get('shop')) and cat!='fuel','operator_checked':e['type']=='owner'}
   if e['type']=='owner':item.update(hours_source=e['source_url'],hours_evidence='Operator schedule',hours_note=e.get('hours_note',''),published_hours_text=e.get('published_hours_text',''))
   previous=oldby.get(ident)
   if previous and previous.get('operator_checked'):
    for k in ['opening_hours','hours_source','hours_evidence','hours_note','operator_checked','phone','website']:
     if k in previous:item[k]=previous[k]
   pois.append(item)
 pois.sort(key=lambda p:(not p['operator_checked'],not bool(p['opening_hours']),p['walk_oneway_m']));dedup=[]
 for p in pois:
  if any((p['name'].lower()==q['name'].lower() or 'spar' in p['name'].lower() and 'spar' in q['name'].lower()) and np.hypot(*(np.array(PROJ.transform(p['lon'],p['lat']))-np.array(PROJ.transform(q['lon'],q['lat']))))<40 for q in dedup):continue
  dedup.append(p)
 dedup.sort(key=lambda p:(p['km'],p['walk_oneway_m']));return dedup,{'graph_attachment_tolerance_m':3,'mapped_attachment_nodes':len(src),'route_corridor_pois_excluded_for_no_verified_approach':unmatched,'method':'Shortest mapped pedestrian-network approach from OSM nodes within 3m of the official GPX; attachment and final entrance offsets are estimates, not drawn as invented connecting trails. Graph/places dated 24–25 October 2026. One shortest network attachment per venue; repeated-pass opportunities beyond that attachment are not exhaustively enumerated.'}

def main():
 c,xy,dd,wps,normalization=merge_sources();grid,z,up,down,profile=terrain(c,dd);old,report=comparison(c,xy,dd,wps,up,down,profile,normalization)
 print('Comparison completed:',json.dumps(report['official']), 'official within30m:',report['official_to_candidate']['within_30m_percent'],flush=True)
 pois,audit=resupply(c,xy,dd,old)
 before={p['id']:p for p in old['pois']};after={p['id']:p for p in pois};report['resupply_change']={'before':len(before),'after':len(after),'retained_venues':len(before.keys()&after.keys()),'new_venues':[{'id':p['id'],'name':p['name'],'km':p['km']} for p in pois if p['id'] not in before],'removed_venues':[{'id':p['id'],'name':p['name'],'previous_km':p['km']} for p in old['pois'] if p['id'] not in after]};write(R/'docs/route-comparison.json',report)
 # Anchor every organiser waypoint, retain nearby named candidate towns by geography,
 # and split any remaining overlong interval at an explicitly labelled route kilometre.
 anchors=[{'name':w['title'],'km':w['km'],'checkpoint':w['type'] in ['start','aid','control','lifebase','finish'],'waypoint':w['number']} for w in wps]
 oldxy=geo(np.array([[p[1],p[0],0] for p in old['route']]))
 for a in old['anchors'][1:-1]:
  if a['checkpoint']:continue
  x=np.interp(a['km'],old['route_km'],oldxy[:,0]);y=np.interp(a['km'],old['route_km'],oldxy[:,1]);off,j=cKDTree(xy).query([x,y]);km=float(dd[j]/1000)
  if off<=300 and min(abs(km-v['km']) for v in anchors)>2:anchors.append({'name':a['name'],'km':km,'checkpoint':False})
 anchors.sort(key=lambda a:a['km']);extra=[]
 for a,b in zip(anchors,anchors[1:]):
  n=int(np.ceil((b['km']-a['km'])/12))
  for j in range(1,n):
   km=a['km']+(b['km']-a['km'])*j/n;extra.append({'name':f'Route km {km:.1f}','km':km,'checkpoint':False})
 anchors=sorted(anchors+extra,key=lambda a:a['km']);checkpoints=[w for w in wps if w['type'] in ['start','aid','control','lifebase','finish']];sections=[]
 for i,(a,b) in enumerate(zip(anchors,anchors[1:])):
  start,end=a['km']*1000,b['km']*1000;j=int(np.searchsorted(dd,end));j=min(j,len(c)-1);sections.append({'id':i,'start_name':a['name'],'end_name':b['name'],'from_km':a['km'],'to_km':b['km'],'distance_km':b['km']-a['km'],'gain_m':round(float(np.interp(end,grid,up)-np.interp(start,grid,up))),'loss_m':round(float(np.interp(end,grid,down)-np.interp(start,grid,down))),'end_elevation_m':round(float(np.interp(end,grid,z))),'stage':next(k for k,cp in enumerate(checkpoints[1:],1) if b['km']<=cp['km']+1e-6),'checkpoint':b['checkpoint'],'waypoint':b.get('waypoint'),'lat':float(c[j,1]),'lon':float(c[j,0])})
 indices=simplified_indices(xy,.75);assert np.all(np.diff(dd[indices])>0)
 sources=old['sources']+[{'url':'https://github.com/bigreddog/360-26/blob/main/'+name,'retrieved_utc':'2026-10-26','sha256':sha(R/name),'type':'Official 2026 source supplied by runner'} for name in ['360_2026_Total.gpx','360_2026_Waypoints.gpx','docs/evidence/ROAD_BOOK_2026_-ESP_ENG_FRA.pdf']]
 data=dict(old,title='Canarias 360 · Official 2026 roadbook',based_on='Official 360_2026_Total.gpx combined with 360_2026_Waypoints.gpx and the supplied official 2026 roadbook PDF; imported 26 October 2026',route_status='official',gpx_file='routes/canarias360_official_2026.gpx',gpx_download_name='canarias360_official_2026.gpx',gpx_sha256=normalization['combined_gpx_sha256'],published_distance_km=254.11,distance_km=float(dd[-1]/1000),gain_m=round(float(up[-1])),loss_m=round(float(down[-1])),profile=profile,profile_method='Official GPX elevations resampled every 25m, Gaussian sigma 50m; positive/negative increments summed globally. Display profile retains common cumulative totals at ~100m spacing.',route=[[float(c[j,1]),float(c[j,0])] for j in indices],route_km=[float(dd[j]/1000) for j in indices],track_km=[round(float(d/1000),8) for d in dd],route_geometry_method='Main map/matching/weather polyline uses original vertices simplified within 0.75m for phone performance, retaining full official geodesic chainage. Full canonical GPX and track_km are used by Trail Vision.',sections=sections,anchors=anchors,checkpoints=checkpoints,waypoints=wps,pois=pois,sources=sources,normalization=normalization,resupply_audit=audit,route_comparison=report,researched='2026-10-26')
 data['notes']=[n for n in old['notes'] if 'intermediate closing' not in n]+['Official PDF cut-offs and all 29 numbered instructions are included. Artenara is an aid checkpoint, not a sleeping lifebase.','The supplied GPX measures 249.373km; the official PDF retains 254.11km. Course geometry is not stretched.','Resupply uses dated OSM/operator snapshots with approaches recalculated on the official course; unmapped final entrance offsets remain estimates.']
 write(R/'data/roadbook_data.json',data);write(R/'docs/official-route-validation.json',{'source':normalization,'course':report['official'],'waypoints':len(wps),'checkpoints':len(checkpoints),'lifebases':sum(w['type']=='lifebase' for w in wps),'sections':len(sections),'map_points':len(indices),'pois':len(pois),'resupply':audit,'instruction_source_sha256':sha(R/'docs/evidence/ROAD_BOOK_2026_-ESP_ENG_FRA.pdf')});print('Updated:',len(sections),'legs',len(checkpoints),'checkpoints',len(pois),'POIs',len(indices),'map points',flush=True)
if __name__=='__main__':main()
