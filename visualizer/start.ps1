param(
    [int]$Port = 8765,
    [switch]$Preview,
    [string]$Python = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python)) {
    throw 'Python was not found. Supply -Python with the full path to your PyTorch Python executable.'
}
$arguments = @('-B', (Join-Path $PSScriptRoot 'server.py'), '--host', '0.0.0.0', '--port', "$Port")
if ($Preview) { $arguments += '--preview' }
& $Python @arguments
