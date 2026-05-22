$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$modelCache = Join-Path $root 'docker\volumes\local-models\huggingface'
$outLog = Join-Path $root 'docker\volumes\local-models\server.out.log'
$errLog = Join-Path $root 'docker\volumes\local-models\server.err.log'

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outLog) | Out-Null

$existing = Get-NetTCPConnection -LocalPort 8008 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    $existing | Select-Object LocalAddress, LocalPort, OwningProcess
    return
}

$env:HF_HOME = $modelCache
$env:LOCAL_MODELS_CACHE_ROOT = $modelCache
$env:LOCAL_MODELS_API_KEY = 'local-dify-models'

Start-Process `
    -FilePath python `
    -ArgumentList @('-m', 'uvicorn', 'server:app', '--host', '0.0.0.0', '--port', '8008') `
    -WorkingDirectory $PSScriptRoot `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru |
    Select-Object Id, ProcessName
