# build-push.ps1
# 🛠️ Compila, sube, actualiza y prepara todo el entorno de add-on para Home Assistant

$imagen = "vmn2513/addon1"
$version = "1.0.0"
$nombreCompleto = "$imagen`:$version"
$configFile = "config.json"
$releaseFile = "release.yaml"

Write-Host "`n🚧 Compilando imagen local: $nombreCompleto" -ForegroundColor Yellow

docker build -t $nombreCompleto .

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al compilar la imagen. Abortando." -ForegroundColor Red
    exit 1
}

Write-Host "`n📤 Subiendo imagen a Docker Hub..." -ForegroundColor Cyan

docker push $nombreCompleto

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al hacer push de la imagen. Revisa tu login de Docker." -ForegroundColor Red
    exit 1
}

Write-Host "`n📝 Actualizando config.json con versión $version..." -ForegroundColor Blue

if (Test-Path $configFile) {
    $json = Get-Content $configFile | ConvertFrom-Json
    $json.version = $version
    $json | ConvertTo-Json -Depth 10 | Out-File $configFile -Encoding utf8
    Write-Host "✅ config.json actualizado." -ForegroundColor Green
} else {
    Write-Host "❌ No se encontró config.json. No se pudo actualizar la versión." -ForegroundColor Red
}

# 🕵️‍♂️ Verificar existencia en Docker Hub
Write-Host "`n🔎 Verificando imagen en Docker Hub..." -ForegroundColor Gray
$response = Invoke-WebRequest -Uri "https://hub.docker.com/v2/repositories/$imagen/tags/$version" -UseBasicParsing -ErrorAction SilentlyContinue

if ($response.StatusCode -eq 200) {
    Write-Host "✅ Imagen confirmada en Docker Hub." -ForegroundColor Green
} else {
    Write-Host "⚠️  No se pudo verificar la existencia de la imagen en Docker Hub." -ForegroundColor DarkYellow
}

# 📦 Crear release.yaml
Write-Host "`n📦 Generando release.yaml para repositorio Home Assistant..." -ForegroundColor Magenta

@"
version: "$version"
image: "$imagen"
"@ | Out-File $releaseFile -Encoding utf8

Write-Host "✅ Archivo $releaseFile creado." -ForegroundColor Green

# ✅ Instrucciones finales
Write-Host "`n🎉 Todo listo. Pasos siguientes sugeridos:" -ForegroundColor Cyan
Write-Host "1️⃣  Añade release.yaml a tu repo GitHub si usas releases por versión"
Write-Host "2️⃣  Asegúrate de que repository.json apunta al repositorio correcto"
Write-Host "3️⃣  Prueba el add-on desde Home Assistant → Configuración → Add-ons → Repositorios personalizados"
Write-Host "4️⃣  Usa como URL: https://github.com/2513mendez/home-assistant-ezviz-snapshots"
Write-Host "`n🚀 ¡A disfrutar del poder de EZVIZ + Home Assistant, chef!" -ForegroundColor Yellow
