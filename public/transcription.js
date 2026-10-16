const transcriptionRuns=new Set();
function audioForVisit(v){if(v.audioId)return v.audioId;return state.files.filter(f=>f.record_id===v.id&&f.mime.startsWith('audio/')).sort((a,b)=>(b.created||'').localeCompare(a.created||''))[0]?.id||null}
function setTranscriptionStatus(message,error=false){const box=document.getElementById('transcriptionStatus');if(box){box.className='callout '+(error?'':'success');box.textContent=message}}
function transcriptionSetup(){
 const available=config.transcriptionSetup==='local',chosen=config.transcriptionProvider||'openai';
 const currentAudio=route==='visitas'&&document.getElementById('visitTranscript')&&audioForVisit(visitDraft||{});
 openModal('Conectar audio e inteligencia artificial',`<p class="body-copy">Conectá tu cuenta para transcribir las grabaciones. Con OpenAI, la misma clave prepara las hojas y permite consultar el historial.</p>${available?`<form id="transcriptionSetupForm" data-visit="${currentAudio?esc(visitDraft.id):''}"><div class="form-grid">${selectField('Servicio de transcripción','provider',[['openai','OpenAI — audio, hojas e historial'],['assemblyai','AssemblyAI — transcripción de audio']],chosen)}<div class="field full"><label for="transcriptionKey">Clave API del servicio seleccionado</label><input id="transcriptionKey" type="password" autocomplete="off" spellcheck="false" minlength="16" maxlength="512" placeholder="Ingresá la clave; dejá vacío para conservar la existente"></div>${selectField('Modelo de audio de OpenAI','audioModel',[['gpt-4o-mini-transcribe','Económico — GPT-4o Mini Transcribe'],['gpt-transcribe','GPT Transcribe'],['gpt-4o-transcribe-diarize','Identificación de hablantes']],config.audioModel||'gpt-4o-mini-transcribe')}</div><p class="notice">Obtené tu clave en <a class="link" href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">OpenAI</a> o <a class="link" href="https://www.assemblyai.com/dashboard" target="_blank" rel="noopener">AssemblyAI</a>. Se guarda en este servidor y no se muestra de nuevo. El uso de la API se paga por separado de ChatGPT.</p><p class="notice">El audio se enviará al servicio elegido. OpenAI admite archivos de hasta 25 MB en WebM, MP3, MP4, M4A o WAV. Los modelos económicos no separan hablantes.</p><div class="form-error" id="transcriptionSetupError" role="alert"></div><div class="form-footer"><button type="button" class="btn" data-action="close-modal">Cancelar</button><button type="submit" class="btn primary">${currentAudio?'Guardar conexión y transcribir':'Guardar conexión'}</button></div></form>`:'<p class="body-copy">Pedile al administrador que conecte el servicio desde Configuración. Tu grabación permanece guardada.</p>'}`)
}
async function transcribeSavedVisit(){
 const v=visitDraft,vid=v?.id,fid=v&&audioForVisit(v);
 if(!fid)throw Error('Grabá o subí un audio de esta visita primero.');
 if(!config.transcription){transcriptionSetup();return null}
 if(transcriptionRuns.has(vid))throw Error('Esta grabación ya se está transcribiendo. Esperá a que termine.');
 const active=()=>visitDraft?.id===vid&&document.getElementById('visitTranscript');
 transcriptionRuns.add(vid);
 const button=document.querySelector('[data-action="transcribe-file"]');if(button){button.disabled=true;button.textContent='Transcribiendo…'}
 try{
  if(active())setTranscriptionStatus('Convirtiendo el audio en texto. La grabación se conserva mientras se procesa.');
  let jobId=v.transcriptionJobId;
  if(!jobId){const job=await api('/api/transcribe',{method:'POST',body:JSON.stringify({fileId:fid})});jobId=job.jobId;await api('/api/visits/'+encodeURIComponent(vid),{method:'PATCH',body:JSON.stringify({audioId:fid,transcriptionJobId:jobId})});v.transcriptionJobId=jobId}
  for(let i=0;i<480;i++){
   await new Promise(resolve=>setTimeout(resolve,2500));
   const result=await api('/api/transcribe/'+encodeURIComponent(jobId));
   if(result.status==='error'){await api('/api/visits/'+encodeURIComponent(vid),{method:'PATCH',body:JSON.stringify({transcriptionJobId:null})});v.transcriptionJobId=null;throw Error(result.error||'El servicio no pudo transcribir esta grabación. El audio se conserva.')}
   if(result.status==='completed'){
    const text=String(result.text||'').trim();
    if(text.length<15){await api('/api/visits/'+encodeURIComponent(vid),{method:'PATCH',body:JSON.stringify({transcriptionJobId:null})});v.transcriptionJobId=null;throw Error('No se detectó suficiente voz para preparar la hoja. Escuchá el audio y comprobá que la conversación se oiga.')}
    await api('/api/visits/'+encodeURIComponent(vid),{method:'PATCH',body:JSON.stringify({transcript:text,transcriptSource:'audio',audioId:fid,transcriptionJobId:null,transcriptionCompletedAt:new Date().toISOString()})});
    v.transcript=text;v.transcriptionJobId=null;v.transcriptSource='audio';await refresh();
    if(active()){$('#visitTranscript').value=text;visitDraft.transcript=text;visitDraft.transcriptionJobId=null;visitDraft.transcriptSource='audio';setTranscriptionStatus('Transcripción completa. Preparando la hoja de visita…')}
    else toast('Transcripción guardada. Abrí la visita para generar su hoja.');
    return {visitId:vid,text};
   }
  }
  throw Error('El servicio sigue procesando el audio. La grabación y el trabajo se conservaron; tocá nuevamente para consultar su estado.');
 }catch(error){if(active())setTranscriptionStatus(error.message,true);throw error}
 finally{transcriptionRuns.delete(vid);if(button?.isConnected){button.disabled=false;button.textContent='Transcribir y generar hoja'}}
}
async function afterAudioSaved(){readVisit();if(!audioForVisit(visitDraft))return;if(config.transcription){try{await transcribeFile()}catch(error){toast(error.message,true)}return}if(String(visitDraft.transcript||'').trim().length<15){setTranscriptionStatus('Audio guardado. Falta conectar la transcripción para completar la hoja desde esta grabación.',true);return}setTranscriptionStatus('Usando el texto capturado en vivo. Revisalo antes de confirmar; el audio se conserva.');try{await generateSheet()}catch(error){toast(error.message,true)}}
document.addEventListener('submit',async event=>{
 if(event.target.id!=='transcriptionSetupForm')return;
 event.preventDefault();const form=event.target,button=form.querySelector('[type="submit"]');button.disabled=true;
 try{const data=Object.fromEntries(new FormData(form));data.key=$('#transcriptionKey').value.trim();delete data.transcriptionKey;
 await api('/api/ai-settings',{method:'POST',body:JSON.stringify(data)});$('#transcriptionKey').value='';config=await api('/api/config');
 const vid=form.dataset.visit;closeModal();toast('Conexión guardada. Probá una grabación para verificar el audio.');
 if(vid&&visitDraft?.id===vid&&document.getElementById('visitTranscript'))await transcribeFile();else if(route==='configuracion')renderSettings()
 }catch(error){const box=document.getElementById('transcriptionSetupError');if(box)box.textContent=error.message;else toast(error.message,true)}finally{if(button.isConnected)button.disabled=false}
});
document.addEventListener('click',event=>{if(event.target.closest('[data-action="connect-transcription"]'))transcriptionSetup()});
