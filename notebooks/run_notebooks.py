"""Ejecuta ambos notebooks sin guardar outputs; conserva PNG agregados y evidencia mínima."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
PRIVATE=ROOT/'.local/eda'
from retailops_eda.runtime import configure
configure()
os.environ['MPLBACKEND']='module://matplotlib_inline.backend_inline'
import nbformat
from nbclient import NotebookClient
from jupyter_client.kernelspec import KernelSpecManager


def main():
    if sys.version_info[:2]!=(3,12):raise RuntimeError('Se requiere Python 3.12')
    kernel=KernelSpecManager().get_kernel_spec('retailops-eda')
    if Path(kernel.argv[0]).absolute()!=Path(sys.executable).absolute():
        raise RuntimeError('El kernel python3 no pertenece al entorno uv de notebooks')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',choices=['01_exploratory_data_analysis.ipynb','02_time_series_analysis.ipynb','03_baseline_backtesting.ipynb'])
    args=parser.parse_args()
    baseline=args.only=='03_baseline_backtesting.ipynb'
    execution=[]
    names=[args.only] if args.only else ['01_exploratory_data_analysis.ipynb','02_time_series_analysis.ipynb']
    for name in names:
        path=HERE/name;notebook=nbformat.read(path,as_version=4);nbformat.validate(notebook)
        for cell in notebook.cells:
            if cell.cell_type=='code':cell.outputs=[];cell.execution_count=None
        started=time.monotonic()
        NotebookClient(notebook,timeout=300 if baseline else 120,kernel_name='retailops-eda',resources={'metadata':{'path':str(HERE)}},allow_errors=False,store_widget_state=False).execute()
        code=[c for c in notebook.cells if c.cell_type=='code']
        if any(c.execution_count is None or any(o.output_type=='error' for o in c.outputs) for c in code):raise RuntimeError('Notebook no ejecutado completamente')
        # Nunca persistir el notebook ejecutado ni tracebacks/valores de conexión.
        execution.append({'notebook':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'code_cells_executed':len(code),'duration_seconds':round(time.monotonic()-started,3),'outputs_persisted':False,'status':'SUCCEEDED'})
        print(f'{name}: {len(code)} celdas completas, sin errores ni outputs persistidos.',flush=True)
    evidence={'uv_lock_sha256':hashlib.sha256((HERE/'uv.lock').read_bytes()).hexdigest(),'module_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((HERE/'retailops_eda').glob('*.py'))},'python':sys.version.split()[0],'role':'retailops_trainer','period_start':'2013-01-01','period_end':'2014-12-31','notebooks':execution}
    if baseline:
        evidence['module_sha256']={'retailops_baselines.py':hashlib.sha256((HERE/'retailops_baselines.py').read_bytes()).hexdigest(),
          'connection.py':hashlib.sha256((HERE/'retailops_eda/data.py').read_bytes()).hexdigest()}
        output=ROOT/'.local/baselines/execution.json';output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        output.write_text(json.dumps(evidence,indent=2)+'\n')
        print('Figuras en docs/baseline_figures; resultados y evidencia en .local/baselines.')
    else:
        (PRIVATE/'execution.json').write_text(json.dumps(evidence,indent=2)+'\n')
        (ROOT/'docs/EDA_EXECUTION.json').write_text(json.dumps(evidence,indent=2)+'\n')
        print('Figuras agregadas en docs/eda_figures; evidencia local en .local/eda/execution.json.')

if __name__=='__main__':main()
