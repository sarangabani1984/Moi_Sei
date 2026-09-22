# organize-moi-sei.ps1 - Organize Moi Sei project folders

Write-Host "Organizing Moi Sei Project Structure..." -ForegroundColor Cyan
Write-Host ""

# Move documentation files
Write-Host "Moving documentation files..." -ForegroundColor Yellow
$docFiles = @("README.md", "CLOUD_DEPLOYMENT.md", "CLOUD_READINESS_CHECKLIST.md", "GITHUB_SETUP.md", "VOICE_AI_SETUP.md", "FLUTTER_GUIDE.md", "learning_roadmap.md")
foreach ($file in $docFiles) {
    if (Test-Path $file) {
        Move-Item $file "docs/" -Force
        Write-Host "  OK: $file" -ForegroundColor Green
    }
}

# Move script files
Write-Host ""
Write-Host "Moving utility scripts..." -ForegroundColor Yellow
$scriptFiles = @("test_api_key.py", "test_litellm.py", "delete_user.py", "fix_dummy_tamil_profiles.py", "fix_imported_tamil_profiles.py", "import_excel_contributions.py")
foreach ($file in $scriptFiles) {
    if (Test-Path $file) {
        Move-Item $file "scripts/" -Force
        Write-Host "  OK: $file" -ForegroundColor Green
    }
}

# Move config files
Write-Host ""
Write-Host "Moving configuration files..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    Move-Item "requirements.txt" "config/" -Force
    Write-Host "  OK: requirements.txt" -ForegroundColor Green
}

# Move archive/legacy files
Write-Host ""
Write-Host "Archiving legacy files..." -ForegroundColor Yellow
$archiveFiles = @("cloud_deployment_plan.md", "conversation_log.md", "process_flow.md", "chat_moi.json", "Moi_Sei.docx")
foreach ($file in $archiveFiles) {
    if (Test-Path $file) {
        Move-Item $file "archive/" -Force
        Write-Host "  OK: $file" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Organization complete!" -ForegroundColor Green
