$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$appName = -join ([char[]](0x91cd, 0x547d, 0x540d, 0x5de5, 0x5177))
$distDir = Join-Path $PSScriptRoot "dist"
$oldOneFolder = Join-Path $distDir $appName
$oneFile = Join-Path $distDir "$appName.exe"

if (Test-Path -LiteralPath $oldOneFolder) {
  Remove-Item -LiteralPath $oldOneFolder -Recurse -Force
}

if (Test-Path -LiteralPath $oneFile) {
  Remove-Item -LiteralPath $oneFile -Force
}

python -m PyInstaller `
  --name $appName `
  --onefile `
  --windowed `
  --noconfirm `
  --clean `
  --paths "." `
  main.py

Write-Host ""
Write-Host "Build complete: $PSScriptRoot\dist\$appName.exe"
