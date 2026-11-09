# PrintBridge Agent tek dosya .exe üretimi (PyInstaller).
#
# Kullanım (depo kökünden):
#   powershell -ExecutionPolicy Bypass -File tools\build_agent.ps1
#   powershell -ExecutionPolicy Bypass -File tools\build_agent.ps1 -Console   # hata ayıklama
#
# Çıktı: dist\PrintBridge-Agent.exe

param(
    [switch]$Console,
    [switch]$SkipIcon,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '==> Bağımlılık kontrolü' -ForegroundColor Cyan
py -3 -c "import PyInstaller, pystray, uvicorn, fastapi, pypdfium2" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'Eksik bağımlılık. Önce: py -3 -m pip install -r requirements.txt'
}

if (-not $SkipIcon) {
    Write-Host '==> Simge üretiliyor' -ForegroundColor Cyan
    py -3 tools\make_icon.py
    if ($LASTEXITCODE -ne 0) { throw 'Simge üretilemedi.' }
}

if (-not $SkipTests) {
    Write-Host '==> Testler' -ForegroundColor Cyan
    py -3 -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Testler başarısız; paketleme durduruldu.' }
}

Write-Host '==> PyInstaller' -ForegroundColor Cyan
$windowMode = if ($Console) { '--console' } else { '--noconsole' }
$arguments = @(
    '-m', 'PyInstaller',
    '--noconfirm', '--clean', '--onefile',
    $windowMode,
    '--name', 'PrintBridge-Agent',
    '--icon', 'agent\assets\printbridge.ico',
    '--collect-all', 'pypdfium2',
    '--collect-all', 'pillow_heif',
    '--collect-submodules', 'uvicorn',
    '--collect-submodules', 'pystray',
    '--collect-submodules', 'zeroconf',
    '--collect-submodules', 'segno',
    '--hidden-import', 'win32timezone',
    'agent_entry.py'
)

py -3 @arguments
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller başarısız.' }

$exe = Join-Path $root 'dist\PrintBridge-Agent.exe'
if (-not (Test-Path $exe)) { throw "Çıktı bulunamadı: $exe" }

$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ''
Write-Host "Hazır: $exe ($sizeMb MB)" -ForegroundColor Green
Write-Host 'İlk çalıştırma: dist\PrintBridge-Agent.exe'
