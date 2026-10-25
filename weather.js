/* Route-aware forecast: same pacing curve and distance axis as the roadbook. */
(function(root){
'use strict';
const HOUR=3600000,MAX_HOURS=18,CACHE_KEY='canarias360-weather-v1';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function signature(state){return JSON.stringify([state.quotas,state.terrainWeight,state.extraHours]);}
function routePoint(data,km,E){
 const axis=data.route_km;let a=0,b=axis.length-1;while(b-a>1){const m=(a+b)>>1;if(axis[m]<=km)a=m;else b=m;}
 const t=Math.max(0,Math.min(1,(km-axis[a])/(axis[b]-axis[a]||1))),p=data.route[a],q=data.route[b];
 const near=data.anchors.reduce((x,y)=>Math.abs(x.km-km)<=Math.abs(y.km-km)?x:y);
 const leg=data.sections.find(s=>km>=s.from_km&&km<=s.to_km)||data.sections.at(-1);
 return {km,lat:p[0]+t*(q[0]-p[0]),lon:p[1]+t*(q[1]-p[1]),elevation:E.interp(data.profile,km,1),place:Math.abs(near.km-km)<=3?'Near '+near.name:leg.start_name+' → '+leg.end_name};
}
function createPlan(data,state,now,E){
 const start=Date.parse(data.start),fromKm=Math.max(0,Math.min(data.distance_km,state.progressKm)),plannedElapsed=state.anchorLive?state.elapsedHours:now<start?E.etaHours(data,fromKm,state.quotas,state.terrainWeight):0,base=Math.max(now,start+plannedElapsed*HOUR);
 const startEffort=E.etaHours(data,fromKm,state.quotas,state.terrainWeight),finishEffort=E.etaHours(data,data.distance_km,state.quotas,state.terrainWeight);
 const remaining=fromKm>=data.distance_km?0:Math.max(0,finishEffort-startEffort+Number(state.extraHours||0));
 const samples=[];
 for(let hour=0;hour<=MAX_HOURS;hour++){
  if(hour>remaining+.00001)break;
  const effort=startEffort+Math.max(0,hour-Number(state.extraHours||0));let lo=fromKm,hi=data.distance_km;
  if(hour===0)hi=lo;
  else for(let i=0;i<42;i++){const mid=(lo+hi)/2;if(E.etaHours(data,mid,state.quotas,state.terrainWeight)<effort)lo=mid;else hi=mid;}
  samples.push({...routePoint(data,(lo+hi)/2,E),hour,time:base+hour*HOUR});
 }
 if(remaining>0&&remaining<MAX_HOURS&&remaining%1>.00001)samples.push({...routePoint(data,data.distance_km,E),hour:remaining,time:base+remaining*HOUR,finish:true});
 return {requestedAt:now,base,fromKm,remaining,samples,signature:signature(state),routeSha256:data.gpx_sha256};
}
function forecastRange(plan,now){const today=Math.floor(now/(24*HOUR))*24*HOUR;return plan.base>=today&&plan.base<today+16*24*HOUR;}
function requestURL(plan){
 const params=new URLSearchParams({latitude:plan.samples.map(p=>p.lat.toFixed(5)).join(','),longitude:plan.samples.map(p=>p.lon.toFixed(5)).join(','),elevation:plan.samples.map(p=>Math.round(p.elevation)).join(','),hourly:'temperature_2m,apparent_temperature,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_gusts_10m,wind_direction_10m,is_day',start_hour:new Date(Math.floor(plan.base/HOUR)*HOUR).toISOString().slice(0,13)+':00',end_hour:new Date(Math.min(Math.ceil(plan.samples.at(-1).time/HOUR)*HOUR,Math.floor(plan.requestedAt/(24*HOUR))*24*HOUR+16*24*HOUR-HOUR)).toISOString().slice(0,13)+':00',timeformat:'unixtime',timezone:'GMT',temperature_unit:'celsius',wind_speed_unit:'kmh',precipitation_unit:'mm',cell_selection:'land'});
 return 'https://api.open-meteo.com/v1/forecast?'+params;
}
function readLocation(response,sample){
 const hourly=response?.hourly,times=hourly?.time;if(!Array.isArray(times)||!times.length||times.some((t,i)=>!finite(t)||i>0&&t<=times[i-1]))return null;
 const t=sample.time/1000;if(t<times[0]||t>times.at(-1))return null;
 let a=0,b=times.length-1;while(b-a>1){const m=(a+b)>>1;if(times[m]<=t)a=m;else b=m;}
 const f=(t-times[a])/(times[b]-times[a]||1),nearest=f<=.5?a:b;
 const value=(key,interpolate=false)=>{const arr=hourly[key];if(!Array.isArray(arr))return null;if(interpolate){if(f===0)return finite(arr[a])?arr[a]:null;if(f===1)return finite(arr[b])?arr[b]:null;return finite(arr[a])&&finite(arr[b])?arr[a]+(arr[b]-arr[a])*f:null;}return finite(arr[nearest])?arr[nearest]:null;};
 const result={temperature:value('temperature_2m',true),feels:value('apparent_temperature',true),chance:value('precipitation_probability'),rain:value('precipitation'),code:value('weather_code'),wind:value('wind_speed_10m',true),gust:value('wind_gusts_10m',true),direction:value('wind_direction_10m'),day:value('is_day')};
 return Object.values(result).some(finite)?result:null;
}
function readResponses(payload,plan){const locations=Array.isArray(payload)?payload:[payload];if(locations.length!==plan.samples.length)throw Error('Forecast provider returned an incomplete location list.');return plan.samples.map((sample,i)=>({sample,weather:readLocation(locations[i],sample)}));}
function summarize(rows,hours,profile){
 const selected=rows.filter(r=>r.sample.hour<=hours+.00001),values=key=>selected.map(r=>r.weather?.[key]).filter(finite),temps=values('temperature'),feels=values('feels'),winds=values('wind').filter(n=>n>=0),gusts=values('gust').filter(n=>n>=0),chances=values('chance');
 const rainy=selected.filter(r=>r.sample.hour>0),rainValues=rainy.map(r=>r.weather?.rain),completeRain=rainValues.length>0&&rainValues.every(finite);
 const elevations=selected.map(r=>r.sample.elevation).filter(finite);if(profile&&selected.length)for(const point of profile)if(point[0]>=selected[0].sample.km&&point[0]<=selected.at(-1).sample.km&&finite(point[1]))elevations.push(point[1]);
 const min=a=>a.length?Math.min(...a):null,max=a=>a.length?Math.max(...a):null;
 const windiest=selected.filter(r=>finite(r.weather?.wind)&&r.weather.wind>=0).sort((a,b)=>b.weather.wind-a.weather.wind)[0];
 const gustiest=selected.filter(r=>finite(r.weather?.gust)).sort((a,b)=>b.weather.gust-a.weather.gust)[0];
 return {rows:selected,available:selected.filter(r=>r.weather).length,total:selected.length,temperatureMin:min(temps),temperatureMax:max(temps),feelsMin:min(feels),feelsMax:max(feels),windMax:max(winds),gustMax:max(gusts),chanceMax:max(chances),rain:completeRain?rainValues.reduce((sum,n,i)=>sum+n*Math.min(1,rainy[i].sample.hour-(i?rainy[i-1].sample.hour:0)),0):null,elevationMin:min(elevations),elevationMax:max(elevations),gustiest,windiest};
}
function codeLabel(code){const groups=[[[0],'Clear'],[[1,2],'Some cloud'],[[3],'Overcast'],[[45,48],'Fog'],[[51,53,55],'Drizzle'],[[56,57],'Freezing drizzle'],[[61,63,65],'Rain'],[[66,67],'Freezing rain'],[[71,73,75,77],'Snow'],[[80,81,82],'Rain showers'],[[85,86],'Snow showers'],[[95,96,99],'Thunderstorm signal']];return groups.find(([codes])=>codes.includes(code))?.[1]||'Conditions unavailable';}
function compass(degrees){return finite(degrees)?['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'][Math.round(((degrees%360)+360)%360/22.5)%16]:'';}
function windInfo(weather={}){const speed=finite(weather.wind)&&weather.wind>=0?weather.wind:null,direction=finite(weather.direction)?((weather.direction%360)+360)%360:null,calm=speed!==null&&speed<1;return {calm,direction:calm?null:direction,speed,from:calm?'Calm · no prevailing direction':direction===null?'Direction unavailable':'From '+compass(direction),gust:finite(weather.gust)&&weather.gust>=0?weather.gust:null};}
function weatherKind(weather={}){
 const code=weather.code,night=weather.day===0;
 if(code===0)return {kind:night?'moon':'sun',label:night?'Clear night':'Clear',rank:0};
 if([1,2].includes(code))return {kind:night?'partly-night':'partly-day',label:night?'Some cloud · night':'Some cloud',rank:1};
 if(code===3)return {kind:'cloud',label:'Overcast',rank:1};
 if([45,48].includes(code))return {kind:'fog',label:'Fog',rank:4};
 if([51,53,55].includes(code))return {kind:'drizzle',label:'Drizzle',rank:2};
 if([56,57,66,67].includes(code))return {kind:'ice',label:code<60?'Freezing drizzle':'Freezing rain',rank:5};
 if([61,63,65,80,81,82].includes(code))return {kind:'rain',label:code>=80?'Rain showers':'Rain',rank:3};
 if([71,73,75,77,85,86].includes(code))return {kind:'snow',label:code>=85?'Snow showers':'Snow',rank:5};
 if([95,96,99].includes(code))return {kind:'storm',label:'Thunderstorm signal',rank:6};
 return {kind:'unknown',label:'Conditions unavailable',rank:-1};
}
function conditions(rows){const unique=[];for(const row of rows){const item=weatherKind(row.weather||{});if(item.kind!=='unknown'&&!unique.some(v=>v.kind===item.kind&&v.label===item.label))unique.push({...item,index:unique.length});}return unique.length?unique.sort((a,b)=>b.rank-a.rank||a.index-b.index).slice(0,3).sort((a,b)=>a.index-b.index):[weatherKind()];}
function weatherIcon(kind){
 const cloud='<path class="wx-cloud" d="M12 31a7 7 0 0 1-1-14 10 10 0 0 1 19-3 9 9 0 1 1 6 17Z"/>';
 const sun='<circle class="wx-sun" cx="24" cy="24" r="8"/><path class="wx-sun-rays" d="M24 4v6m0 28v6M4 24h6m28 0h6M10 10l4 4m20 20 4 4M10 38l4-4m20-20 4-4"/>';
 const moon='<path class="wx-moon" d="M34 29A16 16 0 0 1 19 7a16 16 0 1 0 15 22Z"/>';
 const rain='<path class="wx-rain" d="m15 36-3 6m14-6-3 6m14-6-3 6"/>';
 const snow='<path class="wx-snow" d="M14 35v9m-4-7 8 5m-8 0 8-5m15-2v9m-4-7 8 5m-8 0 8-5"/>';
 const shapes={sun,moon,'partly-day':'<g transform="translate(-4 -6) scale(.78)">'+sun+'</g><g transform="translate(3 12) scale(.87)">'+cloud+'</g>','partly-night':'<g transform="translate(0 -4) scale(.78)">'+moon+'</g><g transform="translate(3 12) scale(.87)">'+cloud+'</g>',cloud,rain:cloud+rain,drizzle:cloud+'<g class="wx-rain"><circle cx="14" cy="38" r="1"/><circle cx="25" cy="41" r="1"/><circle cx="36" cy="38" r="1"/></g>',ice:cloud+'<path class="wx-rain" d="m14 35-3 7m13-7-3 7"/>'+snow,fog:cloud+'<path class="wx-fog" d="M6 36h36M10 42h28"/>',snow:cloud+snow,storm:cloud+'<path class="wx-bolt" d="m26 28-8 10h7l-3 8 12-13h-8l4-5Z"/>',temperature:'<path class="wx-thermometer" d="M19 29V10a5 5 0 0 1 10 0v19a9 9 0 1 1-10 0Z"/><path class="wx-heat" d="M24 16v19"/><circle class="wx-heat-fill" cx="24" cy="36" r="4"/>',drop:'<path class="wx-drop" d="M24 5S10 22 10 31a14 14 0 0 0 28 0C38 22 24 5 24 5Z"/><path class="wx-drop-glint" d="M16 30a8 8 0 0 0 8 9"/>',mountain:'<path class="wx-mountain" d="m4 40 16-30 10 18 5-8 10 20Z"/><path class="wx-snowcap" d="m14 21 6 3 5-4"/>',unknown:'<circle class="wx-unknown" cx="24" cy="24" r="17"/><path class="wx-unknown" d="M19 18a5 5 0 1 1 8 4c-3 2-3 3-3 6m0 7h.01"/>'};
 return `<svg class="weather-icon" data-weather-icon="${Object.hasOwn(shapes,kind)?kind:'unknown'}" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">${Object.hasOwn(shapes,kind)?shapes[kind]:shapes.unknown}</svg>`;
}
function directionIcon(info){
 const arrow=info.direction!==null&&!info.calm?`<g transform="rotate(${(info.direction+180)%360} 24 26)"><path class="wx-direction-arrow" d="M24 39V15m-6 7 6-8 6 8"/></g>`:info.calm?'<circle class="wx-direction-calm" cx="24" cy="26" r="4"/>':'<path class="wx-direction-unknown" d="M19 23a5 5 0 1 1 8 4c-3 2-3 3-3 5m0 4h.01"/>';
 return `<svg class="weather-direction" data-wind-bearing="${info.direction===null?'unknown':info.direction}" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><circle class="wx-direction-ring" cx="24" cy="26" r="19"/><text x="24" y="8" class="wx-north" text-anchor="middle">N</text>${arrow}</svg>`;
}
function clock(ms,zone,full=false){return new Intl.DateTimeFormat('en-GB',{timeZone:zone,weekday:'short',...(full?{day:'numeric',month:'short'}:{}),hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(ms)).replace(',','');}
const round=n=>finite(n)?String(Math.round(n)):'—';
function range(a,b,unit){return finite(a)&&finite(b)?`${round(a)}${Math.round(a)!==Math.round(b)?'–'+round(b):''}${unit}`:'Unavailable';}
class Panel{
 constructor({element,data,getState,engine,fetcher=(...a)=>fetch(...a),now=()=>Date.now()}){
  Object.assign(this,{el:element,data,getState,E:engine,fetcher,now});this.hours=6;this.visible=false;this.loading=false;this.message='';this.cache=null;this.sequence=0;
  try{const stored=JSON.parse(document.getElementById('savedWeatherData')?.textContent||localStorage.getItem(CACHE_KEY)||'null');if(stored?.version===1&&stored.routeSha256===data.gpx_sha256&&finite(stored.base)&&Math.abs(stored.base)<=8640000000000000&&finite(stored.fromKm)&&finite(stored.remaining)&&typeof stored.signature==='string'&&finite(stored.fetchedAt)&&Math.abs(stored.fetchedAt)<=8640000000000000&&Array.isArray(stored.rows)&&stored.rows.length>0&&stored.rows.length<=20&&stored.rows.every(r=>finite(r.sample?.time)&&Math.abs(r.sample.time)<=8640000000000000&&finite(r.sample?.hour)&&finite(r.sample?.km)&&finite(r.sample?.elevation)))this.cache=stored;}catch(e){}
  this.el.querySelectorAll('[data-weather-hours]').forEach(b=>b.onclick=()=>{this.hours=Number(b.dataset.weatherHours);this.render();});
  this.el.querySelector('[data-weather-refresh]').onclick=()=>this.refresh(true);
  this.timer=setInterval(()=>this.update(),60000);
  this.resume=()=>{if(!document.hidden)this.update();};window.addEventListener('online',this.resume);window.addEventListener('offline',this.resume);document.addEventListener('visibilitychange',this.resume);window.addEventListener('pagehide',()=>this.controller?.abort());this.render();
 }
 setVisible(visible){this.visible=visible;if(visible)this.update();}
 update(force=false){
  if(!this.visible||document.hidden)return;
  clearTimeout(this.debounce);this.debounce=setTimeout(()=>{
   if(!this.visible||document.hidden)return;
   const state=this.getState(),age=this.cache?this.now()-this.cache.fetchedAt:Infinity;
   const relocated=this.cache&&Math.abs(this.cache.fromKm-state.progressKm)>=5;
   const changed=this.cache&&(this.cache.signature!==signature(state)||relocated||Math.abs(this.cache.fromKm-state.progressKm)>=2&&age>10*60000);
   if(force||!this.cache||age>=30*60000||changed)this.refresh(force||!!relocated&&(!finite(this.lastAttemptFromKm)||Math.abs(this.lastAttemptFromKm-state.progressKm)>=5));else this.render();
  },500);
 }
 async refresh(manual=false){
  if(this.loading){this.pendingManual=this.pendingManual||manual;return;}if(!this.visible)return;
  this.suppressCache=false;const now=this.now(),state=structuredClone(this.getState()),plan=createPlan(this.data,state,now,this.E);this.plan=plan;
  if(plan.remaining<=.00001){this.message='Route complete. There is no upcoming race section to forecast.';this.cache=null;this.render();return;}
  if(!forecastRange(plan,now)){this.suppressCache=true;this.message='The planned race dates are outside the provider’s forecast window (up to 16 days). Refresh closer to the race.';this.render();return;}
  if(navigator.onLine===false){this.message=this.cache?'Offline · showing the saved forecast for its original time and route positions.':'Connect once to load weather for the route ahead.';this.render();return;}
  if(!manual&&this.lastAttempt&&now-this.lastAttempt<(this.lastError?5:1)*60000){this.render();return;}
  this.lastAttempt=now;this.lastAttemptFromKm=state.progressKm;this.loading=true;this.message='Loading weather along your projected route…';this.render();const sequence=++this.sequence;this.controller=new AbortController();const timeout=setTimeout(()=>this.controller.abort(),20000);
  try{
   const response=await this.fetcher(requestURL(plan),{signal:this.controller.signal,credentials:'omit',referrerPolicy:'no-referrer'});if(!response.ok)throw Error(response.status===429?'The forecast service is busy. Try again shortly.':'Weather service unavailable. Try Refresh.');
   const payload=await response.json(),rows=readResponses(payload,plan);if(!rows.some(r=>r.weather))throw Error('No forecast is available yet for these race dates. Refresh closer to the race.');
   if(sequence!==this.sequence)return;
   this.lastError=false;this.cache={version:1,routeSha256:this.data.gpx_sha256,base:plan.base,fromKm:plan.fromKm,remaining:plan.remaining,signature:plan.signature,fetchedAt:this.now(),rows};this.message='';
   try{localStorage.setItem(CACHE_KEY,JSON.stringify(this.cache));}catch(e){this.message='Forecast loaded. This browser could not save it for offline use.';}
  }catch(e){this.lastError=true;if(sequence===this.sequence)this.message=e.name==='AbortError'?'Weather request timed out or was interrupted. Try Refresh.':e instanceof TypeError?'Could not load weather. Check your connection and tap Refresh.':e instanceof SyntaxError?'Forecast response was unreadable. Try Refresh.':e.message;if(this.cache)this.message+=' Saved forecast retains its original times and positions.';}
  finally{clearTimeout(timeout);if(sequence===this.sequence){this.loading=false;this.render();if(this.pendingManual){this.pendingManual=false;this.update(true);}}}
 }
 render(){
  const now=this.now(),cache=this.cache,hours=this.hours,button=this.el.querySelector('[data-weather-refresh]');button.disabled=this.loading;button.textContent=this.loading?'Loading…':'Refresh';
  this.el.querySelectorAll('[data-weather-hours]').forEach(b=>{const selected=Number(b.dataset.weatherHours)===hours;b.classList.toggle('active',selected);b.setAttribute('aria-pressed',String(selected));});
  const route=this.el.querySelector('[data-weather-route]'),destination=this.el.querySelector('[data-weather-destination]');
  const status=this.el.querySelector('[data-weather-status]'),summary=this.el.querySelector('[data-weather-summary]'),cards=this.el.querySelector('[data-weather-cards]'),context=this.el.querySelector('[data-weather-context]'),conditionRow=this.el.querySelector('[data-weather-conditions]');
  if(!cache||this.suppressCache){status.textContent=this.message||'Forecast follows your pace, route position and GPX elevation.';context.textContent='';summary.innerHTML='';conditionRow.innerHTML='';cards.innerHTML='';destination.textContent='';route.hidden=true;return;}
  const age=Math.max(0,(now-cache.fetchedAt)/60000),end=cache.base+Math.min(hours,cache.remaining)*HOUR,expired=end<now;
  const changed=cache.signature!==signature(this.getState())||Math.abs(cache.fromKm-this.getState().progressKm)>=2;
  status.textContent=expired?'This saved forecast window has passed. Refresh for the route ahead.':navigator.onLine===false?'Offline · saved forecast for its original times and route positions.':this.message||(age>=120?'Saved forecast is over 2 hours old. Refresh when connected.':changed?'Progress or pace has changed. Refresh to update forecast locations.':cache.base-now>7*24*HOUR?'Long-range outlook · refresh nearer race day.':'Forecast for the places you are projected to reach.');
  context.textContent=`${hours}-hour outlook from ${clock(cache.base,this.data.timezone,true)} · route km ${cache.fromKm.toFixed(1)}. Fetched ${clock(cache.fetchedAt,this.data.timezone,true)}${age>=120?' · saved / stale':''}.`;
  if(expired){summary.innerHTML='';conditionRow.innerHTML='';cards.innerHTML='';destination.textContent='';route.hidden=true;return;}
  route.hidden=false;
  const s=summarize(cache.rows,hours,this.data.profile);
  const wind=windInfo(s.windiest?.weather||{});
  conditionRow.innerHTML=conditions(s.rows).map(c=>`<span class="weather-condition">${weatherIcon(c.kind)}<span>${esc(c.label)}</span></span>`).join('');
  summary.innerHTML=`<div class="weather-metric weather-temperature"><span class="weather-metric-label">${weatherIcon('temperature')}<span>Temperature</span></span><strong>${range(s.temperatureMin,s.temperatureMax,'°C')}</strong><small>Feels ${range(s.feelsMin,s.feelsMax,'°C')}</small></div><div class="weather-metric weather-rainfall"><span class="weather-metric-label">${weatherIcon('drop')}<span>Rain along plan</span></span><strong>${finite(s.rain)?'~'+s.rain.toFixed(1)+' <small>mm</small>':'Unavailable'}</strong><small>${finite(s.chanceMax)?'Up to '+round(s.chanceMax)+'% hourly chance':'Chance unavailable'}</small></div><div class="weather-wind-summary"><div class="weather-wind-top">${directionIcon(wind)}<div class="weather-wind-main"><span>Peak hourly wind</span><strong>${finite(s.windMax)?round(s.windMax)+' <small>km/h</small>':'Unavailable'}</strong><small>${esc(wind.from)}${wind.direction!==null?' · '+Math.round(wind.direction)+'°':''}</small></div></div><p class="weather-gust">Gusts up to <b>${finite(s.gustMax)?round(s.gustMax)+' km/h':'unavailable'}</b></p></div><div class="weather-terrain-summary">${weatherIcon('mountain')}<div><span>Highest ground</span><strong>${finite(s.elevationMax)?round(s.elevationMax)+' m':'Unavailable'}</strong></div><small>From ${round(s.elevationMin)} m on route</small></div>`;
  const last=s.rows.at(-1)?.sample;destination.textContent=last?`${last.finish?'Finish': 'By +'+hours+' h'} · ${clock(last.time,this.data.timezone)} · km ${last.km.toFixed(1)} · ${last.place} · ${Math.round(last.elevation)} m`:'';
  const selected=s.rows.filter(r=>r.sample.hour===0||r.sample.hour%3===0||r.sample.finish),available=s.available;
  cards.innerHTML=selected.map(({sample:p,weather:w})=>{const info=windInfo(w||{}),condition=weatherKind(w||{});return `<article class="weather-stop"><div class="weather-stop-place"><b class="weather-stop-time">${p.hour===0?'Start of outlook':p.finish?'Finish · +'+p.hour.toFixed(1)+' h':'+'+p.hour+' hours'} · ${clock(p.time,this.data.timezone)}</b><h3>${esc(p.place)}</h3><p class="small muted">km ${p.km.toFixed(1)} · ${Math.round(p.elevation)} m ${p.elevation>=900?'· high ground':p.elevation<200?'· lowland / coast':''}</p></div>${w?`<div class="weather-stop-forecast"><div class="weather-stop-sky">${weatherIcon(condition.kind)}<div><strong class="weather-temp">${finite(w.temperature)?round(w.temperature)+'°C':'Temp unavailable'}</strong><p>${esc(condition.label)}${w.day===0&&!condition.label.includes('night')?' · night':''}</p></div></div><p class="small weather-stop-feels">Feels ${finite(w.feels)?round(w.feels)+'°C':'unavailable'} · ${finite(w.chance)?round(w.chance)+'% rain chance':'rain chance unavailable'}</p><div class="weather-stop-wind">${directionIcon(info)}<div><p>${esc(info.from)} · ${finite(info.speed)?round(info.speed)+' km/h':'wind unavailable'}</p><p class="small muted">Gusts ${finite(info.gust)?round(info.gust)+' km/h':'unavailable'}</p></div></div></div>`:'<p>No forecast for this time yet.</p>'}</article>`;}).join('');
  this.el.querySelector('[data-weather-route-label]').textContent=`Along the route · ${selected.length} forecast stops`;
  this.el.querySelector('[data-weather-coverage]').textContent=`${available} of ${s.total} hourly route samples have forecast data.${cache.remaining<hours?' Outlook stops at your projected finish.':''}`;
 }
}
const api={HOUR,MAX_HOURS,CACHE_KEY,signature,routePoint,createPlan,forecastRange,requestURL,readLocation,readResponses,summarize,codeLabel,compass,windInfo,weatherKind,conditions,weatherIcon,Panel};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.RouteWeather=api;
})(typeof globalThis!=='undefined'?globalThis:this);
