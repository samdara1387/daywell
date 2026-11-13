'use strict';
const form=document.querySelector('#auth-form');
const message=document.querySelector('#form-message');
const button=document.querySelector('#submit-button');
let mode='login', firstAccount=false, emailConfigured=false, challengeId=null, rememberSignup=false;
function setStep(verify){
  document.querySelector('#credentials-step').hidden=verify;
  document.querySelector('#verification-step').hidden=!verify;
  form.elements.email.required=!verify;
  form.elements.password.required=!verify;
  form.elements.code.required=verify;
  button.firstChild.textContent=verify?'Verify email ':'Create account ';
  if(verify)form.elements.code.focus();
}
function show(next){
  mode=next;challengeId=null;
  setStep(false);
  document.querySelector('#login-tab').setAttribute('aria-selected',String(mode==='login'));
  document.querySelector('#signup-tab').setAttribute('aria-selected',String(mode==='signup'));
  document.querySelector('#signup-fields').hidden=mode!=='signup';
  document.querySelector('#password').autocomplete=mode==='signup'?'new-password':'current-password';
  document.querySelector('#form-title').textContent=mode==='signup'?'Create your space':'Sign in to your space';
  document.querySelector('#form-intro').textContent=mode==='signup'?'A clearer way to care for your money and your days.':'Pick up where you left off.';
  button.firstChild.textContent=mode==='signup'?'Create account ':'Sign in ';
  button.disabled=mode==='signup'&&!firstAccount&&!emailConfigured;
  message.textContent=mode==='signup'&&!firstAccount&&!emailConfigured?'New accounts are waiting for the administrator to connect email delivery.':'';
}
async function post(path,data){
  const response=await fetch('/api/auth/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result=await response.json();
  if(!response.ok)throw Error(result.error||'Could not complete this step. Please try again.');
  return result;
}
document.querySelector('#login-tab').addEventListener('click',()=>show('login'));
document.querySelector('#signup-tab').addEventListener('click',()=>show('signup'));
document.querySelector('#restart-signup').addEventListener('click',()=>show('signup'));
form.addEventListener('submit',async event=>{
  event.preventDefault();button.disabled=true;message.textContent='';
  const fields=new FormData(form);
  try{
    if(mode==='signup'&&challengeId){
      await post('signup/verify',{challengeId,code:fields.get('code'),remember:rememberSignup});
    }else if(mode==='signup'&&!firstAccount){
      rememberSignup=fields.has('remember');
      const result=await post('signup/start',{email:fields.get('email'),password:fields.get('password'),privacyAccepted:fields.has('privacyAccepted')});
      challengeId=result.challengeId;
      document.querySelector('#code-description').textContent='We sent an eight-digit code to '+result.email+'. It expires in 10 minutes.';
      setStep(true);button.disabled=false;return;
    }else{
      await post(mode,{email:fields.get('email'),password:fields.get('password'),remember:fields.has('remember'),privacyAccepted:fields.has('privacyAccepted')});
    }
    sessionStorage.removeItem('daywell-drafts');window.location.replace('/');
  }catch(error){message.textContent=error.message;button.disabled=false}
});
fetch('/api/auth/setup').then(response=>response.json()).then(result=>{
  firstAccount=!!result.firstAccount;emailConfigured=!!result.emailConfigured;
  if(firstAccount){show('signup');document.querySelector('#form-intro').textContent='Set up the first account to protect your existing Daywell records.'}
}).catch(()=>{});
