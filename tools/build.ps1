$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        throw 'Create .venv and install requirements-build.txt first; see README.md.'
    }
    & $pythonExe -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    # onedir keeps each HID worker in one process, allowing a timeout to stop it.
    # Keep _internal alongside the EXE; the ZIP is the portable distribution.
    & $pythonExe -m PyInstaller --noconfirm --clean --onedir --windowed --name K621StaticColor app.py
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    Copy-Item -LiteralPath README.md -Destination dist\K621StaticColor\README.md
    Copy-Item -LiteralPath docs -Destination dist\K621StaticColor\docs -Recurse -Force
    Compress-Archive -Path dist\K621StaticColor -DestinationPath dist\K621StaticColor-portable.zip -Force
    $appVersion = & $pythonExe -c "from k621_rgb import __version__; print(__version__)"
    if ($LASTEXITCODE -ne 0) { throw 'Could not read application version.' }
    Copy-Item -LiteralPath dist\K621StaticColor-portable.zip -Destination "dist\K621StaticColor-$appVersion-portable.zip" -Force
    Get-FileHash -LiteralPath dist\K621StaticColor-portable.zip -Algorithm SHA256
} finally {
    Pop-Location
}
