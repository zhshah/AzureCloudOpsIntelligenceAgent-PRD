# Azure CloudOps Intelligence Agent

**AI-Powered Azure Infrastructure Management Platform**

[![Azure](https://img.shields.io/badge/Azure-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com)
[![OpenAI](https://img.shields.io/badge/Azure%20OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Container Apps](https://img.shields.io/badge/Container%20Apps-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com/en-us/products/container-apps)

---

## Overview

Azure CloudOps Intelligence Agent is an AI-powered platform that enables natural language interaction for Azure infrastructure management. Built on Azure OpenAI GPT-4o, it provides:

- **Cost Intelligence** - Real-time cost analysis, trends, and optimization recommendations
- **Security & Compliance** - Defender for Cloud, Azure Policy compliance monitoring
- **Resource Management** - Full inventory across multi-subscription environments
- **Automated Deployments** - Natural language resource creation with approval workflows

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
az account set --subscription "<your-subscription-name-or-id>"
```

### 2.3 Run the Automated Deployment Script

```powershell
.\deploy-automated.ps1 `
    -ResourceGroupName "rg-cloudops-agent" `
    -Location "westeurope" `
    -ContainerRegistryName "mycrname" `
    -EntraAppClientId "<your-app-registration-client-id>" `
    -EntraTenantId "<your-tenant-id>"
```

#### Required Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `-ResourceGroupName` | Name for the resource group | `rg-cloudops-agent` |
| `-ContainerRegistryName` | Globally unique ACR name (alphanumeric, no dashes) | `cloudopsacr2024` |
| `-EntraAppClientId` | Application (client) ID from Step 1.3 | `a1b2c3d4-e5f6-...` |
| `-EntraTenantId` | Directory (tenant) ID from Step 1.3 | `12345678-abcd-...` |

#### Optional Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `-Location` | `westeurope` | Azure region |
| `-OpenAIResourceName` | Auto-generated | Azure OpenAI resource name |
| `-ContainerAppName` | `cloudops-agent` | Container App name |
| `-ContainerAppEnvName` | `cloudops-env` | Container Apps Environment name |

### 2.4 What the Script Creates

The script automatically creates:

| Resource | Purpose |
|----------|---------|
| **Resource Group** | Container for all resources |
| **Azure OpenAI** | GPT-4o model for AI chat |
| **Container Registry** | Docker image storage |
| **Container Apps Environment** | Hosting environment |
| **Container App** | The application with Managed Identity |
| **RBAC Role Assignments** | Reader, Cost Management Reader, OpenAI User |

### 2.5 Post-Deployment: Configure Redirect URI

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

### Security Highlights

- ✅ **Zero Secrets** - Managed Identity handles authentication (no API keys stored)
- ✅ **Read-Only Access** - Application cannot modify your Azure resources
- ✅ **Scoped Permissions** - OpenAI access limited to specific resource only
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

## Features

### Cost Intelligence
- Current month costs and daily trends
- Cost breakdown by service, resource group, tags
- Orphaned resources detection
- CSV export for reporting

### Security & Compliance
- Defender for Cloud recommendations
- Azure Policy compliance status
- Non-compliant resource reports
- Public access auditing

### Resource Management
- Full inventory across subscriptions
- Natural language search
- Tag compliance monitoring

### Automated Deployments
- Natural language resource creation
- Email-based approval workflows (via Logic Apps)
- Supported: VMs, Storage, SQL, VNets, Disks

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
