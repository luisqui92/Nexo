'use strict';
// A small, on-demand spherical viewer. No remote scripts, tracking or API key.
(function(global){
  const vertex='attribute vec2 position; varying vec2 point; void main(){point=position;gl_Position=vec4(position,0.,1.);}';
  const fragment=`precision highp float;
    varying vec2 point; uniform sampler2D panorama;
    uniform float yaw; uniform float pitch; uniform float aspect; uniform float scale;
    void main(){
      vec3 d=normalize(vec3(point.x*aspect*scale,point.y*scale,-1.));
      d=vec3(d.x,cos(pitch)*d.y-sin(pitch)*d.z,sin(pitch)*d.y+cos(pitch)*d.z);
      d=vec3(cos(yaw)*d.x-sin(yaw)*d.z,d.y,sin(yaw)*d.x+cos(yaw)*d.z);
      vec2 uv=vec2(atan(d.x,-d.z)/6.28318530718+.5,.5-asin(clamp(d.y,-1.,1.))/3.14159265359);
      gl_FragColor=texture2D(panorama,uv);
    }`;
  function create(root,{url,label='Ambiente ficticio · Vista 360°'}){
    let stopped=false,ready=false,gl=null,program=null,buffer=null,texture=null,image=null,observer=null;
    let yaw=0,pitch=0,fov=75,drag=null;
    const shaders=[],listeners=[];
    root.innerHTML='<div class="panorama-stage"><canvas class="panorama-canvas" tabindex="0" role="img" aria-label="Vista 360°. Usá las flechas para mirar alrededor y los botones para acercar."></canvas><p class="panorama-status" role="status" aria-live="polite">Cargando sala en 360°…</p><span class="panorama-watermark">AMBIENTE FICTICIO · IA</span></div><div class="panorama-controls" role="group" aria-label="Controles de la vista 360"><button type="button" data-turn="-1" aria-label="Mirar a la izquierda">←</button><button type="button" data-turn="1" aria-label="Mirar a la derecha">→</button><button type="button" data-zoom="-10" aria-label="Acercar">+</button><button type="button" data-zoom="10" aria-label="Alejar">−</button><button type="button" data-reset>Restablecer</button></div><p class="panorama-help">Arrastrá para mirar alrededor. También podés usar las flechas del teclado.</p>';
    const canvas=root.querySelector('canvas'),status=root.querySelector('.panorama-status'),stage=root.querySelector('.panorama-stage'),controls=root.querySelector('.panorama-controls');
    canvas.setAttribute('aria-label',label+'. Arrastrá o usá las flechas para mirar alrededor.');
    function listen(node,name,fn,options){node.addEventListener(name,fn,options);listeners.push(()=>node.removeEventListener(name,fn,options))}
    function release(){
      if(!gl||gl.isContextLost())return;
      if(texture)gl.deleteTexture(texture);if(buffer)gl.deleteBuffer(buffer);if(program)gl.deleteProgram(program);
      shaders.forEach(shader=>gl.deleteShader(shader));texture=buffer=program=null;shaders.length=0;
    }
    function destroy(){if(stopped)return;stopped=true;ready=false;observer?.disconnect();listeners.splice(0).forEach(remove=>remove());if(image){image.onload=image.onerror=null;image.src='';image=null}release()}
    function fail(message){
      if(stopped)return;destroy();canvas.hidden=true;controls.hidden=true;status.hidden=false;status.textContent=message;
      const link=document.createElement('a');link.href=url;link.target='_blank';link.rel='noopener';link.className='panorama-fallback';link.textContent='Ver imagen panorámica';stage.append(link);
    }
    function render(){
      if(stopped||!ready)return;
      const width=Math.max(1,stage.clientWidth),height=Math.max(1,stage.clientHeight),ratio=Math.min(global.devicePixelRatio||1,2);
      canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);gl.viewport(0,0,canvas.width,canvas.height);
      gl.uniform1f(gl.getUniformLocation(program,'yaw'),yaw);gl.uniform1f(gl.getUniformLocation(program,'pitch'),pitch);
      gl.uniform1f(gl.getUniformLocation(program,'aspect'),width/height);gl.uniform1f(gl.getUniformLocation(program,'scale'),Math.tan(fov*Math.PI/360));
      gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
    }
    function move(x,y){yaw=((yaw+x)%(2*Math.PI)+2*Math.PI)%(2*Math.PI);pitch=Math.max(-1.45,Math.min(1.45,pitch+y));render()}
    function zoom(delta){fov=Math.max(35,Math.min(100,fov+delta));render()}
    function compile(type,source){const shader=gl.createShader(type);shaders.push(shader);gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error('shader');return shader}
    try{
      gl=canvas.getContext('webgl',{alpha:false,antialias:false,depth:false})||canvas.getContext('experimental-webgl',{alpha:false});
      if(!gl)throw Error('webgl');
      program=gl.createProgram();gl.attachShader(program,compile(gl.VERTEX_SHADER,vertex));gl.attachShader(program,compile(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(program);
      if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('program');gl.useProgram(program);
      buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
      const position=gl.getAttribLocation(program,'position');gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
      texture=gl.createTexture();gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
      gl.uniform1i(gl.getUniformLocation(program,'panorama'),0);
      image=new Image();image.onload=()=>{
        if(stopped)return;
        try{
          if(image.naturalWidth!==2*image.naturalHeight||image.naturalWidth>gl.getParameter(gl.MAX_TEXTURE_SIZE))throw Error('dimensions');
          gl.texImage2D(gl.TEXTURE_2D,0,gl.RGB,gl.RGB,gl.UNSIGNED_BYTE,image);
          ready=true;status.hidden=true;canvas.focus({preventScroll:true});render();
        }catch{fail('Este dispositivo no pudo mostrar la vista 360°. Podés abrir la imagen panorámica.')}
      };
      image.onerror=()=>fail('No pudimos cargar la panorámica. Cerrá la ficha y volvé a abrirla para reintentar.');
      image.src=url;
      listen(canvas,'pointerdown',event=>{if(!ready||drag||event.isPrimary===false||event.button!==0)return;drag={id:event.pointerId,x:event.clientX,y:event.clientY};canvas.setPointerCapture(event.pointerId);canvas.focus({preventScroll:true})});
      listen(canvas,'pointermove',event=>{if(!drag||event.pointerId!==drag.id)return;const unit=2*Math.tan(fov*Math.PI/360)/Math.max(1,stage.clientHeight);move((drag.x-event.clientX)*unit,(event.clientY-drag.y)*unit);drag.x=event.clientX;drag.y=event.clientY});
      const end=event=>{if(drag?.id===event.pointerId)drag=null};
      for(const name of ['pointerup','pointercancel','lostpointercapture'])listen(canvas,name,end);
      listen(canvas,'keydown',event=>{
        const keys={ArrowLeft:[-.13,0],ArrowRight:[.13,0],ArrowUp:[0,.1],ArrowDown:[0,-.1]};
        if(keys[event.key]){event.preventDefault();move(...keys[event.key])}
        else if(['+','=','-','Home'].includes(event.key)){event.preventDefault();if(event.key==='Home'){yaw=pitch=0;fov=75;render()}else zoom(event.key==='-'?10:-10)}
      });
      for(const button of root.querySelectorAll('[data-turn]'))listen(button,'click',()=>move(Number(button.dataset.turn)*.3,0));
      for(const button of root.querySelectorAll('[data-zoom]'))listen(button,'click',()=>zoom(Number(button.dataset.zoom)));
      listen(root.querySelector('[data-reset]'),'click',()=>{yaw=pitch=0;fov=75;render()});
      listen(canvas,'webglcontextlost',event=>{event.preventDefault();fail('La vista 360° se interrumpió. Cerrá la ficha y volvé a abrirla para reintentar.')});
      if(global.ResizeObserver){observer=new global.ResizeObserver(render);observer.observe(stage)}else listen(global,'resize',render);
    }catch{fail('La vista 360° no está disponible en este dispositivo. Las fotos de los ambientes siguen disponibles.')}
    return {destroy};
  }
  global.NexoPanorama={create};
})(window);
