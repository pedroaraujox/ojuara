$ErrorActionPreference = "Stop"

$raizOjuara = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $raizOjuara ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Ambiente Python nao encontrado: $python"
}

Set-Location -LiteralPath $raizOjuara
& $python (Join-Path $raizOjuara "scripts\backup_sqlite.py")
