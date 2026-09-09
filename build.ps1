$ErrorActionPreference = "Stop"
$pythonExe = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "未找到 Python 3.12：$pythonExe"
}
if (-not (Test-Path -LiteralPath ".build-venv\Scripts\python.exe")) {
    & $pythonExe -m venv .build-venv
}
& ".build-venv\Scripts\python.exe" -m pip install --upgrade pip
& ".build-venv\Scripts\python.exe" -m pip install -r requirements-build.txt
& ".build-venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean FgoTeam.spec
$outputDir = (Get-ChildItem -LiteralPath "dist" -Directory | Select-Object -First 1).FullName
$zipPath = "dist\FgoTeam-Windows-x64.zip"
Copy-Item -LiteralPath "portable-README.txt" -Destination $outputDir -Force
Compress-Archive -LiteralPath $outputDir -DestinationPath $zipPath -CompressionLevel Optimal -Force
Write-Host "构建完成：$zipPath"
