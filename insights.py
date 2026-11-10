"""Local financial analysis; integer cents throughout."""
from datetime import date, timedelta
from collections import defaultdict, Counter
import hashlib, json, re, math

# Get today in the date format used by stored records.
def local_today(): return date.today().isoformat()
# Move a YYYY-MM-DD date by a number of days.
def shift(day,n): return (date.fromisoformat(day)+timedelta(days=n)).isoformat()
# Count calendar days inclusively for averages and comparisons.
def days(start,end): return (date.fromisoformat(end)-date.fromisoformat(start)).days+1
# Check a requested analysis range before calculating anything.
def bounds(start,end):
    date.fromisoformat(start);date.fromisoformat(end)
    if start>end: raise ValueError('Start date must be on or before end date.')
    if days(start,end)>3660: raise ValueError('Choose a range of up to ten years.')
    return {'from':start,'to':end}
# Match the rounding rule used by the browser charts.
def jsround(n): return math.floor(n+0.5)
# Add integer cents and guard against totals too large for browser numbers.
def total(rows):
    n=sum(t['amount'] for t in rows)
    if abs(n)>9007199254740991: raise ValueError('These totals exceed the supported amount range. Narrow the dates.')
    return n
# Hash important transaction fields to detect stale suggestions.
def fingerprint(t):
    return hashlib.sha256(json.dumps([t.get(k) for k in ['id','date','type','amount','category','note']],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
# Group rows by a chosen key and sum each group.
def aggregate(rows,key):
    amounts=defaultdict(int)
    for t in rows: amounts[key(t)]+=t['amount']
    return [{'label':k,'amount':v} for k,v in amounts.items()]
# Calculate spending, income, categories, budgets, and trends locally.
def analyze(state,start,end,as_of=None):
    as_of=as_of or local_today();bounds(start,end);date.fromisoformat(as_of);through=min(end,as_of)
    rows=[t for t in state['transactions'] if start<=t['date']<=through]
    expenses=[t for t in rows if t['type']=='expense'];income=[t for t in rows if t['type']=='income']
    future=[t for t in state['transactions'] if start<=t['date']<=end and t['date']>as_of]
    elapsed=days(start,through) if start<=through else 0
    prior_to=shift(start,-1);prior_from=shift(start,-max(elapsed,1))
    previous=[t for t in state['transactions'] if prior_from<=t['date']<=prior_to and t['type']=='expense']
    spent,earned,prior=total(expenses),total(income),total(previous)
    categories=sorted(aggregate(expenses,lambda t:t['category']),key=lambda t:-t['amount'])
    daily=[{'label':shift(start,i),'amount':total([t for t in expenses if t['date']==shift(start,i)])} for i in range(elapsed)] if elapsed<=366 else []
    monthly={}
    for t in rows:
        key=t['date'][:7];monthly.setdefault(key,{'label':key,'income':0,'expense':0});monthly[key][t['type']]+=t['amount']
    budgets=[]
    for b in state['budgets']:
        if start[:7]<=b['month']<=end[:7]:
            actual=total([t for t in state['transactions'] if t['type']=='expense' and t['date'].startswith(b['month']) and t['date']<=as_of and t['category']==b['category']])
            budgets.append({'month':b['month'],'category':b['category'],'limit':b['amount'],'spent':actual,'remaining':b['amount']-actual})
    return {'range':{'from':start,'to':end,'asOf':as_of,'through':through if through>=start else None,'elapsedDays':elapsed},'currency':state['settings']['currency'],'transactionCount':len(rows),'expenseCount':len(expenses),'income':earned,'expenses':spent,'net':earned-spent,'averageDaily':jsround(spent/elapsed) if elapsed else 0,'previous':{'from':prior_from,'to':prior_to,'days':elapsed,'expenses':prior,'change':spent-prior,'percent':jsround((spent-prior)/prior*1000)/10 if prior else None},'future':{'count':len(future),'expenses':total([t for t in future if t['type']=='expense']),'income':total([t for t in future if t['type']=='income'])},'categories':categories,'daily':daily,'monthly':sorted(monthly.values(),key=lambda m:m['label']),'budgets':budgets,'largest':[{k:t[k] for k in ['date','note','category','amount']} for t in sorted(expenses,key=lambda t:-t['amount'])[:5]]}

# Each rule has a category, a text pattern, and a plain-language reason shown in review.
# Suggestions are never applied until the user selects them.
RULES=[('Food & groceries',r'\b(grocer(?:y|ies)?|supermarket|loblaws|no frills|freshco|sobeys|metro grocery|whole foods|trader joe|aldi|lidl)\b','Grocery-related description'),('Dining out',r'\b(restaurant|cafe|coffee|starbucks|tim hortons|mcdonald|burger|pizza|doordash|uber eats|ubereats|skipthe dishes|takeout|dining)\b','Restaurant or food delivery description'),('Housing',r'\b(rent|mortgage|hydro|electricity|utilities|water bill|property tax)\b','Housing or utility description'),('Transport',r'\b(uber|lyft|taxi|transit|ttc|presto|parking|gasoline|fuel|petrol|car insurance)\b','Transport-related description'),('Health',r'\b(pharmacy|prescription|dentist|dental|doctor|physio|optometrist|medical)\b','Health-related description'),('Subscriptions',r'\b(netflix|spotify|disney\+?|subscription|icloud|youtube premium|prime membership)\b','Subscription-related description'),('Education',r'\b(tuition|textbook|school fee|course|udemy|coursera)\b','Education-related description'),('Entertainment',r'\b(cinema|movie|concert|theatre|theater|museum|video game|steam games)\b','Entertainment-related description'),('Travel',r'\b(airline|airfare|flight|hotel|airbnb|booking\.com)\b','Travel-related description'),('Gifts',r'\b(gift|donation|charity)\b','Gift or donation description')]
# Simplify merchant descriptions for category matching.
def normalize(s):
    s=re.sub(r'^bill:\s*','',str(s or '').lower());return ' '.join(''.join(c if c.isalpha() or c.isspace() else ' ' for c in s).split())
# Suggest categories from past entries and transparent keyword rules.
def suggestions(state,start,end):
    bounds(start,end);history=defaultdict(Counter)
    for t in state['transactions']:
        key=normalize(t['note'])
        if t['type']=='expense' and key and t['category']!='Other':history[key][t['category']]+=1
    proposals=[];reviewed=0
    for t in state['transactions']:
        if t['type']!='expense' or not start<=t['date']<=end:continue
        reviewed+=1;suggested=None;confidence='Review';reason='';h=history[normalize(t['note'])]
        if len(h)==1 and t['category']=='Other':
            category,count=next(iter(h.items()))
            if count>=2:suggested=category;reason='Matches at least two of your similarly described expenses';confidence='Strong match'
        if not suggested:
            matches=[r for r in RULES if re.search(r[1],t['note'] or '',re.I)]
            if len(matches)==1:suggested,_,reason=matches[0];confidence='Keyword match'
        if suggested and suggested!=t['category']:proposals.append({**{k:t[k] for k in ['id','date','note','amount']},'current':t['category'],'suggested':suggested,'reason':reason,'confidence':confidence,'fingerprint':fingerprint(t)})
    return {'reviewed':reviewed,'proposals':proposals[:200],'total':len(proposals),'truncated':len(proposals)>200}
# Turn phrases like last month into exact date boundaries.
def scope_for_question(question,start,end,as_of=None):
    as_of=as_of or local_today();q=question.lower();a,b=start,end
    if re.search(r'\blast month\b',q) and not re.search(r'\bthis month\b',q):b=shift(as_of[:7]+'-01',-1);a=b[:7]+'-01'
    elif re.search(r'\bthis month\b',q):a=as_of[:7]+'-01';b=as_of
    elif re.search(r'\bthis year\b',q):a=as_of[:4]+'-01-01';b=as_of
    elif re.search(r'\btoday\b',q):a=b=as_of
    elif m:=re.search(r'\blast (\d{1,3}) days\b',q):
        n=int(m[1])
        if n<1:raise ValueError('Choose at least one day.')
        a=shift(as_of,1-n);b=as_of
    if m:=re.search(r'\b(\d{4}-\d{2}-\d{2})\s+(?:to|through)\s+(\d{4}-\d{2}-\d{2})\b',q):a,b=m[1],m[2]
    return bounds(a,b)
# Reduce analysis to the numeric summary shown before an online request.
def share_summary(a):
    return {'currency':a['currency'],'range':a['range'],'transactionCount':a['transactionCount'],'expenseCount':a['expenseCount'],**{k:a[k]/100 for k in ['income','expenses','net','averageDaily']},'previous':{**a['previous'],'expenses':a['previous']['expenses']/100,'change':a['previous']['change']/100},'categories':[{'category':c['label'],'amount':c['amount']/100} for c in a['categories']],'monthly':[{'month':m['label'],'income':m['income']/100,'expenses':m['expense']/100} for m in a['monthly']],'budgets':[{**b,**{k:b[k]/100 for k in ['limit','spent','remaining']}} for b in a['budgets']],'futureExcludedCount':a['future']['count']}
# Answer common money questions using local calculations.
def local_answer(state,question,start,end,as_of=None):
    if not isinstance(question,str) or not question.strip() or len(question)>2000:raise ValueError('Ask a question of up to 2,000 characters.')
    as_of=as_of or local_today();scope=scope_for_question(question,start,end,as_of);a=analyze(state,scope['from'],scope['to'],as_of);q=question.lower();chart='categories';recognized=True
    # Format an amount of cents as a readable currency amount.
    def m(n):return f"{a['currency']} {n/100:,.2f}"
    match=lambda pattern:re.search(pattern,q)
    aliases={'Food & groceries':r'\b(grocer(?:y|ies)|food)\b','Dining out':r'\b(dining|restaurant|takeout|coffee)\b','Transport':r'\b(transport|transit|fuel)\b','Housing':r'\b(housing|rent|utilities)\b','Subscriptions':r'\bsubscriptions?\b'}
    focused=next((c for c in a['categories'] if c['label'].lower() in q or (c['label'] in aliases and match(aliases[c['label']]))),None)
    intro=f"For {scope['from']} to {a['range']['through'] or scope['to']}, your recorded expenses are {m(a['expenses'])} across {a['expenseCount']} entries."
    if match(r'\b(invest|stock|crypto|tax|loan|mortgage rate|credit score)\b'):text='The offline helper handles your recorded spending, budgets, and charts. For investment, tax, or lending decisions, speak with a qualified professional who can consider your full situation. I can help review spending or test a savings scenario.';recognized=False
    elif match(r'\b(categori[sz]e|categori[sz]ation|sort.*expenses)\b'):text=f"I found {suggestions(state,scope['from'],scope['to'])['total']} category suggestions. Open Review categories to inspect and apply them. Nothing changes until you select and apply a suggestion."
    elif match(r'\b(afford|buy|purchase)\b'):
        text=intro+f"\nRecorded income minus expenses is {m(a['net'])}. This is not your bank balance or an affordability decision; debts, opening balances and unrecorded commitments may be missing."
        if value:=match(r'(?:\$|cad\s*|usd\s*)(\d+(?:\.\d{1,2})?)'):text+=f"\nA {m(jsround(float(value[1])*100))} purchase would leave {m(a['net']-jsround(float(value[1])*100))} of this recorded cash flow."
        text+='\nCheck upcoming bills, essential costs, and your own savings buffer before deciding.';chart='cashflow'
    elif match(r'\b(save|saving|reduce|cut|help|advice)\b'):
        flexible=[focused] if focused else [c for c in a['categories'] if c['label'] in ['Dining out','Entertainment','Shopping','Subscriptions','Travel']];base=sum(c['amount'] for c in flexible);pm=match(r'(\d+(?:\.\d+)?)\s*%');pct=float(pm[1]) if pm else 10
        if not 0<=pct<=100:raise ValueError('Use a reduction percentage from 0 to 100.')
        text=intro+'\n'+(f"Your {focused['label'] if focused else 'Dining out, Entertainment, Shopping, Subscriptions and Travel'} entries total {m(base)}. Reducing that total by {pct:g}% would free up {m(jsround(base*pct/100))} over the same period. This is a scenario, not a promise or a judgment." if base else 'Review your largest categories and decide which expenses you consider optional. There is not enough category data to estimate a reduction.')+'\nReview subscriptions you no longer use, then set a category limit you can realistically maintain.'
    elif match(r'\b(budget|overspend|over budget|limit)\b'):
        over=[b for b in a['budgets'] if b['remaining']<0];text='No monthly category budgets are set for this range. Add limits in Budgets & bills.' if not a['budgets'] else '\n'.join(f"{b['month']} · {b['category']}: {m(-b['remaining'])} over ({m(b['spent'])} spent / {m(b['limit'])} limit)." for b in over) if over else 'Your recorded spending is within each configured monthly category limit. Categories without a budget are not covered.'
    elif match(r'\b(compare|comparison|increase|decrease|more|less|change)\b'):
        prev=a['previous'];text=intro+f"\nThe previous equal-length period ({prev['from']} to {prev['to']}) has {m(prev['expenses'])} in recorded expenses. "+('No prior spending is recorded for a percentage comparison.' if prev['percent'] is None else f"That is {abs(prev['percent']):g}% {'higher' if prev['change']>=0 else 'lower'} spending ({m(abs(prev['change']))} difference).")+'\nMissing records can make this comparison incomplete.';chart='comparison'
    elif focused and match(r'\b(spend|spent|cost|expense|much|chart|graph)\w*'):text=f"Your recorded {focused['label']} expenses total {m(focused['amount'])} from {scope['from']} to {a['range']['through'] or scope['to']}. That is {jsround(focused['amount']/a['expenses']*100) if a['expenses'] else 0}% of recorded spending."
    elif match(r'\b(biggest|largest|top|expensive)\b'):text=intro+'\n'+('\n'.join(f"{t['date']} · {t['note'] or t['category']}: {m(t['amount'])} ({t['category']})" for t in a['largest']) or 'There are no expenses in this range.')
    elif match(r'\b(daily|day by day|trend|over time)\b'):text=intro+f"\nAverage recorded spending per calendar day is {m(a['averageDaily'])} over {a['range']['elapsedDays']} elapsed days. Days without entries count as zero; incomplete records reduce the usefulness of that average.";chart='daily' if a['daily'] else 'monthly'
    elif match(r'\b(income|cash flow|cashflow|balance|net)\b'):text=f"Recorded income: {m(a['income'])}.\nRecorded expenses: {m(a['expenses'])}.\nIncome minus expenses: {m(a['net'])}.\nThis is not a verified bank balance.";chart='cashflow'
    elif match(r'\b(chart|graph|spend|spent|expense|categor|summary|overview|money|where)\w*'):
        text=intro+'\n'+('\n'.join(f"{c['label']}: {m(c['amount'])} ({jsround(c['amount']/a['expenses']*100)}%)" for c in a['categories'][:8]) or 'There are no expenses to break down yet.')
        if match(r'\bmonthly|by month|year\b'):chart='monthly'
    else:recognized=False;text='I am the offline spending helper, using local calculations and category rules rather than a language model. Try Where did my money go?, Compare my spending, Show a daily chart, Am I over budget?, or How could I reduce spending? Switch to Online AI for broader conversation.'
    if a['future']['count']:text+=f"\n{a['future']['count']} future-dated entries are excluded from actual spending."
    return {'mode':'offline','reply':text,'chart':chart,'analysis':a,'recognized':recognized}
