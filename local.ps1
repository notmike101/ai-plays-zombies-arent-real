# Entry point for this computer's existing, tested Python environment.
$ErrorActionPreference = 'Stop'
$zarPython = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"
if (-not (Test-Path -LiteralPath $zarPython)) {
    throw 'Known Python is missing. Read notes/local-environment.md; do not reinstall or start random training.'
}
& $zarPython -B (Join-Path $PSScriptRoot 'scripts/local_agent.py') @args
exit $LASTEXITCODE
