(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.DaywellPlanning=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const dayNumber=d=>Date.parse(d+'T12:00:00Z')/86400000;
  function goalPlan(goal,day){
    const remaining=Math.max(0,goal.target-goal.saved);
    const days=Math.max(1,Math.round(dayNumber(goal.due)-dayNumber(day))+1);
    return {remaining,days,daily:Math.ceil(remaining/days),weekly:Math.min(remaining,Math.ceil(remaining/days)*7),complete:remaining===0,overdue:remaining>0&&goal.due<day,percent:Math.min(100,Math.floor(goal.saved/goal.target*100))};
  }
  function budgetPace(state,day){
    const month=day.slice(0,7), budgets=state.budgets.filter(b=>b.month===month);
    const expenses=state.transactions.filter(t=>t.type==='expense'&&t.date.startsWith(month)&&t.date<=day);
    const categories=new Set(budgets.map(b=>b.category));
    const allocated=budgets.reduce((sum,b)=>sum+b.amount,0);
    const spent=expenses.filter(t=>categories.has(t.category)).reduce((sum,t)=>sum+t.amount,0);
    const unbudgeted=expenses.filter(t=>!categories.has(t.category)).reduce((sum,t)=>sum+t.amount,0);
    const end=new Date(Date.UTC(Number(day.slice(0,4)),Number(day.slice(5,7)),0)).getUTCDate();
    const days=end-Number(day.slice(8))+1;
    return {hasBudget:budgets.length>0,allocated,spent,unbudgeted,remaining:allocated-spent,days,daily:Math.floor(Math.max(0,allocated-spent)/days)};
  }
  function projection(daily,days){
    if(!Number.isSafeInteger(daily)||daily<0||!Number.isInteger(days)||days<1||days>366)throw Error('Invalid savings projection');
    return daily*days;
  }
  return {goalPlan,budgetPace,projection};
});
