$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONUTF8 = '1'
$python = Join-Path $root '.venv\Scripts\python.exe'
$transcript = $false
try {
    if (-not (Test-Path -LiteralPath $python)) { throw 'Run 01_install_windows.cmd first.' }
    Add-Type -AssemblyName System.Windows.Forms
    $picker = New-Object System.Windows.Forms.OpenFileDialog
    $picker.Title = 'Pixel3MF - Select existing pixel art (not an ordinary photo)'
    $picker.Filter = 'Images (*.png;*.jpg;*.jpeg;*.webp)|*.png;*.jpg;*.jpeg;*.webp'
    if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        $picker.Dispose()
        Write-Host 'Cancelled. No conversion was started.'
        exit 0
    }
    $source = $picker.FileName
    $picker.Dispose()
    Write-Host 'Pixel3MF: existing pixel-art pipeline; source grid checks still apply.'
    Write-Host 'Choose foreground model: 1 = anime (default), 2 = general subjects'
    $choice = Read-Host 'Enter 1 or 2'
    $model = 'auto'
    if ($choice -eq '2') { $model = 'isnet-general-use' }
    elseif ($choice -ne '' -and $choice -ne '1') { throw 'Please enter 1 or 2.' }
    $logDir = Join-Path $root 'output\launcher'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $log = Join-Path $logDir ("convert-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    Start-Transcript -Path $log | Out-Null
    $transcript = $true
    Write-Host "Source: $source"
    Write-Host 'Converting... Do not close this window. First use downloads model weights.'
    & $python (Join-Path $root 'tools\run_pipeline.py') --source-image $source --official-character-research-status not_applicable --background-model $model
    if ($LASTEXITCODE -ne 0) { throw "Conversion failed. See $log and the latest output folder's manifest.json." }
    Write-Host 'Done. Open the newest run folder in output and use the 08_*.3mf files.' -ForegroundColor Green
    Invoke-Item -LiteralPath (Join-Path $root 'output')
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
} finally {
    if ($transcript) { Stop-Transcript | Out-Null }
}
