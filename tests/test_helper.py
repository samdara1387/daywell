"""Helper migration tests use fictional data, fake providers, and temporary stores."""
import copy
import json
import os
import tempfile
import unittest
from core import APIError, validate
from server import DaywellApp
from helper import HelperService
from key_store import KeyStore
from insights import analyze, local_answer, suggestions, fingerprint, share_summary, scope_for_question

class FakeStore:
    available = True
    def __init__(self): self.value = None; self.failure = False
    def load(self): return self.value
    def save(self, value):
        if self.failure: raise OSError('simulated storage error')
        self.value = copy.deepcopy(value)
    def forget(self):
        if self.failure: raise OSError('simulated storage error')
        self.value = None

class HelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = DaywellApp(self.temp.name, helper=False)
        self.store = FakeStore()
        self.calls = []
        def provider(payload,key):
            self.calls.append((payload,key))
            return {'output':[{'type':'message','content':[{'type':'output_text','text':'Example spending answer.'}]}]}
        self.service = HelperService(self.app, self.store, provider)
        self.rows = [
            {'id':'a','date':'2024-02-01','type':'expense','amount':1234,'category':'Other','note':'Coffee at Cafe Example'},
            {'id':'b','date':'2024-02-02','type':'expense','amount':3000,'category':'Dining out','note':'Restaurant Example'},
            {'id':'c','date':'2024-02-03','type':'income','amount':90000,'category':'Salary','note':'Private employer'},
            {'id':'d','date':'2024-02-04','type':'expense','amount':7000,'category':'Housing','note':'Private rent'},
            {'id':'e','date':'2024-01-31','type':'expense','amount':1000,'category':'Other','note':'Earlier expense'},
        ]
        for row in self.rows:self.app.save('transactions',validate('transactions',row))
    def tearDown(self): self.app.close(); self.temp.cleanup()
    def call(self,path,body=None,query=None):
        return self.service.handle('GET' if body is None else 'POST','/api/helper/'+path,query or {},body)[1]
    def connect(self,remember=False):
        return self.call('config',{'apiKey':'fake-test-key-not-a-real-secret-123','model':'example-model','remember':remember})
    def test_analysis_scope_cents_and_summary_privacy(self):
        state=self.app.state();original=copy.deepcopy(state)
        result=analyze(state,'2024-02-01','2024-02-29','2024-02-03')
        self.assertEqual(result['expenses'],4234)
        self.assertEqual(result['averageDaily'],1411)
        self.assertEqual(result['future']['expenses'],7000)
        self.assertEqual(result['previous']['expenses'],1000)
        self.assertEqual(result['range']['elapsedDays'],3)
        shared=json.dumps(share_summary(result))
        self.assertNotIn('Cafe Example',shared);self.assertNotIn('Private employer',shared)
        self.assertNotIn('largest',shared);self.assertEqual(state,original)
        self.assertEqual(scope_for_question('last month','2024-01-01','2024-03-31','2024-03-15'),{'from':'2024-02-01','to':'2024-02-29'})
        self.assertEqual(scope_for_question('today','2024-01-01','2024-03-31','2024-03-15')['from'],'2024-03-15')
    def test_offline_intents_and_scenarios(self):
        for question,chart in [('show daily chart','daily'),('show monthly spending','monthly'),('compare my spending','comparison'),('income and balance','cashflow')]:
            self.assertEqual(local_answer(self.app.state(),question,'2024-02-01','2024-02-29','2024-02-29')['chart'],chart)
        reply=local_answer(self.app.state(),'reduce dining by 20%','2024-02-01','2024-02-29','2024-02-29')['reply']
        self.assertIn('CAD 6.00',reply)
        self.assertFalse(local_answer(self.app.state(),'What is the capital of France?','2024-02-01','2024-02-29')['recognized'])
        with self.assertRaises(ValueError):local_answer(self.app.state(),'save 101%','2024-02-01','2024-02-29')
    def test_suggestions_apply_undo_and_stale_rejection(self):
        original=self.app.state();proposal=suggestions(original,'2024-02-01','2024-02-29')['proposals'][0]
        self.assertEqual(proposal['suggested'],'Dining out')
        change={'id':proposal['id'],'fingerprint':proposal['fingerprint'],'category':proposal['suggested']}
        self.assertEqual(self.call('categories/apply',{'changes':[change]})['updated'],1)
        updated=self.app.get('transactions')[0]
        for field in ['id','date','type','amount','note']:self.assertEqual(updated[field],original['transactions'][0][field])
        self.assertEqual(self.call('categories/undo',{})['undone'],1)
        self.assertEqual(self.app.state(),original)
        self.call('categories/apply',{'changes':[change]})
        self.app.save('transactions',{**self.app.get('transactions')[0],'note':'Edited later'})
        with self.assertRaises(APIError):self.call('categories/undo',{})
        with self.assertRaises(APIError):self.call('categories/apply',{'changes':[change]})
    def test_online_exact_preview_confirmation_and_token_consumption(self):
        question={'question':'Where did my money go?','from':'2024-02-01','to':'2024-02-29'}
        with self.assertRaises(APIError):self.call('prepare',question)
        self.connect();prepared=self.call('prepare',question)
        self.assertEqual(len(self.calls),0)
        with self.assertRaises(APIError):self.call('online',{'token':prepared['token']})
        self.app.save('transactions',validate('transactions',{'date':'2024-02-10','type':'expense','amount':9999,'category':'Other','note':'Not in preview'}))
        answer=self.call('online',{'token':prepared['token'],'confirmed':True})
        payload,key=self.calls[0]
        self.assertFalse(payload['store'])
        actual=json.loads(payload['input'][0]['content'].split('\n',1)[1])
        self.assertEqual(actual,prepared['preview']['summary'])
        self.assertNotIn('Not in preview',json.dumps(payload))
        self.assertEqual(answer['reply'],'Example spending answer.')
        with self.assertRaises(APIError):self.call('online',{'token':prepared['token'],'confirmed':True})
        self.assertEqual(len(self.calls),1)
    def test_key_lifecycle_and_failure_preserves_connection(self):
        self.connect(True);self.assertTrue(self.call('config')['remembered'])
        reconnected=HelperService(self.app,self.store)
        self.assertTrue(reconnected.config()['configured'])
        self.store.failure=True
        with self.assertRaises(APIError):self.call('config',{'apiKey':'new-fake-key-only-for-testing-456','model':'other-model','remember':True})
        self.assertEqual(self.service.model,'example-model')
        self.store.failure=False
        self.call('config',{'apiKey':'','model':'example-model','remember':False})
        self.assertIsNone(self.store.value);self.assertTrue(self.call('config')['configured'])
        self.assertFalse(HelperService(self.app,self.store).config()['configured'])
        self.call('config',{'forget':True});self.assertFalse(self.call('config')['configured'])
        self.assertNotIn('fake-test-key',json.dumps(self.app.state()))
    def test_invalid_inputs_are_client_errors(self):
        for path,body in [('offline',{'question':'hello','from':'bad','to':'2024-01-01'}),('config',{'model':'bad space','apiKey':'fake-test-key-for-tests-12345'}),('categories/apply',{'changes':[{'id':[]}]}),('online',{'confirmed':True,'token':[]})]:
            with self.assertRaises(APIError):self.call(path,body)

@unittest.skipUnless(os.name=='nt','DPAPI needs Windows')
class KeyStoreTests(unittest.TestCase):
    def test_roundtrip_is_encrypted_and_forget_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store=KeyStore(directory);self.assertIsNone(store.load())
            value={'apiKey':'fake-test-key-not-a-real-secret-123','model':'example-model'}
            store.save(value)
            self.assertNotIn(value['apiKey'].encode(),store.filename.read_bytes())
            self.assertEqual(store.load(),{'version':1,**value})
            store.forget();store.forget();self.assertIsNone(store.load())

if __name__=='__main__':unittest.main()
