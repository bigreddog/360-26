/* AEMET municipal forecasts: explicit town/height limits; never treated as a GPX grid. */
(function(root){
'use strict';
const HOUR=3600000,MAX_AGE=6*HOUR,MAX_DISTANCE=8000,MAX_HEIGHT=250;
const FEED='https://raw.githubusercontent.com/bigreddog/360-26/weather-data/aemet.json';
const finite=x=>typeof x==='number'&&Number.isFinite(x);
function distance(a,b){const r=Math.PI/180,x=(b.lon-a.lon)*r*Math.cos((a.lat+b.lat)/2*r),y=(b.lat-a.lat)*r;return 6371008.8*Math.hypot(x,y);}
function validFeed(feed){return feed?.version===1&&feed.provider==='aemet'&&Array.isArray(feed.towns)&&feed.towns.length<=50&&feed.towns.every(t=>typeof t.id==='string'&&typeof t.name==='string'&&finite(t.lat)&&finite(t.lon)&&finite(t.elevation)&&finite(t.fetchedAt)&&Array.isArray(t.hourly)&&t.hourly.length<=100&&t.hourly.every((r,i)=>finite(r.time)&&(!i||r.time>t.hourly[i-1].time))&&Array.isArray(t.probabilities));}
function eligible(town,sample,now){
 const separation=distance(town,sample),heightDelta=sample.elevation-town.elevation;
 return now-town.fetchedAt<=MAX_AGE&&now>=town.fetchedAt-5*60000&&separation<=MAX_DISTANCE&&Math.abs(heightDelta)<=MAX_HEIGHT?{town,separation,heightDelta,score:separation/2000+Math.abs(heightDelta)/100}:null;
}
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
 const weather={temperature:val('temperature',true),feels:val('feels',true),wind:val('wind',true),gust:finite(interval?.gust)?interval.gust:null,direction:val('direction'),code:val('code'),day:val('day'),rain:finite(interval?.rain)?interval.rain:null,chance:probability?.value??null,chanceHours:probability?.hours??null};
 if(!finite(weather.temperature))return null;
 return {...weather,source:{provider:'aemet',town:town.name,id:town.id,elevation:town.elevation,separation,heightDelta,issuedLocal:town.issuedLocal,fetchedAt:town.fetchedAt,url:town.url}};
}
function select(feed,sample,now){
 if(!validFeed(feed))return null;
 const matches=feed.towns.map(t=>eligible(t,sample,now)).filter(Boolean).sort((a,b)=>a.score-b.score||a.town.id.localeCompare(b.town.id));
 for(const match of matches){const weather=readTown(match,sample);if(weather)return weather;}
 return null;
}
function rows(feed,plan,now){return plan.samples.map(sample=>({sample,weather:select(feed,sample,now)}));}
function merge(aemet,fallback){return aemet.map((row,i)=>row.weather?row:{sample:row.sample,weather:fallback?.[i]?.weather?{...fallback[i].weather,source:{provider:'open-meteo'}}:null});}
function counts(rows){return {aemet:rows.filter(r=>r.weather?.source?.provider==='aemet').length,openMeteo:rows.filter(r=>r.weather&&(r.weather.source?.provider||'open-meteo')==='open-meteo').length,missing:rows.filter(r=>!r.weather).length};}
const api={HOUR,MAX_AGE,MAX_DISTANCE,MAX_HEIGHT,FEED,distance,validFeed,eligible,readTown,select,rows,merge,counts};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.AemetWeather=api;
})(typeof globalThis!=='undefined'?globalThis:this);
