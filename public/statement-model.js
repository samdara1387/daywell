/* Local, deterministic statement parsing. Files are data, never instructions. */
(function(root,factory){const api=factory();if(typeof module==='object')module.exports=api;else root.DaywellStatements=api})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const clean=s=>String(s??'').replace(/^\uFEFF/,'').trim();
 const normalize=s=>clean(s).toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
 function amount(value,decimal='dot'){
  let s=clean(value),credit=/\bCR\s*$/i.test(s),negative=/^[-−]|[-−]$|^\(.*\)$/.test(s)||credit;
  s=s.replace(/\b(?:CAD|USD|AUD|EUR|GBP|CR|DR)\b/gi,'').replace(/[$€£\s()＋+−-]/g,'');
  if(decimal==='comma'){if(!/^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?$/.test(s))return null;s=s.replace(/\./g,'').replace(',','.');}else {if(!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$/.test(s))return null;s=s.replace(/,/g,'');}
  if(!/^\d+(?:\.\d{1,2})?$/.test(s))return null;
  const parts=s.split('.'),n=Number(parts[0])*100+Number((parts[1]||'').padEnd(2,'0'));
  return Number.isSafeInteger(n)&&n<=1e12?(negative?-n:n):null;
 }
 function validDate(y,m,d){const s=`${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;if(!/^\d{4}-\d{2}-\d{2}$/.test(s)||y<1900||y>9998)return '';const date=new Date(s+'T12:00:00Z');return Number.isFinite(+date)&&date.toISOString().slice(0,10)===s?s:''}
 const months=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];
 function parseDate(value,order='mdy',end=''){
  let s=clean(value),match,y,m,d;
  if((match=s.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:\s+00:00:00)?$/)))return validDate(+match[1],+match[2],+match[3]);
  if((match=s.match(/^(\d{1,2})[-/.](\d{1,2})(?:[-/.](\d{2}|\d{4}))?$/))){[m,d]=order==='dmy'?[+match[2],+match[1]]:[+match[1],+match[2]];y=match[3]?+match[3]:null;}
  else if((match=s.match(/^([A-Za-z]{3,9})\s+(\d{1,2})(?:,?\s+(\d{4}))?$/))){m=months.indexOf(match[1].slice(0,3).toLowerCase())+1;d=+match[2];y=match[3]?+match[3]:null;}
  else if((match=s.match(/^(\d{1,2})\s+([A-Za-z]{3,9})(?:\s+(\d{4}))?$/))){m=months.indexOf(match[2].slice(0,3).toLowerCase())+1;d=+match[1];y=match[3]?+match[3]:null;}else return '';
  if(y!==null&&y<100)y+=2000;
  if(y===null){if(!/^\d{4}-\d{2}-\d{2}$/.test(end))return '';y=+end.slice(0,4);if(m>+end.slice(5,7))y--;}
  return validDate(y,m,d);
 }
 function csv(text,delimiter){
  text=String(text).replace(/^\uFEFF/,'');if(text.length>10e6)throw Error('Use a file smaller than 10 MB.');
  if(!delimiter){const sample=text.split(/\r?\n/).slice(0,20),score=d=>Math.max(0,...sample.map(line=>{let quoted=false,n=0;for(let i=0;i<line.length;i++){if(line[i]==='"'){if(quoted&&line[i+1]==='"')i++;else quoted=!quoted;}else if(!quoted&&line[i]===d)n++;}return n}));delimiter=[',',';','\t'].sort((a,b)=>score(b)-score(a))[0];}
  const rows=[];let row=[],cell='',quote=false;
  for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quote&&text[i+1]==='"'){cell+='"';i++;}else if(!quote&&cell.length)cell+=c;else quote=!quote;}else if(c===delimiter&&!quote){row.push(cell);cell='';}else if((c==='\r'||c==='\n')&&!quote){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(x=>clean(x)))rows.push(row);row=[];cell='';}else cell+=c;if(rows.length>5000)throw Error('Import up to 5,000 rows at a time.');}
  if(quote)throw Error('A quoted CSV field is unfinished. Export the file again from your bank.');row.push(cell);if(row.some(x=>clean(x)))rows.push(row);return rows;
 }
 function mapping(headers){
  const names=headers.map(normalize),find=patterns=>names.findIndex(n=>patterns.some(p=>p.test(n)));
  return {date:find([/^(transaction |purchase |posted |posting |trans )?date$/]),note:find([/description/,/merchant/,/payee/,/^details$/,/transaction detail/]),amount:find([/^amount$/, /transaction amount/]),debit:find([/^debit/,/^withdrawal/,/^charge/]),credit:find([/^credit/,/^deposit/]),type:find([/^type$/,/transaction type/]),currency:find([/^currency$/,/currency code/])};
 }
 function suggest(note,history=[]){
  const key=normalize(note),previous=history.filter(t=>t.type==='expense'&&normalize(t.note)===key);if(key&&previous.length&&new Set(previous.map(t=>t.category)).size===1)return {category:previous[0].category,reason:'Matches a previous expense'};
  const rules=[['Food & groceries',/grocery|groceries|supermarket|loblaws|sobeys|metro |freshco|no frills|whole foods/],['Dining out',/restaurant|cafe|coffee|starbucks|tim hortons|mcdonald|ubereats|doordash|pizza/],['Transport',/transit|parking|gas station|petro|esso|shell |uber |lyft|presto/],['Subscriptions',/netflix|spotify|subscription|adobe/],['Health',/pharmacy|shoppers drug|dental|clinic/],['Housing',/rent |hydro|electric|utilities/],['Shopping',/amazon|walmart|ikea/],['Travel',/airline|air canada|hotel|airbnb/]];
  const found=rules.find(([,re])=>re.test(key));return {category:found?found[0]:'Other',reason:found?'Suggested from description':'Choose a category'};
 }
 const fingerprint=r=>[r.date,r.type||'expense',r.amount,normalize(r.note)].join('|');
 function classify(note,n,type,options){
  if(/\b(payment received|payment.*thank|payment from|autopay|automatic payment|paiement|thank you|pmt received)\b/i.test(note)||/^(payment|pmt)$/i.test(clean(type)))return 'Card payment — excluded';
  if(/\b(refund|reversal|credit voucher|return credit)\b/i.test(note)||/^(credit|cr|refund|deposit|income)$/i.test(clean(type)))return 'Credit or refund — excluded';
  if(n!==null&&((options.sign==='negative'&&n>0)||(options.sign!=='negative'&&n<0)))return 'Credit or refund — excluded';
  return '';
 }
 function csvCandidates(rows,map,options={},history=[]){
  return rows.map((cells,index)=>{
   const get=k=>map[k]>=0?clean(cells[map[k]]):'',note=get('note'),rawDate=get('date'),date=parseDate(rawDate,options.order,options.end);
   let n,reason='';
   if(options.mode==='split'){const debit=amount(get('debit'),options.decimal),credit=amount(get('credit'),options.decimal);n=debit;if(credit)reason='Credit or refund — excluded';if(debit&&credit)reason='Both debit and credit present — check source';}
   else n=amount(get('amount'),options.decimal);
   reason=reason||(/\bCR\s*$/i.test(get('amount'))?'Credit or refund — excluded':'')||classify(note,n,get('type'),options);
   const currency=get('currency').toUpperCase();if(currency&&currency!==options.currency)reason=`Different currency (${currency}) — excluded`;
   const errors=[!date?'Check the date':'',!n?'Check the amount':'',!note?'Add a description':''].filter(Boolean);
   const suggestion=suggest(note,history);
   return {index,date,rawDate,note,amount:n===null?'':Math.abs(n),type:'expense',...suggestion,reason:reason||suggestion.reason,blocked:!!reason,errors,selected:!reason&&!errors.length,source:cells.join(' | ').slice(0,1000)};
  });
 }
 const dateToken='(?:\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}|\\d{1,2}[-/]\\d{1,2}(?:[-/]\\d{2,4})?|[A-Za-z]{3,9}\\s+\\d{1,2}(?:,?\\s+\\d{4})?|\\d{1,2}\\s+[A-Za-z]{3,9}(?:\\s+\\d{4})?)';
 function pdfCandidates(lines,options={},history=[]){
  const rows=[],unparsed=[];const re=new RegExp('^('+dateToken+')\\s+(?:('+dateToken+')\\s+)?(.+?)\\s+([($€£+−-]?[\\d,.]+(?:\\s*(?:CR|DR))?\\)?-?)$','i');
  const starts=new RegExp('^'+dateToken+'\\s+','i');
  lines.forEach((line,index)=>{
   const s=clean(line),m=s.match(re);if(!m){if(starts.test(s))unparsed.push({line:index+1,text:s});return;}
   // Summary balances and statement dates never become purchases.
   if(/^(?:previous|opening|closing|new|total|minimum|balance|statement|payment due|interest rate)\b/i.test(m[3]))return;
   const candidates=csvCandidates([[m[1],m[3],m[4]]],{date:0,note:1,amount:2},options,history);
   rows.push({...candidates[0],index,source:s});
  });return {rows,unparsed};
 }
 function flagDuplicates(rows,existing){const known=new Set(existing.map(fingerprint)),seen=new Set();return rows.map(row=>{const key=fingerprint(row),duplicate=known.has(key)||seen.has(key);seen.add(key);return {...row,duplicate,selected:row.selected&&!duplicate,reason:duplicate?'Possible duplicate — excluded':row.reason}})}
 function pdfAutoPlan(lines,currency,history=[]){
  const headings=new Set(lines.map(line=>normalize(line)));
  const resume=['education','technical skills','experience','projects','profile'].filter(h=>headings.has(h)).length>=3;
  if(resume)return {rows:[],selected:[],unparsed:[],end:'',currencyMismatch:false,assumedCurrency:false,documentType:'resume'};
  const first=lines.slice(0,40);
  const header=first.flatMap((line,i)=>/statement|period|cycle|closing|ending|through/i.test(line)?[line,first[i+1]||'']:[]);
  const datePattern=/(?:\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b|\b\d{1,2}[-/.]\d{1,2}[-/.]\d{4}\b)/gi;
  const dates=header.flatMap(line=>[...line.matchAll(datePattern)].map(m=>parseDate(m[0])).filter(Boolean));
  const labelIndex=first.findIndex(line=>/\bstatement date\b/i.test(line));
  const labeledDates=labelIndex<0?[]:[first[labelIndex],first[labelIndex+1]||''].flatMap(line=>[...line.matchAll(datePattern)].map(m=>parseDate(m[0])).filter(Boolean));
  const end=labeledDates[0]||dates.sort().at(-1)||'';
  const codes=new Set((header.join(' ').match(/\b(?:CAD|USD|EUR|GBP|AUD|NZD|INR|AED|JPY|CHF|CNY)\b/gi)||[]).map(s=>s.toUpperCase()));
  const currencyMismatch=codes.size>0&&(!codes.has(currency)||codes.size>1);
  const options={order:'mdy',sign:'positive',decimal:'dot',end,currency};
  const cibc=first.some(line=>/\bCIBC\b/i.test(line))&&lines.some(line=>/your new charges and credits/i.test(line));
  let inTable=false;
  const input=cibc?lines.map(line=>{if(/your payments|your new charges and credits/i.test(line))inTable=true; if(/^total (?:payments|for)\b/i.test(clean(line)))inTable=false; return inTable&&new RegExp('^'+dateToken+'\\s+'+dateToken+'\\s+.+\\s+[$]?\\d[\\d,]*\\.\\d{2}(?:\\s*(?:CR|DR))?$', 'i').test(clean(line))?line:''}):lines;
  const parsed=pdfCandidates(input,options,history);
  let rows=flagDuplicates(parsed.rows,history).map(row=>{
   const invalidYearless=!end&&!/\d{4}/.test(row.rawDate);
   const lower=end?new Date(Date.parse(end+'T12:00:00Z')-93*86400000).toISOString().slice(0,10):'';
   const outsidePeriod=!!end&&!!row.date&&(row.date>end||row.date<lower);
   const uncertain=currencyMismatch?'Statement currency differs from your workspace — excluded':invalidYearless?'Statement year could not be found — excluded':outsidePeriod?'Date is outside the detected statement year — excluded':'';
   return uncertain?{...row,selected:false,blocked:true,reason:uncertain}:row;
  });
  const selected=rows.filter(row=>row.selected&&row.date&&row.amount>0&&row.note);
  return {rows,selected,unparsed:parsed.unparsed,end,currencyMismatch,assumedCurrency:codes.size===0};
 }
 return {amount,parseDate,csv,mapping,suggest,csvCandidates,pdfCandidates,flagDuplicates,pdfAutoPlan,fingerprint,normalize};
});
