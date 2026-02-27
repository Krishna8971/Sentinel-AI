"""
Sentinel AI Qwen Proxy - runs on HOST at 0.0.0.0:1235.
Forwards Docker container requests to the Qwen LM Studio on a remote PC.
Set QWEN_HOST env var to the LAN IP of the PC running Qwen, e.g.:
  $env:QWEN_HOST="http://192.168.1.50:1234"; python qwen_proxy.py
"""
import asyncio
import os
import subprocess
import sys
import httpx
from aiohttp import web

# Set QWEN_HOST to the actual LAN IP of the Qwen PC — 169.254.x.x is link-local and won't route
TARGET_HOST = os.getenv('QWEN_HOST', 'http://172.20.219.31:1234')
LISTEN_PORT = 1235

def kill_existing_port():
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                f'netstat -ano | findstr ":{LISTEN_PORT}.*LISTENING"',
                shell=True, capture_output=True, text=True
            )
            for line in result.stdout.strip().splitlines():
                parts = line.strip().split()
                if parts:
                    pid = parts[-1]
                    if pid.isdigit() and int(pid) != os.getpid():
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
                        print(f"[Qwen Proxy] Killed existing PID {pid} on port {LISTEN_PORT}")
    except Exception as e:
        print(f"[Qwen Proxy] Warning killing old process: {repr(e)}")

async def proxy_handler(request: web.Request) -> web.Response:
    url = TARGET_HOST + str(request.rel_url)
    body = await request.read()
    headers = {
        'Content-Type': request.headers.get('Content-Type', 'application/json'),
        'Accept': request.headers.get('Accept', '*/*'),
    }

    try:
        transport = httpx.AsyncHTTPTransport(http2=False, retries=1)
        async with httpx.AsyncClient(transport=transport, timeout=120.0) as client:
            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body
            )
            return web.Response(
                status=resp.status_code,
                content_type='application/json',
                body=resp.content
            )
    except Exception as e:
        error_msg = repr(e)
        print(f"[Qwen Proxy] ERROR: {error_msg}")
        return web.Response(status=502, text=error_msg)

async def main():
    kill_existing_port()
    await asyncio.sleep(0.5)
    app = web.Application()
    app.router.add_route('*', '/{path_info:.*}', proxy_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', LISTEN_PORT)
    print(f"[Qwen Proxy] ✅ Listening on 0.0.0.0:{LISTEN_PORT} → {TARGET_HOST}")
    await site.start()
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
