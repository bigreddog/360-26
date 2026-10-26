/* Isolated, on-demand Canvas 3D view. No camera, WebGL, or network dependency. */
(function(root){
'use strict';
const C=root.TrailVisionCore;
class View{
 constructor({element,tracker,getGpx,getAxis,getProgressKm,getPreferences,onPreferences}){
  Object.assign(this,{el:element,tracker,getGpx,getAxis,getProgressKm,getPreferences,onPreferences});
  this.active=false;this.frames=0;this.raf=0;this.generation=0;this.route=null;this.uploaded=false;this.sensorAttached=false;this.permissionsGranted=false;this.confidence=new C.CompassConfidence();
  this.find=id=>this.el.querySelector('[data-vision="'+id+'"]');this.canvas=this.find('canvas');
  this.find('exit').onclick=()=>this.close();this.el.addEventListener('cancel',e=>{e.preventDefault();this.close();});
  this.find('recenter').onclick=()=>{this.offsetYaw=0;this.offsetPitch=0;if(this.targetQ)this.smoothQ=this.targetQ.slice();this.redraw();};
  for(const name of ['lookAhead','exaggeration','mode','manualHeading'])this.find(name).addEventListener('change',()=>{
   this.preferences=C.prefs({...this.preferences,[name]:this.find(name).value});this.onPreferences(this.preferences);this.offsetYaw=0;this.offsetPitch=0;if(name==='lookAhead')this.updateWindow();this.updateHUD();this.redraw();
  });
  this.find('manualHeading').addEventListener('input',()=>{this.preferences.manualHeading=Number(this.find('manualHeading').value);this.updateHUD();this.redraw();});
  this.find('manualPitch').oninput=()=>{this.manualPitch=Number(this.find('manualPitch').value);this.redraw();};
  this.find('hintApply').onclick=()=>{const km=Number(this.find('hint').value);if(!Number.isFinite(km)||km<0||km>this.route.distance/1000){this.find('fileStatus').textContent='Enter a route kilometre within this GPX.';return;}this.previous=null;this.hint=km*1000;if(this.simulation)this.simulate({distance:this.hint});else this.onGPS(this.tracker.snapshot());};
  this.find('previewOffline').onclick=()=>this.setSimulation(true);
  this.find('help').onclick=()=>{this.find('helpText').hidden=!this.find('helpText').hidden;this.find('help').setAttribute('aria-expanded',String(!this.find('helpText').hidden));};
  this.find('simulate').onchange=()=>this.setSimulation(this.find('simulate').checked);
  for(const name of ['simHeading','simPitch','simDistance'])this.find(name).oninput=()=>this.simulate({heading:Number(this.find('simHeading').value),pitch:Number(this.find('simPitch').value),distance:Number(this.find('simDistance').value)*1000});
  this.find('file').onchange=e=>this.loadFile(e.target.files?.[0]);this.find('raceRoute').onclick=()=>this.restoreRace();
  this.el.querySelectorAll('[data-vision-mode]').forEach(b=>b.onclick=()=>{this.preferences.mode=b.dataset.visionMode;this.find('mode').value=this.preferences.mode;this.onPreferences(this.preferences);this.updateHUD();this.redraw();});
  this.orientationHandler=e=>this.onOrientation(e);this.motionHandler=e=>{const r=e.rotationRate;if(r&&[r.alpha,r.beta,r.gamma].every(Cfinite))this.gyro={rate:Math.hypot(r.alpha,r.beta,r.gamma),time:performance.now()};};
  this.visibilityHandler=()=>{if(!this.active)return;if(document.hidden){this.detachSensors();cancelAnimationFrame(this.raf);this.raf=0;}else{if(this.permissionsGranted&&!this.simulation)this.attachSensors();this.tracker.refresh();this.checkSensors();this.redraw();}};
  this.screenHandler=()=>{this.targetQ=null;this.smoothQ=null;this.confidence.reset();this.quality='Unavailable';this.sensorMessage='Screen rotated. Waiting for a new compass reading.';this.updateHUD();this.redraw();};
  this.canvas.addEventListener('pointerdown',e=>{this.drag={x:e.clientX,y:e.clientY,yaw:this.offsetYaw,pitch:this.offsetPitch};this.canvas.setPointerCapture(e.pointerId);});
  this.canvas.addEventListener('pointermove',e=>{if(!this.drag)return;this.offsetYaw=C.clamp(this.drag.yaw-(e.clientX-this.drag.x)*.18,-180,180);this.offsetPitch=C.clamp(this.drag.pitch+(e.clientY-this.drag.y)*.15,-60,60);this.redraw();});
  this.canvas.addEventListener('pointerup',()=>this.drag=null);this.canvas.addEventListener('pointercancel',()=>this.drag=null);
 }
 async open(){
  if(this.active)return;this.active=true;this.canvasVisible=true;const token=++this.generation;this.preferences=C.prefs(this.getPreferences());this.hint=this.uploaded?(this.previewHint??0):this.getProgressKm()*1000;this.previous=null;this.match=null;this.window=null;this.gps=null;this.targetQ=null;this.smoothQ=null;this.lastPose=null;this.lastSensorTime=0;this.offsetYaw=0;this.offsetPitch=0;this.manualPitch=-5;this.status='';this.matchStatus='waiting';this.quality='Unavailable';this.sensorMessage='Waiting for compass heading. Hold the phone upright.';this.simulation=false;this.confidence.reset();this.frames=0;this.drag=null;
  for(const name of ['lookAhead','exaggeration','mode','manualHeading'])this.find(name).value=this.preferences[name];
  this.find('manualPitch').value=-5;this.find('simulate').checked=false;this.find('simulationPanel').hidden=true;this.find('options').open=false;this.find('helpText').hidden=true;this.find('help').setAttribute('aria-expanded','false');this.find('fileStatus').textContent=this.uploaded?'Custom preview GPX · race map unchanged':'Official race GPX';this.find('direction').textContent='';this.find('offset').textContent='';this.find('hint').value=this.hint/1000;
  this.el.showModal();this.oldOverflow=document.body.style.overflow;document.body.style.overflow='hidden';
  // Call permission methods directly in the initiating user gesture (required by iOS).
  this.requestSensors(token);
  try{if(!this.route)this.restoreRace(false);if(!this.route?.valid)throw Error('No usable GPX loaded. Load a GPX in Settings.');}
  catch(e){this.route=null;this.find('fileStatus').textContent=e.message;}
  this.ctx=this.canvas.getContext('2d',{alpha:false});
  if(!this.ctx)this.sensorMessage='This browser cannot draw the preview. The normal route map is still available.';
  this.resizeObserver=new ResizeObserver(()=>this.redraw());this.resizeObserver.observe(this.canvas);
  if(typeof IntersectionObserver!=='undefined'){this.intersectionObserver=new IntersectionObserver(entries=>{this.canvasVisible=entries[0].isIntersecting;if(this.canvasVisible)this.redraw();},{root:this.el});this.intersectionObserver.observe(this.canvas);}
  document.addEventListener('visibilitychange',this.visibilityHandler);window.addEventListener('orientationchange',this.screenHandler);screen.orientation?.addEventListener('change',this.screenHandler);
  this.sensorTimer=setInterval(()=>this.checkSensors(),1000);
  this.takeGPS();this.updateHUD();this.redraw();
 }
 close(){
  if(!this.active)return;if(this.uploaded)this.previewHint=this.match?.s??0;this.active=false;++this.generation;cancelAnimationFrame(this.raf);this.raf=0;this.detachSensors();clearInterval(this.sensorTimer);this.resizeObserver?.disconnect();this.intersectionObserver?.disconnect();this.releaseGPS();
  document.removeEventListener('visibilitychange',this.visibilityHandler);window.removeEventListener('orientationchange',this.screenHandler);screen.orientation?.removeEventListener('change',this.screenHandler);
  this.canvas.width=1;this.canvas.height=1;this.window=null;this.targetQ=null;this.smoothQ=null;this.drag=null;this.el.close();document.body.style.overflow=this.oldOverflow;
 }
 takeGPS(){this.ownsGPS=!this.tracker.enabled;this.unsubscribe=this.tracker.subscribe(s=>this.onGPS(s));if(this.tracker.enabled)this.onGPS(this.tracker.snapshot());else this.tracker.start();}
 releaseGPS(){this.unsubscribe?.();this.unsubscribe=null;if(this.ownsGPS&&this.tracker.enabled)this.tracker.stop();this.ownsGPS=false;}
 async requestSensors(token){
  let orientationPermission='granted',motionPermission='granted';
  try{
   const orientationPromise=typeof DeviceOrientationEvent!=='undefined'&&typeof DeviceOrientationEvent.requestPermission==='function'?DeviceOrientationEvent.requestPermission(true):Promise.resolve(typeof DeviceOrientationEvent==='undefined'?'unsupported':'granted');
   const motionPromise=typeof DeviceMotionEvent!=='undefined'&&typeof DeviceMotionEvent.requestPermission==='function'?DeviceMotionEvent.requestPermission().catch(()=>'denied'):Promise.resolve('granted');
   [orientationPermission,motionPermission]=await Promise.all([orientationPromise,motionPromise]);
  }catch(e){orientationPermission='denied';}
  if(!this.active||token!==this.generation)return;
  this.permissionsGranted=orientationPermission==='granted';this.motionGranted=motionPermission==='granted';
  if(this.permissionsGranted&&!this.simulation)this.attachSensors();
  else{this.quality='Unavailable';this.sensorMessage=orientationPermission==='denied'?'Compass permission denied. Choose Manual or Follow route.':'Compass sensors unavailable. Choose Manual or Follow route.';this.updateHUD();this.redraw();}
 }
 attachSensors(){if(this.sensorAttached||!this.active||document.hidden)return;window.addEventListener('deviceorientationabsolute',this.orientationHandler);window.addEventListener('deviceorientation',this.orientationHandler);if(this.motionGranted)window.addEventListener('devicemotion',this.motionHandler);this.sensorAttached=true;}
 detachSensors(){window.removeEventListener('deviceorientationabsolute',this.orientationHandler);window.removeEventListener('deviceorientation',this.orientationHandler);window.removeEventListener('devicemotion',this.motionHandler);this.sensorAttached=false;}
 onOrientation(event){
  if(!this.active||document.hidden||this.simulation)return;
  const pose=C.devicePose(event,screen.orientation?.angle??window.orientation??0);if(!pose)return;
  // Prefer the absolute event over duplicate relative events on Android.
  const now=performance.now();if(event.type==='deviceorientationabsolute')this.absoluteTime=now;else if(!Cfinite(event.webkitCompassHeading)&&now-(this.absoluteTime??-Infinity)<1000)return;
  this.acceptPose(pose,now);
 }
 acceptPose(pose,now=performance.now()){
  const priorQuality=this.quality,changed=!this.targetQ||C.qdistance(this.targetQ,pose.q)>.08||pose.reference!==this.lastPose?.reference;
  this.lastPose=pose;this.lastSensorTime=now;this.sensorMessage=Math.abs(pose.pitch)>75?'Hold the phone upright to look along the trail.':'';
  const gyroRate=this.gyro&&now-this.gyro.time<300?this.gyro.rate:null;
  this.quality=this.confidence.update({heading:pose.heading,pitch:pose.pitch,accuracy:pose.accuracy,gyroRate,now});
  if(changed||priorQuality!==this.quality){this.targetQ=pose.q;this.updateHUD();this.redraw();}
 }
 checkSensors(){
  if(!this.active||this.simulation)return;
  if(this.targetQ&&performance.now()-this.lastSensorTime>30000){this.targetQ=null;this.smoothQ=null;this.quality='Unavailable';this.sensorMessage='Compass readings stopped. Choose Manual or Follow route.';this.updateHUD();this.redraw();}
  else if(this.targetQ&&performance.now()-this.lastSensorTime>10000){this.quality='Uncertain';this.sensorMessage='No recent compass update. Turn the phone or choose a fallback.';this.updateHUD();}
  else if(!this.targetQ&&this.permissionsGranted){this.sensorMessage='No absolute compass heading available. Choose Manual or Follow route.';this.updateHUD();}
  if(this.gps?.fix&&Date.now()-this.gps.fix.timestamp>120000)this.onGPS(this.tracker.snapshot());
 }
 restoreRace(update=true){
  const raw=this.getGpx();if(!raw)throw Error('No GPX loaded. Choose a GPX in Settings.');
  this.route=C.makeRoute(C.parseGPX(raw),this.getAxis());this.uploaded=false;this.previous=null;this.match=null;this.window=null;this.hint=this.getProgressKm()*1000;this.find('fileStatus').textContent='Official race GPX';
  if(update){if(this.simulation)this.simulate({distance:this.hint});else this.onGPS(this.tracker.snapshot());this.updateHUD();this.redraw();}
 }
 async loadFile(file){
  if(!file)return;const token=this.generation;
  try{if(file.size>20*1024*1024)throw Error('Choose a GPX smaller than 20 MB.');const raw=await file.text();if(!this.active||token!==this.generation)return;const route=C.makeRoute(C.parseGPX(raw));if(!route.valid)throw Error('This GPX has no connected track.');this.route=route;this.uploaded=true;this.previous=null;this.match=null;this.window=null;this.hint=0;this.find('hint').value=0;this.find('fileStatus').textContent=`Preview GPX: ${file.name}. Race map unchanged.`;if(this.simulation)this.simulate({distance:0});else this.onGPS(this.tracker.snapshot());this.updateHUD();this.redraw();}
  catch(e){this.find('fileStatus').textContent=e.message;}
 }
 onGPS(snapshot){
  if(!this.active||this.simulation)return;this.gps=snapshot;
  if(!this.route?.valid){this.status='No usable GPX loaded. Choose a GPX in Settings.';this.updateHUD();this.redraw();return;}
  if(!snapshot.fix){this.status=snapshot.message;this.updateHUD();this.redraw();return;}
  if(['waiting','error'].includes(snapshot.status)){this.status=snapshot.message;this.updateHUD();this.redraw();return;}
  if(Date.now()-snapshot.fix.timestamp>120000){this.status='GPS fix is over 2 minutes old. Preview stays at the last matched position.';this.updateHUD();this.redraw();return;}
  const matched=C.matchProgress(this.route,snapshot.fix,this.previous,this.hint);this.status=matched.message;this.matchStatus=matched.status;
  if(matched.usable){this.match=matched;this.previous=matched;this.hint=matched.s;this.updateWindow();}
  this.updateHUD();this.redraw();
 }
 updateWindow(){if(this.route&&this.match)this.window=C.windowRoute(this.route,this.match.s,this.preferences.lookAhead,this.match.segment);}
 setSimulation(enabled){
  if(enabled&&!this.route?.valid){this.find('simulate').checked=false;this.find('fileStatus').textContent='Load a GPX before starting simulation.';return;}
  this.simulation=enabled;this.find('simulate').checked=enabled;this.find('simulationPanel').hidden=!enabled;this.previous=null;this.match=null;
  if(enabled){this.releaseGPS();this.detachSensors();this.confidence.reset();this.find('simDistance').max=(this.route?.distance??0)/1000;this.find('simDistance').value=C.clamp(this.hint,0,this.route?.distance??0)/1000;const start=C.at(this.route,C.clamp(this.hint,0,this.route.distance));const next=C.at(this.route,Math.min(this.route.distance,start.s+30),start.segment);this.find('simHeading').value=Math.round(C.bearing(start,next));this.find('simPitch').value=0;this.simulate({distance:start.s,heading:Number(this.find('simHeading').value),pitch:0});}
  else{this.targetQ=null;this.smoothQ=null;this.lastPose=null;this.confidence.reset();this.quality='Unavailable';if(this.permissionsGranted)this.attachSensors();this.takeGPS();this.updateHUD();this.redraw();}
 }
 simulate({distance,heading,pitch,accuracy=8}={}){
  if(!this.active||!this.simulation||!this.route?.valid)return;
  if(Cfinite(distance)){const p=C.at(this.route,C.clamp(distance,0,this.route.distance));this.match={...p,usable:true,status:'active'};this.hint=p.s;this.matchStatus='active';this.status='Simulation — no live GPS or compass';this.gps={fix:{...p,accuracy,timestamp:Date.now()}};this.updateWindow();this.find('simDistance').value=p.s/1000;}
  heading=Cfinite(heading)?heading:Number(this.find('simHeading').value);pitch=Cfinite(pitch)?pitch:Number(this.find('simPitch').value);this.find('simHeading').value=heading;this.find('simPitch').value=pitch;
  const pose=C.devicePose({alpha:C.wrap(360-heading),beta:90+pitch,gamma:0,absolute:true});pose.reference='Simulated north';this.acceptPose(pose);this.updateHUD();this.redraw();
 }
 cameraPose(){
  let h,p,r=0;
  if(this.preferences.mode==='compass'){if(!this.smoothQ)return null;const pose=C.poseFromQ(this.smoothQ);h=pose.heading;p=pose.pitch;r=C.clamp(pose.roll*.15,-8,8);}
  else if(this.preferences.mode==='manual'){h=this.preferences.manualHeading;p=this.manualPitch;}
  else{if(!this.window?.points.length)return null;h=C.bearing(this.window.origin,this.window.points[Math.min(6,this.window.points.length-1)]);p=this.manualPitch;}
  return {heading:C.wrap(h+this.offsetYaw),pitch:C.clamp(p+this.offsetPitch,-89,89),roll:r,basis:C.basis(h+this.offsetYaw,p+this.offsetPitch,r)};
 }
 updateHUD(){
  if(!this.active)return;const w=this.window,p=this.preferences;
  this.find('progress').textContent=this.match&&this.route?`${(this.match.s/1000).toFixed(2)} / ${(this.route.distance/1000).toFixed(1)} km`:'Route position pending';
  this.find('heading').textContent=p.mode==='manual'?`${Math.round(p.manualHeading)}°\nManual view heading`:p.mode==='route'?`${Math.round(this.cameraPose()?.heading??0)}°\nRoute view heading`:this.lastPose?`${Math.round(this.lastPose.heading)}°\n${this.lastPose.reference.startsWith('Device')?'North ref unverified':this.lastPose.reference}`:'Compass heading unavailable';
  this.find('quality').textContent=this.simulation?'Simulated compass':`Compass: ${this.quality}`;
  this.find('gps').textContent=this.gps?.fix?`${this.simulation?'Simulated GPS':'GPS'} ±${Math.round(this.gps.fix.accuracy)} m`:'GPS: waiting';
  this.find('elevation').textContent=w?.elevationOK?`↑ ${Math.round(w.stats.ascent)} m  ↓ ${Math.round(w.stats.descent)} m\nNet ${w.stats.net>=0?'+':''}${Math.round(w.stats.net)} m`:'Elevation unavailable';
  this.find('ahead').textContent=`${w?Math.round(w.available):p.lookAhead} m ahead\n${p.exaggeration}× ${p.exaggeration===1?'true scale':'vertical scale'}`;
  this.find('modeLabel').textContent=this.simulation?`SIMULATION · ${p.mode==='compass'?'compass':p.mode==='route'?'follow route':'manual'} view`:p.mode==='compass'?'Compass view':p.mode==='route'?'Follow route · automatic heading':'Manual heading';
  const warning=!this.simulation&&['Uncertain','Calibration suggested'].includes(this.quality)&&p.mode==='compass';
  this.find('compassWarning').hidden=!warning;this.find('compassWarning').textContent=warning?'Compass accuracy may be low. Move away from metal objects and calibrate your phone if needed.':'';
  this.find('sensorStatus').textContent=p.mode==='compass'?this.sensorMessage:'';
  this.find('fallback').hidden=this.simulation||p.mode!=='compass'||this.quality==='Good';
  this.find('gpsStatus').textContent=this.status==='GPS matched to the route.'?'':this.status||'Waiting for GPS permission and position…';
  this.find('previewOffline').hidden=this.simulation||!!this.match||!this.route?.valid;
  this.find('elevationWarning').textContent=w?.warning??'';
  this.find('segmentWarning').textContent=w?.ended?`Track segment ends in ${Math.round(w.available)} m. No gap is bridged.`:'';
  this.find('manualControls').hidden=p.mode==='compass';this.find('headingControl').hidden=p.mode!=='manual';
  this.find('manualValue').textContent=Math.round(p.manualHeading)+'°';
  const change=w?.change;this.find('change').textContent=change?`${change.kind} ${change.inMetres<5?'now':'in '+Math.round(change.inMetres)+' m'} · ${Math.round(Math.abs(change.change))} m over ${Math.round(change.length)} m`:'';
 }
 redraw(){if(this.active&&this.canvasVisible!==false&&!document.hidden&&!this.raf)this.raf=requestAnimationFrame(t=>this.frame(t));}
 frame(time){
  this.raf=0;if(!this.active||this.canvasVisible===false||document.hidden||!this.ctx)return;
  if(this.lastFrame&&time-this.lastFrame<32){this.redraw();return;}
  const dt=Math.min(.2,Math.max(.016,(time-(this.lastFrame??time-33))/1000));this.lastFrame=time;
  let animating=false;if(this.targetQ){if(!this.smoothQ)this.smoothQ=this.targetQ.slice();else{const angle=C.qdistance(this.smoothQ,this.targetQ);if(angle>.08){this.smoothQ=C.slerp(this.smoothQ,this.targetQ,1-Math.exp(-dt/.11));animating=true;}else this.smoothQ=this.targetQ.slice();}}
  this.draw();this.frames++;if(animating)this.redraw();
 }
 draw(){
  const rect=this.canvas.getBoundingClientRect(),width=Math.max(1,rect.width),height=Math.max(1,rect.height),ratio=Math.min(1.5,window.devicePixelRatio||1);
  if(this.canvas.width!==Math.round(width*ratio)||this.canvas.height!==Math.round(height*ratio)){this.canvas.width=Math.round(width*ratio);this.canvas.height=Math.round(height*ratio);}
  const ctx=this.ctx;ctx.setTransform(ratio,0,0,ratio,0,0);ctx.fillStyle='#06131c';ctx.fillRect(0,0,width,height);
  const pose=this.cameraPose();ctx.font='16px system-ui';ctx.textAlign='center';
  if(!pose){ctx.fillStyle='#d8f4f3';ctx.fillText(this.preferences.mode==='compass'?'Waiting for compass — choose a fallback below':'Waiting for route position',width/2,height/2);this.find('direction').textContent='';return;}
  const b=pose.basis,project=v=>C.perspective(C.cameraPoint(v,b,this.preferences.exaggeration),width,height);
  // A flat reference grid is not terrain; route elevations alone are rendered.
  ctx.lineWidth=1;ctx.strokeStyle='#17404c';
  const gridSize=Math.min(1100,this.preferences.lookAhead+100),spacing=this.preferences.lookAhead>500?100:50;
  const segment=(a,z,color,widthPx=1)=>{let av=C.cameraPoint(a,b,this.preferences.exaggeration),bv=C.cameraPoint(z,b,this.preferences.exaggeration);const clipped=clipNear(av,bv);if(!clipped)return;const p=C.perspective(clipped[0],width,height),q=C.perspective(clipped[1],width,height);if(!p||!q)return;ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.strokeStyle=color;ctx.lineWidth=widthPx;ctx.stroke();};
  for(let n=-gridSize;n<=gridSize;n+=spacing){segment([n,-gridSize,0],[n,gridSize,0],'#12323f');segment([-gridSize,n,0],[gridSize,n,0],'#12323f');}
  // Project the true horizontal plane's line at infinity; clamp only for drawing.
  const horizonY=height/2+Math.tan(pose.pitch*C.RAD)*height/(2*Math.tan(65*C.RAD/2));
  if(horizonY>=0&&horizonY<=height){ctx.strokeStyle='#446370';ctx.beginPath();ctx.moveTo(0,horizonY);ctx.lineTo(width,horizonY);ctx.stroke();ctx.fillStyle='#99b4ba';ctx.textAlign='left';ctx.fillText('Horizon',12,horizonY-7);}
  const w=this.window;if(!w?.local.length){this.find('direction').textContent=this.route?.valid?'Waiting for a reliable route position':'Load a GPX in Settings';ctx.fillStyle='#e0f1ef';ctx.textAlign='center';ctx.fillText('Waiting for a reliable route position',width/2,height/2);return;}
  const triangles=[];
  for(let i=0;i<w.local.length-1;i++){
   const a=w.local[i],z=w.local[i+1],dx=z[0]-a[0],dy=z[1]-a[1],length=Math.hypot(dx,dy)||1,side=[-dy/length*1.1,dx/length*1.1,0];
   const quad=[[a[0]+side[0],a[1]+side[1],a[2]],[a[0]-side[0],a[1]-side[1],a[2]],[z[0]-side[0],z[1]-side[1],z[2]],[z[0]+side[0],z[1]+side[1],z[2]]].map(v=>C.cameraPoint(v,b,this.preferences.exaggeration));
   const polygon=clipPolygon(quad);if(polygon.length>=3)triangles.push({polygon,depth:polygon.reduce((s,p)=>s+p[2],0)/polygon.length});
  }
  triangles.sort((a,z)=>z.depth-a.depth);ctx.fillStyle='#18dbc1';
  for(const {polygon} of triangles){const ps=polygon.map(p=>C.perspective(p,width,height));ctx.beginPath();ps.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.closePath();ctx.fill();}
  for(let i=0;i<w.local.length-1;i++)segment(w.local[i],w.local[i+1],'#92ffeb',2);
  const markerPositions=[];let visible=0;
  for(let d=100;d<=w.available+.1;d+=100){const i=Math.min(w.local.length-1,Math.round(d/5)),point=project(w.local[i]);if(!point||point.x<0||point.x>width||point.y<0||point.y>height)continue;visible++;
   ctx.fillStyle='#c5fff2';ctx.beginPath();ctx.arc(point.x,point.y,4,0,Math.PI*2);ctx.fill();
   if(markerPositions.some(p=>Math.hypot(p.x-point.x,p.y-point.y)<42))continue;markerPositions.push(point);
   ctx.font='bold 16px system-ui';ctx.textAlign='center';ctx.lineWidth=4;ctx.strokeStyle='#06131c';ctx.strokeText(d+' m',point.x,point.y-10);ctx.fillText(d+' m',point.x,point.y-10);
  }
  const current=project([0,0,.03]);if(current){ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(current.x,current.y,7,0,Math.PI*2);ctx.fill();}
  ctx.font='bold 17px system-ui';ctx.textAlign='center';ctx.fillStyle='#d5fff5';ctx.fillText('● You',width/2,height-16);
  const target=w.local[Math.min(6,w.local.length-1)],heading=C.wrap(Math.atan2(target[0],target[1])*C.DEG),difference=C.delta(heading,pose.heading);
  const hasVisible=w.local.slice(1).some(v=>{const p=project(v);return p&&p.x>8&&p.x<width-8&&p.y>8&&p.y<height-8;});
  this.find('direction').textContent=Math.abs(difference)>100?`Route starts behind you · turn ${difference>0?'right':'left'}`:Math.abs(difference)>40?`Route starts to your ${difference>0?'right →':'left ←'}`:!hasVisible?'Route is outside the view · tilt the phone':w.ended&&w.available<5?'End of this track segment':'Route ahead';
  this.find('offset').textContent=Math.abs(this.offsetYaw)>.5||Math.abs(this.offsetPitch)>.5?'View offset applied · tap Recenter':'';
 }
 snapshot(){return {active:this.active,simulation:this.simulation,mode:this.preferences?.mode,quality:this.quality,reference:this.lastPose?.reference,heading:this.lastPose?.heading,match:this.match?{distance:this.match.s,segment:this.match.segment}:null,matchStatus:this.matchStatus,geometry:this.window?.local.map(p=>p.slice()),available:this.window?.available,elevationOK:this.window?.elevationOK,stats:this.window?.stats,frames:this.frames,sensorAttached:this.sensorAttached,ownsGPS:this.ownsGPS,preferences:this.preferences};}
}
function Cfinite(n){return typeof n==='number'&&Number.isFinite(n);}
function clipNear(a,b){if(a[2]<.25&&b[2]<.25)return null;const mix=(p,q)=>{const t=(.25-p[2])/(q[2]-p[2]);const out=p.map((v,i)=>v+(q[i]-v)*t);out[2]=.25;return out;};if(a[2]<.25)a=mix(a,b);if(b[2]<.25)b=mix(b,a);return [a,b];}
function clipPolygon(vertices){const output=[];for(let i=0;i<vertices.length;i++){const a=vertices[i],b=vertices[(i+1)%vertices.length],insideA=a[2]>=.25,insideB=b[2]>=.25;if(insideA)output.push(a);if(insideA!==insideB){const t=(.25-a[2])/(b[2]-a[2]);const point=a.map((v,j)=>v+(b[j]-v)*t);point[2]=.25;output.push(point);}}return output;}
root.TrailVisionView=View;
})(typeof globalThis!=='undefined'?globalThis:this);
