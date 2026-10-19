'use strict';
const portalEsc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const portalMoney=(price,currency)=>`${currency==='BOB'?'Bs':'USD'} ${new Intl.NumberFormat('es-BO',{maximumFractionDigits:0}).format(Number(price)||0)}`;
const portalEl=id=>document.getElementById(id);
let portalMap,portalMarkers,portalConfig,portalListings=[],portalPage=1,portalBounds=null,portalRequestVersion=0,portalSelected=null,portalDialogReturnFocus=null,portalDetailVersion=0;
let portalDebounce;
const portalExampleMode=new URLSearchParams(location.search||'').get('ejemplos')==='1'||location.pathname.startsWith('/inmueble/ejemplo-casa-');
async function portalApi(path,options={}){
  let response;try{response=await fetch(path,{...options,headers:{...(options.body?{'Content-Type':'application/json'}:{}),...options.headers}})}catch{throw Error('No pudimos conectar con Nexo. Revisá tu conexión y volvé a intentar.')}
  let data;try{data=await response.json()}catch{throw Error('No pudimos leer la respuesta. Volvé a intentar.')}
  if(!response.ok)throw Error(data.error||'No pudimos completar la solicitud.');return data;
}
function portalCard(p){
  return `<button type="button" class="listing-card ${p.id===portalSelected?'selected':''}" data-listing="${portalEsc(p.id)}">${p.photos[0]?`<img src="${portalEsc(p.photos[0])}" alt="${portalEsc(p.title)}" loading="lazy">`:''}${p.isExample?'<span class="example-badge">EJEMPLO · DATOS FICTICIOS</span>':''}<span class="listing-tag">${portalEsc(p.operation)} · ${portalEsc(p.type)}</span><div class="listing-price">${portalMoney(p.price,p.currency)}${p.operation==='Alquiler'?'<small> / mes</small>':''}</div><h2>${portalEsc(p.title)}</h2><p>${portalEsc(p.zone)} · ${portalEsc(p.city)}</p><p>${Number(p.bedrooms)||0} dormitorios · ${Number(p.area)||0} m²</p><p class="listing-publisher">${portalEsc(p.publisher.company||p.publisher.name)}</p></button>`;
}
function portalMapInit(){
  if(!window.L){portalEl('mapNotice').textContent='No se pudo cargar el mapa. Podés explorar las fichas en la vista Lista.';return}
  portalMap=L.map('publicMap',{scrollWheelZoom:false}).setView(portalConfig.center,portalConfig.zoom);
  L.tileLayer(portalConfig.tileUrl,{maxZoom:19,attribution:`&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> · ${portalEsc(portalConfig.tileProvider)}`}).addTo(portalMap).on('tileerror',()=>{portalEl('mapNotice').textContent='No se pudo cargar parte del mapa. Las fichas siguen disponibles.'});
  portalMarkers=typeof L.markerClusterGroup==='function'?L.markerClusterGroup({showCoverageOnHover:false,maxClusterRadius:50,iconCreateFunction:cluster=>L.divIcon({html:String(cluster.getChildCount()),className:'portal-cluster',iconSize:[40,40]})}):L.layerGroup();portalMap.addLayer(portalMarkers);
  portalMap.on('dragend',()=>{portalEl('searchMapArea').hidden=false});
}
function portalPaintMap(fit=false){
  if(!portalMap)return;portalMarkers.clearLayers();
  const points=[];
  for(const p of portalListings){
    const point=[p.latitude,p.longitude];points.push(point);
    const marker=L.marker(point,{title:(p.isExample?'Ejemplo: ':'')+p.title,keyboard:true,icon:L.divIcon({className:'price-marker '+(p.operation==='Alquiler'?'rental':''),html:`<span>${p.isExample?'<small class="example-marker-label">EJEMPLO</small>':''}${portalMoney(p.price,p.currency)}${p.operation==='Alquiler'?'/mes':''}</span>`,iconSize:[100,36],iconAnchor:[30,4]})});
    marker.on('click',()=>portalOpenListing(p.id));portalMarkers.addLayer(marker);
  }
  if(fit&&points.length)portalMap.fitBounds(points,{padding:[55,55],maxZoom:14});
}
async function portalSearch(fit=false){
  const version=++portalRequestVersion,status=portalEl('portalStatus');status.textContent='Buscando inmuebles…';
  const params=new URLSearchParams();for(const [key,value] of new FormData(portalEl('portalFilters')))if(value)params.set(key,value);
  params.set('page',portalPage);params.set('limit',48);
  const publisher=location.pathname.startsWith('/asesor/')?location.pathname.split('/')[2]:null;if(publisher)params.set('publisher',publisher);
  if(portalBounds)for(const [key,value] of Object.entries(portalBounds))params.set(key,value);
  try{
    const result=await portalApi((portalExampleMode?'/api/public/examples?':'/api/public/listings?')+params);if(version!==portalRequestVersion)return;
    portalListings=result.listings;
    status.textContent=portalExampleMode?`${result.total} casas de ejemplo · Datos ficticios`:`${result.total} ${result.total===1?'inmueble publicado':'inmuebles publicados'}${result.total>result.limit?' · Página '+result.page:''}${publisher?' · Perfil del anunciante':''}`;
    portalEl('listingResults').innerHTML=result.listings.map(portalCard).join('')||(portalExampleMode?'<div class="portal-empty"><h2>Ningún ejemplo coincide con estos filtros.</h2><p>Probá otra moneda, zona o cantidad de dormitorios.</p><a class="portal-button outline" href="/explorar?ejemplos=1">Ver los seis ejemplos</a></div>':'<div class="portal-empty"><h2>No hay inmuebles para esta búsqueda.</h2><p>Probá otra zona o ajustá los filtros. Las propiedades aparecen cuando su responsable las publica.</p><a class="portal-button outline" href="/registro">Publicar un inmueble</a></div>');
    portalEl('portalPagination').innerHTML=`${result.page>1?'<button type="button" data-page="prev">Anterior</button>':''}${result.page*result.limit<result.total?'<button type="button" data-page="next">Siguiente</button>':''}`;
    portalPaintMap(fit);
  }catch(error){if(version!==portalRequestVersion)return;status.innerHTML=`<span class="portal-error">${portalEsc(error.message)}</span> <button type="button" class="portal-reset" data-retry>Reintentar</button>`}
}
function portalCloseDialog(){
  ++portalDetailVersion;portalEl('portalDialogRoot').innerHTML='';document.body.style.overflow='';portalDialogReturnFocus?.focus();
}
function portalDialog(title,body){
  portalDialogReturnFocus=document.activeElement;
  portalEl('portalDialogRoot').innerHTML=`<div class="portal-dialog-backdrop"><section class="portal-dialog" role="dialog" aria-modal="true" aria-label="${portalEsc(title)}"><header class="portal-dialog-header"><h2>${portalEsc(title)}</h2><button type="button" class="portal-close" data-close-dialog aria-label="Cerrar">×</button></header>${body}</section></div>`;
  document.body.style.overflow='hidden';portalEl('portalDialogRoot').querySelector('[data-close-dialog]')?.focus();
}
async function portalOpenListing(id){
  const version=++portalDetailVersion;
  try{
    const p=await portalApi((id.startsWith('ejemplo-casa-')?'/api/public/examples/':'/api/public/listings/')+encodeURIComponent(id));if(version!==portalDetailVersion)return;portalSelected=p.id;
    if(p.isExample){portalExampleDialog(p);return}
    const contact=`https://wa.me/${p.publisher.phone}?text=${encodeURIComponent('Hola, me interesa '+p.title+'. '+location.origin+'/inmueble/'+p.id)}`;
    portalDialog(p.title,`<div class="portal-detail"><div>${p.photos[0]?`<img id="detailMainPhoto" class="detail-photo" src="${portalEsc(p.photos[0])}" alt="${portalEsc(p.title)}">`:''}<div class="photo-thumbnails">${p.photos.map((url,i)=>`<button type="button" data-photo="${portalEsc(url)}" aria-label="Ver foto ${i+1}"><img src="${portalEsc(url)}" alt="Foto ${i+1}" loading="lazy"></button>`).join('')}</div><p class="detail-location">Ubicación aproximada · ${portalEsc(p.zone)}, ${portalEsc(p.city)}</p></div><div><p class="portal-eyebrow">${portalEsc(p.operation)} · ${portalEsc(p.type)}</p><div class="listing-price">${portalMoney(p.price,p.currency)}${p.operation==='Alquiler'?'<small> / mes</small>':''}</div><h1>${portalEsc(p.title)}</h1><div class="detail-facts"><span>${p.bedrooms} dormitorios</span><span>${p.bathrooms} baños</span><span>${p.area} m²</span><span>${p.parking} estacionamientos</span></div><p class="detail-description">${portalEsc(p.description)}</p><p class="detail-description">${(p.features||[]).map(portalEsc).join(' · ')}</p><section class="publisher-card"><strong>${portalEsc(p.publisher.name)}</strong><small>${portalEsc(p.publisher.title||'Responsable de la publicación')} · ${portalEsc(p.publisher.company)}</small><div class="publisher-actions"><a class="portal-button" href="${contact}" target="_blank" rel="noopener noreferrer">Contactar por WhatsApp</a><button class="portal-button outline" type="button" data-request-visit>Solicitar visita</button></div><div class="detail-actions"><a href="/asesor/${encodeURIComponent(p.publisher.id)}">Ver publicaciones del anunciante</a><button type="button" data-share-listing>Compartir</button><button type="button" data-report-listing>Reportar publicación</button></div></section></div></div><section id="portalContactArea" class="portal-request" hidden></section>`);
    const root=portalEl('portalDialogRoot');root.querySelector('[data-request-visit]').onclick=()=>portalVisitForm(p);
    root.querySelector('[data-report-listing]').onclick=()=>portalReportForm(p);
    root.querySelector('[data-share-listing]').onclick=async()=>{const url=location.origin+'/inmueble/'+p.id;try{if(navigator.share)await navigator.share({title:p.title,url});else if(navigator.clipboard){await navigator.clipboard.writeText(url);root.querySelector('[data-share-listing]').textContent='Enlace copiado'}else window.prompt('Copiá el enlace del inmueble:',url)}catch{/* Canceling the system share sheet leaves the listing open. */}};
    if(portalMap){if(!portalListings.some(item=>item.id===p.id))portalMarkers.addLayer(L.marker([p.latitude,p.longitude],{title:p.title,icon:L.divIcon({className:'price-marker',html:'<span>'+portalMoney(p.price,p.currency)+'</span>',iconSize:[100,36]})}).on('click',()=>portalOpenListing(p.id)));portalMap.panTo([p.latitude,p.longitude])}
  }catch(error){if(version!==portalDetailVersion)return;portalDialog('Publicación no disponible',`<div class="portal-empty"><p>${portalEsc(error.message)}</p><a class="portal-button outline" href="/explorar">Volver a explorar</a></div>`)}
}
function portalExampleDialog(p){
  portalDialog('Casa de ejemplo · '+p.zone,`<div class="portal-detail"><div><img class="detail-photo" src="${portalEsc(p.photos[0])}" alt="Ilustración de ${portalEsc(p.title)}"><p class="detail-location">Punto ilustrativo · ${portalEsc(p.zone)}, ${portalEsc(p.city)}. No identifica una casa real.</p></div><div><span class="example-badge">EJEMPLO · NO ES UNA OFERTA REAL</span><p class="portal-eyebrow">${portalEsc(p.operation)} · Casa</p><div class="listing-price">${portalMoney(p.price,p.currency)}${p.operation==='Alquiler'?'<small> / mes</small>':''}</div><h1>${portalEsc(p.title)}</h1><div class="detail-facts"><span>${Number(p.bedrooms)} dormitorios</span><span>${Number(p.bathrooms)} baños</span><span>${Number(p.area)} m²</span><span>${Number(p.parking)} estacionamientos</span></div><p class="detail-description">${portalEsc(p.description)}</p><p class="detail-description">${p.features.map(portalEsc).join(' · ')}</p><div class="example-detail-note">Este ejemplo permite probar los filtros y recorrer el mapa. No recibe consultas ni solicitudes de visita.</div><div class="publisher-actions"><button type="button" class="portal-button" data-close-dialog>Seguir explorando</button><a class="portal-button outline" href="/explorar">Ver inmuebles reales</a></div><a class="example-share-link" href="/inmueble/${encodeURIComponent(p.id)}?ejemplos=1" target="_blank" rel="noopener">Enlace a esta casa de ejemplo ↗</a></div></div>`);
  if(portalMap)portalMap.panTo([p.latitude,p.longitude]);
}
function portalVisitForm(p){
  if(p.isExample)return;
  const area=portalEl('portalContactArea');area.hidden=false;
  area.innerHTML=`<h3>Solicitar una visita</h3><p>El responsable del inmueble te contactará para confirmar disponibilidad y horario.</p><form id="publicInquiryForm"><label>Nombre y apellido<input name="name" required maxlength="120" autocomplete="name"></label><label>Teléfono con código de país<input name="phone" type="tel" required maxlength="40" placeholder="591…" autocomplete="tel"></label><label>Horario que preferís (opcional)<input name="preferredDate" type="datetime-local"></label><label>Mensaje<textarea name="message" maxlength="2000" placeholder="Contale qué te interesa de este inmueble…"></textarea></label><label class="registration-honeypot" aria-hidden="true">Sitio web<input name="website" tabindex="-1" autocomplete="off"></label><label class="consent-row"><input name="consent" type="checkbox" required><span>Autorizo compartir estos datos con ${portalEsc(p.publisher.name)} y su inmobiliaria para atender mi solicitud.</span></label><p class="portal-error" role="alert"></p><button class="portal-button" type="submit">Enviar solicitud</button></form>`;
  area.scrollIntoView({behavior:'smooth',block:'start'});area.querySelector('input').focus();
  area.querySelector('form').onsubmit=async event=>{
    event.preventDefault();const form=event.target,submit=form.querySelector('[type=submit]');submit.disabled=true;
    try{const data=Object.fromEntries(new FormData(form));data.consent=form.elements.consent.checked;const result=await portalApi('/api/public/listings/'+p.id+'/inquiries',{method:'POST',body:JSON.stringify(data)});area.innerHTML=`<h3>Recibimos tu solicitud</h3><p class="portal-success">${portalEsc(result.message)}</p>`}
    catch(error){form.querySelector('[role=alert]').textContent=error.message;submit.disabled=false}
  };
}
function portalReportForm(p){
  if(p.isExample)return;
  const area=portalEl('portalContactArea');area.hidden=false;area.innerHTML=`<h3>Reportar publicación</h3><form><label>Motivo<select name="reason"><option>Información incorrecta</option><option>Posible fraude</option><option>Ya no está disponible</option><option>Otro</option></select></label><label>Detalle<textarea name="details" maxlength="1000"></textarea></label><p class="portal-error" role="alert"></p><button class="portal-button" type="submit">Enviar reporte</button></form>`;area.scrollIntoView({behavior:'smooth',block:'start'});
  area.querySelector('form').onsubmit=async event=>{event.preventDefault();const form=event.target,submit=form.querySelector('[type=submit]');submit.disabled=true;try{await portalApi('/api/public/listings/'+p.id+'/report',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(form)))});area.innerHTML='<p class="portal-success">Recibimos tu reporte. La administración de Nexo lo revisará.</p>'}catch(error){form.querySelector('[role=alert]').textContent=error.message;submit.disabled=false}};
}
portalEl('portalFilters').addEventListener('submit',event=>{event.preventDefault();portalPage=1;portalBounds=null;portalEl('searchMapArea').hidden=true;portalSearch(true)});
portalEl('portalFilters').addEventListener('input',event=>{portalEl('portalFilters').elements.currency.required=!!portalEl('portalFilters').elements.maxPrice.value;if(event.target.name!=='q')return;clearTimeout(portalDebounce);portalDebounce=setTimeout(()=>{portalPage=1;portalSearch(true)},450)});
portalEl('portalFilters').addEventListener('reset',()=>{clearTimeout(portalDebounce);setTimeout(()=>{portalPage=1;portalBounds=null;portalEl('portalFilters').elements.currency.required=false;portalEl('searchMapArea').hidden=true;portalSearch(true)},0)});
portalEl('searchMapArea').onclick=()=>{if(!portalMap)return;const b=portalMap.getBounds();portalBounds={south:b.getSouth(),north:b.getNorth(),west:Math.max(-180,b.getWest()),east:Math.min(180,b.getEast())};portalPage=1;portalEl('searchMapArea').hidden=true;portalSearch()};
for(const mode of ['map','list'])portalEl(mode+'View').onclick=()=>{portalEl('portalLayout').classList.toggle('list-mode',mode==='list');portalEl('mapView').setAttribute('aria-pressed',String(mode==='map'));portalEl('listView').setAttribute('aria-pressed',String(mode==='list'));if(mode==='map')setTimeout(()=>portalMap?.invalidateSize(),0)};
document.addEventListener('click',event=>{
  const card=event.target.closest('[data-listing]');if(card)portalOpenListing(card.dataset.listing);
  if(event.target.closest('[data-close-dialog]')||event.target.classList.contains('portal-dialog-backdrop'))portalCloseDialog();
  const photo=event.target.closest('[data-photo]');if(photo&&portalEl('detailMainPhoto'))portalEl('detailMainPhoto').src=photo.dataset.photo;
  const page=event.target.closest('[data-page]');if(page){portalPage+=page.dataset.page==='next'?1:-1;portalSearch(true)}
  if(event.target.closest('[data-retry]'))portalSearch(true);
});
document.addEventListener('keydown',event=>{
  const root=portalEl('portalDialogRoot');if(!root.firstElementChild)return;
  if(event.key==='Escape')portalCloseDialog();
  if(event.key==='Tab'){const targets=[...root.querySelectorAll('a[href],button,input,select,textarea')].filter(n=>!n.disabled&&n.getClientRects().length);if(event.shiftKey&&document.activeElement===targets[0]){event.preventDefault();targets.at(-1)?.focus()}else if(!event.shiftKey&&document.activeElement===targets.at(-1)){event.preventDefault();targets[0]?.focus()}}
});
(async()=>{
  if(portalExampleMode){const banner=portalEl('exampleBanner');if(banner)banner.hidden=false;document.title='Casas de ejemplo · Nexo';const heading=document.querySelector('.portal-heading h1');if(heading)heading.textContent='Recorré el mapa con seis casas de ejemplo.';const subhead=document.querySelector('.portal-heading > div > p:last-child');if(subhead)subhead.textContent='Probá los filtros y explorá las fichas con datos ilustrativos de Cochabamba.'}
  try{portalConfig=await portalApi('/api/public/config');portalMapInit()}catch(error){portalEl('mapNotice').textContent=error.message}
  // Existing members go straight to their panel when they choose to publish.
  portalApi('/api/auth/me').then(session=>{if(!session.user)return;for(const a of document.querySelectorAll('a[href="/registro"]')){a.href=session.user.role==='admin'||session.user.workspaceKind==='independent'?'/#publicaciones':'/#inicio';a.textContent=a.classList.contains('nav-publish')?'Mi panel':'Ir a mi espacio'}const login=document.querySelector('.portal-nav a[href="/#inicio"]');if(login)login.textContent='Mi cuenta'}).catch(()=>{});
  await portalSearch(true);if(location.pathname.startsWith('/inmueble/'))await portalOpenListing(location.pathname.split('/')[2]);
})();
