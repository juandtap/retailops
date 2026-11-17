"""Solo fixtures/mocks; no kubectl, pods, carga, fallos o cambios de servicios reales."""
import argparse
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts'))
import incident_lab as lab
c=lab.c
spec=importlib.util.spec_from_file_location('training_gateway',ROOT/'infra/helm/retailops-incident-lab/files/gateway.py');gateway=importlib.util.module_from_spec(spec);spec.loader.exec_module(gateway)


def obj(kind,name):
    value={'metadata':{'name':name,'namespace':c.NAMESPACE,'labels':{c.OWNER:c.RELEASE},'uid':kind+'-'+name,'resourceVersion':'1'}}
    if kind=='deployment':value['spec']={'replicas':1}
    elif kind=='configmap':value['data']={'state.json':'{"mode":"normal","deadline":0}'}
    else:value['spec']={'ingress':[{'from':[{'podSelector':{'matchLabels':{'retailops.io/ml-client':'allowed'}}}]}]}
    return value


class FakeBackend:
    def __init__(self):
        self.objects={(kind,name):obj(kind,name) for kind,name in [('deployment','spring'),('deployment','ml'),('deployment','gateway'),('networkpolicy','ml-ingress'),('configmap','exercise-control')]};self.changes=[]
    def get(self,kind,name):return copy.deepcopy(self.objects[kind,name])
    def check_namespace(self,uid=None):
        if uid not in (None,'namespace-fixture'):raise ValueError('UID namespace distinto')
        return 'namespace-fixture'
    def server(self):return 'https://fixture.invalid:6443'
    def change(self,kind,name,path,value,uid):
        v=self.objects[kind,name];c.require_owned(v,kind,name,uid);self.changes.append((kind,name,path))
        if path=='/spec/replicas':v['spec']['replicas']=value
        elif path=='/spec':v['spec']=copy.deepcopy(value)
        else:v['data']['state.json']=value


class GuardsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.private=Path(self.tmp.name)/'facilitator';self.private.mkdir(mode=0o700)
        self.patcher=patch.object(c,'PRIVATE',self.private);self.patcher.start();self.state=self.private/'active/state.json'
        self.approval={'stage':'F5.5-B','action':'start','consent':'I_AUTHORIZE_F5.5_B_ONE_SCENARIO','scenario_id':'IL-001','exercise_id':'a'*32,'issued_at':100,'expires_at':700,'namespace_uid':'namespace-fixture','cluster_server':'https://fixture.invalid:6443','catalog_sha256':c.catalog_hash(),'backup_id':'backup-fixture','approved_by':'facilitator-fixture','approval_reference':'unit test only'}
        self.auth=self.private/'approval.json';self.auth.write_text(json.dumps(self.approval));self.auth.chmod(0o600)
        self.ready={'ready_for_execution':True,'namespace_uid':'namespace-fixture','cluster_server':'https://fixture.invalid:6443','backup_id':'backup-fixture'}
    def tearDown(self):self.patcher.stop();self.tmp.cleanup()
    def test_catalog_has_six_complete_bounded_scenarios(self):
        values=c.catalog()['scenarios'];self.assertEqual([s['id'] for s in values],[f'IL-{i:03}' for i in range(1,7)])
        for item in values:
            for key in ['objective','preconditions','injection','expected_evidence','recovery_criterion','rollback','risks_and_limits']:self.assertTrue(item[key])
            self.assertLessEqual(item['max_duration_seconds'],600)
    def test_authorization_rejects_scope_expiry_catalog_and_permissions(self):
        self.assertEqual(c.authorization(self.auth,'IL-001',clock=200)['exercise_id'],'a'*32)
        for key,value in [('stage','F5.5-A'),('action','anything'),('scenario_id','IL-002'),('catalog_sha256','bad'),('expires_at',1001)]:
            changed=dict(self.approval,**{key:value});self.auth.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):c.authorization(self.auth,'IL-001',clock=200)
        self.auth.write_text(json.dumps(self.approval));self.auth.chmod(0o644)
        with self.assertRaises(ValueError):c.authorization(self.auth,'IL-001',clock=200)
        self.auth.chmod(0o600)
        with self.assertRaises(ValueError):c.authorization(self.auth,'IL-001',clock=701)
        with self.assertRaises(ValueError):c.authorization(ROOT/'README.md','IL-001',clock=200)
        (self.private/'linked').symlink_to(Path(self.tmp.name),target_is_directory=True)
        with self.assertRaises(ValueError):c.private_path(self.private/'linked'/'approval.json')
    def test_start_rejected_before_backend_when_authorization_missing(self):
        args=argparse.Namespace(authorization=str(self.private/'absent.json'),scenario='IL-001')
        with patch.object(lab,'Backend',side_effect=AssertionError('No invocar Kubernetes')):
            with self.assertRaises(ValueError):lab.execute_start(args)
    def test_original_namespace_or_resource_rejected(self):
        original=obj('deployment','spring');original['metadata']['namespace']='retailops'
        with self.assertRaises(ValueError):c.require_owned(original,'deployment','spring')
        with self.assertRaises(ValueError):c.require_owned(original,'deployment','retailops-api')
        backend=lab.Backend('/fixture/kubeconfig',writable=True)
        with patch.object(backend,'call',side_effect=AssertionError('No contactar API')):
            with self.assertRaises(ValueError):backend.change('deployment','retailops-api','/spec/replicas',0,'fixture')
            with self.assertRaises(ValueError):backend.change('deployment','spring','/spec/replicas',100,'fixture')
        with self.assertRaises(ValueError):lab.Backend('/fixture/kubeconfig',context='production')
    def test_readonly_backend_cannot_patch(self):
        backend=lab.Backend('/fixture/kubeconfig')
        with patch.object(backend,'call',side_effect=AssertionError('No contactar API')):
            with self.assertRaises(ValueError):backend.change('deployment','spring','/spec/replicas',0,'fixture')
    def test_mock_scenarios_reverse_without_source_and_preserve_guides(self):
        for i in range(1,7):
            backend=FakeBackend();baseline=copy.deepcopy(backend.objects);approval=dict(self.approval,scenario_id=f'IL-{i:03}',exercise_id=f'{i:032x}')
            with patch('time.time',return_value=200):state=c.begin(backend,approval,self.ready,self.state)
            self.assertEqual(state['phase'],'active');public=json.dumps(c.public_state(state))
            self.assertNotIn('IL-',public);self.assertNotIn('mode',public);self.assertNotIn('snapshots',public)
            guide=self.private/'exercises'/approval['exercise_id']/'evaluation.md'
            self.assertEqual(guide.stat().st_mode & 0o777,0o600)
            c.end(backend,self.state);self.assertEqual(backend.objects,baseline)
            count=len(backend.changes);c.end(backend,self.state);self.assertEqual(len(backend.changes),count)
    def test_idempotence_replay_not_ready_and_wrong_cluster(self):
        backend=FakeBackend()
        with patch('time.time',return_value=200):c.begin(backend,self.approval,self.ready,self.state)
        count=len(backend.changes)
        with patch('time.time',return_value=200):c.begin(backend,self.approval,self.ready,self.state)
        self.assertEqual(len(backend.changes),count);c.end(backend,self.state)
        with self.assertRaises(ValueError):c.begin(backend,self.approval,self.ready,self.state)
        for changed in [dict(self.ready,ready_for_execution=False),dict(self.ready,namespace_uid='other'),dict(self.ready,cluster_server='https://other.invalid')]:
            with self.assertRaises(ValueError):c.begin(FakeBackend(),dict(self.approval,exercise_id='b'*32),changed,self.state)
    def test_recreated_uid_and_concurrent_policy_fail_closed(self):
        backend=FakeBackend()
        with patch('time.time',return_value=200):c.begin(backend,self.approval,self.ready,self.state)
        backend.objects['deployment','spring']['metadata']['uid']='recreated'
        with self.assertRaises(ValueError):c.end(backend,self.state)
        backend.objects['deployment','spring']['metadata']['uid']='deployment-spring'
        backend.objects['networkpolicy','ml-ingress']['spec']['unexpected']='change'
        with self.assertRaises(ValueError):c.end(backend,self.state)
    def test_helm_safety_rejects_pvc_secret_host_and_external_service(self):
        objects=lab.render();lab.safety(objects)
        for mutate in [lambda p:p['volumes'].append({'name':'data','persistentVolumeClaim':{'claimName':'original'}}),lambda p:p.update(hostNetwork=True),lambda p:p['containers'][0].update(envFrom=[{'secretRef':{'name':'original'}}]),lambda p:p.update(automountServiceAccountToken=True)]:
            changed=copy.deepcopy(objects);pod=next(o for o in changed if o['kind']=='Deployment')['spec']['template']['spec'];mutate(pod)
            with self.assertRaises(ValueError):lab.safety(changed)
        changed=copy.deepcopy(objects);next(o for o in changed if o['kind']=='Service')['spec']['type']='NodePort'
        with self.assertRaises(ValueError):lab.safety(changed)
    def test_preflight_is_readonly_and_closed_namespace_not_ready(self):
        class Closed(FakeBackend):
            def server(self):return 'https://fixture.invalid:6443'
            def call(self,args):
                if 'nodes' in args:return json.dumps({'items':[{'status':{'conditions':[{'type':'Ready','status':'True'}]}}]})
                return '{"items":[]}'
            def check_namespace(self,uid=None):raise ValueError('Namespace exclusivo no provisionado/autorizado')
        backup=self.private/'backup';backup.mkdir();report=self.private/'report.json';report.write_text(json.dumps({'status':'validated','backup_id':'fixture','model_version':'1','model_artifact_load':True}));report.chmod(0o600)
        args=argparse.Namespace(backup=str(backup),key='fixture-key',recovery_report=str(report),kubeconfig='fixture',context='default')
        real_run=lab.subprocess.run
        def read_run(command,**kwargs):
            if command[:2]==['docker','ps']:return argparse.Namespace(stdout='')
            return real_run(command,**kwargs)
        with patch('infra.backup.core.verify_envelope',return_value=({'id':'fixture','started_utc':'2026-11-17T00:00:00Z'},b'k'*64)),patch.object(lab.time,'time',return_value=1794873601),patch.object(lab,'mem_available',return_value=8*1024**3),patch.object(lab.subprocess,'run',side_effect=read_run):
            backend=Closed();result=lab.preflight(args,backend);self.assertFalse(result['ready_for_execution']);self.assertEqual(backend.changes,[])


class GatewayTests(unittest.TestCase):
    def test_deadline_and_invalid_modes(self):
        self.assertEqual(gateway.effective_state({'mode':'latency','deadline':200},now=100),'latency')
        self.assertEqual(gateway.effective_state({'mode':'memory','deadline':99},now=100),'normal')
        self.assertEqual(gateway.effective_state({'mode':'memory','deadline':1000},now=100),'normal')
        with self.assertRaises(ValueError):gateway.effective_state({'mode':'arbitrary'},now=100)
    def test_fixture_only_error_delay_and_storage_reversal(self):
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with tempfile.TemporaryDirectory() as folder,patch.object(gateway,'WORK',Path(folder)),contextlib.redirect_stdout(io.StringIO()):
            gateway.reconcile('normal');self.assertEqual(gateway.probe('storage','normal'),200)
            gateway.reconcile('storage');self.assertEqual(gateway.probe('storage','storage'),503)
            gateway.reconcile('normal');self.assertEqual(gateway.probe('storage','normal'),200)
            with patch.object(gateway.urllib.request,'urlopen',return_value=Response()) as request,patch.object(gateway.time,'sleep') as delay:
                self.assertEqual(gateway.probe('spring','http_5xx'),503);request.assert_not_called()
                self.assertEqual(gateway.probe('spring','latency'),200);delay.assert_called_once_with(1.5)
                self.assertEqual(request.call_args.args[0],'http://spring:8080/actuator/health')
