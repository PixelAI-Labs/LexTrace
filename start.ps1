Write-Host "Starting LexTrace Servers..." -ForegroundColor Green

# Start Backend in a new window
Write-Host "Starting FastAPI Backend..."
Start-Process powershell -ArgumentList "-NoExit -Command `"cd '$PSScriptRoot'; if (Test-Path '$PSScriptRoot\.venv\Scripts\activate.ps1') { . '$PSScriptRoot\.venv\Scripts\activate.ps1' }; pip install -r backend/requirements.txt -q; python -m uvicorn backend.main:app --reload`""

# Start Frontend in a new window
Write-Host "Starting React Frontend..."
Start-Process powershell -ArgumentList "-NoExit -Command `"cd '$PSScriptRoot\frontend'; npm run dev`""

Write-Host "Both servers are starting in separate windows!" -ForegroundColor Blue
