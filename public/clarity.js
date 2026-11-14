'use strict';
// Category identity stays stable when amounts, sorting, or the selected period change.
const clarityCategoryColors=['#83cbb7','#baa9eb','#edbd84','#87bce0','#df9fab','#b7cb80','#d9afe2','#88c7d1','#dfad85','#a6b6eb','#c2bd8c','#a4d6ba','#c5a2be','#b0bac8'];
function categoryColor(name){let n=categories.indexOf(name);if(n<0){n=0;for(const c of name)n=(n*31+c.charCodeAt(0))>>>0;}return clarityCategoryColors[n%clarityCategoryColors.length];}
function applyClarity(){
  if(!state)return;
  document.querySelectorAll('.stat').forEach(card=>{const label=card.querySelector('.stat-label')?.textContent||'',negative=!!card.querySelector('.stat-value.negative')||/^[−-]/.test(card.querySelector('.stat-value')?.textContent.trim()||'');const tone=negative?'alert':/GOAL|SET ASIDE/.test(label)?'goal':/TASK|HABIT|REFLECTION/.test(label)?'life':/EXPENSE|SPENDING|MONEY OUT|BILLS/.test(label)?'expense':/INCOME|MONEY IN|CASH FLOW/.test(label)?'income':null;if(tone)card.dataset.tone=tone;});
  document.querySelectorAll('[data-studio-cat]').forEach(el=>{const color=categoryColor(el.dataset.studioCat);if(el.tagName.toLowerCase()==='circle')el.setAttribute('stroke',color);else el.style.setProperty('--segment',color);});
  if(page==='overview'){const snap=DaywellMoneyModel.snapshot(state,selected);snap.nodes.forEach((node,i)=>{const color=node.kind==='remainder'?'var(--data-income)':categoryColor(node.name);document.querySelectorAll(`[data-flow-band="${i}"]`).forEach(p=>p.style.stroke=color);document.querySelector(`[data-money-flow="${i}"]>i`)?.style.setProperty('--node-colour',color);});}
  const report=document.querySelector('.reports-studio');if(report)report.dataset.measure=studio.metric;
  if(page==='reports')document.querySelectorAll('.budget-row').forEach(row=>{const label=row.querySelector('div>span')?.textContent;const bar=row.querySelector('.progress-track>div');if(label&&bar)bar.style.background=categoryColor(label);});
}
document.addEventListener('click',event=>{if(event.target.closest('#main'))requestAnimationFrame(applyClarity);});
