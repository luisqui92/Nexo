import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const nodes=new Map();
function node(selector){if(!nodes.has(selector))nodes.set(selector,{innerHTML:'',textContent:'',value:'',classList:{add(){},remove(){},toggle(){}},querySelector:s=>node(selector+' '+s),querySelectorAll:()=>[],setAttribute(){},addEventListener(){},append(){},remove(){},focus(){},scrollIntoView(){}});return nodes.get(selector)}
const document={querySelector:node,querySelectorAll:()=>[],getElementById:id=>node('#'+id),addEventListener(){},body:node('body'),createElement:()=>node('created'),hidden:false};
const context={document,window:{addEventListener(){},scrollTo(){}},location:{hash:'#inicio',hostname:'localhost'},navigator:{},console,Intl,Date,setTimeout(){},setInterval(){},structuredClone,sessionStorage:{getItem(){},removeItem(){},setItem(){}}};
vm.createContext(context);
for(const file of ['app.js','transcription.js','team.js','account.js','preparation.js'])vm.runInContext(readFileSync(new URL('../public/'+file,import.meta.url),'utf8'),context);
const run=code=>vm.runInContext(code,context);
run(`config={role:'admin',user:'Administración',profile:{id:'admin'},teamSupported:true};teamUsers=[{id:'ana',name:'Ana',role:'advisor',active:1}];state={clients:[{id:'c',name:'Cliente',role:'Comprador',currency:'USD',advisorId:'ana',needs:[],zones:[]}],properties:[{id:'p',title:'Departamento',zone:'Centro',currency:'USD',operation:'Venta',status:'Disponible',advisorIds:['ana']}],visits:[],events:[],operations:[],files:[]};startPage()`);
assert.match(node('#main').innerHTML,/La jornada/);assert.match(node('#main').innerHTML,/En agenda/);assert.doesNotMatch(node('#main').innerHTML,/stat-card|stat-value|Actividad por asesor|page-header/);assert.match(node('#main').innerHTML,/Ana/);assert.match(node('#nav').innerHTML,/#equipo/);assert.match(node('#nav').innerHTML,/#asignaciones/);
// Dates come from the same local calendar used by the application.
run(`
const day=today();
const tomorrow=new Date();tomorrow.setDate(tomorrow.getDate()+1);
const yesterday=new Date();yesterday.setDate(yesterday.getDate()-1);
state.events=[
 {id:'later',title:'Encuentro futuro',date:localISO(tomorrow).slice(0,10)+'T09:00',status:'Pendiente',advisorId:'ana'},
 {id:'earlier',title:'Conversación atrasada',date:localISO(yesterday).slice(0,10)+'T09:00',status:'Pendiente'},
 {id:'today-late',title:'Visita de la tarde',date:day+'T17:00',status:'Pendiente'},
 {id:'today-first',title:'<script>Encuentro</script>',date:day+'T08:00',status:'Pendiente'},
 {id:'done',title:'NO MOSTRAR COMPLETADA',date:day+'T08:00',status:'Completada'},
 {id:'cancelled',title:'NO MOSTRAR CANCELADA',date:day+'T08:00',status:'Cancelada'}
];
state.visits=[{id:'draft',date:day,clientId:'c',propertyId:'p',advisorId:'ana',status:'Borrador'},{id:'confirmed',date:day,clientId:'c',status:'Confirmada'}];
state.clients.push({id:'unassigned',name:'Persona por asignar',role:'Comprador',needs:[],zones:[]});
renderCentral();
`);
let agenda=run('deskAgendaMarkup()');assert.match(agenda,/&lt;script&gt;/);assert.doesNotMatch(agenda,/<script>|NO MOSTRAR|Encuentro futuro|Conversación atrasada/);
assert.ok(agenda.indexOf('today-first')<agenda.indexOf('today-late'));
assert.match(node('#main').innerHTML,/#visitas\/draft/);assert.doesNotMatch(node('#main').innerHTML,/#visitas\/confirmed/);assert.match(node('#main').innerHTML,/Persona por asignar/);
run("deskAgendaView='next';paintDeskAgenda()");assert.match(node('#deskAgenda').innerHTML,/Encuentro futuro/);assert.doesNotMatch(node('#deskAgenda').innerHTML,/Visita de la tarde|Conversación atrasada/);
run("deskAgendaView='overdue';paintDeskAgenda()");assert.match(node('#deskAgenda').innerHTML,/Conversación atrasada/);assert.doesNotMatch(node('#deskAgenda').innerHTML,/Encuentro futuro|Visita de la tarde/);
run("deskAgendaView='today'");
run('renderClient("c")');assert.match(node('#main').innerHTML,/assign-client/);
run('renderProperty("p")');assert.match(node('#main').innerHTML,/edit-property/);assert.match(node('#main').innerHTML,/assign-property/);
run('renderAssignments()');assert.match(node('#assignedClients').innerHTML,/Cliente/);assert.match(node('#assignedProperties').innerHTML,/Departamento/);
run("config={role:'advisor',user:'Ana Asesora',profile:{id:'ana'}};location.hash='#inicio';startPage()");
assert.doesNotMatch(node('#main').innerHTML,/stat-card|stat-value|data-action="assign-client"|data-action="new-user"/);assert.match(node('#main').innerHTML,/Conversaciones abiertas/);assert.match(node('#nav').innerHTML,/Mis clientes/);assert.doesNotMatch(node('#nav').innerHTML,/#equipo|#asignaciones|#configuracion|#reportes/);assert.match(node('#main').innerHTML,/ANA/);assert.doesNotMatch(node('#main').innerHTML,/new-property/);
run('renderClient("c")');assert.doesNotMatch(node('#main').innerHTML,/assign-client/);
run('renderProperty("p")');assert.doesNotMatch(node('#main').innerHTML,/edit-property|assign-property|data-action="upload"/);
run("location.hash='#configuracion';startPage()");assert.equal(run('route'),'inicio');
run('clearTeamSession();renderLogin(true)');assert.match(node('#authRoot').innerHTML,/Iniciar sesión/);assert.equal(run('state.clients.length'),0);assert.equal(run('config.profile'),undefined);
run('renderLogin(false)');assert.match(node('#authRoot').innerHTML,/Creá tu panel central/);assert.match(node('#authRoot').innerHTML,/data-mode="setup"/);
run(`config={role:'advisor',user:'Ana <script>',teamSupported:true,profile:{id:'ana',username:'ana',name:'Ana <script>',email:'ana@example.test',title:'Ventas',avatarColor:'#164d45'}};renderProfile()`);
assert.match(node('#main').innerHTML,/Personalizar mi cuenta/);assert.match(node('#main').innerHTML,/Cambiar contraseña/);assert.match(node('#main').innerHTML,/Ana &lt;script&gt;/);assert.doesNotMatch(node('#main').innerHTML,/<script>/);
assert.doesNotMatch(node('#authRoot').innerHTML,/Si sos asesor|image-credit/);
run('openAccountSettings()');assert.match(run('modal.innerHTML'),/accountForm/);assert.match(run('modal.innerHTML'),/Elegir y guardar foto/);assert.doesNotMatch(run('modal.innerHTML'),/name="role"|name="username"/);
run('showAboutNexo()');assert.match(run('modal.innerHTML'),/EHT Collaboration/);
console.log('Team interface passed: central overview and assignments, advisor navigation, property permissions, login/setup and clearing data on logout.');
