$ErrorActionPreference = 'Stop'

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python 3.10 or newer is required. Install Python, then run this installer again.'
}

& python (Join-Path $PSScriptRoot 'scripts\install_skill.py')
if ($LASTEXITCODE -ne 0) {
    throw "Skill installation failed (Python exit code $LASTEXITCODE)."
}
