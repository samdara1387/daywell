'use strict';
let csrf='';
let myEmailChallenge='';
const $=selector=>document.querySelector(selector);
const safe=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
async function api(path,method='GET',data={}){
  const response=await fetch('/api/'+path,{method,headers:method==='GET'?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:method==='GET'?undefined:JSON.stringify(data)});
  const value=await response.json();
  if(!response.ok){const error=Error(value.error||'Could not load this information.');error.status=response.status;throw error}
  return value;
}
let unlockPromise=null;
function askForPassword(){
  if(unlockPromise)return unlockPromise;
  const dialog=$('#admin-unlock'),form=$('#admin-unlock-form');
  form.reset();$('#unlock-error').textContent='';dialog.showModal();form.elements.password.focus();
  unlockPromise=new Promise((resolve,reject)=>{
    const cancel=()=>{dialog.close();reject(Error('Password confirmation cancelled.'))};
    const submit=async event=>{
      event.preventDefault();const button=form.querySelector('[type="submit"]');button.disabled=true;
      try{await api('admin/unlock','POST',{password:form.elements.password.value});form.elements.password.value='';dialog.close();resolve()}
      catch(error){$('#unlock-error').textContent=error.message;form.elements.password.select()}
      finally{button.disabled=false}
    };
    const close=()=>{form.removeEventListener('submit',submit);$('#cancel-unlock').removeEventListener('click',cancel);dialog.removeEventListener('cancel',onCancel);unlockPromise=null};
    const onCancel=event=>{event.preventDefault();cancel()};
    form.addEventListener('submit',submit);$('#cancel-unlock').addEventListener('click',cancel);dialog.addEventListener('cancel',onCancel);dialog.addEventListener('close',close,{once:true});
  });
  return unlockPromise;
}
async function adminApi(path,method='GET',data={}){
  try{return await api(path,method,data)}
  catch(error){if(error.status!==403||!error.message.startsWith('Confirm your password'))throw error;await askForPassword();return api(path,method,data)}
}
async function start(){
  try{
    const session=await api('auth/session');csrf=session.csrf;
    if(session.user.role!=='admin'){location.replace('/');return}
    $('#admin-email').textContent=session.user.email;
    const email=await api('admin/email/config');
    $('#email-status').textContent=email.configured?'Connected':'Setup needed';
    if(email.configured){for(const key of ['host','port','username','sender'])$('#email-settings').elements[key].value=email[key]}
    if(session.emailVerified)$('#start-my-verification').textContent='My email is verified';
    const summary=await api('admin/summary');
    $('#user-count').textContent=summary.users.length;
    $('#users').innerHTML=summary.users.map(user=>`<div class="user"><div class="user-avatar" aria-hidden="true">${safe(user.email[0].toUpperCase())}</div><div><strong>${safe(user.email)}</strong><span>${safe(user.role)} · joined ${safe(user.created.slice(0,10))}</span></div><button type="button" data-user="${safe(user.id)}">View workspace ↗</button></div>`).join('');
  }catch(error){$('#users').textContent=error.message}
}
$('#users').addEventListener('click',async event=>{
  const button=event.target.closest('[data-user]');if(!button)return;
  button.disabled=true;
  try{
    const result=await adminApi('admin/users/'+encodeURIComponent(button.dataset.user)+'/state');
    const state=result.state,transactions=state.transactions||[];
    const expense=transactions.filter(item=>item.type==='expense').reduce((sum,item)=>sum+item.amount,0);
    const income=transactions.filter(item=>item.type==='income').reduce((sum,item)=>sum+item.amount,0);
    const currency=state.settings?.currency||'CAD';
    const format=amount=>new Intl.NumberFormat(undefined,{style:'currency',currency}).format(amount/100);
    $('#detail-title').textContent=result.user.email;
    $('#detail-metrics').innerHTML=`<div><small>TRANSACTIONS</small><strong>${transactions.length}</strong></div><div><small>INCOME</small><strong>${safe(format(income))}</strong></div><div><small>SPENDING</small><strong>${safe(format(expense))}</strong></div><div><small>GOALS</small><strong>${state.goals?.length||0}</strong></div>`;
    $('#detail-json').textContent=JSON.stringify(state,null,2);
    $('#detail').hidden=false;$('#detail').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(error){alert(error.message)}finally{button.disabled=false}
});
$('#close-detail').addEventListener('click',()=>{$('#detail').hidden=true;$('#detail-json').textContent='' });
$('#logout').addEventListener('click',async()=>{try{await api('auth/logout','POST');location.replace('/')}catch(error){alert(error.message)}});
$('#email-settings').addEventListener('submit',async event=>{
  event.preventDefault();const form=event.currentTarget,button=form.querySelector('button[type="submit"]');button.disabled=true;
  try{const data=Object.fromEntries(new FormData(form));data.port=Number(data.port);await adminApi('admin/email/config','POST',data);form.elements.password.value='';$('#email-status').textContent='Connected';$('#email-message').textContent='Email settings saved. Send a test email before inviting people.'}
  catch(error){$('#email-message').textContent=error.message}finally{button.disabled=false}
});
$('#test-email').addEventListener('click',async event=>{event.currentTarget.disabled=true;try{const result=await adminApi('admin/email/test','POST');$('#email-message').textContent='Test email sent to '+result.sentTo+'. Check your inbox.'}catch(error){$('#email-message').textContent=error.message}finally{event.currentTarget.disabled=false}});
$('#start-my-verification').addEventListener('click',async event=>{event.currentTarget.disabled=true;try{const result=await api('auth/email/start','POST');myEmailChallenge=result.challengeId;$('#verify-my-email').hidden=false;$('#email-message').textContent='Enter the code sent to '+result.email+'.';$('#verify-my-email').elements.code.focus()}catch(error){$('#email-message').textContent=error.message}finally{event.currentTarget.disabled=false}});
$('#verify-my-email').addEventListener('submit',async event=>{event.preventDefault();const button=event.currentTarget.querySelector('button');button.disabled=true;try{await api('auth/email/verify','POST',{challengeId:myEmailChallenge,code:event.currentTarget.elements.code.value});myEmailChallenge='';event.currentTarget.hidden=true;$('#start-my-verification').textContent='My email is verified';$('#email-message').textContent='Your email is verified.'}catch(error){$('#email-message').textContent=error.message}finally{button.disabled=false}});
start();
