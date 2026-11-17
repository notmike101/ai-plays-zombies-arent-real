param(
    [int]$Port = 8765,
    [switch]$Preview,
    [string]$Python = (Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe')
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python)) {
    throw 'Repository .venv was not found. Follow README.md setup, or supply -Python with a prepared interpreter.'
}
$arguments = @('-B', (Join-Path $PSScriptRoot 'server.py'), '--host', '0.0.0.0', '--port', "$Port")
if ($Preview) { $arguments += '--preview' }
& $Python @arguments
