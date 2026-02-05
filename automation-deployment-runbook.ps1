param(
    [Parameter(Mandatory=$true)]
    [string]$Command,
    
    [Parameter(Mandatory=$true)]
    [string]$ResourceName,
    
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    
    [Parameter(Mandatory=$true)]
    [string]$ResourceType,
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "westeurope",
    
    [Parameter(Mandatory=$false)]
    [string]$RequestId
)

Write-Output "=========================================="
Write-Output "Azure Infrastructure Deployment Runbook"
Write-Output "=========================================="
Write-Output "Request ID: $RequestId"
Write-Output "Resource Type: $ResourceType"
Write-Output "Resource Name: $ResourceName"
Write-Output "Resource Group: $ResourceGroup"
Write-Output "Location: $Location"
Write-Output "Command: $Command"
Write-Output "=========================================="

try {
    # Connect using managed identity
    Write-Output "Connecting to Azure using Managed Identity..."
    Connect-AzAccount -Identity | Out-Null
    Write-Output "✓ Connected successfully"
    
    # Execute the CLI command
    Write-Output "`nExecuting deployment command..."
    Write-Output "Command: $Command"
    
    $result = Invoke-Expression $Command
    
    if ($LASTEXITCODE -eq 0) {
        Write-Output "`n✓ Deployment completed successfully"
        Write-Output "Result: $result"
        
        # Verify resource was created
        Write-Output "`nVerifying resource creation..."
        $checkCommand = "az resource show --name '$ResourceName' --resource-group '$ResourceGroup' --resource-type '$ResourceType' --query '{name:name,location:location,provisioningState:properties.provisioningState}' --output json 2>&1"
        $verification = Invoke-Expression $checkCommand
        
        if ($LASTEXITCODE -eq 0) {
            Write-Output "✓ Resource verified: $verification"
        } else {
            Write-Output "⚠ Could not verify resource (may still be creating): $verification"
        }
        
        Write-Output "`n=========================================="
        Write-Output "DEPLOYMENT STATUS: SUCCESS"
        Write-Output "=========================================="
        
    } else {
        Write-Error "Deployment failed with exit code: $LASTEXITCODE"
        Write-Error "Output: $result"
        throw "Deployment command failed"
    }
    
} catch {
    Write-Error "=========================================="
    Write-Error "DEPLOYMENT STATUS: FAILED"
    Write-Error "=========================================="
    Write-Error "Error: $_"
    Write-Error "Error Details: $($_.Exception.Message)"
    throw $_
}
