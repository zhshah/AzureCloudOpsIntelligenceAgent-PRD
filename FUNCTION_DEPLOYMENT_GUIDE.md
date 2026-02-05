# Azure Function Approval Workflow - Deployment Guide

## Architecture
```
User Request → Python API → Logic App → Approval Email
                                 ↓ (Approve clicked)
                           Azure Function (executes az cli)
                                 ↓
                           Returns success/failure
                                 ↓
                           Logic App → Success/Failure Email
```

## Why This Works 100%

1. **No polling needed** - Logic App waits synchronously for Function response
2. **No server to keep running** - Function is serverless, auto-scales
3. **Proven technology** - Same Azure CLI commands we already tested
4. **Direct feedback** - Function returns deployment result immediately
5. **Full tracking** - Request ID tracked through entire flow

## Deployment Steps

### Step 1: Install Azure Functions Core Tools
```powershell
# Install Azure Functions Core Tools v4
winget install Microsoft.Azure.FunctionsCore Tools
```

### Step 2: Deploy the Function App
```powershell
# Run the deployment script
.\deploy-function.ps1
```

This will:
- Create Function App with Python 3.11 runtime
- Enable Managed Identity
- Assign Contributor role (for deploying Azure resources)
- Deploy the function code
- Output the Function URL

### Step 3: Update .env File
Copy the Function URL from Step 2 output and add to `.env`:
```
ENABLE_APPROVAL_WORKFLOW=true
FUNCTION_EXECUTOR_URL=https://func-cli-executor-XXXX.azurewebsites.net/api/execute-deployment?code=XXXXX
```

### Step 4: Update Logic App Parameter
Edit `logic-app-with-function.json` line 19:
```json
"functionUrl": {
    "type": "String",
    "defaultValue": "PASTE_YOUR_FUNCTION_URL_HERE"
}
```

### Step 5: Deploy Updated Logic App
```powershell
az rest --method put `
  --url "https://management.azure.com/subscriptions/b28cc86b-8f84-47e5-a38a-b814b44d047e/resourceGroups/Az-AICost-Agent-RG/providers/Microsoft.Logic/workflows/logagzs0230?api-version=2019-05-01" `
  --body '@logic-app-with-function.json' `
  --headers "Content-Type=application/json"
```

### Step 6: Restart Python Server
```powershell
Get-Process | Where-Object { $_.ProcessName -eq 'python' } | Stop-Process -Force
Start-Sleep -Seconds 2
python main.py
```

## How It Works

### 1. User Requests Resource
Chat interface → Python API → generates CLI command

### 2. Python Submits to Logic App
```python
POST to Logic App webhook
{
    "requestId": "uuid",
    "resourceName": "avail-set-123",
    "command": "az vm availability-set create ...",
    "userEmail": "admin@zahir.cloud",
    ...
}
```

### 3. Logic App Sends Approval Email
Office365 connector sends email with Approve/Reject buttons

### 4. User Clicks "Approve"

### 5. Logic App Calls Azure Function
```http
POST https://func-cli-executor-XXXX.azurewebsites.net/api/execute-deployment
{
    "command": "az vm availability-set create ...",
    "resourceName": "avail-set-123",
    "resourceGroup": "Az-Arc-JBOX",
    "resourceType": "Availability Set",
    "requestId": "uuid"
}
```

### 6. Azure Function Executes
- Runs `subprocess.run(command)` 
- Waits for completion (max 5 minutes)
- Verifies resource exists with `az resource list`
- Returns JSON response

### 7. Logic App Sends Result Email
Based on Function response status:
- `"status": "success"` → Success email with resource details
- `"status": "failed"` → Failure email with error message
- `"status": "timeout"` → Timeout notification

## Advantages Over Previous Approach

| Previous (Polling) | New (Function) |
|-------------------|----------------|
| ❌ Python server must run 24/7 | ✅ Serverless, no persistent server |
| ❌ Daemon threads die silently | ✅ Synchronous, full error handling |
| ❌ No deployment verification | ✅ Function verifies and reports back |
| ❌ No success/failure emails | ✅ Logic App sends result emails |
| ❌ Chat blocks OR no tracking | ✅ Immediate response + full tracking |
| ❌ 10-minute polling complexity | ✅ Direct HTTP call, simple flow |

## Testing

1. Open chat interface: http://localhost:8000
2. Request: "create availability set named test-func-approval in Az-Arc-JBOX westeurope"
3. Chat responds: "Approval request sent"
4. Check email → Click "Approve"
5. Wait 30-60 seconds
6. Check email → Success/failure notification
7. Verify in Azure Portal → Resource exists

## Monitoring

### View Function Logs
```powershell
# Stream live logs
func azure functionapp logstream func-cli-executor-XXXX

# Or view in Azure Portal
# Function App → Functions → execute-deployment → Monitor
```

### View Logic App Runs
```powershell
az rest --method get `
  --url "https://management.azure.com/subscriptions/b28cc86b-8f84-47e5-a38a-b814b44d047e/resourceGroups/Az-AICost-Agent-RG/providers/Microsoft.Logic/workflows/logagzs0230/runs?api-version=2019-05-01&`$top=10"
```

## Troubleshooting

### Function Returns 403 Forbidden
- Check Managed Identity is enabled
- Verify Contributor role assignment: `az role assignment list --assignee <principal-id>`

### Function Times Out
- Check Function timeout setting in `host.json` (default: 10 minutes)
- Review command execution time

### Azure CLI Not Available in Function
- Function uses Linux container with Azure CLI pre-installed
- If missing, add to `requirements.txt`: `azure-cli`

### Resource Not Found After Deployment
- Function waits 5 seconds for Azure propagation
- May need to increase wait time for complex resources

## Cost Estimate

- **Function App** (Consumption Plan): ~$0.20/million executions
- **Logic App**: ~$0.000125 per action (5-7 actions per workflow)
- **Storage Account**: ~$0.02/GB/month

**Total cost per deployment approval**: < $0.01

## Production Considerations

1. **Increase Function timeout** for complex deployments (edit `host.json`)
2. **Add Application Insights** for detailed monitoring
3. **Enable deployment slots** for zero-downtime updates
4. **Add retry policy** in Logic App HTTP action
5. **Store Function URL** in Azure Key Vault instead of Logic App parameters
