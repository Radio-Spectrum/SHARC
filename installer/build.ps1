<#
  Builds the SHARC Windows installer.
  Usage: powershell -ExecutionPolicy Bypass -File installer\build.ps1 [-Version 1.0.0] [-SkipFreeze]
  Needs: Python with the project requirements + pyinstaller + pillow, and Inno Setup 6 (ISCC.exe).
#>
param(
    [string]$Version = "1.0.0",
    [switch]$SkipFreeze
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$build = Join-Path $here "build"

function Step($t) { Write-Host "`n== $t" -ForegroundColor Cyan }

Step "Brand assets"
python (Join-Path $here "make_assets.py")
if ($LASTEXITCODE) { throw "make_assets failed" }

Step "Build info (read by the in-app updater)"
Push-Location $root
$commit = (git rev-parse HEAD).Trim()
$branch = (git branch --show-current).Trim()
$repo = ((git remote get-url origin).Trim() -replace '^.*github\.com[:/]', '' -replace '\.git$', '')
if (git status --porcelain --untracked-files=no) { Write-Warning "Tracked files have uncommitted changes: the build will not match commit $commit." }
Pop-Location
[ordered]@{
    repo = $repo; branch = $branch; tag = "v$Version-$branch"; commit = $commit
    version = $Version; built_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
} | ConvertTo-Json | Set-Content (Join-Path $root "sharc\build_info.json") -Encoding UTF8
Get-Content (Join-Path $root "sharc\build_info.json")

if (-not $SkipFreeze) {
    Step "PyInstaller (onedir)"
    python -m PyInstaller (Join-Path $here "sharc.spec") --noconfirm `
        --distpath (Join-Path $build "frozen") --workpath (Join-Path $build "work")
    if ($LASTEXITCODE) { throw "PyInstaller failed" }
}
$exe = Join-Path $build "frozen\SHARC\SHARC.exe"
if (-not (Test-Path $exe)) { throw "Missing $exe" }

Step "Examples"
$examples = Join-Path $build "examples"
if (Test-Path $examples) { Remove-Item $examples -Recurse -Force }
New-Item -ItemType Directory -Path $examples | Out-Null
Push-Location $root
git ls-files "sharc/campaigns/IMT_TO_SES_Database" | ForEach-Object {
    $rel = $_.Substring("sharc/campaigns/IMT_TO_SES_Database/".Length)
    $dst = Join-Path $examples $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
    Copy-Item $_ $dst
}
Pop-Location

Step "VC++ runtime"
$redist = Join-Path $here "redist\vc_redist.x64.exe"
if (-not (Test-Path $redist)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $redist) | Out-Null
    Invoke-WebRequest "https://aka.ms/vs/17/release/vc_redist.x64.exe" -OutFile $redist
}

Step "Inno Setup"
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
          "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "ISCC.exe not found. Install: winget install JRSoftware.InnoSetup" }
& $iscc "/DAppVersion=$Version" "/DSourceDir=$(Join-Path $build 'frozen\SHARC')" `
    "/DExamplesDir=$examples" "/DOutputDir=$(Join-Path $build 'out')" (Join-Path $here "sharc.iss")
if ($LASTEXITCODE) { throw "ISCC failed" }
Write-Host "`nInstaller: $(Join-Path $build "out\SHARC-$Version-Setup-x64.exe")" -ForegroundColor Green
