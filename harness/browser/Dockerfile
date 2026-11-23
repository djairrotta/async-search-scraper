# browser-harness com Chromium próprio, exposto como servidor MCP (HTTP) pelo mcp-proxy.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends chromium fonts-liberation fonts-noto-color-emoji \
    tini curl ca-certificates tzdata && rm -rf /var/lib/apt/lists/*
ARG BH_REF=main
RUN pip install --no-cache-dir "browser-harness[mcp] @ git+https://github.com/browser-use/browser-harness@${BH_REF}" mcp-proxy
ENV TZ=America/Sao_Paulo PYTHONUNBUFFERED=1 \
    BU_CDP_URL=http://127.0.0.1:9222 BH_TELEMETRY=0 BROWSER_HARNESS_TELEMETRY=0 ANONYMIZED_TELEMETRY=false \
    BH_UPDATE_CHECK=0 BH_TMP_DIR=/dados/tmp
COPY harness/browser/iniciar.sh /iniciar.sh
RUN chmod +x /iniciar.sh && useradd -m -u 10002 navegador && mkdir -p /dados && chown navegador /dados
USER navegador
EXPOSE 8000
VOLUME ["/dados"]
ENTRYPOINT ["/usr/bin/tini", "--", "/iniciar.sh"]
