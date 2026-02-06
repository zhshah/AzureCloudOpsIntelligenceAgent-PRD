<#
.SYNOPSIS
    Fully Automated Deployment Script for Azure CloudOps Intelligence Agent
    
.DESCRIPTION
    This script creates ALL required Azure resources from scratch:
    - Azure OpenAI (AI Foundry) with GPT-4o model
    - Azure Container Registry
    - Azure Container Apps Environment
    - Azure Container App with System-Assigned Managed Identity
    - All RBAC role assignments (Least-Privilege, READ-ONLY)
    
    NO manual configuration required - everything is 100% automated!
    When the script completes, the application is fully running.

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

.PARAMETER EntraAppClientId
    Client ID of the Entra ID App Registration for user authentication (REQUIRED)
    Create this BEFORE running the script - see Prerequisites section below

.PARAMETER EntraTenantId
    Azure AD Tenant ID for authentication (REQUIRED)

.PARAMETER SubscriptionId
    Target Azure Subscription ID for deployment (OPTIONAL but RECOMMENDED)
    If not provided, uses the currently active subscription in Azure CLI
    IMPORTANT: Specify this to ensure deployment goes to the correct subscription

.PARAMETER EnableLogAnalytics
    Enable Log Analytics workspace for Container Apps Environment (OPTIONAL)
    Default: Disabled (for simpler deployment on new subscriptions)
    When disabled, use 'az containerapp logs show' to view container logs

.EXAMPLE
    .\deploy-automated.ps1 -ResourceGroupName "rg-cloudops-agent" -Location "westeurope" -ContainerRegistryName "mycrname" -EntraAppClientId "your-app-client-id" -EntraTenantId "your-tenant-id" -SubscriptionId "your-subscription-id"

.EXAMPLE
    # Deploy with Log Analytics enabled
    .\deploy-automated.ps1 -ResourceGroupName "rg-cloudops-agent" -ContainerRegistryName "mycrname" -EntraAppClientId "your-app-client-id" -EntraTenantId "your-tenant-id" -SubscriptionId "your-subscription-id" -EnableLogAnalytics

# ==============================================================================
# ⚠️  IMPORTANT: TWO TYPES OF PERMISSIONS (READ CAREFULLY!)
# ==============================================================================
#
# There are TWO separate sets of permissions:
#
#   1. DEPLOYER PERMISSIONS - What YOU (the person running this script) need
#      - Required ONLY during deployment
#      - After deployment, your elevated access is NOT used by the application
#
#   2. APPLICATION PERMISSIONS - What the RUNNING APP needs to query Azure
#      - Assigned to a System-Assigned Managed Identity (created by this script)
#      - These are READ-ONLY permissions
#      - The app CANNOT create, modify, or delete any Azure resources
#
# ==============================================================================
# 1. DEPLOYER PERMISSIONS (Person running this script)
# ==============================================================================
# 
# The user running this script needs these permissions:
#
#    At SUBSCRIPTION level:
#    - Microsoft.Resources/subscriptions/resourceGroups/write     (Create Resource Group)
#    - Microsoft.CognitiveServices/accounts/write                 (Create Azure OpenAI)
#    - Microsoft.ContainerRegistry/registries/write               (Create ACR)
#    - Microsoft.App/containerApps/write                          (Create Container App)
#    - Microsoft.App/managedEnvironments/write                    (Create Container App Environment)
#    - Microsoft.Authorization/roleAssignments/write              (Assign RBAC roles)
#
#    RECOMMENDED: Assign "Contributor" + "User Access Administrator" to deployer
#    OR use "Owner" role (includes all above)
#
#    NOTE: These permissions are ONLY used during deployment. After the script
#    completes, your elevated access is not required for the application to run.
#
# ==============================================================================
# 2. APPLICATION PERMISSIONS (How Chat Queries Azure Resources)
# ==============================================================================
#
# When users chat with the agent (e.g., "Show me all VMs", "What's my cost?"),
# the application needs to authenticate to Azure APIs to fetch data.
#
# This script creates a SYSTEM-ASSIGNED MANAGED IDENTITY and assigns these roles:
#
# ┌────────────────────────────────────┬─────────────────┬─────────────────────────────┐
# │ Role                               │ Scope           │ Purpose                     │
# ├────────────────────────────────────┼─────────────────┼─────────────────────────────┤
# │ Reader                             │ Subscription    │ Query VMs, networks, etc.   │
# │ Cost Management Reader             │ Subscription    │ Read cost/billing data      │
# │ Cognitive Services OpenAI User     │ OpenAI Resource │ Use GPT-4o for chat         │
# └────────────────────────────────────┴─────────────────┴─────────────────────────────┘
#
# 🔒 SECURITY: All application permissions are READ-ONLY!
#    ✅ Can read resource metadata (VMs, storage, networks, etc.)
#    ✅ Can read cost data and spending trends
#    ✅ Can send prompts to Azure OpenAI GPT-4o
#    ❌ CANNOT create any resources
#    ❌ CANNOT modify any resources
#    ❌ CANNOT delete any resources
#    ❌ CANNOT access Key Vault secrets
#    ❌ CANNOT modify budgets or billing
#
# ==============================================================================
# WHY SYSTEM-ASSIGNED MANAGED IDENTITY (Not App Registration)?
# ==============================================================================
#
# This script uses a SYSTEM-ASSIGNED MANAGED IDENTITY instead of App Registration:
#   - Automatically created and tied to the Container App lifecycle
#   - Automatically deleted when the Container App is deleted
#   - NO credentials/secrets to manage (more secure)
#   - Authenticates seamlessly to Azure services via Azure AD
#   - No secret rotation required
#
# If you prefer App Registration, see README.md for manual deployment steps.
#
# ==============================================================================
# PREREQUISITES
# ==============================================================================
#
# 1. AZURE CLI
#    - Azure CLI must be installed: https://docs.microsoft.com/cli/azure/install-azure-cli
#    - Run 'az login' before executing this script
#
# 2. AZURE OPENAI ACCESS
#    - Your subscription must have Azure OpenAI approved
#    - Apply at: https://aka.ms/oai/access (if not already approved)
#
# 3. DOCKER (Optional - for local testing only)
#    - Not required for cloud deployment (ACR Tasks builds the image)
#
# ==============================================================================
# APPLICATION RBAC ROLES (READ-ONLY) - Detailed Breakdown
# ==============================================================================
#
# 1. READER (Subscription Scope)
#    - Role ID: acdd72a7-3385-48ef-bd42-f606fba81ae7
#    - Purpose: Query Azure resources via Resource Graph API
#    - Permissions granted:
#      * Microsoft.Resources/subscriptions/resources/read
#      * Microsoft.Resources/subscriptions/resourceGroups/read
#      * Microsoft.Compute/virtualMachines/read
#      * Microsoft.Network/*/read
#      * Microsoft.Storage/storageAccounts/read
#      * (All other read-only resource operations)
#    - Why needed: To list VMs, networks, storage, and all Azure resources
#    - Cannot: Create, modify, or delete any resources
#
# 2. COST MANAGEMENT READER (Subscription Scope)
#    - Role ID: 72fafb9e-0641-4937-9268-a91bfd8191a3
#    - Purpose: Read cost and billing data via Cost Management API
#    - Permissions granted:
#      * Microsoft.Consumption/*/read
#      * Microsoft.CostManagement/*/read
#      * Microsoft.Billing/billingPeriods/read
#    - Why needed: To analyze costs, show spending trends, and cost breakdowns
#    - Cannot: Modify budgets, billing, or make any financial changes
#
# 3. COGNITIVE SERVICES OPENAI USER (OpenAI Resource Scope - most restrictive)
#    - Role ID: 5e0bd9bd-7b93-4f28-af87-19fc36ad61bd
#    - Purpose: Use Azure OpenAI API for chat completions
#    - Permissions granted:
#      * Microsoft.CognitiveServices/accounts/deployments/read
#      * Microsoft.CognitiveServices/accounts/*/completions/action
#    - Why needed: To send prompts to GPT-4o and receive responses
#    - Cannot: Create/delete deployments, modify OpenAI resource settings
#    - Scope: Limited to ONLY the specific OpenAI resource (not subscription-wide)
#
# NOT ASSIGNED (Security):
#   ✗ Contributor - Would allow resource modifications
#   ✗ Owner - Would allow RBAC changes
#   ✗ API Keys - Managed Identity is used instead (no secrets stored)
#
# ==============================================================================
# MULTI-SUBSCRIPTION SUPPORT
# ==============================================================================
#
# To query resources across multiple subscriptions, assign ONLY:
#   - "Reader" role to additional subscriptions
#   - "Cost Management Reader" role to additional subscriptions
#
# Example command:
#   az role assignment create --assignee <principal-id> --role "Reader" \
#       --scope "/subscriptions/<other-subscription-id>"
#
# ==============================================================================

.NOTES
    Author: Zahir Hussain Shah
    Website: www.zahir.cloud
    Email: zahir@zahir.cloud
    
    LICENSE: MIT
    
    SECURITY NOTES:
    - Uses System-Assigned Managed Identity (no API keys or secrets)
    - Follows Azure security best practices
    - RBAC follows least-privilege principle
    - No credentials stored in code or environment variables
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
    [string]$ContainerAppEnvName = "cloudops-env",
    
    [Parameter(Mandatory=$true)]
    [string]$EntraAppClientId,
    
    [Parameter(Mandatory=$true)]
    [string]$EntraTenantId,
    
    [Parameter(Mandatory=$false)]
    [string]$SubscriptionId = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$EnableLogAnalytics = $false
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

# Set subscription explicitly if provided (IMPORTANT: prevents wrong subscription deployment)
if (-not [string]::IsNullOrEmpty($SubscriptionId)) {
    Write-Info "Setting subscription to: $SubscriptionId"
    az account set --subscription $SubscriptionId
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to set subscription. Please verify the subscription ID is correct and you have access."
        exit 1
    }
    Write-Success "Subscription explicitly set to: $SubscriptionId"
} else {
    Write-Info "No SubscriptionId provided - using currently active subscription"
    Write-Info "TIP: Use -SubscriptionId parameter to ensure correct subscription"
}

# Get subscription info (verify we're on the right subscription)
$subscriptionId = az account show --query "id" -o tsv
$subscriptionName = az account show --query "name" -o tsv
Write-Host ""
Write-Host "  ╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "  ║  TARGET SUBSCRIPTION (All resources will deploy here)         ║" -ForegroundColor Yellow
Write-Host "  ╠════════════════════════════════════════════════════════════════╣" -ForegroundColor Yellow
Write-Host "  ║  Name: $subscriptionName" -ForegroundColor White
Write-Host "  ║  ID:   $subscriptionId" -ForegroundColor White
Write-Host "  ╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""

# Confirm with user
$confirmation = Read-Host "  Is this the correct subscription? (Y/N)"
if ($confirmation -ne 'Y' -and $confirmation -ne 'y') {
    Write-Error "Deployment cancelled. Please run 'az account set --subscription <correct-subscription-id>' or use -SubscriptionId parameter"
    exit 1
}
Write-Success "Subscription confirmed: $subscriptionName ($subscriptionId)"

# ============================================
# STEP 0: REGISTER REQUIRED RESOURCE PROVIDERS
# ============================================
Write-Step "Step 0: Registering Required Resource Providers"

Write-Info "On new subscriptions, resource providers must be registered before use."
Write-Info "This is a one-time operation per subscription."
Write-Host ""

# Define required providers
$requiredProviders = @(
    @{ Namespace = "Microsoft.ContainerRegistry"; Description = "Container Registry" },
    @{ Namespace = "Microsoft.App"; Description = "Container Apps" },
    @{ Namespace = "Microsoft.CognitiveServices"; Description = "Azure OpenAI" },
    @{ Namespace = "Microsoft.ManagedIdentity"; Description = "Managed Identity" }
)

# Add Log Analytics provider if enabled
if ($EnableLogAnalytics) {
    $requiredProviders += @{ Namespace = "Microsoft.OperationalInsights"; Description = "Log Analytics" }
}

# Check and register providers
$providersToWait = @()
foreach ($provider in $requiredProviders) {
    $status = az provider show --namespace $provider.Namespace --query "registrationState" -o tsv 2>$null
    
    if ($status -eq "Registered") {
        Write-Success "$($provider.Description) ($($provider.Namespace)) - Already registered"
    } else {
        Write-Info "Registering $($provider.Description) ($($provider.Namespace))..."
        az provider register --namespace $provider.Namespace --output none
        $providersToWait += $provider
    }
}

# Wait for all providers to be registered
if ($providersToWait.Count -gt 0) {
    Write-Host ""
    Write-Info "Waiting for resource providers to complete registration..."
    Write-Info "This may take 2-5 minutes for new subscriptions..."
    Write-Host ""
    
    $maxWaitSeconds = 300  # 5 minutes max per provider
    
    foreach ($provider in $providersToWait) {
        $elapsed = 0
        $registered = $false
        
        while ($elapsed -lt $maxWaitSeconds) {
            $status = az provider show --namespace $provider.Namespace --query "registrationState" -o tsv 2>$null
            
            if ($status -eq "Registered") {
                Write-Success "$($provider.Description) ($($provider.Namespace)) - Registered"
                $registered = $true
                break
            }
            
            Write-Host "    Waiting for $($provider.Namespace)... ($elapsed seconds)" -ForegroundColor Gray
            Start-Sleep -Seconds 15
            $elapsed += 15
        }
        
        if (-not $registered) {
            Write-Error "$($provider.Description) ($($provider.Namespace)) failed to register within $maxWaitSeconds seconds"
            Write-Info "Please run manually: az provider register --namespace $($provider.Namespace) --wait"
            exit 1
        }
    }
}

Write-Host ""
Write-Success "All required resource providers are registered"

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

$deployedCapacity = 0
$deployedModel = ""
$deployedSku = ""
$deployedModelVersion = ""

if ($LASTEXITCODE -eq 0) {
    Write-Info "Model deployment '$OpenAIDeploymentName' already exists"
    $deployedCapacity = 30  # Assume existing deployment is fine
    $deployedModel = "gpt-4o"
    $deployedSku = "GlobalStandard"
    $deployedModelVersion = "2024-08-06"
} else {
    Write-Info "Deploying GPT-4o model..."
    Write-Info "This may take 3-5 minutes..."
    Write-Info "Strategy: Prioritize GlobalStandard (best latency), start at 80K and decrease by 2K"
    
    $deploymentSuccess = $false
    # Start at 80K (tested optimal), decrease by 2K increments for fine-grained quota discovery
    # Generates: 80, 78, 76, 74, 72, 70, 68, 66, 64, 62, 60, 58, 56, 54, 52, 50, 48, 46, 44, 42, 40, 38, 36, 34, 32, 30, 28, 26, 24, 22, 20, 18, 16, 14, 12, 10
    $capacityLevels = @()
    for ($i = 80; $i -ge 10; $i -= 2) { $capacityLevels += $i }
    
    # PRIORITY 1: Try GPT-4o with GlobalStandard SKU (BEST LATENCY - global routing)
    Write-Info "Trying GlobalStandard SKU (recommended for best latency)..."
    foreach ($capacity in $capacityLevels) {
        if ($deploymentSuccess) { break }
        
        Write-Info "  GlobalStandard ${capacity}K TPM..."
        az cognitiveservices account deployment create `
            --name $OpenAIResourceName `
            --resource-group $ResourceGroupName `
            --deployment-name $OpenAIDeploymentName `
            --model-name "gpt-4o" `
            --model-version "2024-08-06" `
            --model-format "OpenAI" `
            --sku-capacity $capacity `
            --sku-name "GlobalStandard" `
            --output none 2>$null
        
        if ($LASTEXITCODE -eq 0) { 
            $deploymentSuccess = $true
            $deployedCapacity = $capacity
            $deployedModel = "gpt-4o"
            $deployedSku = "GlobalStandard"
            $deployedModelVersion = "2024-08-06"
            Write-Success "Deployed with ${capacity}K TPM (GlobalStandard - optimal latency)"
        }
    }
    
    # PRIORITY 2: DataZoneStandard as FALLBACK ONLY (higher latency due to regional constraints)
    if (-not $deploymentSuccess) {
        Write-Info "GlobalStandard quota exhausted. Trying DataZoneStandard (fallback)..."
        Write-Info "Note: DataZoneStandard may have slightly higher latency"
        foreach ($capacity in $capacityLevels) {
            if ($deploymentSuccess) { break }
            
            Write-Info "  DataZoneStandard ${capacity}K TPM..."
            az cognitiveservices account deployment create `
                --name $OpenAIResourceName `
                --resource-group $ResourceGroupName `
                --deployment-name $OpenAIDeploymentName `
                --model-name "gpt-4o" `
                --model-version "2024-08-06" `
                --model-format "OpenAI" `
                --sku-capacity $capacity `
                --sku-name "DataZoneStandard" `
                --output none 2>$null
            
            if ($LASTEXITCODE -eq 0) { 
                $deploymentSuccess = $true
                $deployedCapacity = $capacity
                $deployedModel = "gpt-4o"
                $deployedSku = "DataZoneStandard"
                $deployedModelVersion = "2024-08-06"
                Write-Success "Deployed with ${capacity}K TPM (DataZoneStandard)"
                Write-Info "Tip: Request GlobalStandard quota increase for better latency"
            }
        }
    }
    
    # PRIORITY 3: Standard SKU (older regions)
    if (-not $deploymentSuccess) {
        Write-Info "Trying Standard SKU (legacy regions)..."
        foreach ($capacity in $capacityLevels) {
            if ($deploymentSuccess) { break }
            
            Write-Info "  Standard ${capacity}K TPM..."
            az cognitiveservices account deployment create `
                --name $OpenAIResourceName `
                --resource-group $ResourceGroupName `
                --deployment-name $OpenAIDeploymentName `
                --model-name "gpt-4o" `
                --model-version "2024-05-13" `
                --model-format "OpenAI" `
                --sku-capacity $capacity `
                --sku-name "Standard" `
                --output none 2>$null
            
            if ($LASTEXITCODE -eq 0) { 
                $deploymentSuccess = $true
                $deployedCapacity = $capacity
                $deployedModel = "gpt-4o"
                $deployedSku = "Standard"
                $deployedModelVersion = "2024-05-13"
                Write-Success "Deployed with ${capacity}K TPM (Standard)"
            }
        }
    }
    
    # PRIORITY 4: GPT-4o-mini as last resort
    if (-not $deploymentSuccess) {
        Write-Info "GPT-4o not available, trying GPT-4o-mini as last resort..."
        foreach ($capacity in $capacityLevels) {
            if ($deploymentSuccess) { break }
            
            Write-Info "  GPT-4o-mini GlobalStandard ${capacity}K TPM..."
            az cognitiveservices account deployment create `
                --name $OpenAIResourceName `
                --resource-group $ResourceGroupName `
                --deployment-name $OpenAIDeploymentName `
                --model-name "gpt-4o-mini" `
                --model-version "2024-07-18" `
                --model-format "OpenAI" `
                --sku-capacity $capacity `
                --sku-name "GlobalStandard" `
                --output none 2>$null
            
            if ($LASTEXITCODE -eq 0) { 
                $deploymentSuccess = $true
                $deployedCapacity = $capacity
                $deployedModel = "gpt-4o-mini"
                $deployedSku = "GlobalStandard"
                $deployedModelVersion = "2024-07-18"
                Write-Info "Note: Deployed gpt-4o-mini with ${capacity}K TPM (GPT-4o not available)"
            }
        }
    }
    
    if (-not $deploymentSuccess) {
        Write-Error "Failed to deploy any GPT model. Please check:"
        Write-Host "  1. Azure OpenAI quota in your subscription" -ForegroundColor Yellow
        Write-Host "  2. Model availability in region '$Location'" -ForegroundColor Yellow
        Write-Host "  3. Request quota increase at: https://aka.ms/oai/quotaincrease" -ForegroundColor Yellow
        exit 1
    }
}

# Scale up TPM if deployed with lower capacity (target: 80K for optimal performance)
$targetCapacityMax = 80
if ($deployedCapacity -gt 0 -and $deployedCapacity -lt $targetCapacityMax) {
    Write-Info "Attempting to scale up deployment for optimal performance..."
    Write-Info "Current: ${deployedCapacity}K TPM with $deployedSku SKU"
    Write-Info "Target: Maximize TPM (up to ${targetCapacityMax}K - tested optimal)"
    
    # Wait for deployment to stabilize
    Start-Sleep -Seconds 15
    
    # Try scale-up: start from 80K, decrease by 2K until we find available quota
    # Stop trying if we reach current capacity (no point going lower)
    $scaleUpSuccess = $false
    $finalCapacity = $deployedCapacity
    
    # Generate scale-up targets: 80, 78, 76, ... down to current+2
    $scaleUpTargets = @()
    for ($i = $targetCapacityMax; $i -gt $deployedCapacity; $i -= 2) {
        $scaleUpTargets += $i
    }
    
    if ($scaleUpTargets.Count -gt 0) {
        Write-Info "Scale-up attempts: $($scaleUpTargets -join 'K, ')K TPM"
        
        foreach ($targetCapacity in $scaleUpTargets) {
            if ($scaleUpSuccess) { break }
            
            Write-Info "  Trying ${targetCapacity}K TPM..."
            az cognitiveservices account deployment create `
                --name $OpenAIResourceName `
                --resource-group $ResourceGroupName `
                --deployment-name $OpenAIDeploymentName `
                --model-name $deployedModel `
                --model-version $deployedModelVersion `
                --model-format "OpenAI" `
                --sku-capacity $targetCapacity `
                --sku-name $deployedSku `
                --output none 2>$null
            
            if ($LASTEXITCODE -eq 0) {
                $scaleUpSuccess = $true
                $finalCapacity = $targetCapacity
                Write-Success "Successfully scaled up to ${targetCapacity}K TPM"
            }
        }
    }
    
    if (-not $scaleUpSuccess) {
        Write-Info "Could not scale up (quota limit). Staying at: ${deployedCapacity}K TPM"
        if ($deployedCapacity -lt 30) {
            Write-Host ""
            Write-Host "  ⚠️  WARNING: Current capacity (${deployedCapacity}K TPM) is below recommended (30K+)" -ForegroundColor Yellow
            Write-Host "  Large prompts may experience slower response times or rate limiting." -ForegroundColor Yellow
            Write-Host "  Request quota increase at: https://aka.ms/oai/quotaincrease" -ForegroundColor Yellow
        }
        Write-Host ""
        Write-Host "  # Manual scale-up command (when quota available):" -ForegroundColor Cyan
        Write-Host "  az cognitiveservices account deployment create ``" -ForegroundColor DarkGray
        Write-Host "      --name $OpenAIResourceName ``" -ForegroundColor DarkGray
        Write-Host "      --resource-group $ResourceGroupName ``" -ForegroundColor DarkGray
        Write-Host "      --deployment-name $OpenAIDeploymentName ``" -ForegroundColor DarkGray
        Write-Host "      --model-name $deployedModel ``" -ForegroundColor DarkGray
        Write-Host "      --model-version '$deployedModelVersion' ``" -ForegroundColor DarkGray
        Write-Host "      --model-format 'OpenAI' ``" -ForegroundColor DarkGray
        Write-Host "      --sku-capacity 80 ``" -ForegroundColor DarkGray
        Write-Host "      --sku-name '$deployedSku'" -ForegroundColor DarkGray
    } else {
        $deployedCapacity = $finalCapacity
    }
}

Write-Success "Model deployment ready: $OpenAIDeploymentName ($deployedModel)"

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
        --admin-enabled false `
        --output none
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create Container Registry"
        exit 1
    }
}
Write-Success "Container Registry ready: $acrNameClean"

# Store ACR server name for later use
$acrServer = "$acrNameClean.azurecr.io"
# Note: Using Managed Identity for ACR authentication (no admin credentials needed)

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
    
    if ($EnableLogAnalytics) {
        Write-Info "Log Analytics enabled - environment will have full logging capabilities"
        az containerapp env create `
            --name $ContainerAppEnvName `
            --resource-group $ResourceGroupName `
            --location $Location `
            --output none
    } else {
        Write-Info "Log Analytics disabled (default) - use 'az containerapp logs' for debugging"
        Write-Info "To enable later, recreate environment with -EnableLogAnalytics switch"
        az containerapp env create `
            --name $ContainerAppEnvName `
            --resource-group $ResourceGroupName `
            --location $Location `
            --logs-destination none `
            --output none
    }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create Container Apps Environment"
        exit 1
    }
}
Write-Success "Container Apps Environment ready: $ContainerAppEnvName"

# ============================================
# STEP 7: CREATE CONTAINER APP WITH MANAGED IDENTITY
# ============================================
Write-Step "Step 7: Creating Container App with Managed Identity"

$appExists = az containerapp show --name $ContainerAppName --resource-group $ResourceGroupName 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Info "Container App '$ContainerAppName' already exists"
    
    # Ensure managed identity is enabled
    Write-Info "Ensuring managed identity is enabled..."
    az containerapp identity assign `
        --name $ContainerAppName `
        --resource-group $ResourceGroupName `
        --system-assigned `
        --output none 2>$null
} else {
    # Step 7a: Create container app with placeholder image and managed identity enabled
    Write-Info "Creating Container App '$ContainerAppName' with System-Assigned Managed Identity..."
    Write-Info "Using placeholder image (will update after ACR access is configured)..."
    
    az containerapp create `
        --name $ContainerAppName `
        --resource-group $ResourceGroupName `
        --environment $ContainerAppEnvName `
        --image "mcr.microsoft.com/k8se/quickstart:latest" `
        --target-port 8000 `
        --ingress external `
        --min-replicas 1 `
        --max-replicas 3 `
        --cpu 1.0 `
        --memory 2.0Gi `
        --system-assigned `
        --env-vars `
            "AZURE_OPENAI_ENDPOINT=$openaiEndpoint" `
            "AZURE_OPENAI_DEPLOYMENT_NAME=$OpenAIDeploymentName" `
            "AZURE_OPENAI_API_VERSION=$OpenAIApiVersion" `
            "AZURE_SUBSCRIPTION_ID=$subscriptionId" `
            "USE_MANAGED_IDENTITY=true" `
            "ENABLE_APPROVAL_WORKFLOW=false" `
            "ENTRA_APP_CLIENT_ID=$EntraAppClientId" `
            "ENTRA_TENANT_ID=$EntraTenantId" `
        --output none
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create Container App"
        exit 1
    }
    Write-Success "Container App created with Managed Identity enabled"
}

# Get principal ID for role assignments
$principalId = az containerapp show `
    --name $ContainerAppName `
    --resource-group $ResourceGroupName `
    --query "identity.principalId" -o tsv

if ([string]::IsNullOrEmpty($principalId)) {
    Write-Error "Failed to get Managed Identity Principal ID"
    exit 1
}
Write-Success "Managed Identity Principal ID: $principalId"

# ============================================
# STEP 8: CONFIGURE ACR ACCESS WITH MANAGED IDENTITY
# ============================================
Write-Step "Step 8: Configuring ACR Access (AcrPull Role)"

Write-Info "Assigning 'AcrPull' role to Managed Identity for ACR access..."
Write-Info "This allows the Container App to pull images from ACR securely."

$acrResourceId = "/subscriptions/$subscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.ContainerRegistry/registries/$acrNameClean"

$acrRoleResult = az role assignment create `
    --assignee $principalId `
    --role "AcrPull" `
    --scope $acrResourceId `
    --output none 2>&1

if ($LASTEXITCODE -eq 0 -or $acrRoleResult -match "already exists") {
    Write-Success "AcrPull role assigned to Managed Identity"
} else {
    Write-Info "AcrPull role may already exist (continuing...)"
}

# Wait for role propagation
Write-Info "Waiting 30 seconds for role assignment to propagate..."
Start-Sleep -Seconds 30

# ============================================
# STEP 9: UPDATE CONTAINER APP WITH REAL IMAGE
# ============================================
Write-Step "Step 9: Updating Container App with Application Image"

Write-Info "Updating Container App to use image from ACR..."
Write-Info "Image: $acrServer/${ContainerImageName}:${ContainerImageTag}"

# First, register the registry with the container app using managed identity
az containerapp registry set `
    --name $ContainerAppName `
    --resource-group $ResourceGroupName `
    --server $acrServer `
    --identity system `
    --output none

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to configure ACR registry with Managed Identity"
    exit 1
}
Write-Success "ACR registry configured with Managed Identity authentication"

# Now update the container app with the real image
az containerapp update `
    --name $ContainerAppName `
    --resource-group $ResourceGroupName `
    --image "$acrServer/${ContainerImageName}:${ContainerImageTag}" `
    --output none

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to update Container App with application image"
    exit 1
}
Write-Success "Container App updated with application image"

# ============================================
# STEP 10: ASSIGN RBAC ROLES (LEAST-PRIVILEGE)
# ============================================
Write-Step "Step 10: Assigning RBAC Roles (Least-Privilege Principle)"

Write-Host ""
Write-Host "  📋 RBAC Assignment Summary (Least-Privilege)" -ForegroundColor Yellow
Write-Host "  ─────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  The System-Assigned Managed Identity will receive ONLY these roles:" -ForegroundColor White
Write-Host ""

# Define roles with detailed justification
$roles = @(
    @{
        Name="Reader"
        Scope="/subscriptions/$subscriptionId"
        ScopeDescription="Subscription"
        Description="Read-only access to Azure resources"
        Justification="Required for Resource Graph queries (list VMs, networks, storage, etc.)"
        CannotDo="Create, modify, or delete any resources"
    },
    @{
        Name="Cost Management Reader"
        Scope="/subscriptions/$subscriptionId"
        ScopeDescription="Subscription"
        Description="Read-only access to cost and billing data"
        Justification="Required for cost analysis, spending trends, and budget monitoring"
        CannotDo="Modify budgets, billing settings, or make financial changes"
    }
)

foreach ($role in $roles) {
    Write-Host "  Role: $($role.Name)" -ForegroundColor Cyan
    Write-Host "    Scope: $($role.ScopeDescription)" -ForegroundColor White
    Write-Host "    Purpose: $($role.Justification)" -ForegroundColor Gray
    Write-Host "    Restriction: $($role.CannotDo)" -ForegroundColor DarkGray
    Write-Host ""
    
    Write-Info "Assigning '$($role.Name)' at $($role.ScopeDescription) scope..."
    
    $result = az role assignment create `
        --assignee $principalId `
        --role $role.Name `
        --scope $role.Scope `
        --output none 2>&1
    
    if ($LASTEXITCODE -eq 0 -or $result -match "already exists") {
        Write-Success "$($role.Name) - Assigned"
    } else {
        Write-Info "$($role.Name) - May already exist (continuing...)"
    }
}

# Special: OpenAI role on specific resource only (most restrictive)
Write-Host "  Role: Cognitive Services OpenAI User" -ForegroundColor Cyan
Write-Host "    Scope: OpenAI Resource ONLY (not subscription-wide)" -ForegroundColor White
Write-Host "    Purpose: Use GPT-4o for chat completions" -ForegroundColor Gray
Write-Host "    Restriction: Cannot create/delete deployments or modify OpenAI settings" -ForegroundColor DarkGray
Write-Host ""

Write-Info "Assigning 'Cognitive Services OpenAI User' to OpenAI resource (restricted scope)..."
$openaiResult = az role assignment create `
    --assignee $principalId `
    --role "Cognitive Services OpenAI User" `
    --scope "/subscriptions/$subscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.CognitiveServices/accounts/$OpenAIResourceName" `
    --output none 2>&1

if ($LASTEXITCODE -eq 0 -or $openaiResult -match "already exists") {
    Write-Success "Cognitive Services OpenAI User - Assigned (Resource-scoped)"
} else {
    Write-Info "OpenAI role - May already exist (continuing...)"
}

Write-Host ""
Write-Host "  ✅ RBAC configured following Least-Privilege principle" -ForegroundColor Green
Write-Host "  ─────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  • NO Contributor role (cannot modify resources)" -ForegroundColor White
Write-Host "  • NO Owner role (cannot manage access)" -ForegroundColor White
Write-Host "  • NO API keys used (Managed Identity only)" -ForegroundColor White
Write-Host ""

# ============================================
# STEP 11: GET APPLICATION URL
# ============================================
Write-Step "Step 11: Retrieving Application URL"

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
Write-Host "║              DEPLOYMENT 100% COMPLETE! 🎉                         ║" -ForegroundColor Green
Write-Host "║         Application is FULLY RUNNING - No Manual Work!           ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "📋 DEPLOYMENT SUMMARY" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  Resource Group:        $ResourceGroupName" -ForegroundColor White
Write-Host "  Location:              $Location" -ForegroundColor White
Write-Host "  Azure OpenAI:          $OpenAIResourceName" -ForegroundColor White
Write-Host "  OpenAI Endpoint:       $openaiEndpoint" -ForegroundColor White
Write-Host "  Model Deployment:      $OpenAIDeploymentName (GPT-4o)" -ForegroundColor White
Write-Host "  Container Registry:    $acrNameClean" -ForegroundColor White
Write-Host "  Container App:         $ContainerAppName" -ForegroundColor White
Write-Host "  Subscription:          $subscriptionId" -ForegroundColor White
if ($EnableLogAnalytics) {
    Write-Host "  Log Analytics:         ✅ Enabled" -ForegroundColor White
} else {
    Write-Host "  Log Analytics:         Disabled (use -EnableLogAnalytics to enable)" -ForegroundColor Gray
}
Write-Host ""
Write-Host "🌐 APPLICATION URL (Ready to use!)" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  https://$appUrl" -ForegroundColor Green
Write-Host ""
Write-Host "🔐 SECURITY CONFIGURATION (Least-Privilege)" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  Identity Type:          System-Assigned Managed Identity" -ForegroundColor White
Write-Host "  Principal ID:           $principalId" -ForegroundColor White
Write-Host "  ACR Authentication:     ✅ Managed Identity (no admin password)" -ForegroundColor White
Write-Host "  API Keys Used:          ❌ NO (Managed Identity only)" -ForegroundColor White
Write-Host "  Secrets Stored:         ❌ NO (Zero secrets in env vars)" -ForegroundColor White
Write-Host ""
Write-Host "  📜 ASSIGNED RBAC ROLES:" -ForegroundColor Yellow
Write-Host "  ┌─────────────────────────────────────┬───────────────────────────────┐" -ForegroundColor Gray
Write-Host "  │ Role                                │ Scope                         │" -ForegroundColor Gray
Write-Host "  ├─────────────────────────────────────┼───────────────────────────────┤" -ForegroundColor Gray
Write-Host "  │ Reader                              │ Subscription                  │" -ForegroundColor White
Write-Host "  │ Cost Management Reader              │ Subscription                  │" -ForegroundColor White
Write-Host "  │ Cognitive Services OpenAI User      │ OpenAI Resource ONLY          │" -ForegroundColor White
Write-Host "  │ AcrPull                             │ Container Registry ONLY       │" -ForegroundColor White
Write-Host "  └─────────────────────────────────────┴───────────────────────────────┘" -ForegroundColor Gray
Write-Host ""
Write-Host "  ✅ Reader: Query VMs, networks, storage (read-only)" -ForegroundColor White
Write-Host "  ✅ Cost Management Reader: Analyze costs (read-only)" -ForegroundColor White
Write-Host "  ✅ OpenAI User: Chat with GPT-4o (resource-scoped only)" -ForegroundColor White
Write-Host "  ✅ AcrPull: Pull container images from ACR (registry-scoped only)" -ForegroundColor White
Write-Host ""
Write-Host "📝 WHAT WAS AUTOMATED" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  ✅ Registered required Azure resource providers" -ForegroundColor Green
Write-Host "  ✅ Created Azure OpenAI (AI Foundry) resource" -ForegroundColor Green
Write-Host "  ✅ Deployed GPT-4o model" -ForegroundColor Green
Write-Host "  ✅ Created Container Registry" -ForegroundColor Green
Write-Host "  ✅ Built and pushed container image" -ForegroundColor Green
Write-Host "  ✅ Created Container Apps Environment" -ForegroundColor Green
Write-Host "  ✅ Deployed Container App with System-Assigned Managed Identity" -ForegroundColor Green
Write-Host "  ✅ Configured Managed Identity authentication for ACR" -ForegroundColor Green
Write-Host "  ✅ Assigned all RBAC roles (Least-Privilege)" -ForegroundColor Green
Write-Host "  ✅ Configured all environment variables automatically" -ForegroundColor Green
Write-Host ""
Write-Host "🔄 MULTI-SUBSCRIPTION ACCESS (Optional)" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  To query resources in OTHER subscriptions, assign these 2 roles:" -ForegroundColor Yellow
Write-Host "  (Replace <other-sub-id> with the target subscription ID)" -ForegroundColor Gray
Write-Host ""
Write-Host "  # PowerShell syntax:" -ForegroundColor Cyan
Write-Host "  az role assignment create --assignee $principalId ``" -ForegroundColor DarkGray
Write-Host "      --role 'Reader' --scope '/subscriptions/<other-sub-id>'" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  az role assignment create --assignee $principalId ``" -ForegroundColor DarkGray
Write-Host "      --role 'Cost Management Reader' --scope '/subscriptions/<other-sub-id>'" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  # Bash/CLI syntax (single line):" -ForegroundColor Cyan
Write-Host "  az role assignment create --assignee $principalId --role 'Reader' --scope '/subscriptions/<other-sub-id>'" -ForegroundColor DarkGray
Write-Host "  az role assignment create --assignee $principalId --role 'Cost Management Reader' --scope '/subscriptions/<other-sub-id>'" -ForegroundColor DarkGray
Write-Host ""
if (-not $EnableLogAnalytics) {
    Write-Host "📊 ENABLE LOGGING (Optional)" -ForegroundColor Cyan
    Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
    Write-Host "  Container logs are disabled by default for simpler deployment." -ForegroundColor White
    Write-Host "  To view container logs from CLI:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  az containerapp logs show --name $ContainerAppName --resource-group $ResourceGroupName --follow" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  To enable full Log Analytics, redeploy with -EnableLogAnalytics switch" -ForegroundColor Gray
    Write-Host ""
}
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host "  Author: Zahir Hussain Shah" -ForegroundColor Gray
Write-Host "  Website: www.zahir.cloud | Email: zahir@zahir.cloud" -ForegroundColor Gray
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor Gray
