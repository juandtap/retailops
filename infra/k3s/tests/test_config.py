"""Regresión del fallo de arranque por node-external-ip vacío; sin root."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = ROOT / 'infra/k3s/validate_config.py'
spec = importlib.util.spec_from_file_location('k3s_config', VALIDATOR)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class ConfigTests(unittest.TestCase):
    def test_template_omits_external_ip(self):
        config.validate_config((ROOT / 'infra/k3s/config.yaml.example').read_text())

    def test_invalid_or_unneeded_external_ip_is_rejected(self):
        for value in ['""', "''", '', 'null', '[]', '192.168.0.121']:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Omitir node-external-ip'):
                config.validate_config(f'node-ip: "192.168.0.121"\nnode-external-ip: {value}\n')

    def test_cli_rejects_original_failure_without_changing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.yaml'
            original = 'node-external-ip: ""\n'
            path.write_text(original)
            result = subprocess.run([sys.executable, str(VALIDATOR), str(path)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Omitir node-external-ip', result.stderr)
            self.assertEqual(path.read_text(), original)


if __name__ == '__main__':
    unittest.main()
