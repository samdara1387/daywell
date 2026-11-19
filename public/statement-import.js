'use strict';
let statementSession=null;
function importShell(step,content){
 const modal=$('#statement-modal');modal.innerHTML=`<div class="import-head"><div><span class="eyebrow">STATEMENT IMPORT</span><h2>${['Add expenses from a statement','Check how your file is read','Review your expenses','Your expenses are ready'][step]}</h2></div><button class="icon-button" id="import-close" aria-label="Close statement import">✕</button></div>${statementSession?.kind==='csv'?`<ol class="import-steps" aria-label="Import progress">${['Choose file','Check format','Review & save'].map((s,i)=>`<li class="${step===i?'current':step>i?'complete':''}" ${step===i?'aria-current="step"':''}><span>${step>i?'✓':i+1}</span>${s}</li>`).join('')}</ol>`:''}<div id="import-body">${content}</div><p id="import-error" class="form-error" role="alert"></p>`;
 $('#import-close').onclick=()=>modal.close();if(!modal.open)modal.showModal();modal.scrollTop=0;modal.querySelector('h2').tabIndex=-1;modal.querySelector('h2').focus();
}
function openStatementImport(){
 statementSession={rows:[],fileHash:'',options:{order:'mdy',sign:'positive',decimal:'dot',mode:'amount',currency:state.settings.currency,end:''}};
 importShell(0,`<div class="import-intro"><div class="import-file-art" aria-hidden="true"><span>≡</span><i>✓</i></div><h3>Upload a statement. Preview your expenses.</h3><p>Choose a readable credit-card PDF. Money Theory finds the purchases, prepares a preview, and saves the expenses when you confirm.</p></div><label class="import-drop"><strong>Choose a PDF statement</strong><span>Readable PDF · up to 10 MB</span><input id="statement-file" type="file" accept=".csv,.pdf,text/csv,application/pdf"></label><details class="import-help"><summary>Have a CSV instead?</summary><p>CSV imports still let you review columns and expenses. Scanned or protected PDFs need a CSV export from your bank.</p></details><div id="import-history"></div>`);
 $('#statement-file').onchange=async e=>{const file=e.target.files[0];if(file)await readStatementFile(file)};
 const current=statementSession;api('imports').then(items=>{if(statementSession!==current||!$('#import-history'))return;const last=items.find(i=>!i.undone&&i.count);if(last){$('#import-history').innerHTML=`<div class="import-history"><span>Last import · ${last.count} expenses · ${new Date(last.created).toLocaleDateString()}</span><button class="text-button" id="undo-previous">Undo this import</button></div>`;$('#undo-previous').onclick=()=>showImportUndo(last.id,last.count)}}).catch(()=>{});
 $('#statement-modal').onclose=()=>{statementSession=null};
}
async function readStatementFile(file){
 const session=statementSession;try{
  if(file.size>10*1024*1024||!file.size)throw Error('Choose a non-empty file smaller than 10 MB.');
  const ext=file.name.toLowerCase().split('.').pop();if(!['csv','pdf'].includes(ext))throw Error('Choose a CSV or text-based PDF. For Excel, export as CSV first.');
  $('#statement-file').disabled=true;$('#import-error').textContent='Reading your file on this device…';
  const buffer=await file.arrayBuffer();session.fileHash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',buffer)),x=>x.toString(16).padStart(2,'0')).join('');session.kind=ext;session.name=file.name;
  if(ext==='csv'){
   const bytes=new Uint8Array(buffer);let text;if(bytes[0]===255&&bytes[1]===254)text=new TextDecoder('utf-16le').decode(buffer);else if(bytes[0]===254&&bytes[1]===255)text=new TextDecoder('utf-16be').decode(buffer);else {try{text=new TextDecoder('utf-8',{fatal:true}).decode(buffer)}catch{text=new TextDecoder('windows-1252').decode(buffer)}}
   session.table=DaywellStatements.csv(text);if(!session.table.length)throw Error('The CSV contains no rows.');
   session.header=Math.max(0,session.table.slice(0,20).findIndex(row=>{const m=DaywellStatements.mapping(row);return m.date>=0&&m.note>=0&&(m.amount>=0||m.debit>=0)}));
   session.map=DaywellStatements.mapping(session.table[session.header]);if(session.map.date<0&&session.table[0].some(cell=>DaywellStatements.parseDate(cell,'mdy')||DaywellStatements.parseDate(cell,'dmy')))session.header=-1;session.options.mode=session.map.amount<0&&session.map.debit>=0?'split':'amount';
  }else{
   const pdfjs=await import('./vendor/pdf.min.mjs');pdfjs.GlobalWorkerOptions.workerSrc='/vendor/pdf.worker.min.mjs';
   const loading=pdfjs.getDocument({data:new Uint8Array(buffer),isEvalSupported:false,useSystemFonts:true,stopAtErrors:true});let doc;
   try{doc=await loading.promise;if(doc.numPages>60)throw Error('Use a PDF with 60 pages or fewer, or download a CSV.');const lines=[];
    for(let n=1;n<=doc.numPages;n++){const page=await doc.getPage(n),text=await page.getTextContent(),groups=[];
     for(const item of text.items){if(!item.str?.trim())continue;const y=item.transform[5];let group=groups.find(g=>Math.abs(g.y-y)<2.5);if(!group){group={y,items:[]};groups.push(group)}group.items.push(item)}
     groups.sort((a,b)=>b.y-a.y).forEach(g=>lines.push(g.items.sort((a,b)=>a.transform[4]-b.transform[4]).map(i=>i.str).join(' ')));page.cleanup();
    }session.lines=lines;if(lines.join('').length<30)throw Error('This looks like a scanned statement. Download a CSV or searchable PDF from your bank.');
   }finally{await loading.destroy()}
  }
  if(statementSession!==session)return;if(ext==='pdf')await autoImportPdf(session);else showImportFormat();
 }catch(err){if(statementSession!==session)return;$('#import-error').textContent=err.name==='PasswordException'?'This PDF is password-protected. Use a CSV export or an unlocked copy.':err.message||'This file could not be read. Try a CSV export.';if($('#statement-file'))$('#statement-file').disabled=false;}
}
async function autoImportPdf(session,confirmed=false){
 const plan=DaywellStatements.pdfAutoPlan(session.lines,state.settings.currency,state.transactions);
 session.rows=plan.rows;session.unparsed=plan.unparsed;session.options.end=plan.end;
 const skipped=plan.rows.filter(r=>!r.selected).length+plan.unparsed.length;
 if(!plan.selected.length){
  const repeated=plan.rows.length>0&&plan.rows.every(r=>r.duplicate||r.reason==='Possible duplicate — excluded');
  const title=plan.documentType==='resume'?'This looks like a résumé':repeated?'This statement is already imported':'No expenses were added';
  const explanation=plan.documentType==='resume'?'This file contains résumé information rather than a list of purchases. Choose a bank or credit-card statement to add expenses.':repeated?'All detected purchases already appear in Money Theory. Nothing was added again.':plan.currencyMismatch?'The statement labels a different currency from your Money Theory workspace. Nothing was added.':'Money Theory could not identify purchases confidently from this PDF. Your records are unchanged.';
  importShell(3,`<div class="import-success"><h3>${title}</h3><p>${explanation}</p><button class="secondary" id="pdf-try-another">Try another file</button>${plan.documentType==='resume'?'':'<button class="text-button" id="pdf-review">Inspect detected lines</button>'}</div>`);
  $('#statement-modal h2').textContent=title;
  $('#pdf-try-another').onclick=openStatementImport;if($('#pdf-review'))$('#pdf-review').onclick=showImportReview;return;
 }
 if(!confirmed){
  importShell(3,`<div class="import-preview"><h3>Review your statement</h3><p>${esc(session.name)}</p><div class="preview-summary"><strong>${plan.selected.length} expenses · ${money(plan.selected.reduce((n,r)=>n+r.amount,0))}</strong><p>${skipped} payment, credit, duplicate or unclear lines excluded.</p>${plan.assumedCurrency?`<p>Currency was not labeled. Amounts will use ${esc(state.settings.currency)}.</p>`:''}</div>${pdfPreviewRows(plan.selected)}<p>Nothing has been saved yet. Dates and categories are filled in for you.</p><div class="actions"><button class="primary" id="pdf-confirm">Add these ${plan.selected.length} expenses</button><button class="secondary" id="pdf-cancel">Cancel</button><button class="text-button" id="pdf-adjust">Adjust entries</button></div></div>`);
  $('#statement-modal h2').textContent='Preview before saving';
  $('#pdf-confirm').onclick=()=>autoImportPdf(session,true);$('#pdf-cancel').onclick=()=>$('#statement-modal').close();$('#pdf-adjust').onclick=showImportReview;return;
 }
 importShell(3,`<div class="import-success"><div class="import-success-icon">↗</div><h3>Adding ${plan.selected.length} expenses…</h3><p>Reading the clear purchases into your Money Theory records.</p></div>`);
 $('#import-close').disabled=true;$('#statement-modal').oncancel=e=>e.preventDefault();
 try{
  if(!await approveStatementMonths(session,plan.selected))return;
  const result=await api('import/commit','POST',{allowMonthOverlap:session.allowMonthOverlap===true,fileHash:session.fileHash,currency:state.settings.currency,rows:plan.selected.map(r=>({index:r.index,date:r.date,note:r.note,amount:r.amount,category:r.category,type:'expense'}))});
  if(statementSession!==session)return;await refresh();
  const skippedText=skipped||result.skipped?`<p>${skipped} unclear, credit, payment or duplicate lines were left out. ${result.skipped?`${result.skipped} matching saved expenses were also skipped.`:''}</p>`:'';
  importShell(3,`<div class="import-success"><div class="import-success-icon">✓</div><h3>${result.added} expense${result.added===1?'':'s'} added</h3><p>Your spending charts and budgets are updated. ${plan.assumedCurrency?`Amounts were treated as ${esc(state.settings.currency)} because the PDF did not label a currency.`:''}</p>${skippedText}${pdfPreviewRows(plan.selected)}<div class="actions"><button class="primary" id="pdf-done">See my expenses →</button>${result.added?'<button class="secondary" id="pdf-undo">Undo import</button>':''}</div></div>`);
  $('#pdf-done').onclick=()=>{if(plan.selected.length)selected=plan.selected.map(r=>r.date).sort().at(-1);period='month';query='';typeFilter='expense';studio.category=null;$('#statement-modal').close();location.hash='money';render()};
  if($('#pdf-undo'))$('#pdf-undo').onclick=()=>showImportUndo(result.id,result.added);

 }catch(err){if(statementSession!==session)return;importShell(3,`<div class="import-success"><h3>Nothing was added</h3><p>${esc(err.message)}</p><button class="secondary" id="pdf-retry">Try again</button></div>`);$('#statement-modal h2').textContent='Import needs attention';$('#pdf-retry').onclick=()=>autoImportPdf(session)}
 finally{if($('#import-close'))$('#import-close').disabled=false;$('#statement-modal').oncancel=null;}
}
function formatSelect(label,name,choices,value){return `<label class="field"><span>${label}</span><select id="import-${name}">${choices.map(([v,label])=>`<option value="${v}" ${String(v)===String(value)?'selected':''}>${esc(label)}</option>`).join('')}</select></label>`}
function showImportFormat(){
 const s=statementSession,o=s.options,cols=s.kind==='csv'?(s.header<0?Array.from({length:Math.max(...s.table.slice(0,20).map(r=>r.length))},(_,i)=>`Column ${i+1}`):s.table[s.header]):[],choices=[[-1,'Not present'],...cols.map((v,i)=>[i,`${i+1}. ${v||'Unnamed column'}`])];
 importShell(1,`<div class="import-file-line"><span>▧ ${esc(s.name)}</span><button class="text-button" id="import-new">Choose another file</button></div><p class="form-intro">Confirm the date and amount format your bank uses. These choices prevent reversed dates or credits being counted as expenses.</p>${s.kind==='csv'?`<details class="import-column-mapping" ${s.map.date<0||s.map.note<0||(o.mode==='amount'?s.map.amount<0:s.map.debit<0)?'open':''}><summary>Adjust columns <small>Dates, descriptions and amounts are matched automatically when possible</small></summary>`:''}<div class="import-format-grid">${s.kind==='csv'?formatSelect('Header row','header',[[-1,'No header — all rows are transactions'],...s.table.slice(0,20).map((r,i)=>[i,`Row ${i+1}: ${r.join(' · ').slice(0,85)}`])],s.header)+formatSelect('Date column','date',choices,s.map.date)+formatSelect('Description column','note',choices,s.map.note)+formatSelect('Amount columns','mode',[['amount','One amount column'],['split','Separate debit and credit columns']],o.mode)+(o.mode==='amount'?formatSelect('Amount column','amount',choices,s.map.amount):formatSelect('Debit / charge column','debit',choices,s.map.debit)+formatSelect('Credit / payment column','credit',choices,s.map.credit))+formatSelect('Currency column (if present)','currency-column',choices,s.map.currency):''}</div>${s.kind==='csv'?'</details>':''}<div class="import-format-grid">${formatSelect('Numeric date format','order',[['mdy','Month / day / year'],['dmy','Day / month / year']],o.order)}${formatSelect('Decimal separator','decimal',[['dot','Dot: 1,234.56'],['comma','Comma: 1.234,56']],o.decimal)}${o.mode==='amount'?formatSelect('Purchases are shown as','sign',[['positive','Positive amounts (e.g. 25.00)'],['negative','Negative amounts (e.g. -25.00)']],o.sign):''}<label class="field"><span>Statement end date <small>for dates without a year</small></span><input type="date" id="import-end" value="${o.end}" required></label></div><details class="import-source"><summary>Preview the original file text</summary><pre>${esc((s.kind==='csv'?s.table.slice(Math.max(0,s.header),Math.max(0,s.header)+6).map(r=>r.join(' | ')):s.lines.slice(0,70)).join('\n'))}</pre></details><label class="import-check"><input type="checkbox" id="import-currency-confirm">This statement uses <strong>${esc(state.settings.currency)}</strong>, my workspace currency. No currency conversion is needed.</label><div class="import-footer"><span>Nothing has been saved.</span><button class="primary" id="import-preview">Find expenses →</button></div>`);
 $('#import-new').onclick=openStatementImport;
 if(s.kind==='csv'){
  $('#import-header').onchange=e=>{s.header=Number(e.target.value);s.map=DaywellStatements.mapping(s.table[s.header]||[]);showImportFormat();$('.import-column-mapping').open=true};
  $('#import-mode').onchange=e=>{captureFormat();o.mode=e.target.value;showImportFormat();$('.import-column-mapping').open=true};
 }
 $('#import-preview').onclick=()=>{try{captureFormat();if(!$('#import-currency-confirm').checked)throw Error('Confirm the statement currency before continuing.');
  if(s.kind==='csv'&&(s.map.date<0||s.map.note<0||(o.mode==='amount'?s.map.amount<0:s.map.debit<0)))throw Error('Choose the date, description and amount columns.');
  if(s.kind==='csv'){const mapped=[s.map.date,s.map.note,o.mode==='amount'?s.map.amount:s.map.debit,...(o.mode==='split'&&s.map.credit>=0?[s.map.credit]:[])];if(new Set(mapped).size!==mapped.length)throw Error('Choose a different column for each field.');}
  const result=s.kind==='csv'?{rows:DaywellStatements.csvCandidates(s.table.slice(s.header+1),s.map,o,state.transactions).map(r=>({...r,index:r.index+s.header+1})),unparsed:[]}:DaywellStatements.pdfCandidates(s.lines,o,state.transactions);
  if(!o.end&&result.rows.some(r=>!r.date&&DaywellStatements.parseDate(r.rawDate,o.order,'2026-12-31')))throw Error('Enter the statement end date so dates without a year can be read correctly.');
  s.rows=DaywellStatements.flagDuplicates(result.rows,state.transactions);s.unparsed=result.unparsed;if(s.rows.length>5000)throw Error('Import up to 5,000 rows at a time.');showImportReview();
 }catch(err){$('#import-error').textContent=err.message}};
}
function captureFormat(){const s=statementSession;for(const key of ['order','decimal','sign','mode','end'])if($('#import-'+key))s.options[key]=$('#import-'+key).value;if(s.kind==='csv'){for(const key of ['date','note','amount','debit','credit'])if($('#import-'+key))s.map[key]=Number($('#import-'+key).value);s.map.currency=Number($('#import-currency-column').value)}}
function reviewRow(row,i){return `<article class="import-row ${row.selected?'is-selected':''}"><label class="import-select"><input type="checkbox" data-row-select="${i}" ${row.selected?'checked':''} aria-label="Include row ${i+1}"><span>${i+1}</span></label><div class="import-row-fields"><label class="field"><span>Date</span><input type="date" data-row-date="${i}" value="${esc(row.date)}" required></label><label class="field import-description"><span>Description</span><input data-row-note="${i}" value="${esc(row.note)}" maxlength="2000" placeholder="Description"></label><label class="field"><span>Amount (${esc(state.settings.currency)})</span><input type="number" min="0.01" step="0.01" data-row-amount="${i}" value="${row.amount===''?'':(row.amount/100).toFixed(2)}"></label><label class="field"><span>Category</span><select data-row-category="${i}">${[...new Set([...categories,row.category])].map(c=>`<option ${c===row.category?'selected':''}>${esc(c)}</option>`).join('')}</select></label><div class="import-row-note"><span class="${row.duplicate||row.blocked||row.errors.length?'review-warning':''}">${esc(row.errors.length?row.errors.join(' · '):row.reason)}</span><details><summary>Source row</summary><p>${esc(row.source)}</p></details></div></div></article>`}
function showImportReview(){
 const s=statementSession;s.reviewPage=0;
 importShell(2,`<div class="import-file-line"><span>▧ ${esc(s.name)}</span><button class="text-button" id="import-back">← Adjust file format</button></div><div class="import-review-summary" id="import-summary" aria-live="polite"></div><p class="import-review-instruction">Check the rows against your statement. Only checked rows become expenses. Category suggestions are editable. Selecting a payment, credit or duplicate overrides its exclusion.</p>${s.kind==='pdf'?'<p class="import-warning">PDF layouts vary. Some purchases may be missed; compare all detected rows and the total with your statement before saving.</p>':''}${s.unparsed?.length?`<details class="import-warning"><summary>${s.unparsed.length} date-like lines could not be read — check these</summary>${s.unparsed.map(r=>`<p>Line ${r.line}: ${esc(r.text)}</p>`).join('')}</details>`:''}<div class="import-review-toolbar"><label><input id="import-show-excluded" type="checkbox"> Show excluded rows only</label><button class="text-button" id="import-deselect">Deselect all</button></div><div id="import-rows"></div><div class="import-pagination" id="import-pagination"></div><div class="import-save-panel"><label class="import-check"><input type="checkbox" id="import-reviewed">I checked the dates, amounts and selected expenses against my statement.</label><div class="import-footer"><span id="import-save-note">Your original file is not stored.</span><button class="primary" id="import-save">Save selected expenses</button></div></div>`);
 $('#import-back').onclick=showImportFormat;
 $('#import-show-excluded').onchange=()=>{s.reviewPage=0;renderReviewRows()};
 $('#import-deselect').onclick=()=>{s.rows.forEach(r=>r.selected=false);renderReviewRows();$('#import-reviewed').checked=false};
 $('#import-save').onclick=saveStatementImport;renderReviewRows();
}
function renderReviewRows(){
 const s=statementSession,filtered=s.rows.map((r,i)=>({r,i})).filter(({r})=>!$('#import-show-excluded').checked||!r.selected),pages=Math.max(1,Math.ceil(filtered.length/25));s.reviewPage=Math.min(s.reviewPage,pages-1);
 $('#import-rows').innerHTML=filtered.length?filtered.slice(s.reviewPage*25,s.reviewPage*25+25).map(({r,i})=>reviewRow(r,i)).join(''):`<div class="import-empty"><h3>${s.rows.length?'No excluded rows':'No purchases were detected'}</h3><p>${s.rows.length?'All rows are selected.':'Adjust the format settings, or use a CSV transaction export from your bank.'}</p></div>`;
 $('#import-pagination').innerHTML=pages>1?`<button class="secondary" id="import-prev-page" ${s.reviewPage===0?'disabled':''}>Previous</button><span>Page ${s.reviewPage+1} of ${pages} · ${filtered.length} rows</span><button class="secondary" id="import-next-page" ${s.reviewPage===pages-1?'disabled':''}>Next</button>`:'';
 for(const [id,delta] of [['import-prev-page',-1],['import-next-page',1]])if($('#'+id))$('#'+id).onclick=()=>{s.reviewPage+=delta;renderReviewRows();$('#import-rows').scrollIntoView({block:'start'})};
 $('#import-rows').oninput=e=>{const el=e.target,key=Object.keys(el.dataset).find(k=>k.startsWith('row'));if(!key)return;const row=s.rows[Number(el.dataset[key])];if(key==='rowSelect'){row.selected=el.checked;el.closest('.import-row').classList.toggle('is-selected',row.selected)}else if(key==='rowAmount'){row.amount=DaywellStatements.amount(el.value)}else row[key.slice(3).toLowerCase()]=el.value;$('#import-reviewed').checked=false;updateImportSummary()};
 updateImportSummary();
}
function updateImportSummary(){const rows=statementSession.rows,selectedRows=rows.filter(r=>r.selected),total=selectedRows.reduce((sum,r)=>sum+(Number.isSafeInteger(r.amount)?r.amount:0),0);$('#import-summary').innerHTML=`<div><span>Ready to save</span><strong>${selectedRows.length} <small>expenses</small></strong></div><div><span>Selected total</span><strong>${money(total)}</strong></div><div><span>Not selected</span><strong>${rows.length-selectedRows.length} <small>rows</small></strong></div>`;$('#import-save').disabled=!selectedRows.length;$('#import-save').textContent=`Save ${selectedRows.length} expense${selectedRows.length===1?'':'s'}`}
async function saveStatementImport(){
 const s=statementSession,button=$('#import-save');try{
  if(!$('#import-reviewed').checked)throw Error('Check the review confirmation before saving.');
  const rows=s.rows.filter(r=>r.selected);for(const r of rows){if(!r.date||DaywellStatements.parseDate(r.date)!==r.date||!Number.isSafeInteger(r.amount)||r.amount<=0||!r.note.trim())throw Error(`Check the date, description and positive amount in row ${r.index+1}.`)}
  button.disabled=true;$('#import-close').disabled=true;$('#import-body').inert=true;$('#import-error').textContent='Saving reviewed expenses…';$('#statement-modal').oncancel=e=>e.preventDefault();
  if(!await approveStatementMonths(s,rows))return;
  const result=await api('import/commit','POST',{allowMonthOverlap:s.allowMonthOverlap===true,fileHash:s.fileHash,currency:s.options.currency,rows:rows.map(r=>({index:r.index,date:r.date,note:r.note,amount:r.amount,category:r.category,type:'expense',allowDuplicate:!!r.duplicate}))});
  await refresh();
  importShell(3,`<div class="import-success"><div class="import-success-icon">✓</div><h3>${result.added} expense${result.added===1?'':'s'} saved</h3><p>${result.skipped?`${result.skipped} already-saved or matching rows were skipped. `:''}Your charts and budgets now include these expenses.</p><button class="primary" id="import-done">See my expenses →</button>${result.added?'<button class="text-button" id="import-undo">Undo this import</button>':''}<small>You can also undo recent imports from the import window.</small></div>`);
  $('#import-done').onclick=()=>{if(rows.length)selected=rows.map(r=>r.date).sort().at(-1);period='month';query='';typeFilter='expense';studio.category=null;$('#statement-modal').close();location.hash='money';render()};
  if($('#import-undo'))$('#import-undo').onclick=()=>showImportUndo(result.id,result.added);
 }catch(err){if($('#import-error'))$('#import-error').textContent=err.message;if(button.isConnected)button.disabled=false;}finally{if($('#import-body'))$('#import-body').inert=false;if($('#import-close'))$('#import-close').disabled=false;$('#statement-modal').oncancel=null;}
}
function showImportUndo(id,count){importShell(3,`<div class="import-success"><h3>Undo this import?</h3><p>Remove the ${count} expenses added by this import. Entries you edited afterward are kept. A recovery backup is created first.</p><div class="actions"><button class="secondary" id="undo-cancel">Keep expenses</button><button class="primary" id="undo-confirm">Undo import</button></div></div>`);$('#undo-cancel').onclick=openStatementImport;$('#undo-confirm').onclick=async()=>{try{$('#undo-confirm').disabled=true;const result=await api('import/undo','POST',{id});await refresh();$('#statement-modal').close();toast(`${result.removed} imported expenses removed${result.kept?`; ${result.kept} edited entries kept`:''}`)}catch(err){$('#import-error').textContent=err.message;$('#undo-confirm').disabled=false}}}

function pdfPreviewRows(rows){return `<div class="preview-table"><table><thead><tr><th>Date</th><th>Purchase</th><th>Category</th><th>Amount</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.date)}</td><td>${esc(r.note)}</td><td>${esc(r.category)}</td><td>${money(r.amount)}</td></tr>`).join('')}</tbody></table></div>`;}

async function approveStatementMonths(session,rows){
 const imports=await api('imports'),months=new Set(rows.map(r=>r.date.slice(0,7))),active=imports.filter(i=>!i.undone&&i.count);
 if(active.some(i=>i.fileHash===session.fileHash)){openStatementImport();$('#import-error').textContent='This statement has already been imported. Nothing was added again.';return false;}
 const overlaps=[...new Set(active.flatMap(i=>i.months||[]).filter(m=>months.has(m)))];
 if(!overlaps.length)return true;
 const approved=window.confirm('You already imported expenses for '+overlaps.join(', ')+'.\n\nImporting the same statement again may duplicate expenses. Continue only if this is a different card or a separate statement.\n\nChoose Cancel to keep your records as they are.');
 if(!approved){openStatementImport();return false;}session.allowMonthOverlap=true;return true;
}
