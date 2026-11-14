"""Solo plan temporal y recuperación lógica, sin ajuste/registro real."""
from datetime import date
import hashlib,json
import pytest
from app.plan import for_cutoff
from app import orchestrated

def test_plan_respects_fit_and_holdout_boundaries():
    plan=for_cutoff('2015-01-31')
    train=plan['splits']['train'];valid=plan['splits']['validation'];test=plan['splits']['evaluation']
    assert train[2]<valid[0] and valid[2]<test[0]
    assert test[1].toordinal()+7==date(2015,1,31).toordinal()
    assert for_cutoff('2014-12-31')['splits']['evaluation'][0]>date(2014,12,7)

def test_logical_retry_uses_existing_candidate(tmp_path,monkeypatch):
    monkeypatch.setattr(orchestrated,'ROOT',tmp_path)
    key=hashlib.sha256(b'logical-test').hexdigest()
    folder=tmp_path/'.local/airflow/ml'/key;folder.mkdir(parents=True)
    result={'status':'SUCCEEDED','metadata':{'historical_cutoff':'2015-01-31'},'model_version':'test-only'}
    (folder/'candidate.json').write_text(json.dumps(result))
    def forbidden(**kwargs):raise AssertionError('Un reintento no debe entrenar ni registrar')
    monkeypatch.setattr(orchestrated,'train',forbidden)
    assert orchestrated.execute('2015-01-31','logical-test')==result
    with pytest.raises(ValueError):orchestrated.execute('2015-02-28','logical-test')
