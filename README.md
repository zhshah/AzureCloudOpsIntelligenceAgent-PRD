# Azure CloudOps Intelligence Agent

**AI-Powered Azure Infrastructure Management Platform**

[![Azure](https://img.shields.io/badge/Azure-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com)
[![OpenAI](https://img.shields.io/badge/Azure%20OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Container Apps](https://img.shields.io/badge/Container%20Apps-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com/en-us/products/container-apps)

---

## Overview

Azure CloudOps Intelligence Agent is an AI-powered platform that enables natural language interaction for Azure infrastructure management. Built on Azure OpenAI GPT-4o with 120+ tool functions, it spans **29 categories with 249+ pre-built prompts** — turning hours of portal navigation, KQL queries, and PowerShell scripts into instant conversational answers.

### Key Capabilities

- **Cloud Ops Health Assessment** — 6-pillar scoring engine (Advisor, Backup, Monitor, Security, Updates, Policy) with resource-level detail and health grades (A–F)
- **Architecture Diagram Generation** — Auto-generates professional Graphviz diagrams from your live Azure environment (per-RG, per-subscription, multi-workload, tag-based)
- **Comprehensive Inventory** — 26 inventory categories across compute, networking, PaaS, storage, monitoring, security, and governance
- **Cost Intelligence** — Real-time cost analysis, trends, savings opportunities, and orphaned resource detection (24 resource types)
- **Security & Compliance** — Defender for Cloud, Azure Policy, RBAC analysis, NSG auditing, public access exposure
- **Identity Governance** — Entra ID users, groups, app registrations, conditional access, privileged roles, stale devices
- **Automated Deployments** — Natural language resource creation with email-based approval workflows via Logic Apps
- **Multi-Scope Support** — Individual subscriptions, management groups, or entire tenant with automatic scope filtering

---

## Dashboard Preview

![Agent Dashboard](Agent%20Screenshot.png)

---

## Architecture

![Solution Architecture](Architecture%20Image%20for%20Github.png)

| Component | Purpose |
|-----------|---------|
| **Azure Container Apps** | Hosts the application with auto-scaling |
| **Azure OpenAI (GPT-4o)** | Natural language processing with function calling |
| **Microsoft Entra ID** | User authentication (SSO) |
| **Managed Identity** | Secure, credential-free Azure API access |
| **Azure Resource Graph** | KQL-based resource queries |
| **Cost Management API** | Billing and cost data |

---

# Deployment Guide

## Section 1: Prerequisites

Complete these steps BEFORE running the deployment script.

### 1.1 Azure Requirements

| Requirement | Description | Verification |
|-------------|-------------|--------------|
| **Azure Subscription** | With appropriate permissions | `az account show` |
| **Azure CLI** | Version 2.50+ | `az --version` |
| **Azure OpenAI Access** | Subscription must have OpenAI approved | [Request access](https://aka.ms/oai/access) |
| **PowerShell 5.1+** | For deployment script | `$PSVersionTable.PSVersion` |

### 1.2 Deployer Permissions

The person running the deployment script needs:

| Role | Scope | Purpose |
|------|-------|---------|
| **Contributor** | Subscription | Create resources (OpenAI, ACR, Container App) |
| **User Access Administrator** | Subscription | Assign RBAC roles to Managed Identity |

> **Alternative**: **Owner** role includes both permissions.

### 1.3 Create Entra ID App Registration (Required for User Login)

Users authenticate via Microsoft Entra ID. You must create an App Registration BEFORE deployment:

#### Step-by-Step:

**Step 1: Navigate to App Registrations**
```
Azure Portal → Microsoft Entra ID → App registrations → New registration
```

**Step 2: Configure Basic Settings**
| Field | Value |
|-------|-------|
| Name | `CloudOps-Agent-UserAuth` (or your preferred name) |
| Supported account types | `Accounts in this organizational directory only (Single tenant)` |
| Redirect URI | Leave blank for now (configure after deployment) |

Click **Register**

**Step 3: Record Required Values**

After registration, note these values from the **Overview** page:

| Value | Where to Find | Example |
|-------|---------------|---------|
| **Application (client) ID** | Overview → Application (client) ID | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| **Directory (tenant) ID** | Overview → Directory (tenant) ID | `12345678-abcd-ef12-3456-7890abcdef12` |

> **Important**: You'll provide these values as parameters to the deployment script.

**Step 4: Configure Authentication (After Deployment)**

After the Container App is deployed, you'll get an application URL (e.g., `https://cloudops-agent.azurecontainerapps.io`). Then:

1. Return to your App Registration → **Authentication**
2. Click **Add a platform** → **Single-page application**
3. Add Redirect URI: `https://<your-container-app-url>/login.html`
4. Check:
   - ✅ Access tokens
   - ✅ ID tokens
5. Click **Configure** then **Save**

**Step 5: Configure API Permissions**
1. Go to **API permissions** → **Add a permission**
2. Add these **Microsoft Graph** delegated permissions:
   - `openid`
   - `profile`
   - `email`
   - `User.Read`

---

## Section 2: Deployment

### 2.1 Clone the Repository

```powershell
git clone https://github.com/zhshah/AzureCloudOpsIntelligenceAgent-PRD.git
cd AzureCloudOpsIntelligenceAgent-PRD
```

### 2.2 Login to Azure

```powershell
az login
```

### 2.3 Run the Automated Deployment Script

> **IMPORTANT**: Always use the `-SubscriptionId` parameter to ensure resources deploy to the correct subscription. Azure CLI may cache credentials from previous sessions.

```powershell
.\deploy-automated.ps1 `
    -ResourceGroupName "rg-cloudops-agent" `
    -Location "westeurope" `
    -ContainerRegistryName "mycrname" `
    -EntraAppClientId "<your-app-registration-client-id>" `
    -EntraTenantId "<your-tenant-id>" `
    -SubscriptionId "<your-target-subscription-id>"
```

The script will display the target subscription and ask for confirmation:

```
╔════════════════════════════════════════════════════════════════╗
║  TARGET SUBSCRIPTION (All resources will deploy here)          ║
╠════════════════════════════════════════════════════════════════╣
║  Name: Your Subscription Name
║  ID:   xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
╚════════════════════════════════════════════════════════════════╝

Is this the correct subscription? (Y/N): _
```

#### Required Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `-ResourceGroupName` | Name for the resource group | `rg-cloudops-agent` |
| `-ContainerRegistryName` | Globally unique ACR name (alphanumeric, no dashes) | `cloudopsacr2024` |
| `-EntraAppClientId` | Application (client) ID from Step 1.3 | `a1b2c3d4-e5f6-...` |
| `-EntraTenantId` | Directory (tenant) ID from Step 1.3 | `12345678-abcd-...` |

#### Recommended Parameters

| Parameter | Description | Why Use It |
|-----------|-------------|------------|
| `-SubscriptionId` | Target Azure Subscription ID | **Prevents deploying to wrong subscription** - Azure CLI may use cached credentials |

#### Optional Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `-Location` | `westeurope` | Azure region |
| `-OpenAIResourceName` | Auto-generated | Azure OpenAI resource name |
| `-ContainerAppName` | `cloudops-agent` | Container App name |
| `-ContainerAppEnvName` | `cloudops-env` | Container Apps Environment name |
| `-EnableLogAnalytics` | `$false` | Enable Log Analytics for Container Apps logging (can be enabled later) |

### 2.4 Resource Provider Registration (Automatic)

The script automatically registers required Azure resource providers on new subscriptions:
- `Microsoft.ContainerRegistry` - Container Registry
- `Microsoft.App` - Container Apps
- `Microsoft.CognitiveServices` - Azure OpenAI
- `Microsoft.ManagedIdentity` - Managed Identity

> **Note**: This may take 2-5 minutes on new subscriptions.

### 2.5 What the Script Creates

The script automatically creates:

| Resource | Purpose |
|----------|---------|
| **Resource Group** | Container for all resources |
| **Azure OpenAI** | GPT-4o model for AI chat |
| **Container Registry** | Docker image storage |
| **Container Apps Environment** | Hosting environment (without Log Analytics by default) |
| **Container App** | The application with Managed Identity |
| **RBAC Role Assignments** | Reader, Cost Management Reader, OpenAI User, AcrPull |

### 2.6 Post-Deployment: Configure Redirect URI

After deployment completes, the script displays your application URL. Complete Step 1.3 → Step 4 to configure the redirect URI in your App Registration.

---

## Section 3: Security Architecture

### Application Permissions (Least-Privilege)

The Container App's Managed Identity receives only these READ-ONLY roles:

| Role | Scope | Purpose | Limitations |
|------|-------|---------|-------------|
| **Reader** | Subscription | Query resources via Resource Graph | ❌ Cannot create/modify/delete |
| **Cost Management Reader** | Subscription | Read cost and billing data | ❌ Cannot modify budgets |
| **Cognitive Services OpenAI User** | OpenAI Resource | Use GPT-4o API | ❌ Cannot manage deployments |
| **AcrPull** | Container Registry | Pull container images | ❌ Cannot push images |

### Security Highlights

- ✅ **Zero Secrets** - Managed Identity handles all authentication (no API keys or ACR passwords stored)
- ✅ **Read-Only Access** - Application cannot modify your Azure resources
- ✅ **Scoped Permissions** - OpenAI and ACR access limited to specific resources only
- ✅ **Enterprise SSO** - Users authenticate via your organization's Entra ID

---

## Section 4: Multi-Subscription Access (Optional)

By default, the agent can only query resources in the deployment subscription. For multi-subscription access:

### Get the Container App's Principal ID

```bash
az containerapp show \
    --name cloudops-agent \
    --resource-group rg-cloudops-agent \
    --query "identity.principalId" -o tsv
```

### Grant Access to Additional Subscriptions

```bash
PRINCIPAL_ID="<principal-id-from-above>"
OTHER_SUBSCRIPTION_ID="<subscription-id-to-access>"

# Assign Reader role
az role assignment create --assignee $PRINCIPAL_ID --role "Reader" \
    --scope "/subscriptions/$OTHER_SUBSCRIPTION_ID"

# Assign Cost Management Reader role
az role assignment create --assignee $PRINCIPAL_ID --role "Cost Management Reader" \
    --scope "/subscriptions/$OTHER_SUBSCRIPTION_ID"
```

### Grant Access at Management Group Level (All Subscriptions Under It)

```bash
PRINCIPAL_ID="<principal-id>"
MANAGEMENT_GROUP_NAME="<your-mg-name>"

az role assignment create --assignee $PRINCIPAL_ID --role "Reader" \
    --scope "/providers/Microsoft.Management/managementGroups/$MANAGEMENT_GROUP_NAME"

az role assignment create --assignee $PRINCIPAL_ID --role "Cost Management Reader" \
    --scope "/providers/Microsoft.Management/managementGroups/$MANAGEMENT_GROUP_NAME"
```

---

## Section 5: Securing with Private Endpoints (Optional)

For organizations that require private connectivity without public internet exposure, you can secure the deployment with Azure Private Endpoints.

### Recommended Approach

> **Important**: First complete the standard deployment (Sections 1-2), then follow these steps to add private networking.

**Why this order?**
1. The automated script deploys resources with public access for simplicity
2. After deployment is verified working, you add private endpoints
3. Finally, you disable public access

This approach ensures you can troubleshoot any deployment issues before restricting network access.

### 5.1 Prerequisites for Private Networking

| Requirement | Purpose |
|-------------|---------|
| **Azure Virtual Network** | Network where private endpoints will be created |
| **Subnet for Private Endpoints** | Dedicated subnet (recommended: `/27` or larger) |
| **Azure Private DNS Zones** | For name resolution (or custom DNS) |

### 5.2 Create Private Endpoint for Azure OpenAI (AI Foundry)

```bash
# Variables
RESOURCE_GROUP="rg-cloudops-agent"
OPENAI_RESOURCE_NAME="<your-openai-resource-name>"
VNET_NAME="<your-vnet-name>"
SUBNET_NAME="<your-private-endpoint-subnet>"
LOCATION="westeurope"

# Create Private Endpoint for Azure OpenAI
az network private-endpoint create \
    --name "pe-openai-cloudops" \
    --resource-group $RESOURCE_GROUP \
    --vnet-name $VNET_NAME \
    --subnet $SUBNET_NAME \
    --private-connection-resource-id $(az cognitiveservices account show \
        --name $OPENAI_RESOURCE_NAME \
        --resource-group $RESOURCE_GROUP \
        --query id -o tsv) \
    --group-id "account" \
    --connection-name "openai-private-connection" \
    --location $LOCATION

# Create Private DNS Zone for OpenAI (if not exists)
az network private-dns zone create \
    --resource-group $RESOURCE_GROUP \
    --name "privatelink.openai.azure.com"

# Link DNS Zone to VNet
az network private-dns link vnet create \
    --resource-group $RESOURCE_GROUP \
    --zone-name "privatelink.openai.azure.com" \
    --name "openai-dns-link" \
    --virtual-network $VNET_NAME \
    --registration-enabled false

# Create DNS Zone Group for automatic DNS registration
az network private-endpoint dns-zone-group create \
    --resource-group $RESOURCE_GROUP \
    --endpoint-name "pe-openai-cloudops" \
    --name "openai-dns-zone-group" \
    --private-dns-zone "privatelink.openai.azure.com" \
    --zone-name "openai"
```

### 5.3 Create Private Endpoint for Container Apps Environment

Container Apps uses a different approach - you configure the environment for internal-only access:

```bash
# Variables
RESOURCE_GROUP="rg-cloudops-agent"
CONTAINER_APP_ENV="cloudops-env"
VNET_NAME="<your-vnet-name>"
INFRASTRUCTURE_SUBNET="<subnet-for-container-apps>"  # Requires /23 or larger

# Note: For existing environments, you may need to recreate with internal configuration
# Create new Container Apps Environment with internal-only ingress
az containerapp env create \
    --name "${CONTAINER_APP_ENV}-internal" \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --infrastructure-subnet-resource-id $(az network vnet subnet show \
        --resource-group $RESOURCE_GROUP \
        --vnet-name $VNET_NAME \
        --name $INFRASTRUCTURE_SUBNET \
        --query id -o tsv) \
    --internal-only true

# Update Container App to use internal environment
# (Requires redeployment to the new environment)
```

**Alternative: Use Azure Front Door or Application Gateway**

For production scenarios, consider:
- **Azure Front Door** with Private Link for global load balancing
- **Application Gateway** with private backend for regional deployments

### 5.4 Disable Public Access on Azure OpenAI

After private endpoints are configured and verified:

```bash
# Disable public network access on Azure OpenAI
az cognitiveservices account update \
    --name $OPENAI_RESOURCE_NAME \
    --resource-group $RESOURCE_GROUP \
    --public-network-access Disabled

# Verify the setting
az cognitiveservices account show \
    --name $OPENAI_RESOURCE_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "properties.publicNetworkAccess" -o tsv
```

### 5.5 Configure Container App for Internal-Only Access

```bash
# Update Container App ingress to internal only
az containerapp ingress update \
    --name cloudops-agent \
    --resource-group $RESOURCE_GROUP \
    --type internal

# Verify ingress configuration
az containerapp show \
    --name cloudops-agent \
    --resource-group $RESOURCE_GROUP \
    --query "properties.configuration.ingress" -o json
```

### 5.6 Network Architecture (Private Deployment)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Azure Virtual Network                             │
│  ┌────────────────────┐    ┌────────────────────┐                       │
│  │  Container Apps    │    │  Private Endpoints │                       │
│  │  Infrastructure    │    │  Subnet            │                       │
│  │  Subnet (/23)      │    │  (/27)             │                       │
│  │                    │    │                    │                       │
│  │  ┌──────────────┐  │    │  ┌──────────────┐  │                       │
│  │  │ Container    │  │    │  │ PE: Azure    │  │                       │
│  │  │ App          │◄─┼────┼──┤ OpenAI       │  │                       │
│  │  │ (Internal)   │  │    │  └──────────────┘  │                       │
│  │  └──────────────┘  │    │                    │                       │
│  └────────────────────┘    └────────────────────┘                       │
│                                      │                                   │
│              Private DNS Zones       │                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  privatelink.openai.azure.com → Azure OpenAI Private IP         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ ExpressRoute / VPN
                                      ▼
                            ┌──────────────────┐
                            │  Corporate       │
                            │  Network         │
                            │  (Users)         │
                            └──────────────────┘
```

### 5.7 Verification Checklist

After configuring private endpoints:

| Check | Command | Expected Result |
|-------|---------|-----------------|
| OpenAI public access disabled | `az cognitiveservices account show --name <name> --resource-group <rg> --query "properties.publicNetworkAccess"` | `"Disabled"` |
| Private endpoint connected | `az network private-endpoint show --name pe-openai-cloudops --resource-group <rg> --query "privateLinkServiceConnections[0].privateLinkServiceConnectionState.status"` | `"Approved"` |
| DNS resolution works | `nslookup <openai-name>.openai.azure.com` (from VNet) | Returns private IP |
| Container App accessible | Access via internal URL from VNet | Application loads |

---

## Features

### Cloud Ops Health Assessment
- **6-Pillar Operational Scoring** — Azure Advisor, Backup Protection, Monitor Alerts, Defender for Cloud, Update Compliance, Azure Policy
- **Overall Health Grade** (A–F) with weighted scoring and priority actions
- **Resource-Level Detail** — every score backed by specific resource names, resource groups, locations, and subscription IDs
- **Supporting Assessments** — Environment Overview, Network Security Health, Tagging Governance, Disaster Recovery Readiness, Advisor Recommendations Breakdown
- Works at subscription, management group, or tenant scope

### Architecture Diagram Generation
- **Live Environment Diagrams** — generates professional architecture diagrams from your actual Azure resources using Graphviz
- **Scope Options** — per-resource group, per-subscription, environment overview, multi-workload, or tag-based grouping
- **Workload Categories** — App Services, VMs, AKS, SQL, AI/ML, Data Platform, Networking, Security, Monitoring, AVD
- **Template Patterns** — web-3tier, microservices, serverless, hub-spoke, data-platform, multi-region, zero-trust, IoT, DevOps CI/CD, and more
- **700+ Azure Native Icons** — automatically mapped to resource types for professional output
- Interactive: select resources from numbered lists, combine RGs, filter by tags

### Comprehensive Azure Inventory (26 Categories)
- **Compute** — VMs, VMSS, VM networking (NICs/IPs), VM disks, Azure Arc machines
- **PaaS** — App Services, Containers (AKS, Container Apps), Databases (SQL, PostgreSQL, MySQL, Cosmos DB), Storage, IoT, ML/AI, AVD, Automation, Event Hubs
- **Networking** — VNets, NSGs with rules, IP inventory, Load Balancers, Firewalls, VPN/ExpressRoute, Front Door, Traffic Manager, WAF, DDoS
- **Monitoring** — Alerts, Application Insights, Log Analytics workspaces, resources without Azure Monitor
- **Security** — Security scores, Defender recommendations, regulatory compliance
- **Governance** — Policy compliance, non-compliant resources, policy exemptions
- CSV export for all inventory queries with full dataset download

### Orphaned Resources Detection
- **24 Resource Types** — App Service Plans, Availability Sets, Managed Disks, SQL Elastic Pools, Public IPs, NICs, NSGs, Route Tables, Load Balancers, Front Door WAF, Traffic Manager, Application Gateways, VNets, Subnets, NAT Gateways, IP Groups, Private DNS Zones, Private Endpoints, VNet Gateways, DDoS Plans, Resource Groups, API Connections, Certificates
- Identifies resources silently draining budgets with no active associations
- Individual or consolidated summary view

### Cost Intelligence
- Current month costs and daily trends
- Cost breakdown by service, resource group, and tags
- Resource-level cost analysis with tag-based cost allocation
- Cost savings opportunities from Azure Advisor
- CSV export for reporting and chargeback

### Security & Compliance
- Defender for Cloud recommendations and security score details
- Azure Policy compliance status with non-compliant resource drill-down
- RBAC analysis — role assignments at subscription, management group, resource group levels; privileged role detection
- NSG rule auditing with risky rule identification
- Public access exposure for Storage, SQL, AKS, App Services, PostgreSQL, MySQL, Cosmos DB
- Regulatory compliance framework status

### Identity & Access (Entra ID)
- Entra ID overview with user/group/device counts
- Inactive users (30+ days), orphaned guest accounts
- Global admins and privileged role holders
- App registrations, enterprise apps, unused applications
- Conditional access policies, disabled policies, policies without MFA
- Stale devices and empty groups

### Resource Management
- Full inventory across all subscriptions with natural language search
- Tag compliance monitoring with per-resource gap analysis
- Management group hierarchy visualization
- Multi-region distribution analysis

### Automated Deployments
- Natural language resource creation — describe what you need, the agent deploys it
- Email-based approval workflows via Azure Logic Apps
- Supported resources: VMs (Windows/Linux), Storage Accounts, SQL Databases, Virtual Networks, Managed Disks, Availability Sets, Resource Groups
- Tag management for existing resources

### Dashboard & UX
- Live dashboard widgets with resource counts, cost summaries, and security scores
- 29 sidebar categories with 249+ pre-built prompts for guided exploration
- Subscription and management group dropdown for scope selection
- CSV export with full dataset download button on large result sets
- Responsive single-page app with Entra ID SSO authentication

---

## Support

| Resource | Link |
|----------|------|
| Author | Zahir Hussain Shah |
| Website | [www.zahir.cloud](https://www.zahir.cloud) |
| Email | zahir@zahir.cloud |

---

## License

MIT License - See LICENSE file for details.
