param(
    [string]$OutputFolder = 'C:\ControleVendas\Utils'
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$distributionFolder = $OutputFolder
$icon = Join-Path $projectRoot 'assets\firebird-maintenance-studio.ico'

Push-Location $projectRoot
try {
    python -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name FirebirdMaintenanceStudioPortable `
        --icon $icon `
        --add-data 'assets;assets' `
        --paths . `
        --runtime-hook qt_runtime_hook.py `
        --collect-submodules firebird `
        --collect-submodules fdb `
        --collect-submodules keyring `
        run_app.py

    New-Item -ItemType Directory -Force -Path $distributionFolder | Out-Null
    $builtExecutable = Join-Path $projectRoot 'dist\FirebirdMaintenanceStudioPortable.exe'
    Copy-Item -LiteralPath $builtExecutable -Destination (Join-Path $distributionFolder 'FirebirdMaintenanceStudio.exe') -Force

    Write-Host "Executáveis atualizados em: $distributionFolder"
    Get-ChildItem $distributionFolder -Filter '*.exe' |
        Select-Object Name, Length, LastWriteTime
}
finally {
    Pop-Location
}
