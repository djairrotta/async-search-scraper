#!/bin/sh
# Sobe o Chromium (perfil persistente em /dados/perfil) e o servidor MCP do browser-harness.
set -e
mkdir -p /dados/perfil /dados/tmp
rm -f /dados/perfil/SingletonLock /dados/perfil/SingletonSocket /dados/perfil/SingletonCookie
chromium --headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu \
  --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 \
  --user-data-dir=/dados/perfil --lang=pt-BR --window-size=1366,900 about:blank &
for i in $(seq 1 30); do curl -sf http://127.0.0.1:9222/json/version >/dev/null && break; sleep 1; done
exec /opt/proxy/bin/mcp-proxy --host 0.0.0.0 --port 8000 --pass-environment -- browser-harness-mcp
