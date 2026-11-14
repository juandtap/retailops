"""Kernel y configuración Jupyter locales al proyecto, sin registro global."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]

def configure():
    if sys.version_info[:2]!=(3,12):raise RuntimeError('Se requiere Python 3.12')
    if Path(sys.prefix).resolve()!=(ROOT/'notebooks/.venv').resolve():raise RuntimeError('Usar el entorno uv de notebooks')
    private=ROOT/'.local/eda'
    private.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(private,0o700)
    for name,folder in {'MPLCONFIGDIR':'matplotlib','IPYTHONDIR':'ipython','JUPYTER_CONFIG_DIR':'jupyter','JUPYTER_RUNTIME_DIR':'runtime','JUPYTER_DATA_DIR':'jupyter-data'}.items():
        path=private/folder;path.mkdir(parents=True,exist_ok=True,mode=0o700);os.environ[name]=str(path)
    kernel=private/'jupyter-data/kernels/retailops-eda'
    kernel.mkdir(parents=True,exist_ok=True,mode=0o700)
    (kernel/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],'display_name':'RetailOps EDA · Python 3.12 (uv)','language':'python'})+'\n')


def strip_outputs_on_save(model,path,contents_manager,**kwargs):
    """Jupyter conserva código/markdown, pero nunca guarda outputs de celdas."""
    if model.get('type')!='notebook':return
    notebook=model.get('content',{})
    for cell in notebook.get('cells',[]):
        if cell.get('cell_type')=='code':
            cell['outputs']=[];cell['execution_count']=None
            cell.get('metadata',{}).pop('execution',None)
