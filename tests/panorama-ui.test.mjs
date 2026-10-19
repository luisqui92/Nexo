import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const code=readFileSync(new URL('../public/panorama.js',import.meta.url),'utf8');
function fixture({webgl=true}={}){
  const values={},deleted=[],images=[],nodes=new Map();let draws=0,observerDisconnected=0;
  function node(id){if(!nodes.has(id))nodes.set(id,{id,hidden:false,dataset:{},clientWidth:400,clientHeight:300,events:{},children:[],setAttribute(){},addEventListener(name,fn){this.events[name]=fn},removeEventListener(name,fn){if(this.events[name]===fn)delete this.events[name]},append(child){this.children.push(child)},focus(){},setPointerCapture(){},querySelector:node,querySelectorAll(selector){return selector==='[data-turn]'?[node('left'),node('right')]:[node('in'),node('out')]}});return nodes.get(id)}
  const gl={createShader:()=>({}),shaderSource(){},compileShader(){},getShaderParameter:()=>true,createProgram:()=>({}),attachShader(){},linkProgram(){},getProgramParameter:()=>true,useProgram(){},createBuffer:()=>({}),bindBuffer(){},bufferData(){},getAttribLocation:()=>0,enableVertexAttribArray(){},vertexAttribPointer(){},createTexture:()=>({}),activeTexture(){},bindTexture(){},texParameteri(){},uniform1i(){},getUniformLocation:(_,name)=>name,uniform1f:(name,value)=>values[name]=value,viewport(){},drawArrays(){draws++},getParameter:()=>4096,texImage2D(){},isContextLost:()=>false,deleteShader(){deleted.push('shader')},deleteProgram(){deleted.push('program')},deleteBuffer(){deleted.push('buffer')},deleteTexture(){deleted.push('texture')}};
  node('canvas').getContext=()=>webgl?gl:null;
  node('left').dataset.turn='-1';node('right').dataset.turn='1';node('in').dataset.zoom='-10';node('out').dataset.zoom='10';
  class ImageMock{constructor(){images.push(this);this.naturalWidth=1774;this.naturalHeight=887}set src(value){this.url=value}}
  const window={devicePixelRatio:1,ResizeObserver:class{observe(){}disconnect(){observerDisconnected++}}};
  const context={window,document:{createElement:()=>node('link')},Image:ImageMock,Float32Array,Math};vm.createContext(context);vm.runInContext(code,context);
  const root=node('root');const viewer=window.NexoPanorama.create(root,{url:'/examples/interiores/sala-360.webp'});
  const key=value=>{let prevented=false;node('canvas').events.keydown({key:value,preventDefault(){prevented=true}});assert.ok(prevented)};
  return {root,node,images,viewer,values,deleted,key,draws:()=>draws,disconnected:()=>observerDisconnected};
}
const f=fixture();assert.equal(f.images.length,1);assert.equal(f.draws(),0);
f.images[0].onload();assert.equal(f.draws(),1);assert.equal(f.node('.panorama-status').hidden,true);
assert.equal(f.values.aspect,4/3);f.key('ArrowRight');assert.ok(f.values.yaw>0);
for(let i=0;i<100;i++)f.key('ArrowUp');assert.ok(f.values.pitch<=1.45);
for(let i=0;i<100;i++)f.key('ArrowRight');assert.ok(f.values.yaw>=0&&f.values.yaw<2*Math.PI);
f.key('+');assert.ok(f.values.scale<Math.tan(75*Math.PI/360));f.key('Home');assert.equal(f.values.yaw,0);assert.equal(f.values.pitch,0);
f.node('canvas').events.pointerdown({button:0,pointerId:1,clientX:200,clientY:100});
f.node('canvas').events.pointermove({pointerId:1,clientX:150,clientY:110});assert.ok(f.values.yaw>0&&f.values.pitch>0);
f.node('canvas').events.pointerup({pointerId:1});const before=f.values.yaw;
f.node('canvas').events.pointermove({pointerId:1,clientX:50,clientY:110});assert.equal(f.values.yaw,before);
f.viewer.destroy();f.viewer.destroy();assert.equal(f.deleted.length,5);assert.equal(f.disconnected(),1);assert.equal(Object.keys(f.node('canvas').events).length,0);assert.equal(f.images[0].onload,null);
const unsupported=fixture({webgl:false});assert.equal(unsupported.images.length,0);assert.equal(unsupported.node('canvas').hidden,true);assert.match(unsupported.node('.panorama-status').textContent,/fotos/);assert.equal(unsupported.node('.panorama-stage').children[0].href,'/examples/interiores/sala-360.webp');
const invalid=fixture();invalid.images[0].naturalWidth=1000;invalid.images[0].onload();assert.equal(invalid.draws(),0);assert.equal(invalid.node('canvas').hidden,true);
const failed=fixture();failed.images[0].onerror();assert.match(failed.node('.panorama-status').textContent,/reintentar/);assert.equal(failed.deleted.length,5);
console.log('Panorama passed: spherical image validation, rotation, pitch/zoom bounds, touch drag, keyboard, cleanup and failure fallback.');
