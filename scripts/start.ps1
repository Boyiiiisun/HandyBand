$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
try {
    $uv = Join-Path (Get-Location) '.tools\uv.exe'
    if (-not (Test-Path -LiteralPath $uv)) {
        Write-Host 'Preparing HandyBand (first launch requires internet)...'
        $env:UV_UNMANAGED_INSTALL = Join-Path (Get-Location) '.tools'
        Invoke-RestMethod 'https://astral.sh/uv/0.12.17/install.ps1' | Invoke-Expression
    }
    & $uv run --locked python scripts/download_models.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $uv run --locked python -m handyband @args
    exit $LASTEXITCODE
} catch {
    Write-Host "HandyBand could not start: $_" -ForegroundColor Red
    exit 1
}
