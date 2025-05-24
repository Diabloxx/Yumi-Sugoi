$ErrorActionPreference = "Stop"

# Verify changes
git status

Write-Host ""
Write-Host "The following files have been modified:" -ForegroundColor Green
git diff --name-only

Write-Host ""
Write-Host "Summary of Changes:" -ForegroundColor Green
Get-Content -Path ".\COMMIT_MESSAGE.md"

Write-Host ""
Write-Host "Do you want to commit these changes? (y/n)" -ForegroundColor Yellow
$confirm = Read-Host

if ($confirm -eq "y") {    # Add all changed files
    git add .
    
    # Commit with message from our file
    $commitMsg = "Fix: Lockdown command behavior and persistence"
    git commit -m "$commitMsg"
    
    Write-Host "Changes committed successfully!" -ForegroundColor Green
    Write-Host "You can now push the changes with 'git push'"
} else {
    Write-Host "Commit cancelled." -ForegroundColor Red
}
