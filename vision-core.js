/* Trail Vision geometry and orientation maths. Metres in local east/north/up. */
(function(root){
'use strict';
const RAD=Math.PI/180,DEG=180/Math.PI,R=6371008.8;
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
const wrap=n=>(n%360+360)%360;
const delta=(a,b)=>(a-b+540)%360-180;
const finite=n=>typeof n==='number'&&Number.isFinite(n);
function distance(a,b){const p=a.lat*RAD,q=b.lat*RAD,h=Math.sin((q-p)/2)**2+Math.cos(p)*Math.cos(q)*Math.sin((b.lon-a.lon)*RAD/2)**2;return 2*R*Math.asin(Math.sqrt(clamp(h,0,1)));}
function local(p,origin){return [(p.lon-origin.lon)*RAD*R*Math.cos(origin.lat*RAD),(p.lat-origin.lat)*RAD*R,(p.ele??0)-(origin.ele??0)];}
function prefs(p={}){return {lookAhead:[100,250,500,1000].includes(Number(p.lookAhead))?Number(p.lookAhead):500,exaggeration:[1,1.5,2,3].includes(Number(p.exaggeration))?Number(p.exaggeration):1,mode:['compass','manual','route'].includes(p.mode)?p.mode:'compass',manualHeading:finite(Number(p.manualHeading))?wrap(Number(p.manualHeading)):0};}
function makeRoute(rawSegments,axis){
 const points=[],segments=[];let s=0,gaps=0,axisIndex=0,current=null,previous=null;
 for(const raw of rawSegments){current=null;previous=null;
  for(const rawPoint of raw){const p={lat:Number(rawPoint.lat),lon:Number(rawPoint.lon),ele:rawPoint.ele===null||rawPoint.ele===undefined?null:Number(rawPoint.ele)};
   if(!finite(p.lat)||!finite(p.lon)||Math.abs(p.lat)>90||Math.abs(p.lon)>180){current=null;previous=null;gaps++;axisIndex++;continue;}
   const step=previous?distance(previous,p):0;
   // A sparse jump is unverified geometry. Do not interpolate a bridge across it.
   if(step>400){current=null;previous=null;gaps++;}
   if(!current){current={id:segments.length,start:points.length,startM:s,endM:s,end:points.length};segments.push(current);}
   if(previous)s+=step;
   if(axis&&finite(axis[axisIndex])&&(!points.length||axis[axisIndex]>=s-1))s=axis[axisIndex];
   p.s=s;p.segment=current.id;points.push(p);current.end=points.length-1;current.endM=s;previous=p;axisIndex++;
  }
 }
 return {points,segments,distance:s,gaps,valid:points.length>=2&&segments.some(g=>g.end>g.start)};
}
function parseGPX(xml,Parser=root.DOMParser){
 if(!Parser)throw Error('GPX parsing is unavailable in this browser.');
 const doc=new Parser().parseFromString(xml,'application/xml');if(doc.querySelector('parsererror')||doc.documentElement.localName!=='gpx')throw Error('This file is not valid GPX.');
 const read=e=>{const z=e.getElementsByTagNameNS('*','ele')[0]?.textContent.trim();return {lat:e.hasAttribute('lat')&&e.getAttribute('lat').trim()?Number(e.getAttribute('lat')):NaN,lon:e.hasAttribute('lon')&&e.getAttribute('lon').trim()?Number(e.getAttribute('lon')):NaN,ele:z?Number(z):null};};
 let segments=[...doc.getElementsByTagNameNS('*','trkseg')].map(s=>[...s.children].filter(p=>p.localName==='trkpt').map(read));
 if(!segments.length)segments=[...doc.getElementsByTagNameNS('*','rte')].map(s=>[...s.children].filter(p=>p.localName==='rtept').map(read));
 if(!segments.some(s=>s.length>=2))throw Error('This GPX has no usable track or route segments.');return segments;
}
function segmentAt(route,s,id){if(id!==undefined&&route.segments[id]&&s>=route.segments[id].startM-.001&&s<=route.segments[id].endM+.001)return route.segments[id];return route.segments.find(g=>s>=g.startM-.001&&s<=g.endM+.001)||route.segments.at(-1);}
function at(route,s,segmentId){
 const g=segmentAt(route,s,segmentId);if(!g)return null;s=clamp(s,g.startM,g.endM);let a=g.start,b=g.end;
 while(b-a>1){const m=(a+b)>>1;if(route.points[m].s<=s)a=m;else b=m;}
 const p=route.points[a],q=route.points[b],t=q.s>p.s?clamp((s-p.s)/(q.s-p.s),0,1):0;
 return {lat:p.lat+(q.lat-p.lat)*t,lon:p.lon+(q.lon-p.lon)*t,ele:finite(p.ele)&&finite(q.ele)?p.ele+(q.ele-p.ele)*t:null,s,segment:g.id,index:a,t};
}
function elevationStats(points){let ascent=0,descent=0;for(let i=1;i<points.length;i++){const d=points[i].ele-points[i-1].ele;if(d>0)ascent+=d;else descent-=d;}return {ascent,descent,net:points.length?points.at(-1).ele-points[0].ele:0};}
function significantChange(points){
 let start=null,end=null,sign=0;
 for(let i=0;i+6<points.length;i++){const d=points[i+6].s-points[i].s,z=points[i+6].ele-points[i].ele,k=d>=20&&Math.abs(z/d)>=.06?Math.sign(z):0;
  if(k&&(!sign||k===sign)){if(start===null){start=i;sign=k;}end=i+6;}
  else if(start!==null){if(points[end].s-points[start].s>=30&&Math.abs(points[end].ele-points[start].ele)>=3)break;start=null;end=null;sign=0;}
 }
 return start!==null&&points[end].s-points[start].s>=30?{kind:sign>0?'Climb':'Descent',inMetres:points[start].s-points[0].s,length:points[end].s-points[start].s,change:points[end].ele-points[start].ele}:null;
}
function windowRoute(route,start,length=500,segmentId){
 const g=segmentAt(route,start,segmentId);if(!g||g.end===g.start)return {points:[],local:[],available:0,elevationOK:false,warning:'No connected track segment at this position.'};
 start=clamp(start,g.startM,g.endM);const end=Math.min(g.endM,start+length),points=[];
 for(let s=start;s<end;s+=5)points.push(at(route,s,g.id));points.push(at(route,end,g.id));
 let elevationOK=points.every(p=>finite(p.ele)&&p.ele>=-500&&p.ele<=9000);
 if(elevationOK)for(let i=1;i<points.length;i++)if(Math.abs(points[i].ele-points[i-1].ele)>35&&points[i].s-points[i-1].s<=5)elevationOK=false;
 if(elevationOK){const original=points.map(p=>p.ele),weights=[1,2,3,2,1];for(let i=1;i<points.length-1;i++){let z=0,w=0;for(let j=-2;j<=2;j++){let k=clamp(i+j,0,points.length-1);z+=original[k]*weights[j+2];w+=weights[j+2];}points[i].ele=z/w;}}
 else points.forEach(p=>p.ele=0);
 const origin=points[0],stats=elevationStats(points),available=end-start;
 return {points,origin,local:points.map(p=>local(p,origin)),available,elevationOK,stats,change:elevationOK?significantChange(points):null,segment:g.id,ended:available<length-.1,warning:!elevationOK?'GPX elevation is missing or unreliable. Flat preview.':null};
}
function projectSegment(fix,a,b){const av=local(a,fix),bv=local(b,fix),dx=bv[0]-av[0],dy=bv[1]-av[1],den=dx*dx+dy*dy,t=den?clamp(-(av[0]*dx+av[1]*dy)/den,0,1):0;return {s:a.s+(b.s-a.s)*t,offsetM:Math.hypot(av[0]+dx*t,av[1]+dy*t),lat:a.lat+(b.lat-a.lat)*t,lon:a.lon+(b.lon-a.lon)*t,ele:finite(a.ele)&&finite(b.ele)?a.ele+(b.ele-a.ele)*t:null,segment:a.segment,t};}
function matchProgress(route,fix,previous,hint){
 if(!route?.valid)return {usable:false,status:'empty',message:'No usable GPX loaded.'};
 if(!fix||!finite(fix.lat)||!finite(fix.lon))return {usable:false,status:'waiting',message:'Waiting for a GPS fix.'};
 const candidates=[];for(const g of route.segments)for(let i=g.start;i<g.end;i++)candidates.push(projectSegment(fix,route.points[i],route.points[i+1]));
 const nearest=candidates.reduce((a,b)=>a.offsetM<=b.offsetM?a:b),accuracy=finite(fix.accuracy)?fix.accuracy:1000;
 if(accuracy>80)return {...nearest,usable:false,status:'weak',message:'GPS accuracy is too poor. Move to a clearer view of the sky.'};
 if(nearest.offsetM>clamp(accuracy*2,35,80))return {...nearest,usable:false,status:'offroute',message:`Off route by about ${Math.round(nearest.offsetM)} m. Preview stays at the last matched position.`};
 const allowance=clamp(accuracy*.75,5,18),near=candidates.filter(p=>p.offsetM<=nearest.offsetM+allowance);
 const prior=previous?.s??hint,dt=previous?Math.max(0,((fix.timestamp??0)-(previous.timestamp??0))/1000):0;
 const budget=previous?Math.max(35,dt*6+accuracy*2):150;
 const plausible=finite(prior)?near.filter(p=>Math.abs(p.s-prior)<=budget):[];
 let selected=nearest;
 if(plausible.length)selected=plausible.reduce((a,b)=>(a.offsetM+.2*Math.abs(a.s-prior))<=(b.offsetM+.2*Math.abs(b.s-prior))?a:b);
 const groups=[];for(const p of [...near].sort((a,b)=>a.s-b.s)){if(!groups.length||p.s-groups.at(-1).at(-1).s>40)groups.push([]);groups.at(-1).push(p);}
 if((previous&&!plausible.length)||(groups.length>1&&!plausible.length))return {...selected,usable:false,status:'ambiguous',message:'Several route passes are possible. Set an approximate route km in Settings to choose the right pass.'};
 return {...selected,usable:true,status:'active',timestamp:fix.timestamp,message:'GPS matched to the route.'};
}
function qmul(a,b){return [a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1],a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0],a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3],a[3]*b[3]-a[0]*b[0]-a[1]*b[1]-a[2]*b[2]];}
function qaxis(axis,angle){const h=angle*RAD/2,s=Math.sin(h);return [axis[0]*s,axis[1]*s,axis[2]*s,Math.cos(h)];}
function rotate(q,v){const r=qmul(qmul(q,[...v,0]),[-q[0],-q[1],-q[2],q[3]]);return r.slice(0,3);}
function slerp(a,b,t){let d=a.reduce((v,x,i)=>v+x*b[i],0);if(d<0){b=b.map(x=>-x);d=-d;}let u,v;if(d>.9995){u=1-t;v=t;}else{const angle=Math.acos(clamp(d,-1,1)),sin=Math.sin(angle);u=Math.sin((1-t)*angle)/sin;v=Math.sin(t*angle)/sin;}const q=a.map((x,i)=>u*x+v*b[i]),n=Math.hypot(...q);return q.map(x=>x/n);}
function qdistance(a,b){return 2*Math.acos(clamp(Math.abs(a.reduce((v,x,i)=>v+x*b[i],0)),0,1))*DEG;}
function poseFromQ(q){const forward=rotate(q,[0,0,-1]),right=rotate(q,[1,0,0]),up=rotate(q,[0,1,0]),flat=Math.hypot(forward[0],forward[1]);return {q,heading:wrap(Math.atan2(flat>.01?forward[0]:up[0],flat>.01?forward[1]:up[1])*DEG),pitch:Math.asin(clamp(forward[2],-1,1))*DEG,roll:Math.atan2(right[2],up[2])*DEG};}
function devicePose(event,screenAngle=0){
 if(!finite(event.beta)||!finite(event.gamma))return null;
 let alpha,reference,accuracy=null;
 if(finite(event.webkitCompassHeading)){alpha=wrap(360-event.webkitCompassHeading);reference='Magnetic north';accuracy=finite(event.webkitCompassAccuracy)?event.webkitCompassAccuracy:null;}
 else if(finite(event.alpha)&&(event.absolute===true||event.type==='deviceorientationabsolute')){alpha=event.alpha;reference='Device north · unverified reference';}
 else return null;
 // W3C intrinsic Z-X-Y rotation; camera looks out the BACK of the screen (-Z).
 const q=qmul(qmul(qmul(qaxis([0,0,1],alpha),qaxis([1,0,0],event.beta)),qaxis([0,1,0],event.gamma)),qaxis([0,0,1],screenAngle));
 return {...poseFromQ(q),reference,accuracy};
}
function basis(heading,pitch=0,roll=0){const h=heading*RAD,p=clamp(pitch,-89.5,89.5)*RAD,r=roll*RAD,f=[Math.sin(h)*Math.cos(p),Math.cos(h)*Math.cos(p),Math.sin(p)],right=[Math.cos(h),-Math.sin(h),0],up=[-Math.sin(h)*Math.sin(p),-Math.cos(h)*Math.sin(p),Math.cos(p)];return {forward:f,right:right.map((v,i)=>v*Math.cos(r)+up[i]*Math.sin(r)),up:up.map((v,i)=>v*Math.cos(r)-right[i]*Math.sin(r))};}
function cameraPoint(v,b,exaggeration=1){const p=[v[0],v[1],v[2]*exaggeration-1.7],dot=a=>a.reduce((s,x,i)=>s+x*p[i],0);return [dot(b.right),dot(b.up),dot(b.forward)];}
function perspective(v,width,height,fov=65){if(v[2]<.25)return null;const f=height/(2*Math.tan(fov*RAD/2));return {x:width/2+v[0]*f/v[2],y:height/2-v[1]*f/v[2],depth:v[2]};}
function bearing(a,b){const v=local(b,a);return wrap(Math.atan2(v[0],v[1])*DEG);}
class CompassConfidence{
 constructor(){this.reset();}
 reset(){this.last=null;this.count=0;this.suspectUntil=0;this.jumps=[];this.state='Unavailable';}
 update({heading,pitch=0,accuracy=null,gyroRate=null,now=0,available=true}){
  if(!available||!finite(heading)){this.state='Unavailable';return this.state;}
  this.count++;
  if(accuracy!==null&&(accuracy<0||accuracy>=45)){this.state='Calibration suggested';this.suspectUntil=now+5000;}
  else{
   if(this.last){const dt=now-this.last.now,jump=Math.abs(delta(heading,this.last.heading));
    if(dt>0&&dt<300&&jump>50&&Math.abs(pitch)<70){this.suspectUntil=now+3000;if(finite(gyroRate)&&gyroRate<8)this.jumps.push(now);}
   }
   this.jumps=this.jumps.filter(t=>now-t<10000);
   this.state=this.jumps.length>=3?'Calibration suggested':accuracy!==null&&accuracy>20||now<this.suspectUntil||this.count<5?'Uncertain':'Good';
  }
  this.last={heading,now};return this.state;
 }
}
const api={RAD,DEG,clamp,wrap,delta,distance,local,prefs,makeRoute,parseGPX,at,windowRoute,elevationStats,significantChange,projectSegment,matchProgress,qmul,qaxis,rotate,slerp,qdistance,poseFromQ,devicePose,basis,cameraPoint,perspective,bearing,CompassConfidence};
if(typeof module!=='undefined'&&module.exports)module.exports=api;root.TrailVisionCore=api;
})(typeof globalThis!=='undefined'?globalThis:this);
