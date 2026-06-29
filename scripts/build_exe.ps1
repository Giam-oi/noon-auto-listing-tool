param(
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

& $Python -m pip install -r requirements.txt
& $Python -m PyInstaller .\packaging\noon_listing_tool.spec --clean --noconfirm

Write-Host "Built dist\NoonListingTool\NoonListingTool.exe"
