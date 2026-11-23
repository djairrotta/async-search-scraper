# Contexto de build: raiz do repositório (precisa do pacote search_engines).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/requirements-lib.txt
COPY harness/busca/requirements.txt /app/requirements-api.txt
RUN pip install --no-cache-dir -r requirements-lib.txt -r requirements-api.txt
COPY search_engines /app/search_engines
COPY harness/busca/app.py /app/app.py
RUN useradd -r -u 10001 busca
USER busca
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/saude',timeout=4)"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
