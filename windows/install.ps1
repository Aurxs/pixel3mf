$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONUTF8 = '1'
$env:UV_CACHE_DIR = Join-Path $root '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $root '.windows-tools\python'
$logDir = Join-Path $root 'output\setup'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("install-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
Start-Transcript -Path $log | Out-Null
try {
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
        throw 'This package requires Windows x64 (Intel/AMD). ARM and 32-bit Windows are not supported by this installer.'
    }
    $downloads = Join-Path $root '.windows-tools\downloads'
    New-Item -ItemType Directory -Force -Path $downloads | Out-Null
    $uv = Join-Path $root '.windows-tools\uv\uv.exe'
    if (-not (Test-Path -LiteralPath $uv)) {
        Write-Host '[1/5] Downloading uv 0.10.7...'
        $uvZip = Join-Path $downloads 'uv.zip'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/astral-sh/uv/releases/download/0.10.7/uv-x86_64-pc-windows-msvc.zip' -OutFile $uvZip
        Expand-Archive -LiteralPath $uvZip -DestinationPath (Split-Path $uv) -Force
        if (-not (Test-Path -LiteralPath $uv)) { throw 'uv.exe was not found after extraction.' }
    }
    Write-Host '[2/5] Preparing Python 3.12...'
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if ((Test-Path -LiteralPath (Join-Path $root '.venv')) -and -not (Test-Path -LiteralPath $python)) {
        throw 'An incompatible .venv already exists. Rename it, then run this installer again.'
    }
    if (-not (Test-Path -LiteralPath $python)) {
        & $uv venv --python 3.12 --managed-python (Join-Path $root '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
    }
    Write-Host '[3/5] Preparing Lumina-Layers...'
    $revision = '8af9cdfd513fcde3d98c3e4de7bb36620942f51a'
    $lumina = Join-Path $root 'Lumina-Layers'
    $marker = Join-Path $lumina '.pixel3mf-revision'
    if (Test-Path -LiteralPath $lumina) {
        if (-not (Test-Path -LiteralPath $marker) -or (Get-Content -LiteralPath $marker -Raw).Trim() -ne $revision) {
            throw 'An unmanaged or different Lumina-Layers folder exists. Rename it before installation; it will not be overwritten.'
        }
    } else {
        $luminaZip = Join-Path $downloads 'lumina.zip'
        Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/lumina-layer-studio/Lumina-Layers/archive/$revision.zip" -OutFile $luminaZip
        $staging = Join-Path $downloads ('lumina-' + [guid]::NewGuid().ToString('N'))
        Expand-Archive -LiteralPath $luminaZip -DestinationPath $staging
        $extracted = Join-Path $staging "Lumina-Layers-$revision"
        if (-not (Test-Path -LiteralPath (Join-Path $extracted 'requirements.txt'))) { throw 'Lumina download is incomplete.' }
        Set-Content -LiteralPath (Join-Path $extracted '.pixel3mf-revision') -Value $revision -Encoding ASCII
        Move-Item -LiteralPath $extracted -Destination $lumina
    }
    Write-Host '[4/5] Installing dependencies (internet required)...'
    & $uv pip install --python $python -r (Join-Path $lumina 'requirements.txt') -r (Join-Path $root 'requirements-pixel3mf.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the network and retry.' }
    Write-Host '[5/5] Checking imports, LUT and nozzle settings...'
    & $python (Join-Path $root 'windows\check_environment.py')
    if ($LASTEXITCODE -ne 0) { throw 'Environment check failed.' }
    Write-Host 'Installation complete. Next: double-click 02_convert_image.cmd' -ForegroundColor Green
    Write-Host 'Model weights are downloaded on first conversion. Keep internet connected.'
} catch {
    Write-Host ("INSTALL FAILED: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host "Log: $log"
    exit 1
} finally {
    Stop-Transcript | Out-Null
}
