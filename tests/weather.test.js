const assert=require('node:assert/strict'),W=require('../weather.js'),E=require('../engine.js'),D=require('../data/roadbook_data.json');let passed=0;
const state={quotas:[85,70,60,50],progressKm:0,elapsedHours:0,anchorLive:false,extraHours:0,terrainWeight:1};const start=Date.parse(D.start),now=start-24*W.HOUR;
function test(name,fn){fn();console.log('ok',++passed,'-',name);}
const plan=W.createPlan(D,state,now,E);
function payload(p){return p.samples.map((s,i)=>{const first=Math.floor(p.base/W.HOUR)*W.HOUR/1000,n=28,time=Array.from({length:n},(_,j)=>first+j*3600);return {hourly:{time,temperature_2m:time.map(()=>20-i*.5),apparent_temperature:time.map(()=>18-i*.5),precipitation_probability:time.map(()=>i*2),precipitation:time.map(()=>.2),weather_code:time.map(()=>i<8?0:61),wind_speed_10m:time.map(()=>10+i),wind_gusts_10m:time.map(()=>20+i),wind_direction_10m:time.map(()=>0),is_day:time.map(()=>1)}};});}
test('pre-race forecast begins at the race start, not today',()=>assert.equal(plan.base,start));
test('12 and 24-hour horizons share twenty-five hourly projected points',()=>{assert.equal(plan.samples.length,25);for(const h of [12,24])assert.equal(W.summarize(W.readResponses(payload(plan),plan),h).rows.length,h+1);});
test('projected positions follow the existing climb-weighted pace curve',()=>{for(const p of plan.samples)assert(Math.abs(E.etaHours(D,p.km,state.quotas,state.terrainWeight)-p.hour)<1e-7);});
test('latitude/longitude and elevation move with the actual course',()=>{const a=plan.samples[0],b=plan.samples[24];assert.notEqual(a.lat,b.lat);assert.notEqual(a.lon,b.lon);assert.notEqual(a.elevation,b.elevation);assert.equal(a.elevation,E.interp(D.profile,a.km,1));});
test('current route progress anchors future locations at the current time',()=>{const n=start+40*W.HOUR,p=W.createPlan(D,{...state,progressKm:100},n,E);assert.equal(p.base,n);assert.equal(p.samples[0].km,100);assert(p.samples[6].km>100);});
test('manual future elapsed time can preview a later race stage',()=>{const p=W.createPlan(D,{...state,anchorLive:true,elapsedHours:48,progressKm:150},now,E);assert.equal(p.base,start+48*W.HOUR);assert.equal(p.samples[0].km,150);});
test('extra delay holds route position before movement resumes',()=>{const p=W.createPlan(D,{...state,extraHours:3,progressKm:50},now,E);for(const x of p.samples.slice(0,4))assert(Math.abs(x.km-50)<1e-7);assert(p.samples[4].km>50);});
test('outlook stops at the exact projected finish without inventing onward travel',()=>{const p=W.createPlan(D,{...state,progressKm:D.distance_km-4},now,E);assert(p.remaining<6);assert(p.samples.at(-1).finish);assert(Math.abs(p.samples.at(-1).km-D.distance_km)<.000001);assert(p.samples.every(x=>x.km<=D.distance_km));});
test('completed course has no upcoming forecast even with delay set',()=>assert.equal(W.createPlan(D,{...state,progressKm:D.distance_km,extraHours:3},now,E).remaining,0));
test('API request includes changing coordinates and GPX elevations',()=>{const u=new URL(W.requestURL(plan));assert.equal(u.searchParams.get('latitude').split(',').length,25);assert.equal(u.searchParams.get('elevation').split(',')[6],String(Math.round(plan.samples[6].elevation)));assert.equal(u.searchParams.get('timeformat'),'unixtime');assert.equal(u.searchParams.get('wind_speed_unit'),'kmh');assert.equal(u.searchParams.get('cell_selection'),'land');});
test('forecast date availability respects a sixteen-day provider limit',()=>{assert(W.forecastRange(plan,now));assert(!W.forecastRange(plan,start-20*24*W.HOUR));});
test('request end is clipped at the provider limit for partial windows',()=>{const n=start-15*24*W.HOUR,p=W.createPlan(D,state,n,E),u=new URL(W.requestURL(p));assert(Date.parse(u.searchParams.get('end_hour')+'Z')<Math.floor(n/(24*W.HOUR))*24*W.HOUR+16*24*W.HOUR);});
test('each projected point reads its own location forecast',()=>{const rows=W.readResponses(payload(plan),plan);assert.equal(rows[0].weather.temperature,20);assert.equal(rows[24].weather.temperature,8);});
test('temperature is interpolated in time without interpolating weather codes',()=>{const p={time:1500*1000},r={hourly:{time:[1000,2000],temperature_2m:[10,20],weather_code:[0,61]}};assert.equal(W.readLocation(r,p).temperature,15);assert.equal(W.readLocation(r,p).code,0);});
test('missing fields and nulls remain unavailable rather than becoming zero',()=>{const x=payload(plan);x[0].hourly.precipitation_probability.fill(null);assert.equal(W.readResponses(x,plan)[0].weather.chance,null);});
test('past and beyond-horizon data are never extrapolated',()=>{const r={hourly:{time:[1000,2000],temperature_2m:[10,20]}};assert.equal(W.readLocation(r,{time:2100*1000}),null);assert.equal(W.readLocation(r,{time:900*1000}),null);});
test('missing a location response cannot misalign forecasts with route points',()=>assert.throws(()=>W.readResponses(payload(plan).slice(1),plan),/incomplete/));
test('malformed timestamps cannot be read as valid weather',()=>assert.equal(W.readLocation({hourly:{time:['bad'],temperature_2m:[20]}},plan.samples[0]),null));
test('summary rainfall excludes the preceding hour at the starting point',()=>{const s=W.summarize(W.readResponses(payload(plan),plan),6);assert(Math.abs(s.rain-1.2)<1e-8);});
test('rainfall is unavailable if any future hour is missing',()=>{const x=payload(plan);x[3].hourly.precipitation.fill(null);assert.equal(W.summarize(W.readResponses(x,plan),6).rain,null);});
test('fractional final hour only contributes its fraction of rainfall',()=>{const rows=[{sample:{hour:0,elevation:0},weather:{rain:10}},{sample:{hour:1,elevation:0},weather:{rain:2}},{sample:{hour:1.25,elevation:0},weather:{rain:2}}];assert.equal(W.summarize(rows,6).rain,2.5);});
test('trace rain adds an explicit trace label to known amounts without inventing a total',()=>{
 const rows=[{sample:{hour:0},weather:{rain:100}},{sample:{hour:1},weather:{rain:2}},{sample:{hour:2},weather:{rain:null,rainTrace:true}}],s=W.summarize(rows,12);
 assert.equal(s.rain,null);assert.equal(s.rainKnown,2);assert.equal(s.rainTraceHours,1);
 assert.match(W.rainSummary(s).html,/2.0.*mm \+ trace/);assert.match(W.rainSummary(s).note,/less than 0.1 mm/);
 rows[1].weather.rain=null;assert.equal(W.summarize(rows,12).rainKnown,null);assert.equal(W.rainSummary(W.summarize(rows,12)).html,'Unavailable');
});
test('trace-only forecast and fractional finish stay explicit, not zero or unavailable',()=>{
 const rows=[{sample:{hour:0},weather:{rain:1}},{sample:{hour:.25},weather:{rain:null,rainTrace:true}}],s=W.summarize(rows,12);
 assert.equal(s.rain,null);assert.equal(s.rainKnown,0);assert.equal(s.rainTraceHours,.25);assert.equal(W.rainSummary(s).html,'Trace only');
});
test('trace in the hour before the outlook is excluded from the sum',()=>{
 const rows=[{sample:{hour:0},weather:{rain:null,rainTrace:true}},{sample:{hour:1},weather:{rain:0}}],s=W.summarize(rows,12);
 assert.equal(s.rainTraceHours,0);assert.equal(s.rain,0);assert.equal(W.rainSummary(s).html,'~0.0 <small>mm</small>');
});
test('fractional forecast time reads accumulated rain from its containing hour',()=>{
 const h=Date.parse('2026-11-04T09:00:00Z'),response={hourly:{time:[h/1000,h/1000+3600],precipitation:[1,3]}};
 const w=W.readLocation(response,{time:h+15*60000});assert.equal(w.rain,3);assert.equal(w.rainFrom,h);assert.equal(w.rainUntil,h+W.HOUR);
 assert.equal(W.readLocation(response,{time:h}).rain,1);
 response.hourly.precipitation[1]=null;assert.equal(W.readLocation(response,{time:h+15*60000}),null);
});
test('rain points distinguish zero, trace and missing amounts and label the actual interval',()=>{
 const p={hour:3,time:Date.parse('2026-11-04T12:00:00Z')},w={rain:0,rainFrom:p.time-W.HOUR,rainUntil:p.time};
 assert.equal(W.rainPoint(w,p,'Atlantic/Canary').amount,'0.0 mm');assert.match(W.rainPoint(w,p,'Atlantic/Canary').period,/11:00.*12:00/);
 assert.equal(W.rainPoint({rain:null,rainTrace:true},p,'Atlantic/Canary').amount,'Trace (<0.1 mm)');assert.equal(W.rainPoint({},p,'Atlantic/Canary').amount,'Unavailable');
 assert(W.rainPoint(w,{...p,hour:0},'Atlantic/Canary').beforeOutlook);
});
test('legacy offline rain points keep their original provider interval convention',()=>{
 const p={hour:1,time:Date.parse('2026-11-04T09:15:00Z')};
 assert.equal(W.rainPoint({source:{provider:'open-meteo'}},p,'Atlantic/Canary').until,Date.parse('2026-11-04T09:00:00Z'));
 assert.equal(W.rainPoint({source:{provider:'aemet'}},p,'Atlantic/Canary').until,Date.parse('2026-11-04T10:00:00Z'));
});
test('hourly audit includes only contributing intervals and escapes source/place names',()=>{
 const rows=[0,1,2,3].map(hour=>({sample:{hour,time:Date.parse('2026-11-04T09:00:00Z')+hour*W.HOUR,km:hour,place:'<test>'},weather:{rain:.1,chance:100,source:{provider:'aemet',town:'A&B'}}}));
 const html=W.hourlyRainHTML(rows,2,'Atlantic/Canary');assert.equal((html.match(/<li>/g)||[]).length,2);assert(!html.includes('<test>'));assert(html.includes('&lt;test&gt;'));assert(html.includes('A&amp;B'));
 assert.equal(W.summarize(rows,3).rain,.1*3);
});
test('real 3 November route audit reconciles the small 24-hour amount without scaling by probability',()=>{
 const audit=require('../docs/rainfall-audit-20261103.json'),s=W.summarize(audit.rows,24);
 assert(Math.abs(s.rainKnown-.6)<1e-9);assert.equal(s.rainTraceHours,1);
 const numeric=s.rows.filter(r=>r.sample.hour>0&&r.weather?.rain>0);assert.deepEqual(numeric.map(r=>r.weather.rain),[.1,.3,.2]);
 assert.equal(audit.rows[0].weather.source.town,'Gáldar');assert.equal(audit.rows[0].weather.rain,.1);
});
test('temperature ranges, hourly chance maxima and gusts cover the chosen window',()=>{const s=W.summarize(W.readResponses(payload(plan),plan),6);assert.equal(s.temperatureMin,17);assert.equal(s.temperatureMax,20);assert.equal(s.gustMax,26);assert.equal(s.chanceMax,12);});
test('null probability and calm zero wind are distinguished',()=>{assert.equal(W.compass(0),'N');assert.equal(W.compass(null),'');assert.equal(W.compass(360),'N');});
test('standard weather codes are labelled while unsupported codes remain unknown',()=>{assert.equal(W.codeLabel(45),'Fog');assert.equal(W.codeLabel(95),'Thunderstorm signal');assert.equal(W.codeLabel(999),'Conditions unavailable');assert.equal(W.codeLabel(null),'Conditions unavailable');});
test('terrain height includes a crest between hourly forecast points',()=>{const rows=[{sample:{hour:0,km:0,elevation:100},weather:{}},{sample:{hour:1,km:2,elevation:200},weather:{}}];assert.equal(W.summarize(rows,6,[[0,100],[1,600],[2,200]]).elevationMax,600);});
test('pre-race stage preview uses the planned arrival time at that kilometre',()=>{const p=W.createPlan(D,{...state,progressKm:100},now,E);assert.equal(p.base,start+E.etaHours(D,100,state.quotas,state.terrainWeight)*W.HOUR);});
test('wind direction uses sixteen compass points and wraps at north',()=>{assert.equal(W.compass(22.5),'NNE');assert.equal(W.compass(67.5),'ENE');assert.equal(W.compass(-90),'W');assert.equal(W.compass(360),'N');});
test('summary wind direction belongs to peak hourly wind, independently of gust maximum',()=>{const rows=[{sample:{hour:0,elevation:0},weather:{wind:35,direction:45,gust:40}},{sample:{hour:1,elevation:0},weather:{wind:15,direction:270,gust:70}}],s=W.summarize(rows,6);assert.equal(s.windMax,35);assert.equal(s.gustMax,70);assert.equal(s.windiest.weather.direction,45);assert.equal(W.windInfo(s.windiest.weather).from,'From NE');});
test('calm winds have no prevailing direction and missing speed stays unavailable',()=>{const calm=W.windInfo({wind:0,direction:0});assert(calm.calm);assert.equal(calm.direction,null);assert.match(calm.from,/no prevailing direction/);const missing=W.windInfo({wind:null,gust:20});assert.equal(missing.speed,null);assert.equal(missing.direction,null);assert.equal(missing.gust,20);assert.match(missing.from,/unavailable/);});
test('weather icons distinguish clear and partly-cloudy nights from daytime',()=>{assert.equal(W.weatherKind({code:0,day:1}).kind,'sun');assert.equal(W.weatherKind({code:0,day:0}).kind,'moon');assert.equal(W.weatherKind({code:2,day:0}).kind,'partly-night');assert.equal(W.weatherKind({code:2,day:1}).kind,'partly-day');});
test('rain, fog, snow, ice, storms and unknown conditions get corresponding icons',()=>{for(const [code,kind] of [[61,'rain'],[45,'fog'],[75,'snow'],[66,'ice'],[95,'storm'],[999,'unknown'],[null,'unknown']])assert.equal(W.weatherKind({code}).kind,kind);});
test('condition strip keeps a storm signal visible in a mixed outlook',()=>{const rows=[0,1,3,45,95].map(code=>({weather:{code,day:1}}));const result=W.conditions(rows);assert.equal(result.length,3);assert(result.some(c=>c.kind==='storm'));assert.equal(W.conditions([{weather:null}])[0].kind,'unknown');});
test('weather illustrations are embedded decorative SVG with visible text provided separately',()=>{const icon=W.weatherIcon('sun');assert(icon.includes('<svg'));assert(icon.includes('aria-hidden="true"'));assert(!/(?:href|src)=["']https?:|<img/.test(icon));assert(W.weatherIcon('invalid').includes('data-weather-icon="unknown"'));});
console.log(`${passed} route-weather tests passed`);
