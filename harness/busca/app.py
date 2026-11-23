"""API de busca do harness (busca.judinfo.com.br).

Envolve a biblioteca search_engines deste repositório numa API HTTP:
- GET /saude                      estado do serviço e do banco
- GET /buscar?q=...               resultados de vários buscadores, sem duplicatas
- GET /posicao?q=...&dominio=...  posição de um domínio em cada buscador

Toda rota, menos /saude, exige o cabeçalho X-API-Key (variável BUSCA_API_KEY).
Resultados ficam em cache no Postgres (tabela busca_cache) e cada consulta
é registrada em busca_log, para acompanhar posições ao longo do tempo.
"""

import asyncio
import hashlib
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import asyncpg
from fastapi import FastAPI, Header, HTTPException, Query

from search_engines import Aol, Brave, Duckduckgo, Mojeek, SearchApi, Startpage, Yahoo, Bing

MOTORES = {
    "yahoo": Yahoo,
    "duckduckgo": Duckduckgo,
    "aol": Aol,
    "brave": Brave,
    "bing": Bing,
    "startpage": Startpage,
    "mojeek": Mojeek,
    "searchapi": SearchApi,
}
PADRAO = [m.strip() for m in os.environ.get("BUSCA_MOTORES_PADRAO", "yahoo,duckduckgo").split(",") if m.strip()]
CACHE_HORAS = float(os.environ.get("BUSCA_CACHE_HORAS", "6"))
API_KEY = os.environ.get("BUSCA_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

pool = None

SQL_INICIAL = """
create table if not exists busca_cache (
  chave text primary key,
  resposta jsonb not null,
  criado_em timestamptz not null default now()
);
create table if not exists busca_log (
  id bigserial primary key,
  consulta text not null,
  motores text[] not null,
  paginas int not null,
  total int not null,
  status jsonb not null,
  dominio text,
  posicoes jsonb,
  criado_em timestamptz not null default now()
);
create index if not exists busca_log_consulta on busca_log (consulta, criado_em desc);
"""


@asynccontextmanager
async def ciclo(_app):
    global pool
    if DATABASE_URL:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        async with pool.acquire() as c:
            await c.execute(SQL_INICIAL)
    yield
    if pool:
        await pool.close()


app = FastAPI(title="Busca harness", version="1.0", lifespan=ciclo)


def exigir_chave(chave):
    if not API_KEY or not chave or not secrets.compare_digest(chave, API_KEY):
        raise HTTPException(status_code=401, detail="chave inválida")


def host(link):
    h = urlparse(link).netloc.lower()
    return h[4:] if h.startswith("www.") else h


async def rodar_motor(nome, consulta, paginas):
    cls = MOTORES[nome]
    inicio = time.monotonic()
    try:
        async with cls(suppress_console_output=True) as motor:
            motor.ignore_duplicate_urls = True
            res = await motor.search(consulta, pages=paginas)
            itens = [dict(r) for r in res]
            return nome, {
                "http": motor.http_status,
                "bloqueado": bool(motor.is_banned),
                "degradado": bool(motor.is_degraded),
                "quantidade": len(itens),
                "segundos": round(time.monotonic() - inicio, 2),
            }, itens
    except Exception as erro:  # um motor com defeito não derruba a busca inteira
        return nome, {"erro": type(erro).__name__, "detalhe": str(erro)[:200], "quantidade": 0}, []


async def buscar_tudo(consulta, motores, paginas):
    chave = hashlib.sha256(json.dumps([consulta.lower(), sorted(motores), paginas]).encode()).hexdigest()
    if pool:
        async with pool.acquire() as c:
            linha = await c.fetchrow(
                "select resposta from busca_cache where chave=$1 and criado_em > now() - make_interval(secs => $2)",
                chave, CACHE_HORAS * 3600,
            )
            if linha:
                resposta = json.loads(linha["resposta"])
                resposta["cache"] = True
                return resposta

    saidas = await asyncio.gather(*(rodar_motor(m, consulta, paginas) for m in motores))
    status, resultados, vistos = {}, [], set()
    for nome, st, itens in saidas:
        status[nome] = st
        for pos, item in enumerate(itens, start=1):
            link = item.get("link") or ""
            resultados.append({
                "motor": nome,
                "posicao": pos,
                "titulo": item.get("title"),
                "link": link,
                "host": host(link),
                "texto": item.get("text"),
                "repetido": link in vistos,
            })
            vistos.add(link)

    resposta = {
        "consulta": consulta,
        "motores": status,
        "total_unicos": len(vistos),
        "resultados": resultados,
        "cache": False,
        "em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if pool:
        async with pool.acquire() as c:
            await c.execute(
                "insert into busca_cache (chave, resposta, criado_em) values ($1, $2, now()) "
                "on conflict (chave) do update set resposta=excluded.resposta, criado_em=now()",
                chave, json.dumps(resposta),
            )
    return resposta


def validar_motores(motores):
    lista = [m.strip().lower() for m in (motores.split(",") if motores else PADRAO) if m.strip()]
    invalidos = [m for m in lista if m not in MOTORES]
    if invalidos:
        raise HTTPException(status_code=400, detail=f"motores desconhecidos: {', '.join(invalidos)}")
    return lista


@app.get("/saude")
async def saude():
    banco = None
    if pool:
        async with pool.acquire() as c:
            banco = await c.fetchval("select 1") == 1
    return {"ok": True, "banco": banco, "motores": list(MOTORES), "padrao": PADRAO}


@app.get("/buscar")
async def buscar(
    q: str = Query(..., min_length=2, max_length=300),
    motores: str | None = None,
    paginas: int = Query(1, ge=1, le=3),
    x_api_key: str | None = Header(default=None),
):
    exigir_chave(x_api_key)
    lista = validar_motores(motores)
    resposta = await buscar_tudo(q, lista, paginas)
    if pool and not resposta["cache"]:
        async with pool.acquire() as c:
            await c.execute(
                "insert into busca_log (consulta, motores, paginas, total, status) values ($1,$2,$3,$4,$5)",
                q, lista, paginas, resposta["total_unicos"], json.dumps(resposta["motores"]),
            )
    return resposta


@app.get("/posicao")
async def posicao(
    q: str = Query(..., min_length=2, max_length=300),
    dominio: str = Query(..., min_length=3, max_length=200),
    motores: str | None = None,
    paginas: int = Query(2, ge=1, le=3),
    x_api_key: str | None = Header(default=None),
):
    exigir_chave(x_api_key)
    lista = validar_motores(motores)
    resposta = await buscar_tudo(q, lista, paginas)
    alvo = dominio.lower().removeprefix("www.")
    posicoes = {}
    for r in resposta["resultados"]:
        if r["host"] == alvo or r["host"].endswith("." + alvo):
            posicoes.setdefault(r["motor"], {"posicao": r["posicao"], "link": r["link"]})
    saida = {
        "consulta": q,
        "dominio": alvo,
        "posicoes": {m: posicoes.get(m) for m in lista},
        "motores": resposta["motores"],
        "cache": resposta["cache"],
    }
    if pool:
        async with pool.acquire() as c:
            await c.execute(
                "insert into busca_log (consulta, motores, paginas, total, status, dominio, posicoes) "
                "values ($1,$2,$3,$4,$5,$6,$7)",
                q, lista, paginas, resposta["total_unicos"], json.dumps(resposta["motores"]),
                alvo, json.dumps(saida["posicoes"]),
            )
    return saida
