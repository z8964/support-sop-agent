$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-Checked {
  param(
    [Parameter(Mandatory = $true)]
    [ScriptBlock]$Command
  )
  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code $LASTEXITCODE"
  }
}

Write-Host "Installing backend dependencies..."
Invoke-Checked { py -3.12 -m pip install -r apps/api/requirements.txt }

Write-Host "Installing PyInstaller..."
Invoke-Checked { py -3.12 -m pip install pyinstaller }

Write-Host "Building Windows executable..."
Invoke-Checked {
  py -3.12 -m PyInstaller `
    --clean `
    --noconfirm `
    --onefile `
    --name support-sop-agent `
    --paths apps/api `
    --add-data "knowledge_base;knowledge_base" `
    --add-binary "E:\Anaconda\Library\bin\libexpat.dll;." `
    --add-binary "E:\Anaconda\Library\bin\libssl-3-x64.dll;." `
    --add-binary "E:\Anaconda\Library\bin\libcrypto-3-x64.dll;." `
    --add-binary "E:\Anaconda\Library\bin\ffi.dll;." `
    --add-binary "E:\Anaconda\Library\bin\liblzma.dll;." `
    --add-binary "E:\Anaconda\Library\bin\LIBBZ2.dll;." `
    --add-binary "E:\Anaconda\Library\bin\sqlite3.dll;." `
    --add-binary "E:\Anaconda\Library\bin\yaml.dll;." `
    --add-binary "E:\Anaconda\Library\bin\zstd.dll;." `
    --exclude-module IPython `
    --exclude-module matplotlib `
    --exclude-module numpy `
    --exclude-module pandas `
    --exclude-module PIL `
    --exclude-module PyQt5 `
    --exclude-module zmq `
    --exclude-module paramiko `
    --exclude-module nacl `
    --exclude-module bcrypt `
    --exclude-module langgraph `
    --exclude-module langchain `
    --exclude-module langchain_core `
    --exclude-module langchain_protocol `
    --exclude-module langsmith `
    --exclude-module psutil `
    --exclude-module requests `
    --exclude-module requests_toolbelt `
    --exclude-module scipy `
    --exclude-module sphinx `
    --exclude-module pytest `
    --exclude-module tkinter `
    packaging/windows_launcher.py
}

Write-Host ""
Write-Host "Build complete:"
Write-Host "$Root\dist\support-sop-agent.exe"

$LiteZip = Join-Path $Root "dist\support-sop-agent-v0.1.1-windows-x64-lite.zip"
Compress-Archive -Path "$Root\dist\support-sop-agent.exe" -DestinationPath $LiteZip -Force
Write-Host "Lite package:"
Write-Host $LiteZip
