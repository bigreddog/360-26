(function(root){
'use strict';
const EARTH=6371008.8,RAD=Math.PI/180,FRESH_MS=120000;
function distanceMetres(a,b){const p=a.lat*RAD,q=b.lat*RAD,dp=q-p,dl=(b.lon-a.lon)*RAD;const h=Math.sin(dp/2)**2+Math.cos(p)*Math.cos(q)*Math.sin(dl/2)**2;return 2*EARTH*Math.asin(Math.sqrt(Math.min(1,h)));}
function matchRoute(data,fix,priorKm){
 const cos=Math.cos(fix.lat*RAD),candidates=[];let nearest=Infinity;
 for(let i=0;i<data.route.length-1;i++){
  const a=data.route[i],b=data.route[i+1],ax=(a[1]-fix.lon)*RAD*EARTH*cos,ay=(a[0]-fix.lat)*RAD*EARTH,bx=(b[1]-fix.lon)*RAD*EARTH*cos,by=(b[0]-fix.lat)*RAD*EARTH,dx=bx-ax,dy=by-ay,den=dx*dx+dy*dy,t=den?Math.max(0,Math.min(1,-(ax*dx+ay*dy)/den)):0;
  const offset=Math.hypot(ax+t*dx,ay+t*dy),km=data.route_km[i]+t*(data.route_km[i+1]-data.route_km[i]);
  candidates.push({km,offset,lat:a[0]+t*(b[0]-a[0]),lon:a[1]+t*(b[1]-a[1])});nearest=Math.min(nearest,offset);
 }
 const allowance=Math.max(10,Math.min(30,fix.accuracy||10));
 const near=candidates.filter(c=>c.offset<=nearest+allowance).sort((a,b)=>a.offset-b.offset);
 const spatial=near[0];let chosen=spatial,ambiguous=false;
 const range=Math.max(...near.map(c=>c.km))-Math.min(...near.map(c=>c.km));
 if(range>1){
  if(Number.isFinite(priorKm))chosen=near.reduce((a,b)=>Math.abs(a.km-priorKm)<=Math.abs(b.km-priorKm)?a:b);
  ambiguous=!Number.isFinite(priorKm)||Math.abs(chosen.km-priorKm)>1;
 }
 return {...chosen,offsetM:distanceMetres(fix,chosen),ambiguous,rangeKm:range};
}
class Tracker{
 constructor({data,onChange,getProgressKm,api=()=>globalThis.navigator?.geolocation,secure=()=>globalThis.isSecureContext,now=()=>Date.now()}){
  this.data=data;this.onChange=onChange;this.getProgressKm=getProgressKm;this.api=api;this.secure=secure;this.now=now;this.enabled=false;this.status='off';this.message='Location is off. Current km can be set manually.';this.fix=null;this.match=null;this.watchId=null;this.generation=0;this.timer=null;
 }
 snapshot(){return {enabled:this.enabled,status:this.status,message:this.message,fix:this.fix,match:this.match,usable:this.enabled&&this.status==='active'};}
 emit(){this.onChange(this.snapshot());}
 start(){
  if(this.enabled)return;const api=this.api();
  if(!this.secure()){this.status='error';this.message='Location needs HTTPS or localhost. Open the HTTPS app and try again.';this.emit();return;}
  if(!api?.watchPosition){this.status='error';this.message='This browser does not provide location. Set Current km manually.';this.emit();return;}
  this.enabled=true;this.status='waiting';this.message='Waiting for location permission and a GPS fix…';this.fix=null;this.match=null;const generation=++this.generation;this.emit();
  try{
   const id=api.watchPosition(p=>{if(this.enabled&&generation===this.generation)this.accept(p);},e=>{if(this.enabled&&generation===this.generation)this.fail(e);},{enableHighAccuracy:true,timeout:15000,maximumAge:10000});
   if(this.enabled&&generation===this.generation){this.watchId=id;this.timer=setInterval(()=>this.refresh(),15000);}else api.clearWatch(id);
  }catch(e){this.stop('Location could not start. Check browser permission and use HTTPS.','error');}
 }
 accept(position){
  const c=position?.coords;
  if(!c||!Number.isFinite(c.latitude)||!Number.isFinite(c.longitude)||Math.abs(c.latitude)>90||Math.abs(c.longitude)>180||!Number.isFinite(c.accuracy)||c.accuracy<0){this.status='waiting';this.message='No usable GPS fix yet. Current km is unchanged.';this.emit();return;}
  this.fix={lat:c.latitude,lon:c.longitude,accuracy:c.accuracy,timestamp:Number.isFinite(position.timestamp)?position.timestamp:this.now()};
  this.match=matchRoute(this.data,this.fix,this.getProgressKm());this.refresh(true);
 }
 refresh(force=false){
  if(!this.enabled||!this.fix)return;let status,message;const age=this.now()-this.fix.timestamp,m=this.match;
  if(age>FRESH_MS){status='stale';message='GPS fix is over 2 minutes old. Showing the last known position; progress is unchanged.';}
  else if(this.fix.accuracy>100){status='weak';message='GPS accuracy is too low to update route progress. Move to a clearer view of the sky.';}
  else if(m.offsetM>Math.min(250,Math.max(100,this.fix.accuracy*2))){status='offroute';message=`You are about ${m.offsetM>=1000?(m.offsetM/1000).toFixed(1)+' km':Math.round(m.offsetM)+' m'} from the track. Current km is unchanged.`;}
  else if(m.ambiguous){status='ambiguous';message='The track passes this area more than once. Set an approximate Current km to choose the right pass.';}
  else{status='active';message=`GPS linked · route km ${m.km.toFixed(2)} · accuracy ±${Math.round(this.fix.accuracy)} m`;}
  const changed=status!==this.status||message!==this.message;this.status=status;this.message=message;if(force||changed)this.emit();
 }
 rematch(){if(this.enabled&&this.fix){this.match=matchRoute(this.data,this.fix,this.getProgressKm());this.refresh(true);}}
 fail(error){
  if(error?.code===1){this.stop('Location permission was denied. Allow location for this site in Chrome to try again.','error');return;}
  this.status='waiting';this.message=error?.code===3?'GPS request timed out; still waiting for a new fix. You can switch location off and retry.':'Location is unavailable; check device Location settings. Current km is unchanged.';this.emit();
 }
 stop(message='Location is off. Using the last Current km.',status='off'){
  this.enabled=false;this.generation++;if(this.watchId!==null)this.api()?.clearWatch?.(this.watchId);this.watchId=null;if(this.timer!==null)clearInterval(this.timer);this.timer=null;this.fix=null;this.match=null;this.status=status;this.message=message;this.emit();
 }
}
const api={distanceMetres,matchRoute,Tracker,FRESH_MS};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.RoadbookLocation=api;
})(typeof globalThis!=='undefined'?globalThis:this);
