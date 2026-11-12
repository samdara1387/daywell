(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.DaywellMoneyModel=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const sum=items=>items.reduce((total,item)=>total+item.amount,0);
  const ordinal=date=>Date.parse(date+'T12:00:00Z')/86400000;
  const shift=(date,days)=>{const d=new Date(date+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10)};
  function snapshot(state,through){
    const month=through.slice(0,7),transactions=state.transactions.filter(t=>t.date.startsWith(month)&&t.date<=through);
    const income=sum(transactions.filter(t=>t.type==='income')),expense=sum(transactions.filter(t=>t.type==='expense'));
    const groups=new Map();for(const t of transactions.filter(t=>t.type==='expense'))groups.set(t.category,(groups.get(t.category)||0)+t.amount);
    const categories=[...groups].map(([name,amount])=>({name,amount})).sort((a,b)=>b.amount-a.amount||a.name.localeCompare(b.name));
    const net=income-expense,retained=Math.max(0,net),gap=Math.max(0,-net);
    const nodes=categories.slice(0,3).map(c=>({...c,kind:'expense',categories:[c.name]}));
    if(categories.length>3)nodes.push({name:'Other spending',amount:categories.slice(3).reduce((s,c)=>s+c.amount,0),kind:'expense',categories:categories.slice(3).map(c=>c.name)});
    if(retained)nodes.push({name:'Net remainder',amount:retained,kind:'remainder',categories:[]});
    return {month,through,transactions,income,expense,net,retained,gap,categories,nodes,total:Math.max(income,expense)};
  }
  function calendar(state,through){
    const month=through.slice(0,7),count=new Date(Date.UTC(Number(month.slice(0,4)),Number(month.slice(5,7)),0)).getUTCDate();
    const tx=state.transactions.filter(t=>t.date.startsWith(month)&&t.date<=through);
    const days=Array.from({length:count},(_,i)=>{const date=month+'-'+String(i+1).padStart(2,'0'),items=tx.filter(t=>t.date===date);return {date,expense:sum(items.filter(t=>t.type==='expense')),income:sum(items.filter(t=>t.type==='income')),count:items.length,inScope:date<=through}});
    const max=Math.max(0,...days.map(d=>d.expense)),active=days.filter(d=>d.expense>0),total=active.reduce((s,d)=>s+d.expense,0);
    return {days,max,total,daysWithExpenses:active.length,average:active.length?Math.round(total/active.length):0,biggest:active.sort((a,b)=>b.expense-a.expense||a.date.localeCompare(b.date))[0]||null};
  }
  function scenario(base,percent,goal){
    if(!Number.isSafeInteger(base)||base<0||!Number.isInteger(percent)||percent<0||percent>50)throw Error('Invalid scenario');
    const reduction=Math.round(base*percent/100),limit=base-reduction;
    const impact=goal?{before:Math.min(100,Math.floor(goal.saved/goal.target*100)),after:Math.min(100,Math.floor((goal.saved+reduction)/goal.target*100)),saved:goal.saved+reduction,remaining:Math.max(0,goal.target-goal.saved-reduction),complete:goal.saved+reduction>=goal.target}:null;
    return {base,percent,reduction,limit,impact};
  }
  function billTimeline(state,through){
    const end=shift(through,29),overdue=state.bills.filter(b=>b.nextDate<through).sort((a,b)=>a.nextDate.localeCompare(b.nextDate));
    const upcoming=state.bills.filter(b=>b.nextDate>=through&&b.nextDate<=end).sort((a,b)=>a.nextDate.localeCompare(b.nextDate));
    const weeks=Array.from({length:5},(_,i)=>{const start=shift(through,i*7),finish=shift(through,Math.min(i*7+6,29)),bills=upcoming.filter(b=>b.nextDate>=start&&b.nextDate<=finish);return {start,end:finish,bills,amount:sum(bills)}});
    return {end,overdue,upcoming,weeks,total:sum(upcoming),overdueTotal:sum(overdue)};
  }
  function nextMonth(date){const d=new Date(date.slice(0,7)+'-01T12:00:00Z');d.setUTCMonth(d.getUTCMonth()+1);return d.toISOString().slice(0,7)}
  return {snapshot,calendar,scenario,billTimeline,nextMonth,shift};
});
