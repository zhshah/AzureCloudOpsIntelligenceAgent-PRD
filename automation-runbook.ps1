# Azure Automation Runbook - Execute CLI Deployment
# This runbook is triggered by Logic App webhook after approval

param(
    [Parameter(Mandatory=$false)]
    [object]$WebhookData
)

# Extract parameters from webhook request body
if ($WebhookData) {
    $RequestBody = ConvertFrom-Json -InputObject $WebhookData.RequestBody
    $Command = $RequestBody.Command
    $ResourceName = $RequestBody.ResourceName
    $ResourceGroup = $RequestBody.ResourceGroup
    $ResourceType = $RequestBody.ResourceType
    $RequestId = $RequestBody.RequestId
} else {
    Write-Error "This runbook must be called from a webhook"
    exit 1
}

Write-Output "🚀 Starting deployment execution..."
Write-Output "📋 Request ID: $RequestId"
Write-Output "📦 Resource: $ResourceName"
Write-Output "🗂️ Resource Group: $ResourceGroup"
Write-Output "💻 Command: $Command"

try {
    # Connect using Managed Identity
    Write-Output "🔐 Connecting to Azure using Managed Identity..."
    Connect-AzAccount -Identity
    
    # Execute the CLI command
    Write-Output "⚡ Executing command..."
    $result = Invoke-Expression $Command 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Output "✅ Command executed successfully!"
        Write-Output $result
        
        # Wait for Azure propagation
        Start-Sleep -Seconds 5
        
        # Verify resource exists
        Write-Output "🔍 Verifying resource in Azure..."
        $verify = az resource list --resource-group $ResourceGroup --query "[?name=='$ResourceName'].name" --output tsv
        
        if ($verify -eq $ResourceName) {
            Write-Output "✅ Resource '$ResourceName' verified in Azure!"
            
            # Return success response
            $response = @{
                status = "success"
                message = "✅ $ResourceType '$ResourceName' deployed successfully!"
                resourceName = $ResourceName
                resourceGroup = $ResourceGroup
                requestId = $RequestId
            } | ConvertTo-Json
            
            Write-Output $response
        }
        else {
            Write-Warning "⚠️ Resource created but verification failed"
            
            $response = @{
                status = "partial"
                message = "⚠️ Command executed but resource verification failed"
                resourceName = $ResourceName
                requestId = $RequestId
            } | ConvertTo-Json
            
            Write-Output $response
        }
    }
    else {
        Write-Error "❌ Command failed with exit code: $LASTEXITCODE"
        Write-Error $result
        
        $response = @{
            status = "failed"
            message = "❌ Deployment failed: $result"
            resourceName = $ResourceName
            requestId = $RequestId
        } | ConvertTo-Json
        
        Write-Output $response
    }
}
catch {
    Write-Error "❌ Error: $_"
    
    $response = @{
        status = "error"
        message = "❌ Error: $_"
        requestId = $RequestId
    } | ConvertTo-Json
    
    Write-Output $response
}
