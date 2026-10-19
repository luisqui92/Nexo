import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const nodes=new Map();
function node(key){if(!nodes.has(key))nodes.set(key,{innerHTML:'',textContent:'',hidden:false,value:'',isConnected:true,elements:{currency:{},maxPrice:{value:''}},classList:{add(){},remove(){},toggle(){},contains(){return false}},querySelector:s=>node(key+' '+s),querySelectorAll:()=>[],addEventListener(){},setAttribute(){},append(){},remove(){},focus(){},scrollIntoView(){}});return nodes.get(key)}
const document={querySelector:node,querySelectorAll:()=>[],getElementById:id=>node('#'+id),addEventListener(){},body:node('body'),createElement:()=>node('created'),activeElement:node('active'),hidden:false};document.body.style={};
class FormDataMock{constructor(form){this.entries=Object.entries(form.values||{})}[Symbol.iterator](){return this.entries[Symbol.iterator]()}getAll(name){return this.entries.filter(([key])=>key===name).map(([,value])=>value)}}
const context={document,window:{addEventListener(){},scrollTo(){}},location:{hash:'#inicio',hostname:'localhost',pathname:'/explorar',origin:'https://nexo.test'},navigator:{},console,Intl,Date,URLSearchParams,FormData:FormDataMock,setTimeout(){},setInterval(){},clearTimeout(){},structuredClone,sessionStorage:{getItem(){},removeItem(){},setItem(){}}};
vm.createContext(context);const run=code=>vm.runInContext(code,context);
for(const file of ['app.js','transcription.js','team.js','account.js','marketplace.js','preparation.js'])run(readFileSync(new URL('../public/'+file,import.meta.url),'utf8'));
run(`config={role:'advisor',user:'Ana',marketplace:true,teamSupported:true,profile:{id:'ana',workspaceKind:'independent'}};state={clients:[],properties:[{id:'p',title:'Propiedad propia',zone:'Centro',operation:'Venta',currency:'USD',price:85000,features:[]}],visits:[],events:[],operations:[],files:[]};renderNav();renderProperty('p')`);
assert.match(node('#nav').innerHTML,/#publicaciones/);assert.match(node('#nav').innerHTML,/#solicitudes/);assert.doesNotMatch(node('#nav').innerHTML,/#equipo|#plataforma/);
assert.match(node('#main').innerHTML,/edit-property/);assert.match(node('#main').innerHTML,/edit-publication/);assert.match(node('#main').innerHTML,/data-action="upload"/);
run(`config.profile.workspaceKind='agency';renderNav();renderProperty('p')`);assert.doesNotMatch(node('#nav').innerHTML,/#publicaciones/);assert.doesNotMatch(node('#main').innerHTML,/edit-property|edit-publication|data-action="upload"/);
run(`config.role='admin';config.profile.platformAdmin=false;renderNav();renderSettings()`);assert.doesNotMatch(node('#nav').innerHTML,/#plataforma/);assert.match(node('#main').innerHTML,/workspaceForm/);assert.doesNotMatch(node('#main').innerHTML,/OPENAI_API_KEY/);
run(`config.profile.platformAdmin=true;renderNav()`);assert.match(node('#nav').innerHTML,/#plataforma/);
const html=readFileSync(new URL('../public/portal.html',import.meta.url),'utf8');assert.match(html,/portalFilters/);assert.match(html,/publicMap/);assert.doesNotMatch(html,/src="\/app.js"/); // Public browsing does not boot the private CRM.
const pubNodes=new Map();
function pubNode(key){if(!pubNodes.has(key))pubNodes.set(key,{...node('public '+key),elements:{currency:{},maxPrice:{value:''}},values:{},querySelector:s=>pubNode(key+' '+s)});return pubNodes.get(key)}
const pubDoc={...document,getElementById:pubNode,body:{style:{}},activeElement:{focus(){}}};
const sample={id:'public-1',title:'<script>Nombre del inmueble</script>',photos:['/api/public/photos/public-1/photo-1'],operation:'Venta',type:'Departamento',currency:'USD',price:85000,zone:'Centro',city:'Cochabamba',bedrooms:2,bathrooms:1,parking:1,area:90,description:'<b>Descripción</b>',features:[],latitude:-17.39,longitude:-66.16,publisher:{id:'ana',name:'Ana <script>',company:'Empresa <script>',phone:'59170000000'}};
const response=data=>({ok:true,json:async()=>data});
const publicContext={document:pubDoc,window:{},location:{pathname:'/explorar',origin:'https://nexo.test'},navigator:{},console,Intl,Date,URLSearchParams,FormData:FormDataMock,setTimeout(){},clearTimeout(){},fetch:async path=>response(path==='/api/public/config'?{center:[-17.39,-66.16],zoom:13,tileUrl:'https://tile.example/{z}/{x}/{y}.png'}:{listings:[sample],total:1,page:1,limit:48})};
vm.createContext(publicContext);const pubRun=code=>vm.runInContext(code,publicContext);pubRun(readFileSync(new URL('../public/portal.js',import.meta.url),'utf8'));
await new Promise(resolve=>setImmediate(resolve));
assert.match(pubNode('listingResults').innerHTML,/&lt;script&gt;/);assert.doesNotMatch(pubNode('listingResults').innerHTML,/<script>/);assert.match(pubNode('mapNotice').textContent,/vista Lista/);
// A slow response from an earlier search must not overwrite newer results.
const pending=[];publicContext.fetch=()=>new Promise(resolve=>pending.push(resolve));
const earlier=pubRun('portalSearch()'),later=pubRun('portalSearch()');
pending[1](response({listings:[{...sample,title:'Búsqueda nueva'}],total:1,page:1,limit:48}));await later;
pending[0](response({listings:[{...sample,title:'Respuesta vieja'}],total:1,page:1,limit:48}));await earlier;
assert.match(pubNode('listingResults').innerHTML,/Búsqueda nueva/);assert.doesNotMatch(pubNode('listingResults').innerHTML,/Respuesta vieja/);
publicContext.fetch=async()=>{throw new TypeError('offline')};await pubRun('portalSearch()');assert.match(pubNode('portalStatus').innerHTML,/Reintentar/);assert.match(pubNode('listingResults').innerHTML,/Búsqueda nueva/);
publicContext.fetch=async()=>response(sample);await pubRun("portalOpenListing('public-1')");assert.doesNotMatch(pubNode('portalDialogRoot').innerHTML,/<script>/);assert.match(pubNode('portalDialogRoot').innerHTML,/Solicitar visita/);assert.match(pubNode('portalDialogRoot').innerHTML,/wa.me\/59170000000/);
const example={...sample,id:'ejemplo-casa-cala-cala',isExample:true,features:['Jardín'],publisher:{id:'nexo-ejemplos',name:'Nexo · Demostración',company:'Casa de ejemplo'}};
publicContext.fetch=async()=>response(example);await pubRun("portalOpenListing('ejemplo-casa-cala-cala')");
assert.match(pubNode('portalDialogRoot').innerHTML,/NO ES UNA OFERTA REAL/);assert.doesNotMatch(pubNode('portalDialogRoot').innerHTML,/wa.me|data-request-visit|publicInquiryForm/);
publicContext.example=example;const beforeInquiry=pubNode('portalContactArea').innerHTML;pubRun('portalVisitForm(example)');assert.equal(pubNode('portalContactArea').innerHTML,beforeInquiry);
assert.match(pubRun('portalCard(example)'),/EJEMPLO · DATOS FICTICIOS/);
const exampleCalls=[];
const exampleContext={...publicContext,location:{pathname:'/explorar',search:'?ejemplos=1',origin:'https://nexo.test'},fetch:async path=>{exampleCalls.push(path);return response(path==='/api/public/config'?{center:[-17.39,-66.16],zoom:13,tileUrl:'https://tile.example/{z}/{x}/{y}.png'}:path==='/api/auth/me'?{user:null}:{listings:[example],total:1,page:1,limit:48,exampleMode:true})}};
vm.createContext(exampleContext);vm.runInContext(readFileSync(new URL('../public/portal.js',import.meta.url),'utf8'),exampleContext);
await new Promise(resolve=>setImmediate(resolve));
assert.ok(exampleCalls.some(path=>path.startsWith('/api/public/examples?')));assert.ok(!exampleCalls.some(path=>path.startsWith('/api/public/listings?')));
assert.equal(pubNode('exampleBanner').hidden,false);assert.match(pubNode('portalStatus').textContent,/casas de ejemplo/);
console.log('Marketplace UI passed: independent permissions, agency/platform separation, anonymous browsing, escaped content, stale searches, map fallback and connection recovery.');
