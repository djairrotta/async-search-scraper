#!/bin/sh
# Mantém em $SKILLS_DIR um espelho de cada repositório de skills listado em skills.txt.
set -u
SKILLS_DIR="${SKILLS_DIR:-/dados/skills}"
LISTA="${SKILLS_LISTA:-/app/skills.txt}"
mkdir -p "$SKILLS_DIR"
falhas=0
grep -v '^\s*#' "$LISTA" | while read -r nome url; do
  [ -z "${nome:-}" ] && continue
  if [ -d "$SKILLS_DIR/$nome/.git" ]; then
    git -C "$SKILLS_DIR/$nome" fetch --depth 1 -q origin && git -C "$SKILLS_DIR/$nome" reset -q --hard FETCH_HEAD \
      && echo "$(date '+%F %T') skills: $nome atualizado" || echo "$(date '+%F %T') skills: $nome falhou"
  else
    git clone -q --depth 1 "$url" "$SKILLS_DIR/$nome" \
      && echo "$(date '+%F %T') skills: $nome clonado" || echo "$(date '+%F %T') skills: $nome falhou"
  fi
done
# índice simples, lido por agentes e pelo Obsidian
{
  echo "# Skills espelhadas"; echo; echo "Atualizado em $(date '+%d/%m/%Y %H:%M')"; echo
  for d in "$SKILLS_DIR"/*/; do
    n=$(basename "$d"); c=$(git -C "$d" log -1 --format='%h %cs' 2>/dev/null)
    s=$(find "$d" -name SKILL.md -not -path '*/node_modules/*' | wc -l)
    echo "- **$n** ($c): $s arquivos SKILL.md"
  done
} > "$SKILLS_DIR/INDICE.md"
