#!/bin/sh
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [INFO] Ejecutando EZVIZ Snapshots (v1.2.2)…"
python3 /app/apisnapshot.py
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [INFO] Proceso completado."
