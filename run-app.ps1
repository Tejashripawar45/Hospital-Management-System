# Start HMS app and open Chrome automatically

$projectPath = "c:\Users\pawar\OneDrive\Desktop\TASK1"
$pythonPath = "C:\Users\pawar\AppData\Local\Programs\Python\Python313\python.exe"
$url = "http://127.0.0.1:8000"
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"

# Navigate to project
cd $projectPath

# Start waitress server in background (hidden window)
$process = Start-Process -FilePath $pythonPath `
  -ArgumentList "-m waitress --listen=127.0.0.1:8000 hms_project.wsgi:application" `
  -WindowStyle Hidden `
  -PassThru

# Wait 2 seconds for server to start
Start-Sleep -Seconds 2

# Open Chrome
if (Test-Path $chromePath) {
    Start-Process $chromePath -ArgumentList $url
} else {
    # Fallback to default browser if Chrome not found
    Start-Process $url
}

Write-Host "✓ Server started in background (PID: $($process.Id))" -ForegroundColor Green
Write-Host "✓ Chrome opening: $url" -ForegroundColor Green
Write-Host "`nTo stop the server, run: Stop-Process -Id $($process.Id)" -ForegroundColor Yellow
