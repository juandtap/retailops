"""Sonda de entrenamiento sin datos; nunca conectar a destinos configurables."""
from collections import defaultdict
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import urllib.request
import uuid

STATE=Path('/control/state.json');WORK=Path('/work')
UPSTREAMS={'spring':'http://spring:8080/actuator/health','ml':'http://ml:8000/health'}
BUCKETS=(.1,.25,.5,1,2,5,float('inf'))
COUNTS=defaultdict(int);HIST=defaultdict(lambda: [0]*len(BUCKETS));SUM=defaultdict(float)
LOCK=threading.RLock();SLOTS=threading.BoundedSemaphore(2);RESERVATION=None


def effective_state(value,now=None):
    mode=value.get('mode','normal');deadline=value.get('deadline',0)
    if mode not in {'normal','http_5xx','latency','memory','storage','scale_spring','block_ml'}:raise ValueError('Estado inválido')
    now=time.time() if now is None else now
    if mode!='normal' and not(now < deadline <= now+600):return 'normal'
    return mode


def mode():
    try:return effective_state(json.loads(STATE.read_text()))
    except (OSError,ValueError,TypeError):return 'normal'


def reconcile(selected):
    global RESERVATION
    with LOCK:
        if selected=='memory' and RESERVATION is None:RESERVATION=bytearray(48*1024*1024)
        if selected!='memory':RESERVATION=None
        marker=WORK/'availability.marker';held=WORK/'availability.held'
        if not marker.exists() and not held.exists():marker.write_bytes(b'training-marker-v1\n')
        if selected=='storage' and marker.exists():marker.rename(held)
        if selected!='storage' and held.exists():held.rename(marker)


def probe(component,selected=None):
    selected=mode() if selected is None else selected
    started=time.perf_counter();status=503;exception_type=None
    try:
        if component=='storage':
            if (WORK/'availability.marker').read_bytes()!=b'training-marker-v1\n':raise ValueError('Marcador inválido')
            status=200
        elif component=='spring' and selected=='http_5xx':status=503
        else:
            if component=='spring' and selected=='latency':time.sleep(1.5)
            with urllib.request.urlopen(UPSTREAMS[component],timeout=.75) as response:status=response.status
    except (OSError,ValueError) as error:status=503;exception_type=type(error).__name__
    elapsed=time.perf_counter()-started
    with LOCK:
        COUNTS[(component,status)]+=1;SUM[component]+=elapsed
        for i,bound in enumerate(BUCKETS):HIST[component][i]+=int(elapsed<=bound)
    print(json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'service':'training-probe','level':'ERROR' if status>=500 else 'INFO','request_id':uuid.uuid4().hex,'message':'Solicitud HTTP completada','status':status,'component':component,'exception_type':exception_type or ''},ensure_ascii=False),flush=True)
    return status


def metrics():
    try:watch=int(json.loads(STATE.read_text()).get('mode') in {'http_5xx','latency','memory','storage','scale_spring','block_ml'})
    except (OSError,ValueError,TypeError):watch=0
    with LOCK:
        text=f'incident_lab_watch_enabled {watch}\n'
        text+=f'incident_lab_memory_reserved_bytes {len(RESERVATION) if RESERVATION else 0}\n'
        for (component,status),count in sorted(COUNTS.items()):text+=f'incident_lab_requests_total{{component="{component}",status="{status}"}} {count}\n'
        for component,values in sorted(HIST.items()):
            for bound,count in zip(BUCKETS,values):text+=f'incident_lab_request_seconds_bucket{{component="{component}",le="{bound if bound!=float("inf") else "+Inf"}"}} {count}\n'
            text+=f'incident_lab_request_seconds_count{{component="{component}"}} {values[-1]}\nincident_lab_request_seconds_sum{{component="{component}"}} {SUM[component]}\n'
    try:
        for line in Path('/proc/self/status').read_text().splitlines():
            if line.startswith('VmRSS:'):text+=f'incident_lab_process_resident_memory_bytes {int(line.split()[1])*1024}\n'
    except OSError:pass
    return text


def cycle(stop):
    while not stop.is_set():
        selected=mode();reconcile(selected)
        with SLOTS:
            for component in ['spring','ml','storage']:probe(component,selected)
        stop.wait(5)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/health':status,body,kind=200,b'{"status":"ok"}','application/json'
        elif self.path=='/metrics':status,body,kind=200,metrics().encode(),'text/plain; version=0.0.4'
        elif self.path in ['/spring-health','/ml-health','/storage-health']:
            if not SLOTS.acquire(blocking=False):status=429
            else:
                try:status=probe(self.path[1:].split('-')[0])
                finally:SLOTS.release()
            body=json.dumps({'status':'ok' if status==200 else 'unavailable'}).encode();kind='application/json'
        else:status,body,kind=404,b'{}','application/json'
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass


class Server(ThreadingHTTPServer):
    request_queue_size=4
    pool=threading.BoundedSemaphore(4)
    def process_request(self,request,address):
        request.settimeout(5)
        if not self.pool.acquire(blocking=False):self.shutdown_request(request);return
        try:super().process_request(request,address)
        except Exception:self.pool.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.pool.release()


if __name__=='__main__':
    WORK.mkdir(exist_ok=True);reconcile('normal')
    event=threading.Event();threading.Thread(target=cycle,args=(event,),daemon=True).start()
    Server(('0.0.0.0',8089),Handler).serve_forever()
