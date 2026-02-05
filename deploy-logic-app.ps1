# Deploy Logic App with proper API connections
$token = az account get-access-token --query accessToken -o tsv
$subscriptionId = "b28cc86b-8f84-47e5-a38a-b814b44d047e"
$resourceGroup = "Az-AICost-Agent-RG"
$logicAppName = "logagzs0230"
$location = "westeurope"

# Load the workflow definition
$workflowContent = Get-Content "logic-app-workflow-CLI.json" -Raw | ConvertFrom-Json

# Create the full payload with connections
$payload = @{
    location = $location
    properties = @{
        definition = $workflowContent.definition
        parameters = @{
            '$connections' = @{
                value = @{
                    office365 = @{
                        connectionId = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.Web/connections/office365-1"
                        connectionName = "office365-1"
                        id = "/subscriptions/$subscriptionId/providers/Microsoft.Web/locations/$location/managedApis/office365"
                    }
                }
            }
        }
    }
} | ConvertTo-Json -Depth 20

# Deploy via REST API
$uri = "https://management.azure.com/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.Logic/workflows/$logicAppName?api-version=2019-05-01"

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

Write-Host "Deploying Logic App with API connections..." -ForegroundColor Cyan
$result = Invoke-RestMethod -Uri $uri -Method PUT -Headers $headers -Body $payload
Write-Host "✅ Logic App deployed successfully!" -ForegroundColor Green
Write-Host "State: $($result.properties.state)" -ForegroundColor Yellow
