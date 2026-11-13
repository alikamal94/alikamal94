# ORB NY EA installer for MetaTrader 5 (Windows)
# Copies ORB_NY_EA.mq5 into every MT5 terminal's MQL5\Experts folder and compiles it with MetaEditor.
$ErrorActionPreference = 'Stop'

$src = Join-Path $PSScriptRoot 'ORB_NY_EA.mq5'
if (-not (Test-Path $src)) {
    Write-Host "ORB_NY_EA.mq5 was not found. Put it in the same folder as this installer." -ForegroundColor Red
    Read-Host "Press Enter to close"; exit 1
}

$root = Join-Path $env:APPDATA 'MetaQuotes\Terminal'
$terminals = Get-ChildItem $root -Directory -ErrorAction SilentlyContinue |
             Where-Object { Test-Path (Join-Path $_.FullName 'MQL5\Experts') }
if (-not $terminals) {
    Write-Host "No MetaTrader 5 data folder found. Open MT5 at least once, then run this again." -ForegroundColor Red
    Read-Host "Press Enter to close"; exit 1
}

foreach ($t in $terminals) {
    $experts = Join-Path $t.FullName 'MQL5\Experts'
    $dest    = Join-Path $experts 'ORB_NY_EA.mq5'
    Copy-Item $src $dest -Force
    Write-Host "Copied to $experts" -ForegroundColor Cyan

    # origin.txt holds the MT5 install folder (where metaeditor64.exe lives)
    $origin = Join-Path $t.FullName 'origin.txt'
    if (-not (Test-Path $origin)) { Write-Host "  Could not find the MT5 install folder - compile it in MetaEditor (F7)."; continue }
    $install = (Get-Content $origin -Raw -Encoding Unicode).Trim()
    $editor  = Join-Path $install 'metaeditor64.exe'
    if (-not (Test-Path $editor)) { Write-Host "  metaeditor64.exe not found in $install - compile it in MetaEditor (F7)."; continue }

    $log = Join-Path $experts 'ORB_NY_EA.compile.log'
    Start-Process -FilePath $editor -ArgumentList "/compile:`"$dest`"", "/log:`"$log`"" -Wait
    if (Test-Path (Join-Path $experts 'ORB_NY_EA.ex5')) {
        Write-Host "  Compiled OK for $install" -ForegroundColor Green
    } else {
        Write-Host "  Compile failed. Errors:" -ForegroundColor Red
        if (Test-Path $log) { Get-Content $log -Encoding Unicode | Select-String -Pattern 'error' | ForEach-Object { "   $_" } }
        Write-Host "  Send these errors (or $log) to Claude."
    }
}

Write-Host ""
Write-Host "Done. In MT5: Navigator > Expert Advisors > right-click > Refresh, then drag ORB_NY_EA onto your chart." -ForegroundColor Green
Read-Host "Press Enter to close"
