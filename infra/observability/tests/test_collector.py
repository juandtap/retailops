"""Fixtures explícitas para el adaptador, nunca evidencia de estado real."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('collector', ROOT/'infra/helm/retailops-observability/files/collector.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class CollectorTests(unittest.TestCase):
    def test_units_and_label_escaping(self):
        self.assertEqual(collector.quantity('12000000n', True), .012)
        self.assertEqual(collector.quantity('194Mi'), 194*2**20)
        self.assertEqual(collector.quantity('250m', True), .25)
        self.assertIn(r'pod="a\"b"', collector.sample('example', 1, pod='a"b'))

    def test_actual_usage_and_failures_are_separate(self):
        def fetch(path):
            if 'metrics.k8s.io' in path:
                return {'items':[{'metadata':{'name':'fixture'},'containers':[{'name':'api','usage':{'cpu':'1000000n','memory':'20Mi'}}]}]}
            raise OSError('API no disponible')
        text = collector.kubernetes(fetch)
        self.assertIn('container="api",namespace="retailops",pod="fixture"} 0.001', text)
        self.assertIn('section="nodes"} 0.0', text)
        self.assertIn('section="usage"} 1.0', text)
        self.assertNotIn('retailops_kubernetes_node_ready', text)

    def test_namespace_labels_follow_the_requested_namespace(self):
        def fetch(path):
            if 'metrics.k8s.io' in path:
                return {'items':[{'metadata':{'name':'fixture'},'containers':[{'name':'grafana','usage':{'cpu':'1m','memory':'20Mi'}}]}]}
            return {'items':[]}
        text=collector.kubernetes(fetch,namespace='retailops-observability',include_nodes=False)
        self.assertIn('namespace="retailops-observability",pod="fixture"',text)
        self.assertNotIn('namespace="retailops"',text)

    def test_restarts_are_observed_not_invented(self):
        def fetch(path):
            if path == '/api/v1/namespaces/retailops/pods':
                return {'items':[{'metadata':{'name':'fixture'},'spec':{'containers':[]},'status':{'containerStatuses':[{'name':'api','restartCount':3}]}}]}
            return {'items':[]}
        text=collector.kubernetes(fetch)
        self.assertIn('retailops_kubernetes_container_restarts_total{container="api",namespace="retailops",pod="fixture"} 3.0',text)
