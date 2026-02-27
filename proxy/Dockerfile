FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir aiohttp httpx
COPY proxy_server.py .
CMD ["python", "proxy_server.py"]
