# ✅ FIXED: Webhook Configuration (No Mandatory Parameters!)

## Issue & Solution
The runbook has been **updated to accept WebhookData** instead of individual parameters. Now webhook creation is simple!

## How to Create Webhook (Updated Instructions)

### Step 1: Delete Old Webhook (if exists)
1. Go to Automation Account → Webhooks
2. Delete "DeploymentWebhook" if it exists

### Step 2: Create New Webhook (Simple!)

1. **Click "Add Webhook"**

2. **Create Webhook:**
   - Name: `DeploymentWebhook`
   - Enabled: `Yes`
   - Expires: `1/31/2031` (5 years)
   - ⚠️ **COPY THE URL - IT WILL ONLY BE SHOWN ONCE!**

3. **Select Runbook:**
   - Runbook: `Execute-Deployment`
   - Click "OK"

4. **Configure Parameters:**
   
   You will now see **ONLY ONE parameter**: `WebhookData`
   
   - **WebhookData**: Leave EMPTY or check "Use default value"
   
   ✅ **That's it! No mandatory fields to fill!**

5. **Create:**
   - Click "Create"
   - **IMMEDIATELY COPY THE WEBHOOK URL!**

### Step 3: Update Configuration

```powershell
.\complete-setup.ps1 -WebhookUrl "PASTE_WEBHOOK_URL_HERE"
```

## What Changed?

### Old Runbook (Had 5 Mandatory Parameters):
```powershell
param(
    [Parameter(Mandatory=$true)]
    [string]$Command,
    [Parameter(Mandatory=$true)]
    [string]$ResourceName,
    # ... 3 more mandatory parameters
)
```
❌ Portal forces you to provide values for all 5

### New Runbook (WebhookData Pattern):
```powershell
param(
    [Parameter(Mandatory=$false)]
    [object]$WebhookData
)
# Extracts Command, ResourceName, etc from WebhookData.RequestBody
```
✅ Portal shows only 1 optional parameter

## How It Works Now

```
Logic App sends:
POST webhook URL
Body: {"Command": "az ...", "ResourceName": "...", ...}
        ↓
Automation receives:
$WebhookData.RequestBody = entire JSON
        ↓
Runbook extracts:
$Command = $RequestBody.Command
$ResourceName = $RequestBody.ResourceName
...
        ↓
Executes CLI command ✅
```

## Test After Setup

```
'create availability set test-webhook-fixed in Az-Arc-JBOX westeurope'
```

Expected:
1. ✅ Approval email
2. ✅ Click Approve
3. ✅ Automation executes successfully
4. ✅ Success email with resource details
