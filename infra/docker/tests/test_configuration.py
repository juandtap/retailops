"""Verificación de secretos/configuración sin acceder a Docker ni al dataset."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
import data_infra

class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.secrets=Path(self.directory.name)/'secrets'
        self.override=patch.object(data_infra,'SECRET_DIR',self.secrets)
        self.override.start()

    def tearDown(self):
        self.override.stop();self.directory.cleanup()

    def test_init_does_not_replace_existing_credentials(self):
        data_infra.initialize_secrets()
        before={p.name:p.read_bytes() for p in self.secrets.iterdir()}
        data_infra.initialize_secrets()
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.secrets.iterdir()})
        self.assertEqual(self.secrets.stat().st_mode & 0o777,0o700)
        self.assertTrue(all(p.stat().st_mode & 0o777==0o600 for p in self.secrets.iterdir()))

    def test_missing_credentials_fail_before_docker(self):
        with patch.object(data_infra,'compose') as compose:
            with self.assertRaisesRegex(ValueError,'Secreto'):
                data_infra.validate_configuration()
            compose.assert_not_called()

    def test_open_permissions_rejected(self):
        data_infra.initialize_secrets()
        (self.secrets/'pg_admin_password').chmod(0o644)
        with patch.object(data_infra,'compose') as compose:
            with self.assertRaisesRegex(ValueError,'permisos'):
                data_infra.validate_configuration()
            compose.assert_not_called()

    def test_invalid_port_rejected(self):
        data_infra.initialize_secrets()
        with patch.dict(os.environ,{'POSTGRES_PORT':'0'}),patch.object(data_infra,'compose') as compose:
            with self.assertRaisesRegex(ValueError,'fuera de rango'):
                data_infra.validate_configuration()
            compose.assert_not_called()

if __name__=='__main__':unittest.main()
