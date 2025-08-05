#!/bin/sh

echo "📸 Ejecutando script de snapshot EZVIZ..."

TOKEN=$(jq -r '.token' /data/options.json)
NOW=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="/config/www/snapshots"
mkdir -p "$OUTPUT_DIR"

CAMARAS="salon:BF1659630 mirilla:BF3289406"

for entry in $CAMARAS; do
    NAME=$(echo $entry | cut -d: -f1)
    SERIAL=$(echo $entry | cut -d: -f2)
    echo "🔍 Procesando $NAME ($SERIAL)..."

    SNAP_URL="https://open.ezvizlife.com/api/lapp/device/capture"
    SNAP_JSON=$(curl -s -X POST "$SNAP_URL" \
        -d "accessToken=$TOKEN" \
        -d "deviceSerial=$SERIAL" \
        -d "channelNo=1")

    PIC_URL=$(echo $SNAP_JSON | jq -r '.data.picUrl // empty')

    if [ -n "$PIC_URL" ]; then
        FILENAME="$OUTPUT_DIR/snapshot_${NAME}_${NOW}.jpg"
        curl -s "$PIC_URL" -o "$FILENAME"
        echo "✅ Guardado $FILENAME"
    else
        echo "❌ No se pudo obtener snapshot de $NAME"
        echo "$SNAP_JSON"
    fi
done
