# Complete Deployment Script - Creates Webhook and Updates Logic App

Write-Host "`n🔗 Creating Webhook for Runbook..." -ForegroundColor Cyan

# Create webhook using REST API
$webhookName = "DeploymentWebhook"
$expiryDate = (Get-Date).AddYears(5).ToString("yyyy-MM-ddTHH:mm:ss.fffZ")

$webhookBody = @{
    name = $webhookName
    properties = @{
        isEnabled = $true
        expiryTime = $expiryDate
        runbook = @{
            name = "Execute-Deployment"
        }
    }
} | ConvertTo-Json -Depth 10

$response = az rest --method put `
    --url "https://management.azure.com/subscriptions/b28cc86b-8f84-47e5-a38a-b814b44d047e/resourceGroups/Az-AICost-Agent-RG/providers/Microsoft.Automation/automationAccounts/aa-cli-executor/webhooks/$webhookName`?api-version=2015-10-31" `
    --body $webhookBody `
    --headers "Content-Type=application/json" | ConvertFrom-Json

$webhookUrl = $response.properties.uri

Write-Host "✅ Webhook Created!" -ForegroundColor Green
Write-Host "🔗 URL: $webhookUrl" -ForegroundColor Yellow

# Update Logic App with Automation Account integration
Write-Host "`n📝 Creating Logic App with Automation Account integration..." -ForegroundColor Cyan

$logicAppBody = @"
{
    "location": "westeurope",
    "properties": {
        "definition": {
            "`$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {
                "`$connections": {
                    "type": "Object",
                    "defaultValue": {}
                },
                "automationWebhookUrl": {
                    "type": "String",
                    "defaultValue": "$webhookUrl"
                }
            },
            "triggers": {
                "manual": {
                    "type": "Request",
                    "kind": "Http",
                    "inputs": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "requestId": {"type": "string"},
                                "resourceType": {"type": "string"},
                                "resourceName": {"type": "string"},
                                "resourceGroup": {"type": "string"},
                                "details": {"type": "object"},
                                "userEmail": {"type": "string"},
                                "userName": {"type": "string"},
                                "estimatedCost": {"type": "string"},
                                "justification": {"type": "string"},
                                "location": {"type": "string"}
                            }
                        }
                    }
                }
            },
            "actions": {
                "Parse_Request": {
                    "runAfter": {},
                    "type": "ParseJson",
                    "inputs": {
                        "content": "@triggerBody()",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "requestId": {"type": "string"},
                                "resourceType": {"type": "string"},
                                "resourceName": {"type": "string"},
                                "resourceGroup": {"type": "string"},
                                "details": {"type": "object"},
                                "userEmail": {"type": "string"},
                                "userName": {"type": "string"},
                                "estimatedCost": {"type": "string"},
                                "justification": {"type": "string"},
                                "location": {"type": "string"}
                            }
                        }
                    }
                },
                "Send_Approval_Email": {
                    "runAfter": {
                        "Parse_Request": ["Succeeded"]
                    },
                    "type": "ApiConnectionWebhook",
                    "inputs": {
                        "host": {
                            "connection": {
                                "name": "@parameters('`$connections')['office365']['connectionId']"
                            }
                        },
                        "body": {
                            "Message": {
                                "To": "@body('Parse_Request')?['userEmail']",
                                "Subject": "⚡ Deployment Approval Required: @{body('Parse_Request')?['resourceName']}",
                                "Options": "Approve, Reject",
                                "Body": "@{concat('<html><body><h2>Approval Required</h2><p>Resource: ', body('Parse_Request')?['resourceName'], '</p><p>Type: ', body('Parse_Request')?['resourceType'], '</p><p>Group: ', body('Parse_Request')?['resourceGroup'], '</p></body></html>')}",
                                "Importance": "High"
                            },
                            "NotificationUrl": "@{listCallbackUrl()}"
                        },
                        "path": "/approvalmail/`$subscriptions"
                    }
                },
                "Check_Approval": {
                    "runAfter": {
                        "Send_Approval_Email": ["Succeeded"]
                    },
                    "type": "If",
                    "expression": {
                        "and": [{
                            "equals": ["@body('Send_Approval_Email')?['SelectedOption']", "Approve"]
                        }]
                    },
                    "actions": {
                        "Execute_via_Automation": {
                            "type": "Http",
                            "inputs": {
                                "method": "POST",
                                "uri": "@parameters('automationWebhookUrl')",
                                "headers": {
                                    "Content-Type": "application/json"
                                },
                                "body": {
                                    "Command": "@{body('Parse_Request')?['details']?['command']}",
                                    "ResourceName": "@{body('Parse_Request')?['resourceName']}",
                                    "ResourceGroup": "@{body('Parse_Request')?['resourceGroup']}",
                                    "ResourceType": "@{body('Parse_Request')?['resourceType']}",
                                    "RequestId": "@{body('Parse_Request')?['requestId']}"
                                }
                            }
                        },
                        "Send_Success_Email": {
                            "runAfter": {
                                "Execute_via_Automation": ["Succeeded"]
                            },
                            "type": "ApiConnection",
                            "inputs": {
                                "host": {
                                    "connection": {
                                        "name": "@parameters('`$connections')['office365']['connectionId']"
                                    }
                                },
                                "method": "post",
                                "body": {
                                    "To": "@body('Parse_Request')?['userEmail']",
                                    "Subject": "✅ Deployment Successful: @{body('Parse_Request')?['resourceName']}",
                                    "Body": "@{concat('<html><body><h2>Deployment Complete</h2><p>Resource: ', body('Parse_Request')?['resourceName'], ' deployed successfully!</p></body></html>')}",
                                    "Importance": "Normal"
                                },
                                "path": "/v2/Mail"
                            }
                        }
                    },
                    "else": {
                        "actions": {
                            "Send_Rejection_Email": {
                                "type": "ApiConnection",
                                "inputs": {
                                    "host": {
                                        "connection": {
                                            "name": "@parameters('`$connections')['office365']['connectionId']"
                                        }
                                    },
                                    "method": "post",
                                    "body": {
                                        "To": "@body('Parse_Request')?['userEmail']",
                                        "Subject": "❌ Deployment Rejected: @{body('Parse_Request')?['resourceName']}",
                                        "Body": "<html><body><h2>Deployment Rejected</h2><p>Your request was rejected.</p></body></html>",
                                        "Importance": "Normal"
                                    },
                                    "path": "/v2/Mail"
                                }
                            }
                        }
                    }
                }
            }
        },
        "parameters": {
            "`$connections": {
                "value": {
                    "office365": {
                        "id": "/subscriptions/b28cc86b-8f84-47e5-a38a-b814b44d047e/providers/Microsoft.Web/locations/westeurope/managedApis/office365",
                        "connectionId": "/subscriptions/b28cc86b-8f84-47e5-a38a-b814b44d047e/resourceGroups/Az-AICost-Agent-RG/providers/Microsoft.Web/connections/office365",
                        "connectionName": "office365"
                    }
                }
            }
        }
    }
}
"@

az rest --method put `
    --url "https://management.azure.com/subscriptions/b28cc86b-8f84-47e5-a38a-b814b44d047e/resourceGroups/Az-AICost-Agent-RG/providers/Microsoft.Logic/workflows/logagzs0230?api-version=2019-05-01" `
    --body $logicAppBody `
    --headers "Content-Type=application/json"

Write-Host "`n✅ Logic App Updated with Automation Account integration!" -ForegroundColor Green

# Update .env file
Write-Host "`n📝 Updating .env file..." -ForegroundColor Cyan
$envPath = ".env"
$envContent = Get-Content $envPath -Raw
if ($envContent -match "AUTOMATION_WEBHOOK_URL=") {
    $envContent = $envContent -replace "AUTOMATION_WEBHOOK_URL=.*", "AUTOMATION_WEBHOOK_URL=$webhookUrl"
} else {
    $envContent += "`nAUTOMATION_WEBHOOK_URL=$webhookUrl"
}
Set-Content $envPath $envContent

Write-Host "✅ .env file updated!" -ForegroundColor Green

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "COMPLETE SETUP SUMMARY" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ Automation Account: aa-cli-executor" -ForegroundColor White
Write-Host "✅ Runbook: Execute-Deployment (Published)" -ForegroundColor White
Write-Host "✅ Webhook: Created (valid 5 years)" -ForegroundColor White
Write-Host "✅ Logic App: logagzs0230 (integrated with webhook)" -ForegroundColor White
Write-Host "✅ .env: Updated with webhook URL" -ForegroundColor White
Write-Host "`n🔗 Webhook URL:" -ForegroundColor Cyan
Write-Host "$webhookUrl" -ForegroundColor Yellow

Write-Host "`n📋 TEST WITHOUT APPROVALS FIRST:" -ForegroundColor Cyan
Write-Host "1. Verify ENABLE_APPROVAL_WORKFLOW=false in .env" -ForegroundColor White
Write-Host "2. Start server: python main.py" -ForegroundColor White
Write-Host "3. Go to http://localhost:8000" -ForegroundColor White
Write-Host "4. Request: 'create availability set test-final in Az-Arc-JBOX westeurope'" -ForegroundColor White
Write-Host "5. Should deploy immediately" -ForegroundColor White

Write-Host "`n📋 THEN TEST WITH APPROVALS:" -ForegroundColor Cyan
Write-Host "1. Set ENABLE_APPROVAL_WORKFLOW=true in .env" -ForegroundColor White
Write-Host "2. Restart server" -ForegroundColor White
Write-Host "3. Request resource" -ForegroundColor White
Write-Host "4. Check email and click Approve" -ForegroundColor White
Write-Host "5. Automation Account will execute deployment" -ForegroundColor White
Write-Host "6. Receive success/failure email" -ForegroundColor White
