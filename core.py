"""Validation and money/date rules shared by the Daywell Python API."""
import calendar
import datetime as dt
import re
import uuid

# Each name is a collection of saved records in the SQLite database.
COLLECTIONS = ['transactions','budgets','habits','checks','tasks','journal','goals','bills']
# These preferences are used until the user saves their own settings.
DEFAULTS = {'currency':'CAD','theme':'dark','name':''}

# A validation error carries an HTTP status so the browser can show a useful message.
class APIError(ValueError):
    # Store the readable error message and the response status.
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

# Stop the current request when input does not meet a rule.
def fail(message, status=400):
    raise APIError(message, status)

# Require a JSON object (a Python dictionary) before reading its fields.
def object_value(value):
    if not isinstance(value, dict): fail('Expected an object')
    return value

# Check text length and whether blank text is allowed.
def string(value, name, maximum=200, empty=False):
    if not isinstance(value,str) or len(value)>maximum or (not empty and not value.strip()): fail('Invalid '+name)
    return value.strip()

# Exclude booleans: in Python, bool is technically a subclass of int.
def integer(value):
    return type(value) is int

# Accept only real calendar dates in YYYY-MM-DD form.
def date(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value) or not '1900-01-01'<=value<='9998-12-31': fail('Invalid date')
    try: dt.date.fromisoformat(value)
    except ValueError: fail('Invalid date')
    return value

# Represent money as whole cents to avoid floating-point rounding errors.
def money(value, positive=False):
    minimum=1 if positive else 0
    if not integer(value) or not minimum<=value<=1000000000000: fail(f'Amount must be whole cents between {minimum} and 1 trillion')
    return value

# Limit a value to known options, such as income or expense.
def choice(value, choices, name):
    if value not in choices: fail('Invalid '+name)
    return value

# Keep a recurring bill tied to its original day or month.
def anchor(value, fallback, maximum, name):
    if value is None: return fallback
    if not integer(value) or not 1<=value<=maximum: fail('Invalid '+name)
    return value

# Check preferences and fill in safe defaults.
def validate_settings(value):
    object_value(value)
    result=DEFAULTS.copy()
    if 'currency' in value:
        if not isinstance(value['currency'],str) or not re.fullmatch('[A-Z]{3}',value['currency']): fail('Invalid currency')
        result['currency']=value['currency']
    if 'theme' in value: result['theme']=choice(value['theme'],['dark','light'],'theme')
    if 'name' in value: result['name']=string(value['name'],'name',100,True)
    return result

# Check one saved item according to its collection type.
def validate(kind,value):
    v=object_value(value)
    result={'id':string(v['id'],'id',100) if 'id' in v else str(uuid.uuid4())}
    if kind=='transactions':
        result.update(date=date(v.get('date')),type=choice(v.get('type'),['income','expense'],'type'),amount=money(v.get('amount'),True),category=string(v.get('category'),'category',80),note=string(v.get('note') if v.get('note') is not None else '','note',2000,True))
    elif kind=='budgets':
        month=v.get('month')
        if not isinstance(month,str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',month) or not '1900-01'<=month<='9998-12': fail('Invalid budget month')
        result.update(category=string(v.get('category'),'category',80),amount=money(v.get('amount')),month=month)
    elif kind=='habits': result.update(name=string(v.get('name'),'name',120),created=date(v.get('created')))
    elif kind=='checks': result.update(habitId=string(v.get('habitId'),'id',100),date=date(v.get('date')))
    elif kind=='tasks':
        if type(v.get('done')) is not bool: fail('Invalid task status')
        result.update(title=string(v.get('title'),'title',300),date=date(v.get('date')),done=v['done'])
    elif kind=='journal':
        if not integer(v.get('mood')) or not 1<=v['mood']<=5: fail('Mood must be 1 to 5')
        result.update(id=date(v.get('date')),date=date(v.get('date')),mood=v['mood'],note=string(v.get('note') if v.get('note') is not None else '','note',20000,True))
    elif kind=='goals': result.update(name=string(v.get('name'),'name',120),target=money(v.get('target'),True),saved=money(v.get('saved')),due=date(v.get('due')))
    elif kind=='bills':
        next_date=date(v.get('nextDate'))
        result.update(name=string(v.get('name'),'name',120),amount=money(v.get('amount'),True),category=string(v.get('category'),'category',80),nextDate=next_date,frequency=choice(v.get('frequency'),['monthly','yearly','weekly'],'frequency'),anchorDay=anchor(v.get('anchorDay'),int(next_date[8:]),31,'anchor day'),anchorMonth=anchor(v.get('anchorMonth'),int(next_date[5:7]),12,'anchor month'))
    else: fail('Unknown collection')
    return result

# Check a full backup before restoring any of its records.
def validate_state(value):
    object_value(value)
    result={'settings':validate_settings(value.get('settings'))}
    for kind in COLLECTIONS:
        if not isinstance(value.get(kind),list) or len(value[kind])>100000: fail('Invalid '+kind+' list')
        result[kind]=[validate(kind,item) for item in value[kind]]
        ids=set();keys=set()
        for item in result[kind]:
            if item['id'] in ids: fail('Duplicate '+kind+' id')
            ids.add(item['id'])
            key=(item['habitId'],item['date']) if kind=='checks' else (item['category'],item['month']) if kind=='budgets' else item['date'] if kind=='journal' else None
            if key is not None and key in keys: fail('Duplicate '+kind+' entry')
            keys.add(key)
    habits={v['id'] for v in result['habits']}
    if any(v['habitId'] not in habits for v in result['checks']): fail('Habit check references a missing habit')
    return result

# Move a recurring bill to its next date while respecting short months.
def advance_date(value,frequency,anchor_day=None,anchor_month=None):
    date(value);choice(frequency,['monthly','yearly','weekly'],'frequency')
    current=dt.date.fromisoformat(value)
    try:
        if frequency=='weekly': result=current+dt.timedelta(days=7)
        else:
            day=anchor(anchor_day,current.day,31,'anchor day');month=anchor(anchor_month,current.month,12,'anchor month')
            if frequency=='yearly': year=current.year+1
            else:
                year=current.year+(current.month==12);month=current.month%12+1
            result=dt.date(year,month,min(day,calendar.monthrange(year,month)[1]))
    except (ValueError,OverflowError): fail('Invalid date')
    return date(result.isoformat())

# Quote CSV text and neutralize spreadsheet formula prefixes.
def csv_cell(value):
    value='' if value is None else str(value)
    if re.match(r'^\s*[=+@-]|^[\t\r\n]',value): value="'"+value
    return '"'+value.replace('"','""')+'"'

# Build a stable comparison key used to detect repeated imported expenses.
def fingerprint(item):
    normalized=re.sub('[^a-z0-9]+',' ',str(item.get('note','')).strip().lower()).strip()
    return '|'.join([item['date'],item.get('type','expense'),str(item['amount']),normalized])
