# ============================================================
#  Stacka Clipboard — build the MSIX package for the Microsoft Store
# ============================================================
#  Run the PyInstaller build FIRST:
#
#    python -m PyInstaller --name Stacka --icon assets\stacka.ico `
#           --add-data "assets;assets" --windowed --noconfirm src\main.py
#
#  Then:  .\build_msix.ps1
#
#  Produces:  msix_output\StackaClipboard.msix
#
#  The package is left UNSIGNED on purpose. The Store re-signs it during
#  certification — that is what makes this the zero-cost route to a signed,
#  SmartScreen-clean build. (An unsigned .msix cannot be installed locally;
#  to test on this machine, sign it with a self-signed certificate first.)
# ============================================================

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$dist    = Join-Path $root "dist\Stacka"
$staging = Join-Path $root "msix_staging"
$outDir  = Join-Path $root "msix_output"
$outFile = Join-Path $outDir "StackaClipboard.msix"

# --- 1. Check the app has been built ------------------------------------
if (-not (Test-Path (Join-Path $dist "Stacka.exe"))) {
    Write-Host "dist\Stacka\Stacka.exe not found. Run the PyInstaller build first." -ForegroundColor Red
    exit 1
}

# --- 2. Locate makeappx.exe from the Windows SDK -------------------------
$makeappx = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Recurse `
                -Filter "makeappx.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -like "*\x64\*" } |
            Sort-Object FullName -Descending |
            Select-Object -First 1

if ($null -eq $makeappx) {
    Write-Host "makeappx.exe not found." -ForegroundColor Red
    Write-Host "Install the Windows 10/11 SDK (the 'Windows SDK Signing Tools' component is enough):"
    Write-Host "  https://developer.microsoft.com/windows/downloads/windows-sdk/"
    Write-Host "Alternative: the free MSIX Packaging Tool from the Microsoft Store."
    exit 1
}
Write-Host "makeappx : $($makeappx.FullName)" -ForegroundColor DarkGray

# --- 3. Stage the package layout ----------------------------------------
# Layout:  Stacka.exe + _internal\  +  AppxManifest.xml  +  Assets\
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging -Force | Out-Null

Copy-Item (Join-Path $dist "*") $staging -Recurse -Force
Copy-Item (Join-Path $root "msix\AppxManifest.xml") $staging -Force

$assetsDst = Join-Path $staging "Assets"
New-Item -ItemType Directory -Path $assetsDst -Force | Out-Null
Copy-Item (Join-Path $root "assets\msix\*.png") $assetsDst -Force

Write-Host "staged   : $staging" -ForegroundColor DarkGray

# --- 4. Pack -------------------------------------------------------------
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
if (Test-Path $outFile) { Remove-Item $outFile -Force }

& $makeappx.FullName pack /d $staging /p $outFile /o
if ($LASTEXITCODE -ne 0) {
    Write-Host "makeappx failed (exit $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}

$sizeMb = [math]::Round((Get-Item $outFile).Length / 1MB, 1)
Write-Host ""
Write-Host "Built $outFile ($sizeMb MB)" -ForegroundColor Green
Write-Host "Upload this file in Partner Center. The Store signs it during certification."
