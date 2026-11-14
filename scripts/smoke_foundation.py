"""Verificación local: inicia procesos propios, consulta HTTP y los detiene."""
import os,socket,subprocess,time,urllib.request,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
log_dir=root/'.local'/'verification'
log_dir.mkdir(parents=True, exist_ok=True)
def free_port():
 with socket.socket() as s:
  s.bind(('127.0.0.1',0));return s.getsockname()[1]
api,ml,web=(free_port() for _ in range(3))
env={**os.environ,'API_HOST':'127.0.0.1','API_PORT':str(api),'ML_HOST':'127.0.0.1','ML_PORT':str(ml),'WEB_HOST':'127.0.0.1','WEB_PORT':str(web),'API_PROXY_TARGET':f'http://127.0.0.1:{api}'}
commands=[('api',['java','-jar','target/api-0.0.1-SNAPSHOT.jar'],'apps/api'),('ml',['.venv/bin/python','-m','app'],'apps/ml-service'),('web',['npm','run','dev'],'apps/web')]
processes=[];logs=[]
def get(url):
 with urllib.request.urlopen(url,timeout=2) as r:
  return r.status,r.read().decode()
try:
 for name,cmd,cwd in commands:
  log=open(log_dir/(name+'.log'),'w');logs.append(log)
  processes.append(subprocess.Popen(cmd,cwd=root/cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True))
 for path in [f'http://127.0.0.1:{api}/actuator/health',f'http://127.0.0.1:{api}/actuator/health/liveness',f'http://127.0.0.1:{api}/actuator/health/readiness',f'http://127.0.0.1:{ml}/health',f'http://127.0.0.1:{web}/',f'http://127.0.0.1:{web}/api/actuator/health']:
  for attempt in range(80):
   try:
    status,body=get(path);break
   except (OSError,TimeoutError):
    time.sleep(.2)
  else: raise AssertionError('Servicio no disponible: '+path)
  assert status==200
  if '/actuator/' in path: assert json.loads(body)['status']=='UP'
  elif path.endswith('/health'): assert json.loads(body)=={'status':'ok'}
  else: assert 'lang="es"' in body and 'src="/src/main.tsx"' in body
  print('HTTP 200',path,flush=True)
 print('Smoke local correcto: web, API, ML, probes y proxy. Sin comprobación visual en navegador.')
finally:
 import signal
 for p in processes:
  if p.poll() is None: os.killpg(p.pid,signal.SIGTERM)
 for p in processes:
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
 for f in logs:f.close()
