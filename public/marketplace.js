'use strict';
let publications=[],privatePropertyMap=null,privatePropertyLayer=null,privateMapRequested=false,publicationEditorMap=null,publicationEditorMarker=null,privateMapVersion=0;
const publicationLabel=p=>p?.blocked?'Suspendida por Nexo':p?.status==='published'?'Publicada':p?.status==='paused'?'Pausada':'Borrador';
function publicationNav(){return config.marketplace&&canManageProperties()?[['publicaciones','building','Publicaciones'],['solicitudes','bell','Solicitudes']]:[]}
async function renderPublications(){
  if(!canManageProperties())return renderHome();
  $('#main').innerHTML=heading('TU CARTERA, A LA VISTA','Publicaciones','Elegí qué inmuebles mostrar en el portal público.',`<a class="btn" href="/explorar" target="_blank" rel="noopener">Ver portal público ↗</a>`+button('Agregar inmueble','new-property','plus','primary'))+'<section class="card" id="publicationList"><p class="body-copy">Cargando publicaciones…</p></section>';
  try{
    publications=(await api('/api/publications')).publications;if(route!=='publicaciones')return;
    $('#publicationList').innerHTML=state.properties.length?`<div class="publication-rows">${state.properties.map(p=>{const pub=publications.find(x=>x.property_id===p.id),visible=pub?.status==='published'&&!pub.blocked&&p.status==='Disponible';return `<article class="publication-row"><div class="publication-row-content"><span class="badge">${pub?publicationLabel(pub):'Privado'}</span><h2>${esc(p.title)}</h2><p>${esc(p.zone)} · ${money(p.price,p.currency)} · ${esc(p.status)}</p><small>${pub?'La ubicación pública es aproximada.':'Este inmueble todavía no aparece en el portal.'}</small></div><div class="actions">${button(pub?'Editar publicación':'Ubicar y publicar','edit-publication','link',pub?'':'primary',`data-id="${esc(p.id)}"`)}<a class="btn" href="#inmuebles/${esc(p.id)}">Ficha privada</a>${visible?`<a class="btn" href="/inmueble/${encodeURIComponent(pub.id)}" target="_blank" rel="noopener">Ver publicación ↗</a>`:''}${pub?.status==='published'?button('Pausar','pause-publication','close','',`data-id="${esc(pub.id)}"`):''}</div></article>`}).join('')}</div>`:empty('Tu primera publicación empieza con un inmueble','Agregá sus características y después elegí ubicación, fotos y contacto.','new-property','Agregar inmueble');
  }catch(error){if(route==='publicaciones')$('#publicationList').innerHTML=`<p class="body-copy">${esc(error.message)}</p>${button('Reintentar','reload-publications','arrow')}`}
}
function publicationPhotosMarkup(propertyId,selected=[]){
  const files=filesFor(propertyId).filter(f=>['image/jpeg','image/png','image/webp'].includes(f.mime)&&(!f.size||f.size<=8*1024*1024));
  return files.length?files.map(f=>`<label class="publication-photo-option"><img src="/api/files/${encodeURIComponent(f.id)}" alt="${esc(f.filename)}" loading="lazy"><span><input type="checkbox" name="photoIds" value="${esc(f.id)}" ${selected.includes(f.id)?'checked':''}> Publicar esta foto</span></label>`).join(''):'<p class="body-copy">Todavía no hay fotos. Agregá al menos una para publicar.</p>';
}
async function publicationForm(propertyId){
  if(!canManageProperties())return;
  const p=property(propertyId);if(!p.id)return;
  try{publications=(await api('/api/publications')).publications}catch(error){return toast(error.message,true)}
  const pub=publications.find(x=>x.property_id===propertyId),data=pub?.body||{};
  openModal('Publicar inmueble',`<div class="publication-intro"><h3>${esc(p.title)}</h3><p>Al guardar se copiarán el título, precio, características y descripción actuales de tu ficha. Para actualizar esos datos en el portal, volvé a guardar la publicación. La dirección exacta y los documentos quedan privados.</p>${pub?.blocked?'<p class="callout">Esta publicación está suspendida por Nexo. Guardar cambios no retira la suspensión.</p>':''}</div><form id="publicationForm" data-property="${esc(propertyId)}"><div class="form-grid">${inputField('Ciudad','city',data.city||p.city||'Cochabamba','text','required maxlength="100"')}${inputField('WhatsApp público con código de país','contactPhone',data.contactPhone||config.profile?.phone||'','tel','required maxlength="40" placeholder="591…"')}${inputField('Latitud exacta (privada)','latitude',p.latitude??'','number','required min="-90" max="90" step="any"')}${inputField('Longitud exacta (privada)','longitude',p.longitude??'','number','required min="-180" max="180" step="any"')}</div><div class="publication-map-toolbar"><p>Tocá el mapa para ubicar el inmueble.</p>${button('Usar mi ubicación','publication-gps','building','small')}</div><div id="publicationEditorMap" class="publication-editor-map"></div><p class="notice">El público verá un punto aproximado de la zona. Podés coordinar la dirección exacta al recibir una solicitud.</p><div class="card-header"><h3>Fotos para la publicación</h3>${button('Agregar fotos','publication-photos','upload','small',`data-id="${esc(propertyId)}"`)}</div><p class="notice">Elegí hasta 10 fotos. Se publicarán únicamente las que selecciones.</p><div id="publicationPhotos" class="publication-photo-grid">${publicationPhotosMarkup(propertyId,data.photoIds||[])}</div>${selectField('Estado de la publicación','status',[['draft','Borrador (privado)'],['published','Publicar en el portal'],['paused','Pausada']],pub?.status||'published')}<label class="check-row publication-consent"><input type="checkbox" name="confirmPublication">Autorizo publicar estos datos, las fotos seleccionadas y mi nombre y contacto. Tengo autorización para ofrecer este inmueble.</label>${formFooter('Guardar publicación')}</form>`);
  initPublicationEditor(p);
}
async function mapConfiguration(){return api('/api/public/config')}
async function initPublicationEditor(p){
  if(publicationEditorMap){publicationEditorMap.remove();publicationEditorMap=null;publicationEditorMarker=null}
  const node=$('#publicationEditorMap');if(!node)return;
  if(!window.L){node.innerHTML='<p class="body-copy">No se pudo cargar el mapa. Podés ingresar latitud y longitud o usar tu ubicación.</p>';return}
  try{
    const options=await mapConfiguration();if(!node.isConnected)return;
    const hasPoint=Number.isFinite(Number(p.latitude))&&Number.isFinite(Number(p.longitude))&&p.latitude!==undefined&&p.longitude!==undefined;
    publicationEditorMap=L.map(node).setView(hasPoint?[Number(p.latitude),Number(p.longitude)]:options.center,hasPoint?16:options.zoom);
    L.tileLayer(options.tileUrl,{maxZoom:19,referrerPolicy:'strict-origin-when-cross-origin',attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · '+esc(options.tileProvider)}).addTo(publicationEditorMap);
    const setPoint=(lat,lng)=>{
      const form=$('#publicationForm');if(!form)return;
      form.elements.latitude.value=Number(lat).toFixed(6);form.elements.longitude.value=Number(lng).toFixed(6);
      if(publicationEditorMarker)publicationEditorMarker.setLatLng([lat,lng]);else publicationEditorMarker=L.circleMarker([lat,lng],{radius:10,color:'#fff',weight:3,fillColor:'#164d45',fillOpacity:1}).addTo(publicationEditorMap);
    };
    publicationEditorMap.on('click',event=>setPoint(event.latlng.lat,event.latlng.lng));
    if(hasPoint)setPoint(p.latitude,p.longitude);
    setTimeout(()=>publicationEditorMap?.invalidateSize(),100);
  }catch(error){if(node.isConnected)node.innerHTML=`<p class="body-copy">${esc(error.message)}</p>`}
}
function publicationGPS(){
  if(!navigator.geolocation)return toast('Este dispositivo no ofrece ubicación. Marcá el inmueble en el mapa.',true);
  const button=$('[data-action="publication-gps"]');if(button)button.disabled=true;
  navigator.geolocation.getCurrentPosition(position=>{
    const form=$('#publicationForm');if(form){const {latitude,longitude}=position.coords;form.elements.latitude.value=latitude.toFixed(6);form.elements.longitude.value=longitude.toFixed(6);if(publicationEditorMap){publicationEditorMap.setView([latitude,longitude],17);publicationEditorMap.fire('click',{latlng:{lat:latitude,lng:longitude}})}toast('Ubicación obtenida. Ajustá el punto si hace falta.')}
    if(button?.isConnected)button.disabled=false;
  },()=>{toast('No pudimos obtener tu ubicación. Habilitá el permiso o marcá el punto en el mapa.',true);if(button?.isConnected)button.disabled=false},{enableHighAccuracy:true,timeout:15000,maximumAge:60000});
}
async function prepareListingPhoto(file){
  if(file.size>8*1024*1024||!['image/jpeg','image/png','image/webp'].includes(file.type))throw Error('Usá fotos JPG, PNG o WebP de hasta 8 MB.');
  const url=URL.createObjectURL(file);
  try{
    const image=new Image();image.src=url;await image.decode();
    if(!image.naturalWidth||image.naturalWidth*image.naturalHeight>40000000)throw Error('Elegí una foto de menor resolución.');
    const scale=Math.min(1,1600/Math.max(image.naturalWidth,image.naturalHeight));
    const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(image.naturalWidth*scale));canvas.height=Math.max(1,Math.round(image.naturalHeight*scale));
    const ctx=canvas.getContext('2d');if(!ctx)throw Error('No pudimos preparar la imagen.');
    ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0,canvas.width,canvas.height);
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.82));
    if(!blob||blob.size>2*1024*1024)throw Error('No pudimos reducir esta foto. Elegí otra imagen.');return blob;
  }finally{URL.revokeObjectURL(url)}
}
function uploadPublicationPhotos(propertyId){
  const input=document.createElement('input');input.type='file';input.accept='image/jpeg,image/png,image/webp';input.multiple=true;
  input.onchange=async()=>{
    const form=$('#publicationForm');if(!form||form.dataset.property!==propertyId)return;
    const selected=$$('#publicationPhotos input:checked').map(el=>el.value),controls=$$('button',form);controls.forEach(b=>b.disabled=true);
    try{
      const chosen=[...input.files];if(chosen.length>10)throw Error('Elegí hasta 10 fotos por vez.');
      for(const file of chosen){const blob=await prepareListingPhoto(file),name=file.name.replace(/\.[^.]+$/,'')+'.jpg';const f=await api('/api/files?recordId='+encodeURIComponent(propertyId)+'&name='+encodeURIComponent(name),{method:'POST',headers:{'Content-Type':'image/jpeg'},body:blob});selected.push(f.id)}
      await refresh();if(form.isConnected)$('#publicationPhotos').innerHTML=publicationPhotosMarkup(propertyId,selected);toast('Fotos guardadas. Elegí cuáles publicar.');
    }catch(error){toast(error.message,true);await refresh().catch(()=>{});if(form.isConnected)$('#publicationPhotos').innerHTML=publicationPhotosMarkup(propertyId,selected)}
    finally{controls.forEach(b=>{if(b.isConnected)b.disabled=false})}
  };input.click();
}
async function renderInquiries(){
  $('#main').innerHTML=heading('DEL MAPA A LA CONVERSACIÓN','Solicitudes','Personas interesadas en tus publicaciones. Cada visita debe confirmarse con el cliente.')+'<section class="card" id="inquiryList"><p class="body-copy">Cargando solicitudes…</p></section>';
  try{
    const data=await api('/api/inquiries');if(route!=='solicitudes')return;
    $('#inquiryList').innerHTML=data.inquiries.length?data.inquiries.map(i=>`<article class="inquiry-row"><div><span class="badge">${esc(i.status)}</span><h2>${esc(i.body.name)}</h2><p>${esc(i.body.propertyTitle)}</p><p class="inquiry-message">${esc(i.body.message||'Solicita información del inmueble.')}</p><small>${esc(i.body.phone)} · ${esc(i.created.replace('T',' '))}${i.body.preferredDate?'<br>Horario solicitado: '+esc(i.body.preferredDate.replace('T',' '))+' (por confirmar)':''}</small></div><div class="inquiry-actions"><a class="btn primary" href="https://wa.me/${encodeURIComponent(i.body.phone)}" target="_blank" rel="noopener noreferrer">Contactar por WhatsApp</a><label>Seguimiento<select data-inquiry="${esc(i.id)}">${['Nueva','Contactada','Archivada'].map(s=>`<option ${s===i.status?'selected':''}>${s}</option>`).join('')}</select></label></div></article>`).join(''):empty('Todavía no hay solicitudes','Las consultas que envíen desde tus publicaciones aparecerán acá.');
  }catch(error){if(route==='solicitudes')$('#inquiryList').innerHTML=`<p class="body-copy">${esc(error.message)}</p>${button('Reintentar','reload-inquiries','arrow')}`}
}
async function paintPrivatePropertyMap(properties){
  const version=++privateMapVersion;
  const node=$('#privatePropertyMap');if(!node)return;
  node.hidden=!privateMapRequested;$('#propertyGrid').hidden=privateMapRequested;
  if(!privateMapRequested)return;
  if(!window.L){node.innerHTML='<p class="body-copy">No se pudo cargar el mapa. Usá la vista Lista para consultar tus inmuebles.</p>';return}
  if(privatePropertyMap&&privatePropertyMap.getContainer()!==node){privatePropertyMap.remove();privatePropertyMap=null}
  try{
    if(!privatePropertyMap){const options=await mapConfiguration();if(!node.isConnected||version!==privateMapVersion)return;privatePropertyMap=L.map(node).setView(options.center,options.zoom);L.tileLayer(options.tileUrl,{maxZoom:19,referrerPolicy:'strict-origin-when-cross-origin',attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · '+esc(options.tileProvider)}).addTo(privatePropertyMap);privatePropertyLayer=L.layerGroup().addTo(privatePropertyMap)}
    privatePropertyLayer.clearLayers();const points=[];
    for(const p of properties){if(p.latitude===undefined||p.longitude===undefined||!Number.isFinite(Number(p.latitude))||!Number.isFinite(Number(p.longitude)))continue;const point=[Number(p.latitude),Number(p.longitude)];points.push(point);L.marker(point,{title:p.title,icon:L.divIcon({className:'private-price-marker',html:`<span>${money(p.price,p.currency)}</span>`,iconSize:[100,34]})}).on('click',()=>location.hash='#inmuebles/'+p.id).addTo(privatePropertyLayer)}
    privatePropertyMap.invalidateSize();if(points.length)privatePropertyMap.fitBounds(points,{padding:[45,45],maxZoom:15});
    $('#propertyCount').textContent=`${properties.length} inmuebles · ${points.length} con ubicación${canManageProperties()?' · Ubicalos desde Publicaciones':''}`;
  }catch(error){toast(error.message,true)}
}
function renderWorkspaceSettings(){
  $('#main').innerHTML=heading('TU EQUIPO, TU ESPACIO','Configuración','Administrá el nombre de tu inmobiliaria y conservá una copia de sus datos.')+`<section class="card"><form id="workspaceForm">${inputField('Nombre de la inmobiliaria','name',config.workspaceName||'','text','required maxlength="120"')}${formFooter('Guardar nombre')}</form></section><section class="card"><h2>Tu información y tus servicios</h2><p class="body-copy">Inteligencia artificial: ${config.aiEnabled?'habilitada para este espacio':'por habilitar con la administración de Nexo'}.</p><div class="actions">${button('Exportar datos de mi inmobiliaria','export-data','download')}<a class="btn" href="#perfil">Mi cuenta</a><a class="btn" href="/explorar" target="_blank" rel="noopener">Ver portal público</a></div></section>`;
}
async function renderPlatform(){
  if(!config.profile?.platformAdmin)return renderHome();
  $('#main').innerHTML=heading('ADMINISTRACIÓN DE NEXO','Gestionar el portal','Cuentas, espacios y publicaciones públicas. Las carteras privadas pertenecen a cada espacio.')+'<div id="platformContent" class="card"><p class="body-copy">Cargando…</p></div>';
  try{
    const data=await api('/api/platform');if(route!=='plataforma')return;
    $('#platformContent').innerHTML=`<h2>Espacios registrados</h2><div class="platform-list">${data.workspaces.map(w=>`<div class="platform-row"><div><strong>${esc(w.name)}</strong><p>${w.kind==='independent'?'Asesor independiente':'Inmobiliaria'} · ${w.active?'Activo':'Suspendido'} · IA ${w.ai_enabled?'habilitada':'sin habilitar'}</p></div><div class="actions">${w.id!=='legacy'?button(w.active?'Suspender espacio':'Reactivar espacio','platform-update','shield','small',`data-kind="workspaces" data-id="${esc(w.id)}" data-field="active" data-value="${w.active?'false':'true'}"`)+button(w.ai_enabled?'Desactivar IA':'Habilitar IA','platform-update','spark','small',`data-kind="workspaces" data-id="${esc(w.id)}" data-field="aiEnabled" data-value="${w.ai_enabled?'false':'true'}"`):'<span class="badge">Espacio principal</span>'}</div></div>`).join('')}</div><h2>Cuentas</h2><div class="platform-list">${data.accounts.map(u=>`<div class="platform-row"><div><strong>${esc(u.name)}</strong><p>${esc(u.username)} · ${u.active?'Activo':'Suspendido'}</p></div>${u.id!==config.profile.id?button(u.active?'Suspender cuenta':'Reactivar cuenta','platform-update','shield','small',`data-kind="accounts" data-id="${esc(u.id)}" data-field="active" data-value="${u.active?'false':'true'}"`):''}</div>`).join('')}</div><h2>Publicaciones</h2><div class="platform-list">${data.publications.map(p=>`<div class="platform-row"><div><strong>${esc(p.title)}</strong><p>${publicationLabel(p)}</p></div>${button(p.blocked?'Retirar suspensión':'Suspender publicación','platform-update','shield','small',`data-kind="publications" data-id="${esc(p.id)}" data-field="blocked" data-value="${p.blocked?'false':'true'}"`)}</div>`).join('')||'<p class="body-copy">Todavía no hay publicaciones.</p>'}</div><h2>Reportes pendientes</h2><div class="platform-list">${data.reports.map(r=>`<div class="platform-row"><div><strong>${esc(r.reason)}</strong><p>${esc(r.details)}</p><a class="link" href="/inmueble/${encodeURIComponent(r.publication_id)}" target="_blank" rel="noopener">Ver publicación ↗</a></div>${button('Marcar revisado','platform-update','check','small',`data-kind="reports" data-id="${esc(r.id)}" data-field="resolved" data-value="true"`)}</div>`).join('')||'<p class="body-copy">No hay reportes pendientes.</p>'}</div>`;
  }catch(error){if(route==='plataforma')$('#platformContent').innerHTML=`<p class="body-copy">${esc(error.message)}</p>${button('Reintentar','reload-platform','arrow')}`}
}
document.addEventListener('submit',async event=>{
  const form=event.target;if(!['publicationForm','workspaceForm'].includes(form.id))return;
  event.preventDefault();const submit=form.querySelector('[type=submit]');submit.disabled=true;
  try{
    if(form.id==='workspaceForm'){const result=await api('/api/workspace',{method:'PATCH',body:JSON.stringify({name:form.elements.name.value})});config.workspaceName=result.name;$('.workspace>div').innerHTML=esc(result.name)+'<small>Panel central</small>';toast('Nombre actualizado.');return}
    const data={propertyId:form.dataset.property,city:form.elements.city.value,latitude:form.elements.latitude.value,longitude:form.elements.longitude.value,contactPhone:form.elements.contactPhone.value,photoIds:[...new FormData(form).getAll('photoIds')],status:form.elements.status.value,confirmPublication:form.elements.confirmPublication.checked};
    const result=await api('/api/publications',{method:'POST',body:JSON.stringify(data)});closeModal();await refresh();if(route==='publicaciones')await renderPublications();else startPage();toast(result.blocked?'Cambios guardados. La suspensión de Nexo sigue activa.':result.status==='published'?'Publicación guardada. Ya puede verse en el portal.':'Publicación guardada como '+publicationLabel(result).toLowerCase()+'.');
  }catch(error){const root=form.querySelector('#formError');if(root?.isConnected)root.textContent=error.message;else toast(error.message,true)}
  finally{if(submit.isConnected)submit.disabled=false}
});
document.addEventListener('change',async event=>{if(event.target.dataset.inquiry){const select=event.target;select.disabled=true;try{await api('/api/inquiries/'+encodeURIComponent(select.dataset.inquiry),{method:'PATCH',body:JSON.stringify({status:select.value})});await renderInquiries();toast('Seguimiento actualizado.')}catch(error){toast(error.message,true)}finally{if(select.isConnected)select.disabled=false}}});
document.addEventListener('click',async event=>{
  const el=event.target.closest('[data-action]');if(!el)return;const action=el.dataset.action;
  try{
    if(action==='edit-publication')await publicationForm(el.dataset.id);
    if(action==='publication-gps')publicationGPS();
    if(action==='publication-photos')uploadPublicationPhotos(el.dataset.id);
    if(action==='pause-publication'){await api('/api/publications/'+encodeURIComponent(el.dataset.id),{method:'PATCH',body:JSON.stringify({status:'paused'})});await renderPublications();toast('La publicación dejó de mostrarse en el portal.')}
    if(action==='reload-publications')await renderPublications();
    if(action==='reload-inquiries')await renderInquiries();
    if(action==='properties-map'||action==='properties-list'){privateMapRequested=action==='properties-map';filterProperties()}
    if(action==='reload-platform')await renderPlatform();
    if(action==='platform-update'){el.disabled=true;await api('/api/platform/'+el.dataset.kind+'/'+encodeURIComponent(el.dataset.id),{method:'PATCH',body:JSON.stringify({[el.dataset.field]:el.dataset.value==='true'})});await renderPlatform();toast('Estado actualizado.')}
  }catch(error){toast(error.message,true);if(el.isConnected)el.disabled=false}
});
