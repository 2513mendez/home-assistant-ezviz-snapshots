# build-push.ps1 (modo local para HA Green)
# 🧱 Compila localmente, actualiza version y genera release.yaml (sin subir a Docker Hub)

$version = "1.2.2"
$configFile = "config.json"
$releaseFile = "release.yaml"

Write-Host "`n🧹 Preparando entorno para build local (HA Green / aarch64)" -ForegroundColor Yellow

# 🔧 Actualizar config.json (solo la versión)
if (Test-Path $configFile) {
    $json = Get-Content $configFile | ConvertFrom-Json

    # Eliminar el campo image si existe
    if ($json.PSObject.Properties.Name -contains "image") {
        $json.PSObject.Properties.Remove("image")
        Write-Host "🧨 Campo 'image' eliminado de config.json" -ForegroundColor Gray
    }

    $json.version = $version
    $json | ConvertTo-Json -Depth 10 | Out-File $configFile -Encoding utf8
    Write-Host "✅ config.json actualizado con version $version" -ForegroundColor Green
} else {
    Write-Host "❌ No se encontró config.json. Abortando." -ForegroundColor Red
    exit 1
}

# 📝 Crear release.yaml
Write-Host "`n📦 Generando release.yaml..." -ForegroundColor Cyan

@"
version: "$version"
"@ | Out-File $releaseFile -Encoding utf8

Write-Host "✅ release.yaml generado correctamente" -ForegroundColor Green

# ✅ Final
Write-Host "`n🎯 Listo para commit y build local desde Home Assistant" -ForegroundColor Cyan
Write-Host "Recuerda: git add, commit y push cuando termines." -ForegroundColor Gray
