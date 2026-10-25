/* Offline navigation cache: the HTML already embeds GPX, Leaflet and Trail Vision. */
const CACHE='canarias360-offline-e4cd373468e7';
const INDEX=new URL('index.html',self.registration.scope).href;
self.addEventListener('install',event=>event.waitUntil((async()=>{
 const cache=await caches.open(CACHE);await cache.add(new Request(INDEX,{cache:'reload'}));await self.skipWaiting();
})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{
 for(const name of await caches.keys())if(name.startsWith('canarias360-offline-')&&name!==CACHE)await caches.delete(name);
 await self.clients.claim();
})()));
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url),scope=new URL(self.registration.scope);
 if(event.request.method!=='GET'||event.request.mode!=='navigate'||url.origin!==scope.origin||![scope.pathname,scope.pathname+'index.html'].includes(url.pathname))return;
 event.respondWith((async()=>{
  const cache=await caches.open(CACHE),controller=new AbortController(),timer=setTimeout(()=>controller.abort(),3500);
  try{
   const response=await fetch(new Request(event.request,{signal:controller.signal}));
   if(response.ok){await cache.put(INDEX,response.clone());return response;}
   return await cache.match(INDEX)||response;
  }catch(error){const saved=await cache.match(INDEX);if(saved)return saved;return new Response('Offline copy unavailable. Connect once or open your saved HTML.',{status:503,headers:{'Content-Type':'text/plain'}});}
  finally{clearTimeout(timer);}
 })());
});
