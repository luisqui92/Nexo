import { readFileSync, mkdirSync, writeFileSync, copyFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root=resolve(import.meta.dirname,'..');
const names={'index.html':'text/html; charset=utf-8','app.js':'text/javascript; charset=utf-8','styles.css':'text/css; charset=utf-8','mobile.css':'text/css; charset=utf-8','mobile.js':'text/javascript; charset=utf-8','transcription.js':'text/javascript; charset=utf-8','team.js':'text/javascript; charset=utf-8','team.css':'text/css; charset=utf-8','cosmic.css':'text/css; charset=utf-8','preparation.js':'text/javascript; charset=utf-8','presentacion.html':'text/html; charset=utf-8','presentation.css':'text/css; charset=utf-8','presentation.js':'text/javascript; charset=utf-8','mark.svg':'image/svg+xml','manifest.webmanifest':'application/manifest+json','sw.js':'text/javascript; charset=utf-8'};
const assets=Object.fromEntries(Object.entries(names).map(([f,type])=>[f,{type,body:readFileSync(resolve(root,'public',f),'utf8')}]));
const demo=JSON.parse(readFileSync(resolve(root,'worker/demo.json'),'utf8'));
const combined=`const ASSETS=${JSON.stringify(assets)};\nconst DEMO=${JSON.stringify(demo)};\n`+readFileSync(resolve(root,'worker/logic.js'),'utf8')+'\n'+readFileSync(resolve(root,'worker/reception.js'),'utf8')+'\n'+readFileSync(resolve(root,'worker/index.js'),'utf8');
mkdirSync(resolve(root,'dist/server'),{recursive:true});mkdirSync(resolve(root,'dist/.openai'),{recursive:true});mkdirSync(resolve(root,'dist/migrations'),{recursive:true});
writeFileSync(resolve(root,'dist/server/index.js'),combined);copyFileSync(resolve(root,'.openai/hosting.json'),resolve(root,'dist/.openai/hosting.json'));copyFileSync(resolve(root,'migrations/0001_nexo.sql'),resolve(root,'dist/migrations/0001_nexo.sql'));
let worker;try{worker=await import('data:text/javascript;base64,'+Buffer.from(combined).toString('base64'))}catch(e){console.error(e.message);process.exit(1)}
if(typeof worker.default.fetch!=='function')throw Error('Missing Worker fetch');
const r=await worker.default.fetch(new Request('https://nexo.test/'),{},{});if(r.status!==200||!(await r.text()).includes('Nexo'))throw Error('HTML response failed');
console.log('Hosted Worker built and static response verified.');
