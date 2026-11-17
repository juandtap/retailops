import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('core',Path(__file__).resolve().parents[1]/'core.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)

class BackupTests(unittest.TestCase):
    def test_paths_and_no_overwrite(self):
        with self.assertRaises(ValueError):core.outside_repo(core.ROOT/'.local/backup')
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'new';core.private_dir(p,new=True)
            with self.assertRaises(FileExistsError):core.private_dir(p,new=True)

    def test_hashes_missing_extra_and_modified(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'data').write_bytes(b'fixture');manifest={'files':core.file_inventory(p)}
            core.check_files(p,manifest)
            (p/'data').write_bytes(b'changed')
            with self.assertRaises(ValueError):core.check_files(p,manifest)
            (p/'data').unlink()
            with self.assertRaises(ValueError):core.check_files(p,manifest)
            (p/'data').write_bytes(b'fixture');(p/'extra').touch()
            with self.assertRaises(ValueError):core.check_files(p,manifest)

    def test_tar_traversal_symlink_duplicate_rejected(self):
        for names,kind in [(['../escape'],'file'),(['/absolute'],'file'),(['link'],'symlink'),(['duplicate','duplicate'],'file'),(['duplicate','./duplicate'],'file')]:
            with tempfile.TemporaryDirectory() as folder:
                p=Path(folder);archive=p/'bad.tar'
                with tarfile.open(archive,'w') as tar:
                    for name in names:
                        info=tarfile.TarInfo(name)
                        if kind=='symlink':info.type=tarfile.SYMTYPE;info.linkname='/outside'
                        tar.addfile(info,io.BytesIO())
                with self.assertRaises(ValueError):core.safe_extract(archive,p/'out')

    def test_authenticated_roundtrip_and_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);key=b'k'*64;(p/'plain').write_bytes(b'fixture privada')
            core.crypt(p/'plain',p/'encrypted',key);core.crypt(p/'encrypted',p/'restored',key,decrypt=True)
            self.assertEqual((p/'plain').read_bytes(),(p/'restored').read_bytes())
            tag=core.mac(p/'encrypted',key);(p/'encrypted').write_bytes(b'tampered')
            self.assertNotEqual(tag,core.mac(p/'encrypted',key))
            self.assertNotEqual(core.mac(p/'plain',key),core.mac(p/'plain',b'j'*64))

    def test_envelope_rejects_wrong_key_hash_and_incomplete(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);key=b'k'*64;keyfile=p/'key';keyfile.write_bytes(key);keyfile.chmod(0o600)
            (p/'payload.enc').write_bytes(b'fixture-ciphertext')
            manifest={'format':core.FORMAT,'status':'complete','sha256':core.digest(p/'payload.enc'),'hmac_sha256':core.mac(p/'payload.enc',key)}
            (p/'manifest.json').write_text(json.dumps(manifest));core.verify_envelope(p,keyfile)
            keyfile.write_bytes(b'j'*64)
            with self.assertRaises(ValueError):core.verify_envelope(p,keyfile)
            keyfile.write_bytes(key);manifest['status']='incomplete';(p/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):core.verify_envelope(p,keyfile)
            manifest['status']='complete';(p/'manifest.json').write_text(json.dumps(manifest));(p/'payload.enc').write_bytes(b'broken')
            with self.assertRaises(ValueError):core.verify_envelope(p,keyfile)

    def test_stop_rejects_original_resource_before_docker(self):
        import argparse
        from unittest.mock import patch
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
        import backup_recovery
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            (p/'restore-state.json').write_text(json.dumps({'id':'a'*12,'resources':{'mlflow':'retailops-data-postgres-1'}}))
            with patch('subprocess.run',side_effect=AssertionError('Docker no debe invocarse')):
                with self.assertRaises(ValueError):backup_recovery.stop(argparse.Namespace(workspace=str(p)))
