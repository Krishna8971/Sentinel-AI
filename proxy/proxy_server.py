"""
Sentinel AI Proxy Container - runs INSIDE Docker as a sidecar.
Forwards all LM Studio traffic to the remote LM Studio host at 172.20.194.248:1234
"""
import asyncio
import httpx
from aiohttp import web

TARGET_HOST = 'http://host.docker.internal:1234'

async def proxy_handler(request: web.Request) -> web.Response:
    url = TARGET_HOST + str(request.rel_url)
    body = await request.read()
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ('host', 'connection', 'transfer-encoding')}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(method=request.method, url=url,
                                        headers=headers, content=body)
            out_headers = {k: v for k, v in resp.headers.items()
                           if k.lower() not in ('transfer-encoding', 'connection')}
            return web.Response(status=resp.status_code, headers=out_headers, body=resp.content)
    except Exception as e:
        print(f"[proxy] error: {e}")
        return web.Response(status=502, text=str(e))

async def main():
    app = web.Application()
    app.router.add_route('*', '/{path:.*}', proxy_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    print(f"[Sentinel Proxy] Running on 0.0.0.0:8080 => {TARGET_HOST}")
    await site.start()
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
