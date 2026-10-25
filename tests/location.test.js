const assert=require('node:assert/strict');
const {distanceMetres,matchRoute,Tracker,FRESH_MS}=require('../location.js');
const route={route:[[28,-15.6],[28,-15.59]],route_km:[0,1]};
let passed=0,trackers=[];
function test(name,fn){try{fn();passed++;console.log('ok',passed,'-',name);}finally{trackers.forEach(t=>t.stop());trackers=[];}}
function fixture({secure=true,apiExists=true,watchAction=null}={}){
 let success,failure,calls=0,clears=[],now=1000000,progress=0,updates=[];
 const api={watchPosition(ok,bad,options){calls++;success=ok;failure=bad;assert.equal(options.enableHighAccuracy,true);if(watchAction)watchAction(ok,bad);return 42;},clearWatch(id){clears.push(id);}};
 const t=new Tracker({data:route,secure:()=>secure,api:()=>apiExists?api:null,now:()=>now,getProgressKm:()=>progress,onChange:s=>{updates.push(s);if(s.usable)progress=s.match.km;}});trackers.push(t);
 return {t,get calls(){return calls},clears,updates,get progress(){return progress},advance(ms){now+=ms;t.refresh();},send({lat=28,lon=-15.595,accuracy=8,timestamp=now}={}){success({coords:{latitude:lat,longitude:lon,accuracy},timestamp});},error(code){failure({code});},get success(){return success}};
}
test('straight-line distance is geodesic and zero at the same point',()=>{assert.equal(distanceMetres({lat:28,lon:-15.6},{lat:28,lon:-15.6}),0);assert(Math.abs(distanceMetres({lat:0,lon:0},{lat:1,lon:0})-111195)<5);});
test('position projects onto the segment, not just the nearest vertex',()=>{let m=matchRoute(route,{lat:28,lon:-15.595,accuracy:5},0);assert(Math.abs(m.km-.5)<1e-7);assert(m.offsetM<.01);});
test('off-route displacement is preserved',()=>{let m=matchRoute(route,{lat:28.01,lon:-15.595,accuracy:5},0);assert(m.offsetM>1100);});
test('route crossings use a plausible existing progress hint',()=>{let d={route:[[28,-15.6],[28,-15.59],[28.01,-15.59],[28,-15.6],[28,-15.59]],route_km:[0,1,5,10,11]},fix={lat:28,lon:-15.595,accuracy:5};assert(Math.abs(matchRoute(d,fix,10.4).km-10.5)<.01);assert.equal(matchRoute(d,fix,5).ambiguous,true);});
test('no permission request occurs on page construction',()=>{let f=fixture();assert.equal(f.calls,0);assert.equal(f.t.enabled,false);});
test('explicit start registers one high accuracy watch',()=>{let f=fixture();f.t.start();f.t.start();assert.equal(f.calls,1);assert.equal(f.t.status,'waiting');});
test('good fixes update route progress',()=>{let f=fixture();f.t.start();f.send();assert.equal(f.t.status,'active');assert(Math.abs(f.progress-.5)<1e-7);});
test('weak accuracy does not update route progress',()=>{let f=fixture();f.t.start();f.send({accuracy:500});assert.equal(f.t.status,'weak');assert.equal(f.progress,0);});
test('off-route fixes keep actual coordinates and manual progress',()=>{let f=fixture();f.t.start();f.send({lat:28.01});assert.equal(f.t.status,'offroute');assert.equal(f.t.fix.lat,28.01);assert.equal(f.progress,0);});
test('cached stale fixes do not update progress',()=>{let f=fixture();f.t.start();f.send({timestamp:1000000-FRESH_MS-1});assert.equal(f.t.status,'stale');assert.equal(f.progress,0);});
test('fresh fixes become stale as time passes',()=>{let f=fixture();f.t.start();f.send();f.advance(FRESH_MS+1);assert.equal(f.t.snapshot().usable,false);assert.equal(f.t.status,'stale');});
test('invalid coordinates are not accepted',()=>{let f=fixture();f.t.start();f.send({lat:NaN});assert.equal(f.t.fix,null);assert.equal(f.progress,0);});
test('permission denial clears tracking and shows a recoverable error',()=>{let f=fixture();f.t.start();f.error(1);assert.equal(f.t.enabled,false);assert.equal(f.t.status,'error');assert.deepEqual(f.clears,[42]);assert.match(f.t.message,/permission/i);});
test('timeout keeps the watch available for a later successful fix',()=>{let f=fixture();f.t.start();f.error(3);assert.equal(f.t.enabled,true);f.send();assert.equal(f.t.status,'active');});
test('off stops the watch and ignores late callbacks',()=>{let f=fixture();f.t.start();let callback=f.success;f.t.stop();callback({coords:{latitude:28,longitude:-15.595,accuracy:5},timestamp:1000000});assert.equal(f.t.fix,null);assert.deepEqual(f.clears,[42]);assert.equal(f.progress,0);});
test('unsupported and insecure contexts do not request permission',()=>{let f=fixture({secure:false});f.t.start();assert.equal(f.calls,0);assert.match(f.t.message,/HTTPS/);let g=fixture({apiExists:false});g.t.start();assert.equal(g.calls,0);assert.match(g.t.message,/does not provide/);});
test('synchronous permission denial does not leak a watch',()=>{let f=fixture({watchAction:(ok,bad)=>bad({code:1})});f.t.start();assert.equal(f.t.enabled,false);assert.equal(f.t.watchId,null);assert.deepEqual(f.clears,[42]);});
test('shared subscribers receive updates and can unsubscribe independently',()=>{let f=fixture(),updates=0;const unsubscribe=f.t.subscribe(()=>updates++);f.t.start();f.send();assert.equal(updates,2);unsubscribe();f.send();assert.equal(updates,2);assert(f.progress>.4);assert.equal(f.t.listeners.size,0);});
console.log(`${passed} location tests passed`);
