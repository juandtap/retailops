import json
import logging
import pytest
from app.request_logging import RequestLogging, request_id


def test_identity_rejects_injection():
    assert request_id('a'*32) == 'a'*32
    for invalid in ['token-secret', 'a'*33, 'a'*32+'\n', '']:
        assert len(request_id(invalid)) == 32
        assert request_id(invalid) != invalid


@pytest.mark.anyio
async def test_asgi_correlation_and_safe_exception():
    events = []
    class Capture(logging.Handler):
        def emit(self, record):
            events.append(json.loads(record.getMessage()))
    logger = logging.getLogger('retailops.http')
    handler = Capture()
    logger.addHandler(handler)
    sent = []
    async def send(message): sent.append(message)
    async def receive(): return {'type': 'http.request', 'body': b''}
    async def endpoint(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 204, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})
    scope = {'type': 'http', 'headers': [(b'x-request-id', b'a'*32), (b'authorization', b'secret-token')], 'path': '/private?password=secret'}
    try:
        await RequestLogging(endpoint)(scope, receive, send)
        assert dict(sent[0]['headers'])[b'x-request-id'] == b'a'*32
        assert events[-1]['request_id'] == 'a'*32
        assert events[-1]['status'] == 204
        async def failing(scope, receive, send): raise ValueError('password=secret-token')
        with pytest.raises(ValueError):
            await RequestLogging(failing)(scope, receive, send)
        assert events[-1]['exception_type'] == 'ValueError'
        assert events[-1]['status'] == 500
        assert 'secret' not in json.dumps(events)
    finally:
        logger.removeHandler(handler)
