"""Registro HTTP seguro: sin cuerpo, URL, cabeceras ni texto de excepciones."""
import json
import logging
import re
import uuid
from datetime import datetime, timezone

logger = logging.getLogger('retailops.http')
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def request_id(value):
    return value if value and re.fullmatch(r'[a-f0-9]{32}', value) else uuid.uuid4().hex


class RequestLogging:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        identity = request_id(headers.get(b'x-request-id', b'').decode('ascii', errors='ignore'))
        status = 500
        error_type = None

        async def respond(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                message = dict(message)
                message['headers'] = [(k,v) for k,v in message.get('headers', []) if k.lower() != b'x-request-id'] + [(b'x-request-id', identity.encode())]
            await send(message)

        try:
            await self.app(scope, receive, respond)
        except Exception as error:
            error_type = type(error).__name__
            raise
        finally:
            # Texto constante; no str(error), traceback con valores, query ni payload.
            event = dict(timestamp=datetime.now(timezone.utc).isoformat(), service='fastapi',
                         level='ERROR' if status >= 500 else 'INFO', request_id=identity,
                         status=status, message='Solicitud HTTP completada')
            if error_type:
                event['exception_type'] = error_type
            logger.log(logging.ERROR if status >= 500 else logging.INFO, json.dumps(event, ensure_ascii=False))
