# Windows PowerShell 5.1 and PowerShell 7; no administrator privileges required.
$ErrorActionPreference = 'Stop'
$bootstrap = Join-Path $PSScriptRoot 'bootstrap.py'
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $bootstrap @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $bootstrap @args
} else {
    throw 'Install Python 3.12 or newer and Git, then rerun this script.'
}
exit $LASTEXITCODE
