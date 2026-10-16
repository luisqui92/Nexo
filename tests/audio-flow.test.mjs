import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
const generate=source.slice(source.indexOf('async function generateSheet('),source.indexOf('async function confirmVisit()'));
function scenario({audio=false,configured=false,text=''}){
 const calls=[],button={isConnected:true,disabled:false,innerHTML:''},field={value:text};
 const context={recorder:null,uploading:false,recordStarting:false,transcriptionRuns:new Set(),visitDraft:{id:'visit-test',transcript:text},config:{transcription:configured},calls,
  readVisit(){},audioForVisit:()=>audio?'file-test':null,toast:message=>calls.push(['toast',message]),setTranscriptionStatus:message=>calls.push(['status',message]),transcriptionSetup:()=>calls.push(['setup']),
  transcribeSavedVisit:async()=>{calls.push(['transcribe']);context.visitDraft.transcript='Busca estacionamiento. Presupuesto hasta 90 mil dólares.';return {visitId:'visit-test',text:context.visitDraft.transcript}},
  api:async(path,opts)=>{calls.push(['api',path,JSON.parse(opts.body)]);return {sheet:{summary:'Visita transcrita'},method:'automatic'}},
  persistVisit:async()=>calls.push(['save']),paintSheet:sheet=>calls.push(['sheet',sheet]),icon:()=>'',
  $:selector=>selector==='#generateButton'?button:selector==='#visitTranscript'?field:{scrollIntoView(){}},
  Error,console
 };
 vm.createContext(context);vm.runInContext(generate,context);return {context,calls,button}
}
let run=scenario({audio:true,configured:true});await run.context.generateSheet();assert.equal(run.calls.filter(c=>c[0]==='transcribe').length,1);assert.ok(run.calls.some(c=>c[0]==='api'&&c[2].text.includes('90 mil')));assert.ok(run.calls.some(c=>c[0]==='save'));assert.equal(run.button.disabled,false);
run=scenario({audio:true,configured:false});await run.context.generateSheet();assert.ok(run.calls.some(c=>c[0]==='setup'));assert.ok(!run.calls.some(c=>c[0]==='api'));assert.ok(!run.calls.some(c=>c[0]==='toast'&&c[1].includes('15 caracteres')));
run=scenario({text:'Busca estacionamiento y dos dormitorios.'});await run.context.generateSheet();assert.ok(!run.calls.some(c=>c[0]==='transcribe'));assert.ok(run.calls.some(c=>c[0]==='sheet'));
run=scenario({});await run.context.generateSheet();assert.ok(run.calls.some(c=>c[0]==='toast'&&c[1].includes('Grabá una visita')));
console.log('Audio flow passed: saved audio is transcribed before analysis; missing connection opens setup; text remains supported.');
