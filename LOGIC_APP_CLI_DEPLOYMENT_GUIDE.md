# Logic App CLI Deployment Guide

## 🎯 Overview
This guide explains how to update your Logic App to work with Azure CLI commands instead of ARM templates.

## 📋 What Changed?

### Before (Old Logic App)
- Received ARM template JSON in approval request
- Used `Microsoft.Resources/deployments` API to deploy
- Failed with authentication errors

### After (New Logic App)
- Receives Azure CLI command in approval request
- Calls back to FastAPI server to execute command
- FastAPI executes `az` CLI command directly
- Returns success/failure to Logic App

## 🏗️ Architecture Flow

```
User Request → AI Agent → Universal CLI Deployment
                              ↓
                    Generate CLI Command
                              ↓
                    Submit to Logic App (approval webhook)
                              ↓
                    Logic App sends approval email
                              ↓
                    User clicks Approve
                              ↓
                    Logic App calls /api/execute-approved
                              ↓
                    FastAPI server executes CLI command
                              ↓
                    Returns success/failure
                              ↓
                    Logic App sends result email
```

## 🚀 Deployment Steps

### Step 1: Update FastAPI Server
The `/api/execute-approved` endpoint has been added to `main.py`. Restart your server:

```powershell
# Stop current server (Ctrl+C)
# Start server again
python main.py
```

### Step 2: Deploy Updated Logic App

#### Option A: Update via Azure Portal
1. Go to Azure Portal → Logic Apps → Your Logic App
2. Click "Logic app code view"
3. Copy content from `logic-app-workflow-CLI.json`
4. Paste into the editor
5. **Important**: Update the FastAPI server URL in line 71:
   ```json
   "uri": "http://YOUR_SERVER_IP:8000/api/execute-approved"
   ```
   Replace with your actual server address (e.g., `http://20.121.73.45:8000/api/execute-approved`)
6. Click Save

#### Option B: Deploy via Azure CLI
```powershell
# Login to Azure
az login

# Set variables
$resourceGroup = "your-resource-group"
$logicAppName = "your-logic-app-name"
$serverUrl = "http://YOUR_SERVER_IP:8000"

# Update the workflow file with your server URL
$workflowContent = Get-Content "logic-app-workflow-CLI.json" -Raw
$workflowContent = $workflowContent -replace "http://YOUR_FASTAPI_SERVER:8000", $serverUrl
$workflowContent | Set-Content "logic-app-workflow-CLI-updated.json"

# Deploy the Logic App
az logic workflow create `
    --resource-group $resourceGroup `
    --name $logicAppName `
    --definition "@logic-app-workflow-CLI-updated.json"
```

### Step 3: Configure Connections
The Logic App needs Office 365 connection for emails:

1. Go to Azure Portal → Logic Apps → Your Logic App
2. Click "API connections" in left menu
3. Click "office365" connection
4. Click "Edit API connection"
5. Click "Authorize" and sign in with your Office 365 account
6. Click Save

### Step 4: Enable Approvals in .env
```env
ENABLE_APPROVAL_WORKFLOW=true
```

### Step 5: Test the Flow

#### Test 1: Create Managed Disk
```
User: Create a managed disk named test-disk-001 in rg-test
```

Expected flow:
1. ✅ AI agent generates CLI command
2. ✅ Approval request sent to Logic App
3. ✅ You receive approval email
4. ✅ Click "Approve" in email
5. ✅ Logic App calls FastAPI `/api/execute-approved`
6. ✅ FastAPI executes: `az disk create --name test-disk-001 ...`
7. ✅ You receive success email
8. ✅ Disk appears in Azure Portal

#### Test 2: Create Virtual Network
```
User: Create a virtual network named test-vnet in rg-test with address prefix 10.0.0.0/16
```

Same flow as above.

## 🔧 Troubleshooting

### Issue: "Connection refused" error from Logic App
**Solution**: Ensure your FastAPI server is accessible from Azure Logic App:
- If running locally, use ngrok or expose port 8000
- If on Azure VM, ensure NSG allows inbound on port 8000
- Update firewall rules if needed

```powershell
# Test connectivity from Azure
Test-NetConnection -ComputerName YOUR_SERVER_IP -Port 8000
```

### Issue: "Command not found" error
**Solution**: Ensure Azure CLI is installed on the server running FastAPI:
```powershell
az --version
```

### Issue: Authentication failed during command execution
**Solution**: Login to Azure CLI on the server:
```powershell
az login
az account set --subscription "YOUR_SUBSCRIPTION_ID"
```

### Issue: Email not received
**Solution**: 
1. Check Logic App run history in Azure Portal
2. Verify Office 365 connection is authorized
3. Check spam folder
4. Verify email address is correct in approval request

### Issue: Deployment succeeds but no success email
**Solution**: Check Logic App run history for errors in "Send_Success_Email" action

## 📊 Monitoring

### View Logic App Runs
```powershell
az logic workflow show --resource-group $resourceGroup --name $logicAppName
```

### View FastAPI Logs
Check console output where `main.py` is running:
```
🟢 EXECUTING APPROVED COMMAND
   Request ID: abc123
   Resource: test-disk-001
   Type: Managed Disk
   Command: az disk create --name test-disk-001 --resource-group rg-test --size-gb 128
✅ Command executed successfully
```

## 🎨 Email Templates

The new Logic App includes beautiful HTML email templates:

### Approval Email
- 📧 Purple gradient header
- 📋 All resource details in table format
- 💻 Shows actual CLI command to be executed
- ✅ Approve/Reject buttons

### Success Email
- ✅ Green gradient header
- 🎉 Confirmation of successful deployment
- 📋 Resource details summary

### Failure Email
- ⚠️ Red/pink gradient header
- 🔍 Error details for troubleshooting
- 📋 Request ID for tracking

### Rejection Email
- ❌ Red gradient header
- 📋 Rejection confirmation

## 🔒 Security Notes

1. **Endpoint Security**: The `/api/execute-approved` endpoint executes shell commands. In production:
   - Add authentication (API key, JWT token)
   - Validate command format
   - Use allowlist for commands
   - Log all executions

2. **Network Security**: 
   - Use HTTPS for production
   - Restrict access to FastAPI server
   - Use Azure Virtual Network integration

3. **Managed Identity**: Consider using Managed Identity for Azure CLI authentication instead of user login

## ✅ Verification Checklist

Before going live:
- [ ] FastAPI server running and accessible
- [ ] Logic App deployed with correct server URL
- [ ] Office 365 connection authorized
- [ ] Azure CLI installed and authenticated
- [ ] Test disk creation approved and deployed
- [ ] Approval email received
- [ ] Success email received after deployment
- [ ] Resource visible in Azure Portal
- [ ] `.env` has `ENABLE_APPROVAL_WORKFLOW=true`

## 🎯 Next Steps

1. Deploy Logic App with your server URL
2. Test with simple resource (disk)
3. Verify email flow works
4. Test with complex resource (VM)
5. Add API authentication for production
6. Set up monitoring and alerts

## 📞 Support

If issues persist:
1. Check FastAPI logs for command execution errors
2. Check Logic App run history for approval flow errors
3. Verify Azure CLI authentication: `az account show`
4. Test CLI command manually: Copy from approval email and run in terminal
