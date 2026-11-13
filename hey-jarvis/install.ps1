# Hey Jarvis installer for Windows. Run in PowerShell:
#   irm https://raw.githubusercontent.com/alikamal94/alikamal94/claude/funny-shannon-6zt71u/hey-jarvis/install.ps1 | iex
$ErrorActionPreference = 'Stop'

$Raw    = 'https://raw.githubusercontent.com/alikamal94/alikamal94/claude/funny-shannon-6zt71u/hey-jarvis'
$Root   = if ($env:OPENJARVIS_HOME) { $env:OPENJARVIS_HOME } else { Join-Path $env:LOCALAPPDATA 'OpenJarvis' }
$Py     = Join-Path $Root 'src\.venv\Scripts\python.exe'
$PyW    = Join-Path $Root 'src\.venv\Scripts\pythonw.exe'
$AppDir = Join-Path $Root 'hey-jarvis'
$env:Path = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:Path"

function Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }

# 1. OpenJarvis itself (skipped if already installed)
if (-not (Test-Path $Py)) {
    Step 'Installing OpenJarvis (about 3 minutes)...'
    Invoke-RestMethod https://open-jarvis.github.io/OpenJarvis/install.ps1 | Invoke-Expression
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:Path
}
if (-not (Test-Path $Py)) { throw "OpenJarvis did not install to $Root. Fix that first, then re-run." }

# 2. Wake word + speech recognition into the OpenJarvis environment
Step 'Installing wake word and speech recognition...'
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = Join-Path $env:USERPROFILE '.local\bin\uv.exe' }
& $uv pip install --python $Py 'openwakeword==0.4.0' 'faster-whisper>=1.0' 'av>=11,<19' `
    'sounddevice>=0.5' 'soundfile>=0.12' 'numpy>=1.24'
if ($LASTEXITCODE -ne 0) { throw 'Package install failed.' }

# 3. The listener script
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
Invoke-WebRequest "$Raw/jarvis_wake.py" -OutFile (Join-Path $AppDir 'jarvis_wake.py') -UseBasicParsing

# 4. Download the speech model now so the first "Hey Jarvis" is instant
Step 'Downloading speech model and checking everything loads...'
& $Py (Join-Path $AppDir 'jarvis_wake.py') --check
if ($LASTEXITCODE -ne 0) { throw 'Self-check failed; see the messages above.' }

# 5. Start automatically at login (hidden, no window)
$startup  = [Environment]::GetFolderPath('Startup')
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $startup 'Hey Jarvis.lnk'))
$shortcut.TargetPath       = $PyW
$shortcut.Arguments        = '"' + (Join-Path $AppDir 'jarvis_wake.py') + '"'
$shortcut.WorkingDirectory = $AppDir
$shortcut.Save()

Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -like '*jarvis_wake.py*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Process -FilePath $PyW -ArgumentList ('"' + (Join-Path $AppDir 'jarvis_wake.py') + '"') -WorkingDirectory $AppDir

Step 'Done! Say "Hey Jarvis", wait for the chime, then ask your question.'
Write-Host "Log: $Root\hey-jarvis.log"
