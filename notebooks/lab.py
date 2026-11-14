"""Inicia JupyterLab local con kernel uv y token automático; sin instalaciones globales."""
from pathlib import Path
import sys
from retailops_eda.runtime import configure,strip_outputs_on_save
configure()
from jupyterlab.labapp import LabApp
from traitlets.config import Config

if __name__=='__main__':
    config=Config()
    config.FileContentsManager.pre_save_hook=strip_outputs_on_save
    config.ServerApp.ip='127.0.0.1'
    config.ServerApp.open_browser=False
    config.ServerApp.root_dir=str(Path(__file__).resolve().parent)
    config.ServerApp.terminals_enabled=False
    config.KernelSpecManager.allowed_kernelspecs={'retailops-eda'}
    LabApp.launch_instance(config=config,argv=sys.argv[1:])
