'use strict';
let accountPhotoBusy=false;

function accountAvatar(user=config.profile, extra=''){
  const color=/^#[0-9a-f]{6}$/i.test(user?.avatarColor||'')?user.avatarColor:'#164d45';
  return `<span class="avatar account-avatar ${extra}" style="background-color:${color}">${user?.avatarUpdated?`<img src="/api/account/avatar?v=${encodeURIComponent(user.avatarUpdated)}" alt="" referrerpolicy="same-origin">`:esc(initials(user?.name||config.user||'Nexo'))}</span>`;
}
function paintAccount(user=config.profile){
  if(!user)return;
  config.profile=user;config.user=user.name;
  teamUsers=teamUsers.map(u=>u.id===user.id?user:u);
  $('#advisorName').innerHTML=esc(user.name)+`<small>${esc(user.title||(isAdmin()?'Administración':'Asesor inmobiliario'))}</small>`;
  const side=$('#profile > .avatar');if(side)side.outerHTML=accountAvatar(user);
  const top=$('#accountButton');if(top){top.innerHTML=accountAvatar(user,'small');top.setAttribute('aria-label','Mi cuenta: '+user.name)}
  const preview=$('#accountPhotoPreview');if(preview)preview.innerHTML=accountAvatar(user,'large');
}
function renderAccountPage(){
  const u=config.profile||{};
  $('#main').innerHTML=heading('TU PERFIL EN NEXO','Mi cuenta','Personalizá tu perfil y administrá tu acceso.')+`<div class="account-grid"><section class="card account-summary">${accountAvatar(u,'large')}<h2>${esc(config.user)}</h2><p>${esc(u.title||(isAdmin()?'Administración':'Asesor inmobiliario'))}</p><span class="account-badge">${isAdmin()?'Panel central':'Panel del asesor'}</span><div class="actions">${config.teamSupported?button('Personalizar mi cuenta','personalize-account','settings','primary'):''}</div></section><section class="card account-details"><h2>Datos de contacto</h2><div class="info-grid">${info('Usuario',u.username||'Cuenta de ChatGPT')}${info('Correo electrónico',u.email||'Sin agregar')}${info('Teléfono',u.phone||'Sin agregar')}</div><h2>Seguridad y acceso</h2><div class="actions">${config.teamSupported?button('Cambiar contraseña','change-own-password','shield')+button('Cerrar sesión','logout','arrow'):''}${!isAdmin()?button('Activar avisos','notifications','bell'):''}</div></section></div>`;
}
function openAccountSettings(){
  if(!config.profile||!config.teamSupported)return;
  const u=config.profile;
  openModal('Personalizar mi cuenta',`<div class="account-photo"><div id="accountPhotoPreview">${accountAvatar(u,'large')}</div><div><label class="btn" for="accountPhotoInput">Elegir y guardar foto</label><input id="accountPhotoInput" type="file" accept="image/jpeg,image/png,image/webp" class="account-file"><button class="account-text-button" type="button" data-action="remove-account-photo" ${u.avatarUpdated?'':'hidden'} id="removeAccountPhoto">Quitar foto</button><p class="account-hint">JPG, PNG o WebP. La foto se guarda al elegirla.</p></div></div><p id="accountPhotoStatus" role="status" aria-live="polite"></p><form id="accountForm"><div class="form-grid">${inputField('Nombre y apellido','name',u.name,'text','required maxlength="120" autocomplete="name"')}${inputField('Cargo o especialidad','title',u.title,'text','maxlength="100" placeholder="Ej.: Asesor inmobiliario" autocomplete="organization-title"')}${inputField('Correo electrónico','email',u.email,'email','maxlength="254" autocomplete="email"')}${inputField('Teléfono','phone',u.phone,'tel','maxlength="40" autocomplete="tel"')}${inputField('Color de tus iniciales','avatarColor',u.avatarColor||'#164d45','color')}<div class="field"><label>Usuario de acceso</label><p class="account-username">${esc(u.username)}</p></div></div><p class="account-hint">Tus datos de contacto quedan en tu perfil. El usuario y los permisos los administra la inmobiliaria.</p>${formFooter('Guardar perfil')}</form><div class="account-security"><span>Seguridad de tu cuenta</span>${button('Cambiar contraseña','change-own-password','shield')}</div>`);
}
function openOwnPassword(){
  if(accountPhotoBusy)return toast('Esperá a que termine de guardarse la foto.',true);
  if(recordStarting||recorder?.state==='recording'||uploading||transcriptionRuns.size)return toast('Terminá de guardar la visita antes de cambiar la contraseña.',true);
  openModal('Cambiar contraseña',`<p class="account-intro">Elegí una contraseña de al menos 10 caracteres. Se cerrarán tus otras sesiones y seguirás conectado acá.</p><form id="accountPasswordForm">${inputField('Contraseña actual','currentPassword','','password','required maxlength="256" autocomplete="current-password"')}${inputField('Nueva contraseña','newPassword','','password','required minlength="10" maxlength="256" autocomplete="new-password"')}${inputField('Repetir nueva contraseña','repeatPassword','','password','required minlength="10" maxlength="256" autocomplete="new-password"')}${formFooter('Actualizar contraseña')}</form>`);
}
function showAboutNexo(){
  openModal('Acerca de Nexo',`<div class="about-nexo"><span class="brand-mark" aria-hidden="true"></span><h3>Nexo Inmobiliaria</h3><p>Clientes, inmuebles y visitas, conectados en un solo lugar.</p><hr><p class="account-hint">Imagen de M87*: EHT Collaboration, distribuida por ESO.</p><a class="link" href="https://www.eso.org/public/images/eso1907a/" target="_blank" rel="noopener noreferrer">Ver imagen y créditos en ESO ↗</a></div>`);
}
async function prepareAccountPhoto(file){
  if(!file||!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>8*1024*1024)throw Error('Elegí una foto JPG, PNG o WebP de hasta 8 MB.');
  const url=URL.createObjectURL(file);
  try{
    const image=new Image();image.src=url;await image.decode();
    if(!image.naturalWidth||image.naturalWidth*image.naturalHeight>40000000)throw Error('Elegí una imagen de menor tamaño.');
    const canvas=document.createElement('canvas');canvas.width=canvas.height=384;
    const ctx=canvas.getContext('2d');if(!ctx)throw Error('No se pudo preparar la foto.');
    const size=Math.min(image.naturalWidth,image.naturalHeight);
    ctx.fillStyle='#fff';ctx.fillRect(0,0,384,384);
    ctx.drawImage(image,(image.naturalWidth-size)/2,(image.naturalHeight-size)/2,size,size,0,0,384,384);
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',0.85));
    if(!blob||blob.size>256*1024)throw Error('No se pudo reducir la foto. Probá con otra imagen.');
    return blob;
  }finally{URL.revokeObjectURL(url)}
}
async function updateAccountPhoto(file,remove=false){
  if(accountPhotoBusy)return;
  accountPhotoBusy=true;
  const owner=config.profile?.id,status=$('#accountPhotoStatus');
  const controls=$$('#accountPhotoInput,#removeAccountPhoto,#accountForm button[type="submit"]');controls.forEach(b=>b.disabled=true);
  if(status)status.textContent=remove?'Quitando foto…':'Guardando foto…';
  try{
    const blob=remove?null:await prepareAccountPhoto(file);
    const result=await api('/api/account/avatar',remove?{method:'DELETE'}:{method:'POST',headers:{'Content-Type':'image/jpeg'},body:blob});
    if(config.profile?.id!==owner)return;
    paintAccount(result.user);
    const removeButton=$('#removeAccountPhoto');if(removeButton)removeButton.hidden=!result.user.avatarUpdated;
    if(status?.isConnected)status.textContent=remove?'Foto eliminada.':'Foto guardada.';
    if(route==='perfil')renderAccountPage();
  }catch(error){if(status?.isConnected)status.textContent=error.message;toast(error.message,true)}
  finally{accountPhotoBusy=false;controls.forEach(b=>{if(b.isConnected)b.disabled=false})}
}
document.addEventListener('change',event=>{if(event.target.id==='accountPhotoInput'&&event.target.files?.[0])updateAccountPhoto(event.target.files[0])});
document.addEventListener('click',event=>{
  const action=event.target.closest('[data-action]')?.dataset.action;
  if(action==='personalize-account')openAccountSettings();
  if(action==='change-own-password')openOwnPassword();
  if(action==='remove-account-photo')updateAccountPhoto(null,true);
  if(action==='about-nexo')showAboutNexo();
});
document.addEventListener('submit',async event=>{
  const form=event.target;if(!['accountForm','accountPasswordForm'].includes(form.id))return;
  event.preventDefault();const errorRoot=form.querySelector('#formError'),submit=form.querySelector('[type="submit"]');
  if(accountPhotoBusy){errorRoot.textContent='Esperá a que termine de guardarse la foto.';return}
  submit.disabled=true;errorRoot.textContent='';
  try{
    const data=Object.fromEntries(new FormData(form));
    if(form.id==='accountPasswordForm'){
      if(data.newPassword!==data.repeatPassword)throw Error('Las contraseñas nuevas no coinciden.');
      await api('/api/account/password',{method:'POST',body:JSON.stringify({currentPassword:data.currentPassword,newPassword:data.newPassword})});
      closeModal();toast('Contraseña actualizada. Tus otras sesiones se cerraron.');
    }else{
      const result=await api('/api/account',{method:'PATCH',body:JSON.stringify(data)});
      paintAccount(result.user);closeModal();if(route==='perfil')renderAccountPage();toast('Tu perfil está actualizado.');
    }
  }catch(error){if(errorRoot.isConnected)errorRoot.textContent=error.message}
  finally{if(submit.isConnected)submit.disabled=false}
});
