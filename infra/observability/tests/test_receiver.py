"""Pruebas locales del receptor con almacenamiento temporal, no notificaciones externas."""
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest

spec=importlib.util.spec_from_file_location('receiver',Path(__file__).resolve().parents[2]/'helm/retailops-observability/files/alerting/receiver.py')
receiver=importlib.util.module_from_spec(spec);spec.loader.exec_module(receiver)

class ReceiverTests(unittest.TestCase):
    def test_webhook_drops_unapproved_content(self):
        value=receiver.sanitize({'status':'firing','alerts':[{'status':'firing','labels':{'alertname':'fixture','password':'secret'},'annotations':{'token':'secret'}}],'externalURL':'http://secret'})
        self.assertNotIn('secret',json.dumps(value))
        self.assertEqual(value['alerts'][0]['labels'],{'alertname':'fixture'})

    def test_retention_bounded_and_state_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            original_db,original_state=receiver.DB,receiver.STATE
            try:
                receiver.DB=str(Path(folder)/'events.sqlite');receiver.STATE=Path(folder)/'state.json'
                receiver.STATE.write_text('{"lab_active":0}')
                with receiver.connect() as conn:
                    conn.execute('INSERT INTO events(timestamp,payload) VALUES (?,?)',(time.time()-49*3600,'{}'))
                    conn.executemany('INSERT INTO events(timestamp,payload) VALUES (?,?)',[(time.time(),'{}')]*1005)
                with receiver.connect() as conn:
                    self.assertEqual(conn.execute('SELECT count(*) FROM events').fetchone()[0],1000)
                self.assertIn('retailops_lab_active 0',receiver.metrics())
                receiver.STATE.write_text('{"lab_active":2}')
                with self.assertRaises(ValueError):receiver.metrics()
            finally:receiver.DB,receiver.STATE=original_db,original_state
