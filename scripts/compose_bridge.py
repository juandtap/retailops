"""Puente TCP optativo CNI→loopback Compose, sin Docker socket ni credenciales.

Ejecutar en primer plano tras revisar cni0 y arrancar dependencias Compose.
Solo acepta origen 10.42.0.0/16; no enlaza interfaces LAN.
"""
import asyncio
import ipaddress

BIND = '10.42.0.1'
NETWORK = ipaddress.ip_network('10.42.0.0/16')
PORTS = {15432: 5432, 15000: 5000, 19000: 9000, 18081: 8081}

async def serve(reader, writer, target, slots):
    peer = writer.get_extra_info('peername')[0]
    if ipaddress.ip_address(peer) not in NETWORK:
        writer.close()
        await writer.wait_closed()
        return
    remote_writer = None
    async def copy(source, destination):
        while chunk := await asyncio.wait_for(source.read(65536), 120):
            destination.write(chunk)
            await destination.drain()
    try:
        async with slots:
            remote_reader, remote_writer = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', target), 3)
            tasks = [asyncio.create_task(copy(reader, remote_writer)), asyncio.create_task(copy(remote_reader, writer))]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except (OSError, TimeoutError):
        pass
    finally:
        writer.close()
        if remote_writer:
            remote_writer.close()
            await remote_writer.wait_closed()
        await writer.wait_closed()

async def main():
    slots = asyncio.Semaphore(32)
    servers = []
    try:
        for port, target in PORTS.items():
            server = await asyncio.start_server(lambda r, w, t=target: serve(r, w, t, slots), BIND, port, limit=65536)
            servers.append(server)
        print('Puente local CNI activo; Ctrl-C para detener', flush=True)
        await asyncio.gather(*(s.serve_forever() for s in servers))
    finally:
        for server in servers:
            server.close()
            await server.wait_closed()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
