'use strict';
let sharedMonthSeen='';
function navLinks(){
 const link=([id,,label])=>`<a href="#${id}" aria-label="${label}" class="${page===id?'active':''}" ${page===id?'aria-current="page"':''}><span class="navicon">${appIcon(id==='calendar'?'budgets':id)}</span><span class="navtext">${label}</span></a>`;
 const main=navigation.filter(n=>!['planner','goals','settings'].includes(n[0])),more=navigation.filter(n=>['planner','goals','settings'].includes(n[0]));
 return main.map(link).join('')+`<details class="nav-more"><summary>More tools <span>⌄</span></summary><div>${more.map(link).join('')}</div></details>`;
}
function syncSharedMonth(){
 const month=selected.slice(0,7),input=document.getElementById('shared-month');
 if(input)input.value=month;
 if(month!==sharedMonthSeen){sharedMonthSeen=month;period='month';const end=new Date(Number(month.slice(0,4)),Number(month.slice(5,7)),0).getDate();helperState.from=month+'-01';helperState.to=month+'-'+String(end).padStart(2,'0');helperState.analysis=null;helperState.categoryData=null;helperState.selectedChanges.clear();}
}
document.addEventListener('DOMContentLoaded',()=>{const input=document.getElementById('shared-month');input.addEventListener('change',()=>{if(!/^\d{4}-\d{2}$/.test(input.value))return;selected=input.value+'-01';period='month';render();});});
function monthlyExpensePage(){
 const month=selected.slice(0,7),first=new Date(month+'-01T12:00:00'),offset=first.getDay(),days=new Date(first.getFullYear(),first.getMonth()+1,0).getDate(),items=state.transactions.filter(t=>t.type==='expense'&&t.date.startsWith(month));
 const sums=new Map();for(const t of items)sums.set(t.date,(sums.get(t.date)||0)+t.amount);
 const total=items.reduce((s,t)=>s+t.amount,0),max=Math.max(1,...sums.values());
 const blanks=Array.from({length:offset},()=>'<span class="dw-spend-blank" aria-hidden="true"></span>').join('');
 const cells=Array.from({length:days},(_,i)=>{const day=month+'-'+String(i+1).padStart(2,'0'),amount=sums.get(day)||0,count=items.filter(t=>t.date===day).length;return `<button class="dw-spend-day ${amount?'has-spend':''}" data-dw-spend-day="${day}" style="--heat:${amount?Math.max(.1,amount/max*.5):0}" aria-label="${dateLabel(day)}, ${money(amount)} spent, ${count} expenses"><span>${i+1}</span><strong>${(amount/100).toFixed(2)}</strong><small>${count?count+' '+(count===1?'expense':'expenses'):'No expenses'}</small></button>`}).join('');
 return head('Spending calendar','See what you spent each day. Select a day to see its purchases.',null)+toolbar(false)+`<section class="card dw-spend-calendar"><div class="card-head"><div><h2>${monthLabel(selected)}</h2><p>Daily amounts are in ${esc(state.settings.currency)}. Purchases only; income is not included.</p></div><div class="dw-spend-total"><small>MONTHLY SPENDING</small><strong>${money(total)}</strong></div></div><div class="dw-spend-grid weekdays">${['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d=>`<span>${d}</span>`).join('')}</div><div class="dw-spend-grid">${blanks}${cells}</div><p class="micro-note">Darker days have higher spending. Select any day for the details.</p></section>`;
}
document.addEventListener('click',e=>{const button=e.target.closest('[data-dw-spend-day]');if(!button)return;const day=button.dataset.dwSpendDay,items=state.transactions.filter(t=>t.type==='expense'&&t.date===day);moneyDetails('Purchases · '+dateLabel(day),items,'Expenses recorded for this day.');});


const expandedEmptyPanels=new Set();
function mountCategoryTotals(){
 if(page!=='money')return;
 const expenses=filteredTransactions().filter(t=>t.type==='expense'),names=[...new Set([...categories,...state.transactions.filter(t=>t.type==='expense').map(t=>t.category)])];
 const groups=names.map(name=>({name,items:expenses.filter(t=>t.category===name)})).map(g=>({...g,total:g.items.reduce((n,t)=>n+t.amount,0)})).sort((a,b)=>b.total-a.total||a.name.localeCompare(b.name));
 const section=document.createElement('section');section.className='card dw-categories';section.id='category-totals';
 section.innerHTML=`<div class="card-head"><div><h2>Spending by category</h2><p>${periodName()} · Select a category to see its purchases. Totals include expenses only.</p></div><strong>${money(expenses.reduce((n,t)=>n+t.amount,0))}</strong></div><div class="dw-category-list">${groups.map(g=>`<details class="dw-category"><summary><span>${esc(g.name)}<small>${g.items.length} ${g.items.length===1?'purchase':'purchases'}</small></span><strong>${money(g.total)}</strong><span class="dw-expand" aria-hidden="true">⌄</span></summary><div class="dw-category-content">${g.items.length?g.items.slice().sort((a,b)=>b.date.localeCompare(a.date)).map(t=>`<div class="row"><div class="row-main"><strong>${esc(t.note||t.category)}</strong><small>${dateLabel(t.date)}</small></div><span class="row-amount">${money(t.amount)}</span><button class="edit" data-edit="transactions" data-id="${esc(t.id)}">Edit</button></div>`).join(''):'<p class="micro-note">No expenses recorded in this category for the selected period.</p>'}</div></details>`).join('')}</div>`;
 const positive=groups.filter(g=>g.total>0),highest=Math.max(1,...positive.map(g=>g.total)),grand=expenses.reduce((n,t)=>n+t.amount,0);
 const chartHtml=positive.length?`<div class="dw-category-chart" aria-label="Category spending chart">${positive.map(g=>`<button class="dw-chart-bar" data-chart-category="${esc(g.name)}" aria-label="${esc(g.name)}, ${money(g.total)}, ${Math.round(g.total/grand*100)} percent of expenses. Show purchases."><span class="dw-bar-caption"><span>${esc(g.name)}</span><strong>${money(g.total)} <small>${Math.round(g.total/grand*100)}%</small></strong></span><span class="dw-bar-track"><i style="width:${g.total/highest*100}%;background:${categoryColor(g.name)}"></i></span></button>`).join('')}</div>`:'<p class="micro-note">The chart will appear when you record expenses for this period.</p>';
 section.querySelector('.card-head').insertAdjacentHTML('afterend',chartHtml);
 section.querySelectorAll('[data-chart-category]').forEach(button=>button.onclick=()=>{const index=groups.findIndex(g=>g.name===button.dataset.chartCategory),detail=section.querySelectorAll('.dw-category')[index];detail.open=true;detail.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'center'});detail.querySelector('summary').focus({preventScroll:true});});
 const emptyCategories=[...section.querySelectorAll('.dw-category')].filter(el=>!el.querySelector('.row'));
 if(emptyCategories.length){const group=document.createElement('details');group.className='dw-zero-categories';group.innerHTML='<summary>Categories with no expenses ('+emptyCategories.length+')</summary>';section.querySelector('.dw-category-list').append(group);emptyCategories.forEach(el=>group.append(el));}
 const anchor=document.querySelector('#main>.stats');if(anchor)anchor.after(section);
 const chart=document.querySelector('#page-studio');if(chart){const details=document.createElement('details');details.className='home-explore';details.innerHTML='<summary>Explore the category chart<small>A visual breakdown of the same expenses</small></summary>';chart.before(details);details.append(chart);}
}
function collapseEmptyPanels(){
 document.querySelectorAll('#main section.card').forEach(card=>{
  if(card.closest('details')||!card.querySelector('.empty,.studio-empty')||card.querySelector('.row,.budget-row,.goal-mini,tbody tr'))return;
  const title=card.querySelector('h2')?.textContent||card.querySelector('h3')?.textContent||'More options';
  const key=page+'|'+selected.slice(0,7)+'|'+title,details=document.createElement('details'),summary=document.createElement('summary');
  details.className='dw-empty-panel';summary.textContent=title+' · No entries yet';details.append(summary);
  const content=document.createElement('div');content.className='dw-empty-content';while(card.firstChild)content.append(card.firstChild);details.append(content);card.append(details);card.classList.add('dw-collapsible-card');details.open=expandedEmptyPanels.has(key);
  details.addEventListener('toggle',()=>{if(details.open)expandedEmptyPanels.add(key);else expandedEmptyPanels.delete(key)});
 });
}
let layoutEditing=new URLSearchParams(location.search).get('arrange')==='1',layoutDragged=null;
const layoutStorageKey='daywell-layout-v1';
function readLayouts(){try{return JSON.parse(localStorage.getItem(layoutStorageKey)||'{}')}catch{return {}}}
function mountLayoutEditor(){
 const main=document.getElementById('main');document.body.classList.toggle('dw-arranging',layoutEditing);
 const toggle=document.getElementById('arrange-layout');if(toggle){toggle.textContent=layoutEditing?'Done arranging':'Arrange layout';toggle.setAttribute('aria-pressed',String(layoutEditing));toggle.onclick=()=>{layoutEditing=!layoutEditing;render()};}
 const notice=document.createElement('div');notice.className='dw-layout-notice';notice.innerHTML='<div><strong>Make this page yours</strong><p>Panels become compact tiles while arranging. Drag a tile onto another tile, or use ↑ and ↓. Click Done arranging to see the full page. Changes save in this browser.</p></div><button type="button" class="secondary" id="reset-layout">Reset this page</button>';main.prepend(notice);
 notice.querySelector('button').onclick=()=>{const saved=readLayouts();delete saved[page];try{localStorage.setItem(layoutStorageKey,JSON.stringify(saved));render();toast('Default layout restored')}catch{toast('Your browser could not reset this layout.')}};
 const parents=[main,...main.querySelectorAll('.dashboard-stack,.grid,.helper-layout,.goal-grid')];
 parents.forEach((parent,groupIndex)=>{
  const children=[...parent.children].filter(el=>el.matches('section.card,.stats,.welcome-card,.dashboard-columns,.goal-banner,.goal-grid,.helper-layout,.home-category-strip'));
  if(children.length<2)return;
  const group='group-'+groupIndex;children.forEach((el,i)=>{el.dataset.layoutKey='panel-'+i;el.dataset.layoutGroup=group;});
  const saved=readLayouts()[page]?.[group];if(Array.isArray(saved)){const order=[...children].sort((a,b)=>{const rank=x=>saved.includes(x.dataset.layoutKey)?saved.indexOf(x.dataset.layoutKey):saved.length+children.indexOf(x);return rank(a)-rank(b)});const slots=children.map(el=>{const mark=document.createComment('panel');el.before(mark);return mark});order.forEach((el,i)=>slots[i].replaceWith(el));}
  const persist=()=>{const saved=readLayouts();saved[page]||={};saved[page][group]=[...parent.children].filter(el=>el.dataset.layoutGroup===group).map(el=>el.dataset.layoutKey);try{localStorage.setItem(layoutStorageKey,JSON.stringify(saved))}catch{toast('Layout could not be saved in this browser.')}};
  children.forEach(el=>{
   el.classList.add('dw-layout-panel');const handle=document.createElement('div');handle.className='dw-layout-handle';handle.draggable=false;
   const title=el.querySelector('h2')?.textContent||({'stats':'Summary totals','welcome-card':'Monthly overview','dashboard-columns':'Dashboard panels','goal-banner':'Savings summary','goal-grid':'Savings goals','helper-layout':'Helper panels','home-category-strip':'Top categories'}[el.classList[0]])||'Panel';
   handle.innerHTML=`<span>⠿ Drag · ${esc(title)}</span><div><button type="button" aria-label="Move ${esc(title)} earlier">↑</button><button type="button" aria-label="Move ${esc(title)} later">↓</button></div>`;
   handle.addEventListener('pointerdown',event=>{
    if(event.target.closest('button')||event.button!==0)return;
    event.preventDefault();event.stopPropagation();const startX=event.clientX,startY=event.clientY;let target=null,moved=false;handle.setPointerCapture(event.pointerId);
    const move=e=>{if(Math.hypot(e.clientX-startX,e.clientY-startY)>6)moved=true;if(!moved)return;el.classList.add('dw-dragging');document.querySelectorAll('.dw-drop-target').forEach(n=>n.classList.remove('dw-drop-target'));let hit=document.elementFromPoint(e.clientX,e.clientY);while(hit&&hit.parentElement!==parent)hit=hit.parentElement;target=hit&&hit!==el&&hit.dataset.layoutGroup===group?hit:null;if(!target){const candidates=[...parent.children].filter(n=>n!==el&&n.dataset.layoutGroup===group);target=candidates.find(n=>{const rect=n.getBoundingClientRect();return e.clientY>=rect.top-12&&e.clientY<=rect.bottom+12})||null;}if(target)target.classList.add('dw-drop-target');if(e.clientY>innerHeight-50)window.scrollBy(0,25);else if(e.clientY<150)window.scrollBy(0,-25)};
    const end=()=>{handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',end);handle.removeEventListener('pointercancel',cancel);if(target&&moved){const siblings=[...parent.children];if(siblings.indexOf(el)<siblings.indexOf(target))target.after(el);else target.before(el);persist();}document.querySelectorAll('.dw-dragging,.dw-drop-target').forEach(n=>n.classList.remove('dw-dragging','dw-drop-target'));};
    const cancel=()=>{target=null;end()};handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',end);handle.addEventListener('pointercancel',cancel);
   });
   el.prepend(handle);handle.querySelectorAll('button').forEach((button,index)=>button.onclick=()=>{const siblings=[...parent.children].filter(x=>x.dataset.layoutGroup===group),at=siblings.indexOf(el),other=siblings[at+(index?1:-1)];if(other){if(index)other.after(el);else other.before(el);persist();button.focus();}});
   handle.addEventListener('dragstart',event=>{event.stopPropagation();layoutDragged=el;event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',el.dataset.layoutKey);el.classList.add('dw-dragging')});handle.addEventListener('dragend',()=>{layoutDragged=null;document.querySelectorAll('.dw-dragging,.dw-drop-target').forEach(x=>x.classList.remove('dw-dragging','dw-drop-target'))});
   el.addEventListener('dragover',event=>{if(!layoutEditing||!layoutDragged||layoutDragged===el||layoutDragged.parentElement!==parent)return;event.preventDefault();event.stopPropagation();el.classList.add('dw-drop-target')});el.addEventListener('dragleave',()=>el.classList.remove('dw-drop-target'));
   el.addEventListener('drop',event=>{if(!layoutDragged||layoutDragged===el||layoutDragged.parentElement!==parent)return;event.preventDefault();event.stopPropagation();const siblings=[...parent.children];if(siblings.indexOf(layoutDragged)<siblings.indexOf(el))el.after(layoutDragged);else el.before(layoutDragged);el.classList.remove('dw-drop-target');persist()});
  });
 });
}
