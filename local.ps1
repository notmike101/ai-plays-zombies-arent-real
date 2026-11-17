# Use the repository environment explicitly; activation and PATH are irrelevant.
$ErrorActionPreference = 'Stop'
$zarPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $zarPython)) {
    throw 'Repository .venv is missing. Follow the setup commands in README.md before running this tool.'
}
& $zarPython -B (Join-Path $PSScriptRoot 'scripts/local_agent.py') @args
exit $LASTEXITCODE
