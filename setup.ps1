param(
    [string]$BasePython = "C:\Users\MOS3AD\miniconda3\envs\subway_rl\python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $BasePython)) {
    throw "CUDA Python was not found at $BasePython"
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating the Project 3 environment..."
    & $BasePython -m venv --system-site-packages (Join-Path $ProjectRoot ".venv")
}

Write-Host "Installing desktop and face-pose packages..."
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")

Write-Host "Downloading the pretrained YOLO11 detector..."
$ModelsDir = Join-Path $ProjectRoot "models"
New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
Push-Location $ModelsDir
try {
    & $VenvPython -c "from ultralytics import YOLO; YOLO('yolo11n.pt'); print('YOLO11 model ready')"
}
finally {
    Pop-Location
}

Write-Host "Checking CUDA and application imports..."
& $VenvPython -c "import torch, cv2, mediapipe, PyQt6, ultralytics; print('CUDA:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'); print('Setup complete')"

Write-Host "Run the app with: .\run.ps1"
