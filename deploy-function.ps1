# Deploy Azure Function for CLI Execution

# Variables
$functionAppName = "func-cli-executor-$((Get-Random -Minimum 1000 -Maximum 9999))"
$resourceGroup = "Az-AICost-Agent-RG"
$location = "westeurope"
$storageAccount = "stfuncexec$((Get-Random -Minimum 10000 -Maximum 99999))"
$runtime = "python"
$runtimeVersion = "3.11"

Write-Host "🚀 Deploying Azure Function for CLI Execution..." -ForegroundColor Cyan
Write-Host "📦 Function App: $functionAppName" -ForegroundColor Yellow

# Create storage account
Write-Host "`n📁 Creating storage account..." -ForegroundColor Cyan
az storage account create `
    --name $storageAccount `
    --resource-group $resourceGroup `
    --location $location `
    --sku Standard_LRS `
    --kind StorageV2 `
    --allow-shared-key-access true `
    --allow-blob-public-access false

# Create Function App (Linux with Python 3.11)
Write-Host "`n⚡ Creating Function App..." -ForegroundColor Cyan
az functionapp create `
    --name $functionAppName `
    --resource-group $resourceGroup `
    --storage-account $storageAccount `
    --runtime $runtime `
    --runtime-version $runtimeVersion `
    --functions-version 4 `
    --os-type Linux `
    --consumption-plan-location $location

# Enable Managed Identity
Write-Host "`n🔐 Enabling Managed Identity..." -ForegroundColor Cyan
az functionapp identity assign `
    --name $functionAppName `
    --resource-group $resourceGroup

# Get the Managed Identity principal ID
$principalId = (az functionapp identity show `
    --name $functionAppName `
    --resource-group $resourceGroup `
    --query principalId -o tsv)

Write-Host "✅ Managed Identity Principal ID: $principalId" -ForegroundColor Green

# Assign Contributor role at subscription level
Write-Host "`n🔑 Assigning Contributor role..." -ForegroundColor Cyan
$subscriptionId = (az account show --query id -o tsv)
az role assignment create `
    --assignee $principalId `
    --role "Contributor" `
    --scope "/subscriptions/$subscriptionId"

# Configure App Settings (Enable Azure CLI)
Write-Host "`n⚙️ Configuring app settings..." -ForegroundColor Cyan
az functionapp config appsettings set `
    --name $functionAppName `
    --resource-group $resourceGroup `
    --settings "AZURE_SUBSCRIPTION_ID=$subscriptionId" "FUNCTIONS_WORKER_RUNTIME=python"

# Deploy function code
Write-Host "`n📤 Deploying function code..." -ForegroundColor Cyan
Push-Location azure_function
func azure functionapp publish $functionAppName
Pop-Location

# Get Function URL
Write-Host "`n🔗 Getting Function URL..." -ForegroundColor Cyan
$functionUrl = (az functionapp function show `
    --name $functionAppName `
    --resource-group $resourceGroup `
    --function-name execute-deployment `
    --query invokeUrlTemplate -o tsv)

$functionKey = (az functionapp keys list `
    --name $functionAppName `
    --resource-group $resourceGroup `
    --query functionKeys.default -o tsv)

$fullUrl = "$functionUrl&code=$functionKey"

Write-Host "`n✅ Deployment Complete!" -ForegroundColor Green
Write-Host "📋 Function App Name: $functionAppName" -ForegroundColor Yellow
Write-Host "🔗 Function URL: $fullUrl" -ForegroundColor Yellow
Write-Host "`n📝 Next Steps:" -ForegroundColor Cyan
Write-Host "1. Copy the Function URL above" -ForegroundColor White
Write-Host "2. Update FUNCTION_EXECUTOR_URL in .env file" -ForegroundColor White
Write-Host "3. Deploy updated Logic App workflow" -ForegroundColor White
