#!/bin/sh
# Roda a sincronização das skills e a geração dos vaults; repete a cada ROTINA_INTERVALO_HORAS.
INTERVALO_H="${ROTINA_INTERVALO_HORAS:-24}"
while true; do
  /app/sincronizar_skills.sh
  python /app/gerar_vault.py || echo "$(date '+%F %T') vaults: algum repositório falhou (veja acima)"
  # o Obsidian web roda como o usuário 1000
  chown -R "${PUID:-1000}:${PGID:-1000}" /dados/vaults 2>/dev/null || true
  echo "$(date '+%F %T') rotina concluída; próxima em ${INTERVALO_H} h"
  sleep $(( INTERVALO_H * 3600 ))
done
