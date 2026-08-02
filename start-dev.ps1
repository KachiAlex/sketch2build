# Sketch2Build - Start all local services
# Run: powershell -ExecutionPolicy Bypass -File start-dev.ps1

Write-Host "Starting Sketch2Build local environment..." -ForegroundColor Cyan

# 1. Redis
if ((Get-NetTCPConnection -State Listen -LocalPort 6379 -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
    Write-Host "  Starting Redis..." -ForegroundColor Yellow
    Start-Process -FilePath "C:\Redis\redis-server.exe" -ArgumentList "--port","6379" -WindowStyle Hidden
} else { Write-Host "  Redis already running" -ForegroundColor Green }

# 2. MinIO
if ((Get-NetTCPConnection -State Listen -LocalPort 9000 -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
    Write-Host "  Starting MinIO..." -ForegroundColor Yellow
    $env:MINIO_ROOT_USER = "sketch2build"
    $env:MINIO_ROOT_PASSWORD = "sketch2build"
    Start-Process -FilePath "C:\MinIO\minio.exe" -ArgumentList "server","C:\MinIO\data","--console-address",":9001" -WindowStyle Hidden
} else { Write-Host "  MinIO already running" -ForegroundColor Green }

# Wait for infra
Start-Sleep -Seconds 2

# 3. API
if ((Get-NetTCPConnection -State Listen -LocalPort 3000 -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
    Write-Host "  Starting API Gateway..." -ForegroundColor Yellow
    Start-Process -FilePath "powershell" -ArgumentList "-WindowStyle","Hidden","-Command","npm run dev -w apps/api" -WorkingDirectory "c:\sketch2build"
} else { Write-Host "  API already running" -ForegroundColor Green }

# 4. AI Service
if ((Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
    Write-Host "  Starting AI Service..." -ForegroundColor Yellow
    Start-Process -FilePath "powershell" -ArgumentList "-WindowStyle","Hidden","-Command","py -3.11 -m uvicorn app.main:app --host 0.0.0.0 --port 8000" -WorkingDirectory "c:\sketch2build\apps\ai"
} else { Write-Host "  AI Service already running" -ForegroundColor Green }

# 5. Frontend
if ((Get-NetTCPConnection -State Listen -LocalPort 5173 -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
    Write-Host "  Starting Frontend..." -ForegroundColor Yellow
    Start-Process -FilePath "powershell" -ArgumentList "-WindowStyle","Hidden","-Command","npm run dev -w apps/web" -WorkingDirectory "c:\sketch2build"
} else { Write-Host "  Frontend already running" -ForegroundColor Green }

# Wait for apps to boot
Write-Host "  Waiting for services to boot..." -ForegroundColor Yellow
Start-Sleep -Seconds 6

# Status check
Write-Host "`n=== Service Status ===" -ForegroundColor Cyan
$services = @{
    "PostgreSQL" = 5432
    "Redis"      = 6379
    "MinIO"      = 9000
    "MinIO Console" = 9001
    "API Gateway" = 3000
    "AI Service"  = 8000
    "Frontend"    = 5173
}
foreach ($name in $services.Keys) {
    $port = $services[$name]
    $up = (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0
    if ($up) {
        Write-Host "  $name (:$port) - RUNNING" -ForegroundColor Green
    } else {
        Write-Host "  $name (:$port) - NOT RUNNING" -ForegroundColor Red
    }
}

Write-Host "`nFrontend: http://localhost:5173" -ForegroundColor Cyan
Write-Host "API: http://localhost:3000" -ForegroundColor Cyan
Write-Host "AI Service: http://localhost:8000" -ForegroundColor Cyan
Write-Host "MinIO Console: http://localhost:9001" -ForegroundColor Cyan
