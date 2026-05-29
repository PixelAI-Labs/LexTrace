Write-Host "Starting LexTrace..."

# Install python requirements if needed
Write-Host "Starting Backend on port 8000..."
Start-Process powershell -NoNewWindow -ArgumentList "-NoExit -Command `"cd backend; pip install -r requirements.txt; uvicorn main:app --reload`""

# Install npm requirements if needed
Write-Host "Starting Frontend..."
Start-Process powershell -NoNewWindow -ArgumentList "-NoExit -Command `"cd frontend; npm install; npm run dev`""
