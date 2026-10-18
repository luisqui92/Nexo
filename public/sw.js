// Keep API requests on the network. Only the application shell is cached.
const CACHE='nexo-shell-v9';
const BLACK_HOLE='https://cdn.eso.org/images/screen/eso1907a.jpg';
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(['/','/styles.css','/mobile.css','/app.js','/mobile.js','/transcription.js','/team.js','/team.css','/account.js','/account.css','/marketplace.js','/marketplace.css','/cosmic.css','/preparation.js','/presentacion.html','/presentation.css','/presentation.js','/mark.svg']))));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('nexo-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 if(event.request.method!=='GET')return;
 if(url.href===BLACK_HOLE){
  event.respondWith(caches.open(CACHE).then(async cache=>{
   const saved=await cache.match(event.request);if(saved)return saved;
   try{const response=await fetch(event.request);if(response.ok||response.type==='opaque'){try{await cache.put(event.request,response.clone())}catch{/* Storage may be disabled; the image still displays. */}}return response}
   catch{return new Response('',{status:503})}
  }));return;
 }
 if(url.origin!==self.location.origin||url.pathname.startsWith('/api')||url.pathname.startsWith('/signin')||url.pathname.startsWith('/signout'))return;
 if(!['/','/index.html','/styles.css','/mobile.css','/app.js','/mobile.js','/transcription.js','/team.js','/team.css','/account.js','/account.css','/marketplace.js','/marketplace.css','/cosmic.css','/preparation.js','/presentacion.html','/presentation.css','/presentation.js','/mark.svg','/manifest.webmanifest'].includes(url.pathname))return;
 event.respondWith(fetch(event.request).then(response=>{if(response.ok&&response.type==='basic'&&!response.redirected){const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(event.request,copy))}return response}).catch(()=>caches.match(event.request).then(cached=>cached||new Response('Nexo necesita conexión para abrir esta pantalla.',{status:503}))));
});
