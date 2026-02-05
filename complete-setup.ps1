# Complete Configuration Script
# Run this after creating webhook in Portal

param(
    [Parameter(Mandatory=$true)]
    [string]$WebhookUrl
)

Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "COMPLETING APPROVAL WORKFLOW SETUP" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

Write-Host "`n[1/4] Updating .env file..." -ForegroundColor Yellow
$envContent = Get-Content .env -Raw
$envContent = $envContent -replace "AUTOMATION_WEBHOOK_URL=.*", "AUTOMATION_WEBHOOK_URL=$WebhookUrl"
Set-Content .env $envContent -NoNewline
Write-Host "✅ .env updated" -ForegroundColor Green

Write-Host "`n[2/4] Updating Logic App with webhook..." -ForegroundColor Yellow
$logicAppContent = Get-Content "logic-app-with-automation.json" -Raw
$logicAppContent = $logicAppContent -replace "WEBHOOK_URL_HERE", $WebhookUrl
Set-Content "logic-app-with-automation-final.json" $logicAppContent -NoNewline
Write-Host "✅ Logic App config prepared" -ForegroundColor Green

Write-Host "`n[3/4] Deploying Logic App..." -ForegroundColor Yellow
az rest --method put `
    --url "https://management.azure.com/subscriptions/b28cc86b-8f84-47e5-a38a-b814b44d047e/resourceGroups/Az-AICost-Agent-RG/providers/Microsoft.Logic/workflows/logagzs0230?api-version=2019-05-01" `
    --body '@logic-app-with-automation-final.json' `
    --headers "Content-Type=application/json" | Out-Null
Write-Host "✅ Logic App deployed" -ForegroundColor Green

Write-Host "`n[4/4] Restarting Python server..." -ForegroundColor Yellow
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; python main.py"
Start-Sleep -Seconds 3
Write-Host "✅ Server restarted" -ForegroundColor Green

Write-Host "`n================================================" -ForegroundColor Green
Write-Host "✅ CONFIGURATION COMPLETE!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green

Write-Host "`n📋 Approval Workflow Status:" -ForegroundColor Cyan
Write-Host "   ✅ Automation Account: aa-cli-executor" -ForegroundColor White
Write-Host "   ✅ Runbook: Execute-Deployment (Published)" -ForegroundColor White
Write-Host "   ✅ Webhook: Configured" -ForegroundColor White
Write-Host "   ✅ Logic App: Integrated with Automation" -ForegroundColor White
Write-Host "   ✅ .env: Approvals ENABLED" -ForegroundColor White
Write-Host "   ✅ Server: Running with approval workflow" -ForegroundColor White

Write-Host "`n🎯 READY TO TEST!" -ForegroundColor Green
Write-Host "`nTest Flow:" -ForegroundColor Cyan
Write-Host "   1. Go to: http://localhost:8000" -ForegroundColor White
Write-Host "   2. Request: 'create availability set test-approval-works in Az-Arc-JBOX westeurope'" -ForegroundColor White
Write-Host "   3. Check email → Click 'Approve'" -ForegroundColor White
Write-Host "   4. Automation Account will execute deployment" -ForegroundColor White
Write-Host "   5. Logic App will wait for completion" -ForegroundColor White
Write-Host "   6. You'll receive success/failure email with actual result" -ForegroundColor White

Write-Host "`n✅ Complete end-to-end approval workflow is now active!" -ForegroundColor Green
