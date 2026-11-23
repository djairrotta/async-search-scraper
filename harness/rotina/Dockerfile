# Contexto de build: raiz do repositório.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*
ENV TZ=America/Sao_Paulo PYTHONUNBUFFERED=1
WORKDIR /app
COPY harness/rotina/ /app/
RUN chmod +x /app/*.sh
VOLUME ["/dados"]
CMD ["/app/rotina.sh"]
