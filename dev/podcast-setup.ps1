# Podcast TTS Setup Script
# Run this in PowerShell: .\podcast-setup.ps1

$ErrorActionPreference = "Stop"

$VENV_DIR = "C:\Users\ethan\.openclaw\workspace\podcast-env"
$WORKSPACE = "C:\Users\ethan\.openclaw\workspace"

Write-Host "=== Bark Podcast TTS Setup ===" -ForegroundColor Cyan

# Check for Python 3.11
$python311 = $null
try {
    $python311 = (py -3.11 --version 2>&1)
    Write-Host "[OK] Python 3.11 found: $python311" -ForegroundColor Green
} catch {
    Write-Host "[INFO] Python 3.11 not installed via py launcher." -ForegroundColor Yellow
    Write-Host "[INFO] Downloading Python 3.11.12..." -ForegroundColor Cyan
    $installer = "$env:TEMP\python-3.11.12-amd64.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.12/python-3.11.12-amd64.exe" -OutFile $installer -UseBasicParsing
    Write-Host "[OK] Installer downloaded." -ForegroundColor Green
    Write-Host "[INFO] Running installer (may open a window)..." -ForegroundColor Yellow
    Start-Process $installer -Wait -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1"
    Remove-Item $installer -Force
    Write-Host "[OK] Python 3.11 installed." -ForegroundColor Green
}

# Create venv
Write-Host "[INFO] Creating virtual environment at $VENV_DIR..." -ForegroundColor Cyan
py -3.11 -m venv $VENV_DIR
Write-Host "[OK] Virtual environment created." -ForegroundColor Green

# Activate and upgrade pip
Write-Host "[INFO] Upgrading pip..." -ForegroundColor Cyan
& "$VENV_DIR\Scripts\python.exe" -m pip install --upgrade pip

# Install PyTorch (CPU for now — CUDA optional)
Write-Host "[INFO] Installing PyTorch..." -ForegroundColor Cyan
& "$VENV_DIR\Scripts\pip.exe" install torch --index-url https://download.pytorch.org/whl/cpu

# Install Bark
Write-Host "[INFO] Installing bark..." -ForegroundColor Cyan
& "$VENV_DIR\Scripts\pip.exe" install bark

# Install audio tools
Write-Host "[INFO] Installing audio processing tools..." -ForegroundColor Cyan
& "$VENV_DIR\Scripts\pip.exe" install scipy soundfile pydub

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host "Activate the environment with: $VENV_DIR\Scripts\activate" -ForegroundColor Cyan
Write-Host "Test bark with: python -c 'from bark import generateAudio; print(\"Bark works!\")'" -ForegroundColor Cyan
