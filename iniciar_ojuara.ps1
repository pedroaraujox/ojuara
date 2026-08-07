$ErrorActionPreference = "Stop"

$raizOjuara = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $raizOjuara ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Ambiente Python nao encontrado: $python"
}

$env:OJUARA_AMBIENTE = "producao"
$env:OJUARA_SEED = "0"
$env:OJUARA_DATABASE = Join-Path $raizOjuara "data\ojuara.db"

$ambienteUsuario = Get-ItemProperty -LiteralPath "HKCU:\Environment"
foreach ($nome in @("OJUARA_SECRET_KEY", "OJUARA_SUPERADMIN", "OJUARA_SUPERADMIN_SENHA")) {
    $valor = $ambienteUsuario.$nome
    if (-not [string]::IsNullOrWhiteSpace($valor)) {
        [Environment]::SetEnvironmentVariable($nome, $valor, "Process")
    }
}

$codigoOjuara = $ambienteUsuario.OJUARA_APP_DIR
if ([string]::IsNullOrWhiteSpace($codigoOjuara)) {
    $codigoOjuara = $raizOjuara
}
$servidor = Join-Path $codigoOjuara "servidor_producao.py"
if (-not (Test-Path -LiteralPath $servidor)) {
    throw "Codigo de producao nao encontrado: $servidor"
}

if ([string]::IsNullOrWhiteSpace($env:OJUARA_SECRET_KEY)) {
    throw "OJUARA_SECRET_KEY nao esta configurada no ambiente do Windows."
}
if ([string]::IsNullOrWhiteSpace($env:OJUARA_SUPERADMIN_SENHA)) {
    throw "OJUARA_SUPERADMIN_SENHA nao esta configurada no ambiente do Windows."
}

Set-Location -LiteralPath $codigoOjuara
& $python $servidor
