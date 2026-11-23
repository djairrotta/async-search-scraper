"""Gera um vault do Obsidian por programa, com uma nota por arquivo.

Para cada repositório em repos.txt (formato: nome_do_vault url [ramo]):
- clona ou atualiza em $REPOS_DIR/<nome>
- escreve em $VAULTS_DIR/<nome>/ uma nota por arquivo de código, uma nota
  por pasta e um índice (00 Índice.md), com links [[...]] entre elas, para
  o grafo do Obsidian mostrar como as partes do programa se ligam.

As notas geradas ficam em "Código/". Notas escritas à mão em qualquer outra
pasta do vault nunca são tocadas. Repositórios privados usam GITHUB_TOKEN.
"""

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPOS_DIR = Path(os.environ.get("REPOS_DIR", "/dados/repos"))
VAULTS_DIR = Path(os.environ.get("VAULTS_DIR", "/dados/vaults"))
LISTA = Path(os.environ.get("REPOS_LISTA", "/app/repos.txt"))
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
MAX_ARQUIVOS = int(os.environ.get("VAULT_MAX_ARQUIVOS", "4000"))

IGNORAR_DIRS = {".git", "node_modules", "dist", "build", ".next", ".astro", "__pycache__", ".venv",
                "venv", "coverage", ".turbo", ".cache", "vendor", ".idea", ".vscode"}
EXTENSOES = {
    ".py": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".ts": "typescript",
    ".tsx": "tsx", ".jsx": "jsx", ".astro": "astro", ".vue": "vue", ".svelte": "svelte", ".css": "css",
    ".scss": "scss", ".html": "html", ".sql": "sql", ".sh": "bash", ".md": "markdown", ".json": "json",
    ".yml": "yaml", ".yaml": "yaml", ".toml": "toml", ".conf": "nginx", ".go": "go", ".rs": "rust",
    ".php": "php", ".java": "java", ".kt": "kotlin", ".swift": "swift", ".dart": "dart", ".rb": "ruby",
}
NOMES_ESPECIAIS = {"Dockerfile": "dockerfile", "Makefile": "makefile", "nginx.conf": "nginx"}
PADROES = [
    re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)", re.M),
    re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)", re.M),
    re.compile(r"^\s*export\s+(?:const|let|var|type|interface|enum)\s+([A-Za-z_$][\w$]*)", re.M),
    re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)", re.M),
    re.compile(r"^\s*class\s+([A-Za-z_]\w*)\s*[:(]", re.M),
    re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)", re.M),
]
IMPORTS = [
    re.compile(r"""(?:import|export)\s[^'"]*?from\s+['"](\.{1,2}/[^'"]+)['"]"""),
    re.compile(r"""require\(\s*['"](\.{1,2}/[^'"]+)['"]\s*\)"""),
    re.compile(r"""import\(\s*['"](\.{1,2}/[^'"]+)['"]\s*\)"""),
]


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def url_com_token(url):
    if TOKEN and url.startswith("https://github.com/"):
        return url.replace("https://", f"https://x-access-token:{TOKEN}@", 1)
    return url


def atualizar(nome, url, ramo):
    destino = REPOS_DIR / nome
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    if (destino / ".git").exists():
        cmd = ["git", "-C", str(destino), "pull", "--ff-only", "--depth", "1"]
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if r.returncode == 0:
            return destino
        shutil.rmtree(destino, ignore_errors=True)
    cmd = ["git", "clone", "--depth", "1"] + (["--branch", ramo] if ramo else []) + [url_com_token(url), str(destino)]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        log(f"{nome}: não consegui clonar ({r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'erro'})")
        return None
    # não deixa o token gravado no .git/config
    subprocess.run(["git", "-C", str(destino), "remote", "set-url", "origin", url], env=env)
    return destino


def nota_nome(rel):
    """Nome de nota estável e único para um caminho do repositório."""
    return rel.replace("/", " ∕ ")


def arquivos_do_repo(raiz):
    saida = []
    for pasta, dirs, nomes in os.walk(raiz):
        dirs[:] = sorted(d for d in dirs if d not in IGNORAR_DIRS and not d.startswith(".") or d in {".github"})
        for n in sorted(nomes):
            p = Path(pasta) / n
            ling = NOMES_ESPECIAIS.get(n) or EXTENSOES.get(p.suffix.lower())
            if not ling:
                continue
            try:
                if p.stat().st_size > 1_500_000:
                    continue
            except OSError:
                continue
            saida.append((p, ling))
            if len(saida) >= MAX_ARQUIVOS:
                return saida
    return saida


def resolver_import(origem_rel, alvo, conjunto):
    base = Path(origem_rel).parent
    caminho = os.path.normpath(str(base / alvo)).replace("\\", "/")
    for cand in [caminho] + [caminho + e for e in (".ts", ".tsx", ".js", ".mjs", ".jsx", ".astro", ".vue")] + \
            [caminho + "/index" + e for e in (".ts", ".tsx", ".js", ".mjs")]:
        if cand in conjunto:
            return cand
    return None


def gerar(nome, url, raiz):
    vault = VAULTS_DIR / nome
    codigo = vault / "Código"
    tmp = vault / ".Código.novo"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    (vault / ".obsidian").mkdir(parents=True, exist_ok=True)

    arquivos = arquivos_do_repo(raiz)
    rels = {str(p.relative_to(raiz)).replace("\\", "/"): (p, ling) for p, ling in arquivos}
    pastas = {}
    for rel in rels:
        pasta = str(Path(rel).parent).replace("\\", "/")
        pastas.setdefault("." if pasta == "." else pasta, []).append(rel)

    for rel, (p, ling) in rels.items():
        try:
            texto = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        linhas = texto.count("\n") + 1
        simbolos = []
        for pad in PADROES:
            simbolos += pad.findall(texto)
        simbolos = list(dict.fromkeys(simbolos))[:60]
        ligacoes = []
        for pad in IMPORTS:
            for alvo in pad.findall(texto):
                r = resolver_import(rel, alvo, rels)
                if r and r != rel:
                    ligacoes.append(r)
        ligacoes = list(dict.fromkeys(ligacoes))
        pasta = str(Path(rel).parent).replace("\\", "/")
        pasta = "." if pasta == "." else pasta
        trecho = "\n".join(texto.splitlines()[:40])
        corpo = [
            "---",
            f"programa: {nome}",
            f"caminho: {rel}",
            f"linguagem: {ling}",
            f"linhas: {linhas}",
            "tags: [codigo, " + nome + "]",
            "---",
            f"# {rel}",
            "",
            f"Pasta: [[{nota_nome(pasta) if pasta != '.' else '00 Índice'}]] · Programa: [[00 Índice]]",
            f"Repositório: {url}",
            "",
        ]
        if simbolos:
            corpo += ["## Funções, classes e exportações", ""] + [f"- `{s}`" for s in simbolos] + [""]
        if ligacoes:
            corpo += ["## Usa", ""] + [f"- [[{nota_nome(l)}]]" for l in ligacoes] + [""]
        corpo += ["## Início do arquivo", "", f"```{ling}", trecho.replace("```", "ˋˋˋ"), "```", ""]
        (tmp / (nota_nome(rel) + ".md")).write_text("\n".join(corpo), encoding="utf-8")

    for pasta, itens in pastas.items():
        if pasta == ".":
            continue
        pai = str(Path(pasta).parent).replace("\\", "/")
        corpo = [f"# {pasta}/", "", f"Dentro de: [[{nota_nome(pai) if pai != '.' else '00 Índice'}]]", "",
                 "## Arquivos", ""] + [f"- [[{nota_nome(r)}]]" for r in sorted(itens)] + [""]
        (tmp / (nota_nome(pasta) + ".md")).write_text("\n".join(corpo), encoding="utf-8")

    readme = next((raiz / n for n in ("README.md", "readme.md", "AGENTS.md") if (raiz / n).exists()), None)
    resumo = ""
    if readme:
        resumo = "\n".join(readme.read_text(encoding="utf-8", errors="replace").splitlines()[:25])
    topo = sorted(p for p in pastas if p != "." and "/" not in p)
    indice = [
        "---", f"programa: {nome}", "tags: [indice, " + nome + "]", "---",
        f"# {nome}", "", f"Repositório: {url}",
        f"Atualizado em: {time.strftime('%d/%m/%Y %H:%M')}", f"Arquivos mapeados: {len(rels)}", "",
        "## Pastas", "",
    ] + [f"- [[{nota_nome(p)}]]" for p in topo] + ["", "## Arquivos na raiz", ""] + \
        [f"- [[{nota_nome(r)}]]" for r in sorted(pastas.get(".", []))] + ["", "## Resumo do README", "", resumo, ""]
    (tmp / "00 Índice.md").write_text("\n".join(indice), encoding="utf-8")

    shutil.rmtree(codigo, ignore_errors=True)
    tmp.rename(codigo)
    log(f"{nome}: {len(rels)} arquivos no vault")


def main():
    VAULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    falhas = 0
    for linha in LISTA.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if not linha:
            continue
        partes = linha.split()
        nome, url = partes[0], partes[1]
        ramo = partes[2] if len(partes) > 2 else None
        raiz = atualizar(nome, url, ramo)
        if not raiz:
            falhas += 1
            continue
        try:
            gerar(nome, url, raiz)
        except Exception as erro:
            falhas += 1
            log(f"{nome}: falhou ao gerar ({erro})")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
