"""Receptor local acotado: webhook Alertmanager, retención y señales explícitas de prueba."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import time

DB = os.environ.get('RECEIVER_DB', '/data/events.sqlite')
STATE = Path(os.environ.get('RECEIVER_STATE', '/etc/state/state.json'))
ALLOWED = {'alertname', 'service', 'severity', 'category', 'scope', 'environment', 'case', 'namespace'}


def connect():
    conn = sqlite3.connect(DB, timeout=5)
    conn.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, timestamp REAL, payload TEXT)')
    conn.execute('DELETE FROM events WHERE timestamp < ?', (time.time()-48*3600,))
    conn.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 1000)')
    conn.commit()
    return conn


def sanitize(value):
    if not isinstance(value, dict) or value.get('status') not in {'firing', 'resolved'}:
        raise ValueError('Webhook inválido')
    alerts = []
    for alert in value.get('alerts', [])[:100]:
        labels = {k: str(v)[:200] for k,v in alert.get('labels', {}).items() if k in ALLOWED}
        alerts.append({'status': alert['status'], 'labels': labels, 'startsAt': str(alert.get('startsAt', ''))[:50], 'endsAt': str(alert.get('endsAt', ''))[:50]})
    if not alerts:
        raise ValueError('Sin alertas')
    return {'status': value['status'], 'alerts': alerts,
            'groupLabels': {k:str(v)[:200] for k,v in value.get('groupLabels', {}).items() if k in ALLOWED}}


def metrics():
    state = json.loads(STATE.read_text())
    active = state['lab_active']
    if active not in (0,1): raise ValueError('Estado inválido')
    text = f'retailops_lab_active {active}\n'
    for case in ['api', 'ml']:
        value = state.get('validation', {}).get(case, 0)
        if value not in (0,1): raise ValueError('Señal inválida')
        text += f'retailops_alert_test_signal{{case="{case}"}} {value}\n'
    with connect() as conn:
        count = conn.execute('SELECT count(*) FROM events').fetchone()[0]
    return text + f'retailops_local_notification_events {count}\n'


class Handler(BaseHTTPRequestHandler):
    def answer(self, code, value, content_type='application/json'):
        body = value.encode() if isinstance(value, str) else json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/health':
            with connect() as conn: conn.execute('SELECT 1')
            self.answer(200, {'status':'ok'})
        elif self.path == '/metrics':
            try: self.answer(200, metrics(), 'text/plain; version=0.0.4')
            except (OSError, ValueError, KeyError): self.answer(503, {'status':'state_unavailable'})
        elif self.path == '/events':
            with connect() as conn:
                rows = conn.execute('SELECT id,timestamp,payload FROM events ORDER BY id DESC LIMIT 1000').fetchall()
            self.answer(200, [{'id':i,'timestamp':t,**json.loads(payload)} for i,t,payload in rows])
        else: self.answer(404, {})

    def do_POST(self):
        if self.path != '/webhook': return self.answer(404, {})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 65536: return self.answer(413, {})
            value = sanitize(json.loads(self.rfile.read(size)))
            with connect() as conn:
                conn.execute('INSERT INTO events(timestamp,payload) VALUES (?,?)', (time.time(),json.dumps(value)))
                conn.commit()
            self.answer(200, {'accepted':True})
        except (ValueError, KeyError, TypeError): self.answer(400, {'accepted':False})

    def log_message(self, *args): pass


if __name__ == '__main__':
    with connect(): pass
    ThreadingHTTPServer(('0.0.0.0', 8090), Handler).serve_forever()
