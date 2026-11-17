"""Mide el MLflow ya activo sin reiniciarlo ni cambiar límites; no lee argv/env."""
import json
from pathlib import Path
import subprocess
import time

container = 'retailops-data-mlflow-1'
assert subprocess.check_output(['docker','inspect',container,'--format','{{.State.Running}}'],text=True).strip() == 'true', 'MLflow debe estar activo; este script no lo inicia'
code = r'''
import json,pathlib
root=pathlib.Path('/sys/fs/cgroup')
stat={line.split()[0]:int(line.split()[1]) for line in (root/'memory.stat').read_text().splitlines()}
processes=[]
for path in pathlib.Path('/proc').glob('[0-9]*/smaps_rollup'):
 try:
  values={line.split(':')[0]:int(line.split()[1])*1024 for line in path.read_text().splitlines() if ':' in line and len(line.split())>=2 and line.split()[1].isdigit()}
  processes.append({'pid':int(path.parent.name),'comm':(path.parent/'comm').read_text().strip(),**{k:values.get(k,0) for k in ['Rss','Pss','Pss_Anon','Pss_File','SwapPss']}})
 except (OSError,ValueError):pass
print(json.dumps({'memory_current':int((root/'memory.current').read_text()),'memory_max':(root/'memory.max').read_text().strip(),'swap_current':int((root/'memory.swap.current').read_text()),'stats':{k:stat.get(k) for k in ['anon','file','inactive_file','active_file','kernel','slab','file_mapped']},'processes':processes,'pss_sum':sum(p['Pss'] for p in processes)}))
'''
report=json.loads(subprocess.check_output(['docker','exec','-i',container,'python','-c',code],text=True))
report['container_state']=subprocess.check_output(['docker','inspect',container,'--format','{{.HostConfig.Memory}} {{.HostConfig.MemorySwap}} {{.State.OOMKilled}} {{.RestartCount}}'],text=True).strip()
folder=Path('.local/f51');folder.mkdir(exist_ok=True,mode=0o700)
p=folder/f'mlflow-memory-{time.time_ns()}.json';p.write_text(json.dumps(report,indent=2)+'\n');p.chmod(0o600)
print('MLflow MiB:',{k:round(v/2**20,1) for k,v in report['stats'].items() if v is not None},'swap',round(report['swap_current']/2**20,1),'sin cambios de servicio. Evidencia:',p)
