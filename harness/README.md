# Harness (VM 113 do Proxmox)

Serviços que dão apoio aos agentes e ao SEO, instalados no EasyPanel da VM 113
(`harness`, 192.168.0.20), projeto `harness`. Painel em ep-harness.judinfo.com.br.

| Serviço | O que faz | Endereço |
|---|---|---|
| `busca` | API sobre a biblioteca deste repositório (vários buscadores, sem duplicatas, cache no Postgres) | busca.judinfo.com.br (cabeçalho `X-API-Key`) |
| `rotina` | Espelha os repositórios de skills e gera um vault do Obsidian por programa, uma nota por arquivo | interno, roda 1 vez por dia |
| `browser` | browser-harness com Chromium próprio, como servidor MCP | rede local, porta 8765 (`/mcp`) |
| `postgres` | Banco único da VM (pgvector) | interno |
| `redis` | Fila e cache do Infisical | interno |
| `infisical` | Cofre de segredos | cofre.judinfo.com.br (Cloudflare Access) |
| `couchdb` | Sincronização dos vaults (plugin Self-hosted LiveSync) | obsidian-sync.judinfo.com.br |
| `obsidian` | Obsidian no navegador com os vaults gerados | obsidian.judinfo.com.br (Cloudflare Access) |

## API de busca

```
GET /saude
GET /buscar?q=advogado+bancario+mococa&motores=yahoo,duckduckgo&paginas=1
GET /posicao?q=advogado+bancario+mococa&dominio=djairrotta.adv.br
```

Motores: `yahoo`, `duckduckgo`, `aol`, `brave` (precisa de BRAVE_API_KEY),
`bing`, `startpage`, `mojeek`, `searchapi` (paga, precisa de SEARCHAPI_KEY).
Cada `/posicao` fica registrada em `busca_log`, para acompanhar posições no tempo.

## Vaults

`rotina/repos.txt` lista os programas. Repositórios privados só entram com
`GITHUB_TOKEN` (somente leitura) no env do serviço `rotina`. As notas geradas
ficam em `Código/` dentro de cada vault; o resto do vault é livre para notas à mão.
