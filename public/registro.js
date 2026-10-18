'use strict';
const registrationForm=document.getElementById('registrationForm');
registrationForm.addEventListener('change',()=>{const agency=registrationForm.elements.accountType.value==='agency';document.getElementById('agencyField').hidden=!agency;registrationForm.elements.agencyName.required=agency});
registrationForm.addEventListener('submit',async event=>{
  event.preventDefault();const error=document.getElementById('registrationError'),submit=registrationForm.querySelector('[type=submit]');error.textContent='';
  if(registrationForm.elements.password.value!==registrationForm.elements.repeatPassword.value){error.textContent='Las contraseñas no coinciden.';return}
  submit.disabled=true;submit.textContent='Creando tu espacio…';
  try{
    const data=Object.fromEntries(new FormData(registrationForm));delete data.repeatPassword;data.acceptTerms=registrationForm.elements.acceptTerms.checked;
    const response=await fetch('/api/public/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    const result=await response.json();if(!response.ok)throw Error(result.error||'No se pudo crear la cuenta.');
    location.assign('/#publicaciones');
  }catch(e){error.textContent=e instanceof TypeError?'No hay conexión. Revisá tu conexión y volvé a intentar.':e.message;submit.disabled=false;submit.textContent='Crear cuenta y entrar'}
});
