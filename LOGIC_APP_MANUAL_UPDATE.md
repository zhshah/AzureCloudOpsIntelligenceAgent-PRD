# Logic App Manual Update Instructions

## 📋 What to Update in Azure Portal

Since deploying via CLI doesn't recognize actions properly, follow these steps to manually update your Logic App in Azure Portal:

### 1. Go to Logic App Designer
- Azure Portal → Logic Apps → logagzs0230 → Logic app designer

### 2. Keep These Actions As-Is:
- ✅ **Trigger**: When a HTTP request is received
- ✅ **Parse_Request**: Parse JSON
- ✅ **Send_Approval_Email**: Send approval email
- ✅ **Check_Response**: Condition (if approved)

### 3. DELETE Old Deployment Actions:
In the "If Approved" branch:
- ❌ Delete: **Check_Deployment_Scope**
- ❌ Delete: **Deploy_Resource_Group**  
- ❌ Delete: **Deploy_Other_Resource**

### 4. ADD New Execute Action:
In the "If Approved" branch (where you deleted the old actions):

**Action Name**: `Execute_CLI_Command`
**Type**: HTTP

**Settings**:
```
Method: POST
URI: http://localhost:8000/api/execute-approved

Headers:
  Content-Type: application/json

Body:
{
  "requestId": @{body('Parse_Request')?['requestId']},
  "command": @{body('Parse_Request')?['details']?['command']},
  "resourceName": @{body('Parse_Request')?['resourceName']},
  "resourceType": @{body('Parse_Request')?['resourceType']}
}
```

### 5. ADD Success Email Action:
**Action Name**: `Send_Success_Email`
**Type**: Send an email (V2)
**Run After**: Execute_CLI_Command → Succeeded

**Settings**:
```
To: @{body('Parse_Request')?['userEmail']}
Subject: ✅ Deployment Successful: @{body('Parse_Request')?['resourceName']}
Body: (Use HTML from below)
```

**HTML Body for Success**:
```html
<html><body style='font-family: Segoe UI, Arial, sans-serif;'>
<div style='max-width: 600px; margin: 0 auto; padding: 20px;'>
<div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 30px; border-radius: 10px; text-align: center; color: white;'>
<h1 style='margin: 0;'>✅ Deployment Successful!</h1>
</div>
<div style='background: white; padding: 30px; border: 1px solid #e0e0e0; border-radius: 0 0 10px 10px;'>
<p style='font-size: 16px; color: #333;'>Hi <strong>@{body('Parse_Request')?['userName']}</strong>,</p>
<p>Your resource <strong>@{body('Parse_Request')?['resourceName']}</strong> has been successfully deployed!</p>
<div style='background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;'>
<p style='margin: 5px 0;'><strong>Resource:</strong> @{body('Parse_Request')?['resourceName']}</p>
<p style='margin: 5px 0;'><strong>Type:</strong> @{body('Parse_Request')?['resourceType']}</p>
<p style='margin: 5px 0;'><strong>Resource Group:</strong> @{body('Parse_Request')?['resourceGroup']}</p>
<p style='margin: 5px 0;'><strong>Request ID:</strong> @{body('Parse_Request')?['requestId']}</p>
</div></div></div></body></html>
```

### 6. ADD Failure Email Action:
**Action Name**: `Send_Failure_Email`
**Type**: Send an email (V2)
**Run After**: Execute_CLI_Command → Failed, TimedOut

**Settings**:
```
To: @{body('Parse_Request')?['userEmail']}
Subject: ⚠️ Deployment Failed: @{body('Parse_Request')?['resourceName']}
Body: (Use HTML from below)
```

**HTML Body for Failure**:
```html
<html><body style='font-family: Segoe UI, Arial, sans-serif;'>
<div style='max-width: 600px; margin: 0 auto; padding: 20px;'>
<div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 30px; border-radius: 10px; text-align: center; color: white;'>
<h1 style='margin: 0;'>⚠️ Deployment Failed</h1>
</div>
<div style='background: white; padding: 30px; border: 1px solid #e0e0e0; border-radius: 0 0 10px 10px;'>
<p style='font-size: 16px; color: #333;'>Hi <strong>@{body('Parse_Request')?['userName']}</strong>,</p>
<p>Unfortunately, the deployment of <strong>@{body('Parse_Request')?['resourceName']}</strong> failed.</p>
<div style='background: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #ffc107;'>
<p style='margin: 5px 0;'><strong>Resource:</strong> @{body('Parse_Request')?['resourceName']}</p>
<p style='margin: 5px 0;'><strong>Request ID:</strong> @{body('Parse_Request')?['requestId']}</p>
<p style='margin: 5px 0;'><strong>Error:</strong> @{body('Execute_CLI_Command')?['error']}</p>
</div></div></div></body></html>
```

### 7. Keep Existing Rejection Email:
The rejection email in the "else" branch should remain unchanged.

### 8. Save the Logic App

## 🎯 Final Flow Should Be:

```
Trigger: HTTP Request
  ↓
Parse_Request
  ↓
Send_Approval_Email
  ↓
Check_Response (Condition)
  ├─ If Approved:
  │   ├─ Execute_CLI_Command (HTTP POST to localhost:8000)
  │   ├─ Send_Success_Email (on success)
  │   └─ Send_Failure_Email (on failure/timeout)
  │
  └─ If Rejected:
      └─ Send_Rejection_Email
```

## 📝 Copy-Paste Ready Expressions:

**For Execute_CLI_Command body (switch to code view)**:
```json
{
  "requestId": "@{body('Parse_Request')?['requestId']}",
  "command": "@{body('Parse_Request')?['details']?['command']}",
  "resourceName": "@{body('Parse_Request')?['resourceName']}",
  "resourceType": "@{body('Parse_Request')?['resourceType']}"
}
```

**For Dynamic Content**:
- Resource Name: `@{body('Parse_Request')?['resourceName']}`
- User Email: `@{body('Parse_Request')?['userEmail']}`
- User Name: `@{body('Parse_Request')?['userName']}`
- Request ID: `@{body('Parse_Request')?['requestId']}`
- Resource Type: `@{body('Parse_Request')?['resourceType']}`
- Resource Group: `@{body('Parse_Request')?['resourceGroup']}`
- CLI Command: `@{body('Parse_Request')?['details']?['command']}`

## ✅ After Updating:

1. Click **Save** in Logic App Designer
2. Test by creating a resource from the web app
3. Check your email for approval
4. Click Approve
5. Resource should be created via CLI
6. You'll receive success email

## 🔍 Troubleshooting:

If Execute_CLI_Command fails:
- Check FastAPI server is running: `http://localhost:8000/health`
- Check Logic App run history for error details
- Verify the body format matches expected schema
