"""
Sentinel AI Proxy - runs on HOST at 0.0.0.0:1234.
Forwards Docker container requests to remote LM Studio at 172.20.194.248:1234.
Auto-kills any existing process on port 1234 before binding.
"""
import asyncio
import os
import subprocess
import sys
import httpx
from aiohttp import web

TARGET_HOST = 'http://172.20.194.248:1234'
LISTEN_PORT = 1234

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
                        print(f"[Proxy] Killed existing PID {pid} on port {LISTEN_PORT}")
    except Exception as e:
        print(f"[Proxy] Warning killing old process: {repr(e)}")

async def proxy_handler(request: web.Request) -> web.Response:
    url = TARGET_HOST + str(request.rel_url)
    body = await request.read()
    # Only forward safe headers
    headers = {
        'Content-Type': request.headers.get('Content-Type', 'application/json'),
        'Accept': request.headers.get('Accept', '*/*'),
    }

    try:
        # Force HTTP/1.1, no connection pooling — LM Studio drops keep-alive
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
        error_msg = repr(e)  # repr() always shows type + message even if str(e) is empty
        print(f"[Proxy] ERROR: {error_msg}")
        return web.Response(status=502, text=error_msg)

async def main():
    kill_existing_port()
    await asyncio.sleep(0.5)
    app = web.Application()
    app.router.add_route('*', '/{path_info:.*}', proxy_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', LISTEN_PORT)
    print(f"[Sentinel Proxy] ✅ Listening on 0.0.0.0:{LISTEN_PORT} → {TARGET_HOST}")
    await site.start()
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
