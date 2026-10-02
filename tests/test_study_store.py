import copy
import os
import sys
import tempfile
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'portal'))
from study_store import StudyStore, StoreError, analyze


def snapshot():
    return {'metadata':{'studyId':'test','operator':'QA','numSlots':4,'mode':'MODE_B',
                        'protocol':{'durationSec':3600,'workSec':600,'breakSec':102,'maxCycles':13,'completion':'either'}},
            'machine':{'currentState':'PAUSED'},'inventory':{'totes':{}},'picks':[],
            'events':[{'id':'e1','event':'START','payload':{}}],'corrections':[],'exceptions':[]}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=StudyStore(os.path.join(self.temp.name,'store.sqlite'))
        self.data=snapshot()
        self.payload={'writer':'one','requestId':'request1','revision':0,'snapshot':self.data}

    def tearDown(self):
        self.temp.cleanup()

    def test_idempotent_save_and_restart(self):
        first=self.store.save('session',self.payload)
        self.assertEqual(first,self.store.save('session',self.payload))
        reopened=StudyStore(self.store.path)
        self.assertEqual(reopened.get('session')['revision'],1)
        with reopened.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)

    def test_tab_conflict_and_stale_revision(self):
        self.store.save('session',self.payload)
        with self.assertRaises(StoreError):self.store.claim('session','two')
        with self.assertRaises(StoreError):self.store.save('session',{**self.payload,'requestId':'new'})

    def test_immutable_protocol_and_records(self):
        self.data['picks']=[{'id':'p1','cycleTimeMs':1000}]
        self.store.save('session',self.payload)
        changed=copy.deepcopy(self.data);changed['picks'][0]['cycleTimeMs']=2000
        with self.assertRaises(StoreError):self.store.save('session',{**self.payload,'revision':1,'requestId':'r2','snapshot':changed})
        changed=copy.deepcopy(self.data);changed['metadata']['protocol']['workSec']=30
        with self.assertRaises(StoreError):self.store.save('session',{**self.payload,'revision':1,'requestId':'r3','snapshot':changed})
        changed=copy.deepcopy(self.data);changed['corrections']=[{'id':'c1','pickId':'p1','valid':False,'reason':'bad trial'}]
        self.store.save('session',{**self.payload,'revision':1,'requestId':'r4','snapshot':changed})
        self.assertEqual(self.store.get('session')['snapshot']['picks'][0]['cycleTimeMs'],1000)

    def test_known_analytics_and_unknown_accuracy(self):
        self.assertEqual(analyze(self.data)['accuracy'],'not assessed')
        self.assertIsNone(analyze(self.data)['overall']['p90'])
        self.data['picks']=[{'id':str(i),'cycleTimeMs':v*1000,'slot':i%4+1,'pickBlock':1,'valid':True} for i,v in enumerate([1,2,3,4,5])]
        result=analyze(self.data)
        self.assertEqual(result['overall']['p50'],3)
        self.assertEqual(result['overall']['p90'],5)
        self.assertEqual(result['overall']['compliance'],100)
        self.data['corrections']=[{'pickId':'4','valid':False,'accuracy':'incorrect'}]
        result=analyze(self.data)
        self.assertEqual(result['overall']['count'],4)
        self.assertEqual(result['accuracy']['correctPercent'],0)

    def test_alert_sample_gates_and_slowdown(self):
        self.data['picks']=[{'id':str(i),'cycleTimeMs':7000 if i>=20 else 3000,'slot':1,'pickBlock':1} for i in range(40)]
        self.assertEqual(len(analyze(self.data)['alerts']),2)
        self.data['picks']=self.data['picks'][:19]
        self.assertEqual(analyze(self.data)['alerts'],[])

    def test_presets_and_validation(self):
        self.store.presets({'id':'preset','name':'Baseline','config':self.data['metadata']})
        self.assertEqual(self.store.presets()[0]['name'],'Baseline')
        self.data['metadata']['protocol']['breakSec']=-1
        with self.assertRaises(StoreError):self.store.save('session',self.payload)

    def test_export_column_mapping_and_unknown_accuracy(self):
        import pandas as pd
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
        from analyze_study import normalize_picker_df, analyze_picker_metrics
        frame = pd.DataFrame([{'session_id':'uuid','study_id':'label','operator_id':'QA',
            'configuration':'4-slot','slot':1,'skuId':'SKU-A','skuName':'A','cycleTimeMs':2000,
            'cycleTime':2,'cycle_time_s':2,'accuracy':'not assessed','valid':True},
            {'session_id':'uuid','study_id':'label','operator_id':'QA','configuration':'4-slot',
             'slot':2,'skuId':'SKU-B','skuName':'B','cycleTimeMs':99000,'cycleTime':99,
             'cycle_time_s':99,'accuracy':'incorrect','valid':False}])
        normalized=normalize_picker_df(frame)
        self.assertFalse(normalized.columns.duplicated().any())
        result=analyze_picker_metrics(normalized)
        self.assertEqual(result['mean_time'],2)
        self.assertEqual(result['accuracy'],0)
        result=analyze_picker_metrics(normalize_picker_df(frame.iloc[:1]))
        self.assertTrue(pd.isna(result['accuracy']))


if __name__=='__main__':unittest.main()
