# Complete End-to-End Setup Script

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "AZURE CLI APPROVAL WORKFLOW - END-TO-END SETUP" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

# Step 1: Verify Python Server
Write-Host "`n[STEP 1] Verifying Python Server..." -ForegroundColor Yellow
$serverCheck = Test-NetConnection -ComputerName localhost -Port 8000 -WarningAction SilentlyContinue
if ($serverCheck.TcpTestSucceeded) {
    Write-Host "✅ Server running on http://localhost:8000" -ForegroundColor Green
} else {
    Write-Host "❌ Server not running! Starting..." -ForegroundColor Red
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "python main.py"
    Start-Sleep -Seconds 5
}

# Step 2: Create Automation Account
Write-Host "`n[STEP 2] Creating Azure Automation Account..." -ForegroundColor Yellow
$aaName = "aa-cli-executor"
$rgName = "Az-AICost-Agent-RG"
$location = "westeurope"

$aaCheck = az automation account show --name $aaName --resource-group $rgName 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating new Automation Account..." -ForegroundColor Cyan
    az automation account create --name $aaName --resource-group $rgName --location $location --sku Basic
    
    # Enable Managed Identity
    Write-Host "Enabling Managed Identity..." -ForegroundColor Cyan
    az automation account update --name $aaName --resource-group $rgName --assign-identity
    
    # Get Principal ID
    $principalId = (az automation account show --name $aaName --resource-group $rgName --query identity.principalId -o tsv)
    Write-Host "✅ Principal ID: $principalId" -ForegroundColor Green
    
    # Assign Contributor role
    Write-Host "Assigning Contributor role..." -ForegroundColor Cyan
    $subscriptionId = (az account show --query id -o tsv)
    az role assignment create --assignee $principalId --role Contributor --scope "/subscriptions/$subscriptionId" 2>$null
    
    Write-Host "✅ Automation Account created!" -ForegroundColor Green
} else {
    Write-Host "✅ Automation Account already exists" -ForegroundColor Green
}

# Step 3: Create Runbook
Write-Host "`n[STEP 3] Creating PowerShell Runbook..." -ForegroundColor Yellow
$runbookName = "Execute-Deployment"

az automation runbook create --automation-account-name $aaName --resource-group $rgName --name $runbookName --type PowerShell --description "Execute Azure CLI deployments" 2>$null

Write-Host "Uploading runbook content..." -ForegroundColor Cyan
az automation runbook replace-content --automation-account-name $aaName --resource-group $rgName --name $runbookName --content "@automation-runbook.ps1"

Write-Host "Publishing runbook..." -ForegroundColor Cyan
az automation runbook publish --automation-account-name $aaName --resource-group $rgName --name $runbookName

Write-Host "✅ Runbook created and published!" -ForegroundColor Green

# Step 4: Create Webhook
Write-Host "`n[STEP 4] Creating Webhook..." -ForegroundColor Yellow
$webhookName = "DeploymentWebhook"
$expiryDate = (Get-Date).AddYears(5).ToString("yyyy-MM-ddTHH:mm:ss+00:00")

$webhook = az automation webhook create --automation-account-name $aaName --resource-group $rgName --name $webhookName --runbook-name $runbookName --expiry-time $expiryDate --is-enabled true | ConvertFrom-Json

$webhookUrl = $webhook.uri

Write-Host "✅ Webhook created!" -ForegroundColor Green
Write-Host "`n🔗 WEBHOOK URL:" -ForegroundColor Cyan
Write-Host $webhookUrl -ForegroundColor Yellow

# Step 5: Update .env file
Write-Host "`n[STEP 5] Updating .env file..." -ForegroundColor Yellow
$envContent = Get-Content .env -Raw
if ($envContent -notmatch "AUTOMATION_WEBHOOK_URL") {
    Add-Content .env "`nAUTOMATION_WEBHOOK_URL=$webhookUrl"
} else {
    $envContent = $envContent -replace "AUTOMATION_WEBHOOK_URL=.*", "AUTOMATION_WEBHOOK_URL=$webhookUrl"
    Set-Content .env $envContent
}
Write-Host "✅ .env file updated!" -ForegroundColor Green

# Summary
Write-Host "`n" + ("=" * 80) -ForegroundColor Cyan
Write-Host "SETUP COMPLETE!" -ForegroundColor Green
Write-Host ("=" * 80) -ForegroundColor Cyan

Write-Host "`n📋 CONFIGURATION SUMMARY:" -ForegroundColor Cyan
Write-Host "   Server: http://localhost:8000" -ForegroundColor White
Write-Host "   Automation Account: $aaName" -ForegroundColor White
Write-Host "   Runbook: $runbookName" -ForegroundColor White
Write-Host "   Webhook: Created (valid for 5 years)" -ForegroundColor White
Write-Host "   Approvals: Currently DISABLED" -ForegroundColor White

Write-Host "`n🎯 NEXT STEPS:" -ForegroundColor Cyan
Write-Host "   1. Test WITHOUT approvals first:" -ForegroundColor White
Write-Host "      - Go to http://localhost:8000" -ForegroundColor Gray
Write-Host "      - Request: 'create availability set test-auto-123 in Az-Arc-JBOX westeurope'" -ForegroundColor Gray
Write-Host "      - Should deploy immediately" -ForegroundColor Gray
Write-Host "`n   2. Enable approvals:" -ForegroundColor White
Write-Host "      - Set ENABLE_APPROVAL_WORKFLOW=true in .env" -ForegroundColor Gray
Write-Host "      - Restart Python server" -ForegroundColor Gray
Write-Host "      - Deploy Logic App with webhook integration" -ForegroundColor Gray

Write-Host "`n✅ Ready to test!" -ForegroundColor Green
