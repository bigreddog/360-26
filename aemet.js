/* AEMET municipal forecasts: explicit town/height limits; never treated as a GPX grid. */
(function(root){
'use strict';
const HOUR=3600000,FRESH_AGE=6*HOUR,MAX_AGE=12*HOUR,POLICY_VERSION=4,MAX_DISTANCE=8000,MAX_HEIGHT=250;
const FEED='https://raw.githubusercontent.com/bigreddog/360-26/weather-data/aemet.json';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
function distance(a,b){const r=Math.PI/180,x=(b.lon-a.lon)*r*Math.cos((a.lat+b.lat)/2*r),y=(b.lat-a.lat)*r;return 6371008.8*Math.hypot(x,y);}
function validFeed(feed){return feed?.version===1&&feed.provider==='aemet'&&Array.isArray(feed.towns)&&feed.towns.length<=50&&feed.towns.every(t=>typeof t.id==='string'&&typeof t.name==='string'&&finite(t.lat)&&finite(t.lon)&&finite(t.elevation)&&finite(t.fetchedAt)&&Array.isArray(t.hourly)&&t.hourly.length<=100&&t.hourly.every((r,i)=>finite(r.time)&&(!i||r.time>t.hourly[i-1].time))&&Array.isArray(t.probabilities));}
function locationMatch(town,sample){
 const separation=distance(town,sample),heightDelta=sample.elevation-town.elevation;
 return separation<=MAX_DISTANCE&&Math.abs(heightDelta)<=MAX_HEIGHT?{town,separation,heightDelta,score:separation/2000+Math.abs(heightDelta)/100}:null;
}
function eligible(town,sample,now){return now-town.fetchedAt<=MAX_AGE&&now>=town.fetchedAt-5*60000?locationMatch(town,sample):null;}
function readTown(match,sample){
 const {town,separation,heightDelta}=match,rows=town.hourly,time=sample.time/1000;
 if(!rows.length||time<rows[0].time||time>rows.at(-1).time)return null;
 let a=0,b=rows.length-1;while(b-a>1){const m=(a+b)>>1;if(rows[m].time<=time)a=m;else b=m;}
 const left=rows[a],right=rows[b],gap=right.time-left.time;
 if(time!==left.time&&time!==right.time&&gap!==3600)return null;
 const f=(time-left.time)/(gap||1),nearest=f<=.5?left:right;
 const val=(key,linear=false)=>{if(!linear)return finite(nearest[key])?nearest[key]:null;if(f===0)return finite(left[key])?left[key]:null;if(f===1)return finite(right[key])?right[key]:null;return finite(left[key])&&finite(right[key])?left[key]+(right[key]-left[key])*f:null;};
 // Match the existing end-of-hour rain convention used by the moving-route sum.
 const rainHour=Math.floor((time-.001)/3600)*3600,interval=rows.find(r=>r.time===rainHour);
 const probability=town.probabilities.find(p=>time>=p.start&&time<p.end&&finite(p.value)&&p.value>=0&&p.value<=100);
 const weather={temperature:val('temperature',true),feels:val('feels',true),wind:val('wind',true),gust:finite(interval?.gust)?interval.gust:null,direction:val('direction'),code:val('code'),day:val('day'),rain:finite(interval?.rain)?interval.rain:null,rainTrace:interval?.rainTrace===true,chance:probability?.value??null,chanceHours:probability?.hours??null};
 if(!finite(weather.temperature))return null;
 return {...weather,rainFrom:rainHour*1000,rainUntil:(rainHour+3600)*1000,source:{provider:'aemet',town:town.name,id:town.id,elevation:town.elevation,separation,heightDelta,issuedLocal:town.issuedLocal,fetchedAt:town.fetchedAt,url:town.url}};
}
function select(feed,sample,now){
 if(!validFeed(feed))return null;
 // Prefer usable fresh towns before the bounded delayed-update tier.
 const matches=feed.towns.map(t=>eligible(t,sample,now)).filter(Boolean).sort((a,b)=>Number(now-a.town.fetchedAt>FRESH_AGE)-Number(now-b.town.fetchedAt>FRESH_AGE)||a.score-b.score||a.town.id.localeCompare(b.town.id));
 for(const match of matches){const weather=readTown(match,sample);if(weather)return weather;}
 return null;
}
function availability(feed,sample,now){
 if(!validFeed(feed)||!feed.towns.length)return {kind:'unavailable'};
 const nearby=feed.towns.map(t=>locationMatch(t,sample)).filter(Boolean).sort((a,b)=>a.score-b.score||a.town.id.localeCompare(b.town.id));
 if(!nearby.length)return {kind:'location'};
 const fresh=nearby.filter(m=>eligible(m.town,sample,now));
 if(!fresh.length)return {kind:'stale'};
 const weather=select(feed,sample,now);
 if(weather)return {kind:now-weather.source.fetchedAt>FRESH_AGE?'delayed':'covered',town:weather.source.town,fetchedAt:weather.source.fetchedAt};
 const ranges=fresh.map(m=>{const times=m.town.hourly.filter(r=>finite(r.temperature)).map(r=>r.time*1000);return times.length?{town:m.town.name,from:times[0],until:times.at(-1),fetchedAt:m.town.fetchedAt}:null;}).filter(Boolean);
 if(!ranges.length)return {kind:'gap'};
 const latest=ranges.reduce((a,b)=>b.until>a.until?b:a),earliest=ranges.reduce((a,b)=>b.from<a.from?b:a);
 if(sample.time>latest.until)return {kind:'after',...latest};
 if(sample.time<earliest.from)return {kind:'before',...earliest};
 return {kind:'gap'};
}
function rows(feed,plan,now){return plan.samples.map(sample=>({sample,weather:select(feed,sample,now)}));}
function merge(aemet,fallback){return aemet.map((row,i)=>row.weather?row:{sample:row.sample,weather:fallback?.[i]?.weather?{...fallback[i].weather,source:{provider:'open-meteo'}}:null});}
function counts(rows){return {aemet:rows.filter(r=>r.weather?.source?.provider==='aemet').length,openMeteo:rows.filter(r=>r.weather&&(r.weather.source?.provider||'open-meteo')==='open-meteo').length,missing:rows.filter(r=>!r.weather).length};}
function validOutlook(outlook){const stamp=t=>finite(t)&&Math.abs(t)<=8640000000000000;return outlook?.version===1&&Array.isArray(outlook.entries)&&outlook.entries.length<=8&&outlook.entries.every(b=>['Gran Canaria','Canary Islands'].includes(b.area)&&b.language==='es'&&stamp(b.from)&&stamp(b.until)&&b.until>b.from&&stamp(b.fetchedAt)&&typeof b.issuedLocal==='string'&&Array.isArray(b.paragraphs)&&b.paragraphs.length>0&&b.paragraphs.every(p=>typeof p==='string'&&p.length<=12000)&&Array.isArray(b.significant)&&b.significant.every(p=>typeof p==='string'&&p.length<=12000));}
function englishBulletin(b){if(!Array.isArray(b?.paragraphs)||!Array.isArray(b?.significant))return null;const e=b.english,strings=a=>Array.isArray(a)&&a.every(t=>typeof t==='string'&&t.trim().length>0&&t.length<=12000);return e?.version===1&&e.language==='en'&&['curated','machine'].includes(e.method)&&strings(e.paragraphs)&&e.paragraphs.length===b.paragraphs.length&&strings(e.significant)&&e.significant.length===b.significant.length&&JSON.stringify(e.sourceParagraphs)===JSON.stringify(b.paragraphs)&&JSON.stringify(e.sourceSignificant)===JSON.stringify(b.significant)?e:null;}
function outlookWindow(outlook,now){
 const end=now+72*HOUR;
 const entries=validOutlook(outlook)?outlook.entries.filter(b=>b.until>now&&b.from<end&&now-b.fetchedAt<=24*HOUR&&now>=b.fetchedAt-5*60000).sort((a,b)=>a.from-b.from):[];
 let cursor=now,covered=0;for(const b of entries){const from=Math.max(cursor,b.from),until=Math.min(end,b.until);if(until>from){covered+=until-from;cursor=until;}}
 return {entries,coveredHours:covered/HOUR,end};
}
function validAlerts(a){
 const stamp=x=>finite(x)&&Math.abs(x)<=8640000000000000,str=(x,max=12000)=>typeof x==='string'&&x.length<=max;
 return a?.version===1&&a.provider==='aemet'&&a.scope==='Gran Canaria'&&stamp(a.fetchedAt)&&stamp(a.issuedAt)&&stamp(a.coverageUntil)&&Array.isArray(a.entries)&&a.entries.length<=300&&a.entries.every(e=>str(e.id,1000)&&stamp(e.sent)&&stamp(e.from)&&stamp(e.until)&&e.until>e.from&&['yellow','orange','red'].includes(e.level)&&str(e.event,1000)&&str(e.eventCode,30)&&str(e.zone,100)&&str(e.area,1000)&&Array.isArray(e.parameters)&&e.parameters.length<=10&&e.parameters.every(p=>str(p.code,30)&&str(p.label,1000)&&str(p.value,1000))&&str(e.descriptionOriginal)&&str(e.descriptionOfficialEnglish)&&str(e.instruction)&&typeof e.sourceUrl==='string'&&/^https:\/\/www\.aemet\.es\/documentos_d\/eltiempo\/prediccion\/avisos\/cap\/[A-Za-z0-9_.-]+\.xml$/.test(e.sourceUrl));
}
function alertWindow(a,now){
 const valid=validAlerts(a),age=valid?now-a.fetchedAt:Infinity,usable=valid&&age>=-5*60000;
 const entries=usable?a.entries.filter(e=>e.until>now&&e.from<now+72*HOUR).sort((a,b)=>({red:3,orange:2,yellow:1}[b.level]-{red:3,orange:2,yellow:1}[a.level])||Number(a.from>now)-Number(b.from>now)||a.from-b.from):[];
 return {entries,available:usable&&a.coverageUntil>now&&age<=6*HOUR&&!a.error,stale:usable&&age>6*HOUR,delayed:usable&&age>2*HOUR,error:!usable||!!a.error,coverageUntil:usable?a.coverageUntil:null,fetchedAt:usable?a.fetchedAt:null};
}
const api={HOUR,FRESH_AGE,MAX_AGE,POLICY_VERSION,MAX_DISTANCE,MAX_HEIGHT,FEED,distance,validFeed,eligible,readTown,select,availability,rows,merge,counts,validOutlook,englishBulletin,outlookWindow,validAlerts,alertWindow};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.AemetWeather=api;
})(typeof globalThis!=='undefined'?globalThis:this);
