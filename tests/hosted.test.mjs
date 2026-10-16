import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
const source=readFileSync(new URL('../dist/server/index.js',import.meta.url),'utf8');
const {default:worker}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
class D1{
 constructor(){this.sql=new DatabaseSync(':memory:');this.sql.exec(readFileSync(new URL('../migrations/0001_nexo.sql',import.meta.url),'utf8'))}
 prepare(query){const db=this.sql;let args=[];const statement={bind(...values){args=values;return statement},async first(){return db.prepare(query).get(...args)||null},async all(){return {results:db.prepare(query).all(...args)}},async run(){const r=db.prepare(query).run(...args);return {meta:{changes:Number(r.changes)}}}};return statement}
 async batch(statements){this.sql.exec('BEGIN');try{const r=[];for(const s of statements)r.push(await s.run());this.sql.exec('COMMIT');return r}catch(e){this.sql.exec('ROLLBACK');throw e}}
}
class R2{constructor(){this.files=new Map()}async put(key,bytes){this.files.set(key,new Uint8Array(bytes));return{}}async get(key){const b=this.files.get(key);return b?{body:b}:null}async delete(key){this.files.delete(key)}}
const env={DB:new D1(),BUCKET:new R2()};
async function request(method,path,body,identity='advisor-a',mime='application/json'){
 const headers={'Content-Type':mime};if(identity)headers['oai-authenticated-user-id']=identity;
 const req=new Request('https://nexo.test'+path,{method,headers,...(method!=='GET'?{body:mime==='application/json'?JSON.stringify(body||{}):body}:{})});
 const r=await worker.fetch(req,env,{});const type=r.headers.get('Content-Type');return{status:r.status,data:type?.includes('application/json')?await r.json():await r.text()}
}
const unauth=await request('GET','/api/state',null,null);assert.equal(unauth.status,401);
const c=(await request('POST','/api/clients',{name:'Cliente QA','role':'Comprador','currency':'USD','intent':'Venta','needs':[],'zones':[]})).data;
assert.ok(c.id);
const p=(await request('POST','/api/properties',{title:'Departamento QA',zone:'Cala Cala',type:'Departamento',operation:'Venta',status:'Disponible',currency:'USD',price:85000,parking:1,bedrooms:2})).data;
assert.ok(p.id);
assert.equal((await request('GET','/api/clients/'+c.id,null,'advisor-b')).status,404);
assert.equal((await request('GET','/api/state',null,'advisor-b')).data.clients.length,0);
const bad=await request('POST','/api/visits',{clientId:p.id,propertyId:c.id,date:'2026-10-12T10:00'});assert.equal(bad.status,404);
const text='Busca estacionamiento. Tiene presupuesto hasta 95.000 dólares. Le gustó la luz, pero quiere confirmar las expensas. Acordamos llamar mañana para coordinar otra visita.';
const extraction=await request('POST','/api/analyse',{text});assert.equal(extraction.status,200);assert.equal(extraction.data.sheet.budget,95000);assert.equal(extraction.data.sheet.currency,'USD');
const v=(await request('POST','/api/visits',{clientId:c.id,propertyId:p.id,date:'2026-10-12T10:00',transcript:text,sheet:extraction.data.sheet})).data;
assert.ok(v.id);
const confirm={sheet:{...extraction.data.sheet,followUp:'2026-10-13'},updateClient:true,createFollowUp:true};
const first=await request('POST','/api/visits/'+v.id+'/confirm',confirm);assert.equal(first.status,200,JSON.stringify(first));
assert.equal((await request('POST','/api/visits/'+v.id+'/confirm',confirm)).status,409);
assert.equal((await request('PATCH','/api/visits/'+v.id,{transcript:'Una modificación'})).status,409);
const state=(await request('GET','/api/state')).data;assert.equal(state.events.length,1);assert.equal(state.clients[0].budget,95000);
assert.equal((await request('DELETE','/api/clients/'+c.id)).status,409);
assert.equal((await request('POST','/api/demo')).status,400);
const file=await request('POST','/api/files?recordId='+v.id+'&name=visita.webm',new Uint8Array([1,2,3]),'advisor-a','audio/webm');assert.equal(file.status,201);
assert.equal((await request('GET','/api/files/'+file.data.id,null,'advisor-b')).status,404);
assert.equal((await request('GET','/api/files/'+file.data.id)).status,200);
const matches=(await request('GET','/api/matches/'+c.id)).data.matches;assert.equal(matches[0].score,100);assert.ok(matches[0].reasons.includes('Tiene estacionamiento'));
const ask=(await request('POST','/api/ask',{clientId:c.id,question:'¿Qué objeciones tuvo?'})).data;assert.match(ask.answer,/expensas/);
console.log('Hosted checks passed: identity isolation, links, extraction, unique confirmation, preferences, follow-up, protected files, matching and memory.');
