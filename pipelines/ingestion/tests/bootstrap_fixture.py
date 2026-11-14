"""Fuentes sintéticas explícitas, independientes de los CSV originales."""
import csv
from pathlib import Path
from retailops_bootstrap.extract import sha256
from retailops_profiling.core import SCHEMAS

STAMP='2026-11-13T15:00:00+00:00'

def fixture(root,batch='test-bootstrap'):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    rows={
      'train.csv':[[0,'2014-12-24',1,'A','1.1250001',2],[1,'2014-12-24',1,'B','0.0',0],[2,'2014-12-26',1,'A','2.2500002',1],[3,'2014-12-26',1,'B','3.75',3],[4,'2015-01-01',1,'FUTURE','999.0',99]],
      'stores.csv':[[1,'Quito','Pichincha','D',1]],
      'holidays_events.csv':[['2014-12-25','Holiday','National','Ecuador','Navidad','False'],['2015-01-01','Holiday','National','Ecuador','Futuro','False']],
      'oil.csv':[['2014-12-24',''],['2014-12-26','50.01'],['2015-01-01','99.9']],
      'transactions.csv':[['2014-12-24',1,3],['2014-12-26',1,4],['2015-01-01',1,99]],
      'test.csv':[[5,'2015-01-02',1,'A',0]],'sample_submission.csv':[[5,0]]}
    inventory=[]
    for name,values in rows.items():
        path=root/name
        with path.open('w',newline='') as f:
            writer=csv.writer(f);writer.writerow(SCHEMAS[name]);writer.writerows(values)
        inventory.append({'file':name,'bytes':path.stat().st_size,'sha256':sha256(path)})
    contract={'contract_version':1,'batch_id':batch,'period_start':'2014-12-24','period_end':'2014-12-26','expected_sales':4,
      'expected_stores':1,'expected_families':2,'accepted_missing_dates':['2014-12-25'],
      's3_publishable_entities':['sales','store_transactions','observation_gaps'],'row_group_size':2}
    return contract,inventory
