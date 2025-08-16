#!/bin/bash
set -euo pipefail

echo "🔧 Preparando entorno…"
OPTIONS="/data/options.json"

DEBUG_FLAG="false"
if [ -f "$OPTIONS" ]; then
  DEBUG_FLAG=$(jq -r '.debug // false' "$OPTIONS" 2>/dev/null || echo "false")
fi

echo "🔄 Ejecutando captura de snapshots EZVIZ (debug=$DEBUG_FLAG)…"
python3 /app/apisnapshot.py
echo "✅ Proceso completado."
