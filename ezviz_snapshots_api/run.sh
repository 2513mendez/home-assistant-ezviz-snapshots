#!/bin/sh

CONFIG_PATH=/data/options.json
DEBUG_FLAG=$(jq -r '.debug // false' "$CONFIG_PATH" 2>/dev/null)
NOW_START=$(date +"%d/%m/%Y %H:%M:%S")

echo "[$NOW_START] 🔄 Ejecutando captura de snapshots EZVIZ..."

if [ "$DEBUG_FLAG" = "true" ]; then
    echo "[$NOW_START] 🐞 Modo debug activado (desde options.json)."
    python3 /app/apisnapshot.py --debug
else
    python3 /app/apisnapshot.py
fi

NOW_END=$(date +"%d/%m/%Y %H:%M:%S")
echo "[$NOW_END] ✅ Proceso completado."
