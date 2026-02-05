<#
.SYNOPSIS
    Fully Automated Deployment Script for Azure CloudOps Intelligence Agent
    
.DESCRIPTION
    This script creates ALL required Azure resources from scratch:
    - Azure OpenAI (AI Foundry) with GPT-4o model
    - Azure Container Registry
    - Azure Container Apps Environment
    - Azure Container App with Managed Identity
    - All RBAC role assignments
    
    NO manual configuration required - everything is automated!

.PARAMETER ResourceGroupName
    Name of the resource group to create/use

.PARAMETER Location
    Azure region for deployment (default: westeurope)

.PARAMETER OpenAIResourceName
    Name for the Azure OpenAI resource (default: auto-generated)

.PARAMETER ContainerRegistryName
    Name for Azure Container Registry (must be globally unique, lowercase, no dashes)

.PARAMETER ContainerAppName
    Name for the Container App (default: cloudops-agent)

.EXAMPLE
    .\deploy-automated.ps1 -ResourceGroupName "rg-cloudops-agent" -Location "westeurope" -ContainerRegistryName "mycrname"

.NOTES
    Author: Zahir Hussain Shah
    Website: www.zahir.cloud
    Email: zahir@zahir.cloud
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "westeurope",
    
    [Parameter(Mandatory=$false)]
    [string]$OpenAIResourceName = "",
    
    [Parameter(Mandatory=$true)]
    [string]$ContainerRegistryName,
    
    [Parameter(Mandatory=$false)]
    [string]$ContainerAppName = "cloudops-agent",
    
    [Parameter(Mandatory=$false)]
    [string]$ContainerAppEnvName = "cloudops-env"
)

# ============================================
# CONFIGURATION
# ============================================
$ErrorActionPreference = "Stop"
$OpenAIModelName = "gpt-4o"
$OpenAIDeploymentName = "gpt-4o"
$OpenAIApiVersion = "2024-02-15-preview"
$ContainerImageName = "cloudops-agent"
$ContainerImageTag = "latest"

# Generate unique names if not provided
if ([string]::IsNullOrEmpty($OpenAIResourceName)) {
    $randomSuffix = -join ((48..57) + (97..122) | Get-Random -Count 6 | ForEach-Object {[char]$_})
    $OpenAIResourceName = "openai-cloudops-$randomSuffix"
}

# ============================================
# HELPER FUNCTIONS
# ============================================
function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "  ✅ $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "  ℹ️  $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "  ❌ $Message" -ForegroundColor Red
}

# ============================================
# PRE-FLIGHT CHECKS
# ============================================
Write-Step "Pre-Flight Checks"

# Check Azure CLI is installed
Write-Info "Checking Azure CLI installation..."
$azVersion = az version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Azure CLI is not installed. Please install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
}
Write-Success "Azure CLI is installed"

# Check Azure CLI login
Write-Info "Checking Azure CLI login status..."
$account = az account show 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Info "Not logged in. Running 'az login'..."
    az login
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to login to Azure"
        exit 1
    }
}
Write-Success "Logged in to Azure"

# Get subscription info
$subscriptionId = az account show --query "id" -o tsv
$subscriptionName = az account show --query "name" -o tsv
Write-Success "Using subscription: $subscriptionName ($subscriptionId)"

# ============================================
# STEP 1: CREATE RESOURCE GROUP
# ============================================
Write-Step "Step 1: Creating Resource Group"

$rgExists = az group exists --name $ResourceGroupName
if ($rgExists -eq "true") {
    Write-Info "Resource group '$ResourceGroupName' already exists"
} else {
    Write-Info "Creating resource group '$ResourceGroupName' in '$Location'..."
    az group create --name $ResourceGroupName --location $Location --output none
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create resource group"
        exit 1
    }
}
Write-Success "Resource group ready: $ResourceGroupName"

# ============================================
# STEP 2: CREATE AZURE OPENAI RESOURCE
# ============================================
Write-Step "Step 2: Creating Azure OpenAI Resource (AI Foundry)"

# Check if OpenAI resource exists
$openaiExists = az cognitiveservices account show --name $OpenAIResourceName --resource-group $ResourceGroupName 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Info "Azure OpenAI resource '$OpenAIResourceName' already exists"
} else {
    Write-Info "Creating Azure OpenAI resource '$OpenAIResourceName'..."
    Write-Info "This may take 2-3 minutes..."
    
    az cognitiveservices account create `
        --name $OpenAIResourceName `
        --resource-group $ResourceGroupName `
        --location $Location `
        --kind "OpenAI" `
        --sku "S0" `
        --custom-domain $OpenAIResourceName `
        --output none
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create Azure OpenAI resource"
        Write-Info "Note: Azure OpenAI requires approval. If you haven't requested access, apply at: https://aka.ms/oai/access"
        exit 1
    }
}
Write-Success "Azure OpenAI resource ready: $OpenAIResourceName"

# Get OpenAI endpoint
$openaiEndpoint = az cognitiveservices account show `
    --name $OpenAIResourceName `
    --resource-group $ResourceGroupName `
    --query "properties.endpoint" -o tsv

Write-Success "OpenAI Endpoint: $openaiEndpoint"

# ============================================
# STEP 3: DEPLOY GPT-4O MODEL
# ============================================
Write-Step "Step 3: Deploying GPT-4o Model"

# Check if deployment exists
$deploymentExists = az cognitiveservices account deployment show `
    --name $OpenAIResourceName `
    --resource-group $ResourceGroupName `
    --deployment-name $OpenAIDeploymentName 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Info "Model deployment '$OpenAIDeploymentName' already exists"
} else {
    Write-Info "Deploying GPT-4o model..."
    Write-Info "This may take 3-5 minutes..."
    
    az cognitiveservices account deployment create `
        --name $OpenAIResourceName `
        --resource-group $ResourceGroupName `
        --deployment-name $OpenAIDeploymentName `
        --model-name $OpenAIModelName `
        --model-version "2024-08-06" `
        --model-format "OpenAI" `
        --sku-capacity 30 `
        --sku-name "GlobalStandard" `
        --output none
    
    if ($LASTEXITCODE -ne 0) {
        Write-Info "Trying alternative model version..."
        az cognitiveservices account deployment create `
            --name $OpenAIResourceName `
            --resource-group $ResourceGroupName `
            --deployment-name $OpenAIDeploymentName `
            --model-name $OpenAIModelName `
            --model-version "2024-05-13" `
            --model-format "OpenAI" `
            --sku-capacity 30 `
            --sku-name "Standard" `
            --output none
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to deploy GPT-4o model. Please check model availability in your region."
            exit 1
        }
    }
}
Write-Success "GPT-4o model deployed: $OpenAIDeploymentName"

# ============================================
# STEP 4: CREATE CONTAINER REGISTRY
# ============================================
Write-Step "Step 4: Creating Azure Container Registry"

# Validate ACR name (lowercase, no dashes, 5-50 chars)
$acrNameClean = $ContainerRegistryName.ToLower() -replace '[^a-z0-9]', ''
if ($acrNameClean.Length -lt 5 -or $acrNameClean.Length -gt 50) {
    Write-Error "Container Registry name must be 5-50 alphanumeric characters"
    exit 1
}

$acrExists = az acr show --name $acrNameClean --resource-group $ResourceGroupName 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Info "Container Registry '$acrNameClean' already exists"
} else {
    Write-Info "Creating Container Registry '$acrNameClean'..."
    az acr create `
        --name $acrNameClean `
        --resource-group $ResourceGroupName `
        --sku Basic `
        --admin-enabled true `
        --output none
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create Container Registry"
        exit 1
    }
}
Write-Success "Container Registry ready: $acrNameClean"

# Get ACR credentials
$acrServer = "$acrNameClean.azurecr.io"
$acrUsername = az acr credential show --name $acrNameClean --query "username" -o tsv
$acrPassword = az acr credential show --name $acrNameClean --query "passwords[0].value" -o tsv

# ============================================
# STEP 5: BUILD AND PUSH CONTAINER IMAGE
# ============================================
Write-Step "Step 5: Building and Pushing Container Image"

Write-Info "Building container image using ACR Tasks..."
Write-Info "This may take 3-5 minutes..."

az acr build `
    --registry $acrNameClean `
    --image "${ContainerImageName}:${ContainerImageTag}" `
    --file Dockerfile `
    . `
    --output none

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to build container image"
    exit 1
}
Write-Success "Container image built and pushed: $acrServer/${ContainerImageName}:${ContainerImageTag}"

# ============================================
# STEP 6: CREATE CONTAINER APPS ENVIRONMENT
# ============================================
Write-Step "Step 6: Creating Container Apps Environment"

$envExists = az containerapp env show --name $ContainerAppEnvName --resource-group $ResourceGroupName 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Info "Container Apps Environment '$ContainerAppEnvName' already exists"
} else {
    Write-Info "Creating Container Apps Environment..."
    Write-Info "This may take 2-3 minutes..."
    
    az containerapp env create `
        --name $ContainerAppEnvName `
        --resource-group $ResourceGroupName `
        --location $Location `
        --output none
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create Container Apps Environment"
        exit 1
    }
}
Write-Success "Container Apps Environment ready: $ContainerAppEnvName"

# ============================================
# STEP 7: DEPLOY CONTAINER APP
# ============================================
Write-Step "Step 7: Deploying Container App"

$appExists = az containerapp show --name $ContainerAppName --resource-group $ResourceGroupName 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Info "Container App '$ContainerAppName' already exists, updating..."
    
    az containerapp update `
        --name $ContainerAppName `
        --resource-group $ResourceGroupName `
        --image "$acrServer/${ContainerImageName}:${ContainerImageTag}" `
        --output none
} else {
    Write-Info "Creating Container App '$ContainerAppName'..."
    
    az containerapp create `
        --name $ContainerAppName `
        --resource-group $ResourceGroupName `
        --environment $ContainerAppEnvName `
        --image "$acrServer/${ContainerImageName}:${ContainerImageTag}" `
        --target-port 8000 `
        --ingress external `
        --min-replicas 1 `
        --max-replicas 3 `
        --cpu 1.0 `
        --memory 2.0Gi `
        --registry-server $acrServer `
        --registry-username $acrUsername `
        --registry-password $acrPassword `
        --env-vars `
            "AZURE_OPENAI_ENDPOINT=$openaiEndpoint" `
            "AZURE_OPENAI_DEPLOYMENT_NAME=$OpenAIDeploymentName" `
            "AZURE_OPENAI_API_VERSION=$OpenAIApiVersion" `
            "AZURE_SUBSCRIPTION_ID=$subscriptionId" `
            "USE_MANAGED_IDENTITY=true" `
            "ENABLE_APPROVAL_WORKFLOW=false" `
        --output none
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create Container App"
        exit 1
    }
}
Write-Success "Container App deployed: $ContainerAppName"

# ============================================
# STEP 8: ENABLE MANAGED IDENTITY
# ============================================
Write-Step "Step 8: Configuring Managed Identity"

Write-Info "Enabling system-assigned managed identity..."
az containerapp identity assign `
    --name $ContainerAppName `
    --resource-group $ResourceGroupName `
    --system-assigned `
    --output none

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to enable managed identity"
    exit 1
}

# Get principal ID
$principalId = az containerapp show `
    --name $ContainerAppName `
    --resource-group $ResourceGroupName `
    --query "identity.principalId" -o tsv

Write-Success "Managed Identity enabled. Principal ID: $principalId"

# ============================================
# STEP 9: ASSIGN RBAC ROLES
# ============================================
Write-Step "Step 9: Assigning RBAC Roles"

$roles = @(
    @{Name="Reader"; Description="For resource queries"},
    @{Name="Cost Management Reader"; Description="For cost analysis"},
    @{Name="Cognitive Services OpenAI User"; Description="For Azure OpenAI access"}
)

foreach ($role in $roles) {
    Write-Info "Assigning '$($role.Name)' role..."
    
    az role assignment create `
        --assignee $principalId `
        --role $role.Name `
        --scope "/subscriptions/$subscriptionId" `
        --output none 2>&1 | Out-Null
    
    Write-Success "$($role.Name) - $($role.Description)"
}

# Assign OpenAI role specifically to the OpenAI resource
Write-Info "Assigning OpenAI access to the specific resource..."
az role assignment create `
    --assignee $principalId `
    --role "Cognitive Services OpenAI User" `
    --scope "/subscriptions/$subscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.CognitiveServices/accounts/$OpenAIResourceName" `
    --output none 2>&1 | Out-Null

Write-Success "All RBAC roles assigned"

# ============================================
# STEP 10: GET APPLICATION URL
# ============================================
Write-Step "Step 10: Retrieving Application URL"

Start-Sleep -Seconds 5  # Wait for deployment to stabilize

$appUrl = az containerapp show `
    --name $ContainerAppName `
    --resource-group $ResourceGroupName `
    --query "properties.configuration.ingress.fqdn" -o tsv

# ============================================
# DEPLOYMENT SUMMARY
# ============================================
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    DEPLOYMENT SUCCESSFUL! 🎉                      ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "📋 DEPLOYMENT SUMMARY" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  Resource Group:        $ResourceGroupName" -ForegroundColor White
Write-Host "  Location:              $Location" -ForegroundColor White
Write-Host "  Azure OpenAI:          $OpenAIResourceName" -ForegroundColor White
Write-Host "  OpenAI Endpoint:       $openaiEndpoint" -ForegroundColor White
Write-Host "  Model Deployment:      $OpenAIDeploymentName" -ForegroundColor White
Write-Host "  Container Registry:    $acrNameClean" -ForegroundColor White
Write-Host "  Container App:         $ContainerAppName" -ForegroundColor White
Write-Host "  Subscription:          $subscriptionId" -ForegroundColor White
Write-Host ""
Write-Host "🌐 APPLICATION URL" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  https://$appUrl" -ForegroundColor Green
Write-Host ""
Write-Host "🔐 ASSIGNED RBAC ROLES" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  ✅ Reader (Subscription scope)" -ForegroundColor White
Write-Host "  ✅ Cost Management Reader (Subscription scope)" -ForegroundColor White
Write-Host "  ✅ Cognitive Services OpenAI User (OpenAI resource)" -ForegroundColor White
Write-Host ""
Write-Host "📝 NEXT STEPS" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  1. Open the application URL in your browser" -ForegroundColor White
Write-Host "  2. Wait 1-2 minutes for the container to fully start" -ForegroundColor White
Write-Host "  3. Start chatting with your Azure infrastructure!" -ForegroundColor White
Write-Host ""
Write-Host "  (Optional) To enable multi-subscription access:" -ForegroundColor Yellow
Write-Host "  Assign 'Reader' and 'Cost Management Reader' roles to other subscriptions" -ForegroundColor Yellow
Write-Host ""
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  Author: Zahir Hussain Shah" -ForegroundColor Gray
Write-Host "  Website: www.zahir.cloud | Email: zahir@zahir.cloud" -ForegroundColor Gray
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
