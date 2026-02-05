# Azure CloudOps Intelligence Agent

**AI-Powered Azure Infrastructure Operations & Management Platform**

[![Azure](https://img.shields.io/badge/Azure-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com)
[![OpenAI](https://img.shields.io/badge/Azure%20OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Container Apps](https://img.shields.io/badge/Container%20Apps-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com/en-us/products/container-apps)

---

## 🎯 Overview

Azure CloudOps Intelligence Agent is an enterprise-grade, AI-powered platform that revolutionizes Azure infrastructure management. Built on Azure OpenAI GPT-4o with advanced function calling capabilities, it provides natural language interaction for cost intelligence, security compliance, resource management, and automated deployments across your entire Azure estate.

---

## 📸 Dashboard Preview

![Agent Dashboard](Agent%20Screenshot.png)

---

## 🏗️ Solution Architecture

![Solution Architecture](Architecture%20Image%20for%20Github.png)

### Architecture Components

| Layer | Component | Description |
|-------|-----------|-------------|
| **User Access** | Web Dashboard | Modern HTML/CSS/JavaScript interface with Azure-styled design |
| | Microsoft Entra ID | Enterprise SSO authentication with JWT tokens |
| | Conditional Access | Policy-based access control |
| **Application Layer** | Azure Container Apps | Serverless container hosting with auto-scaling |
| | Container Registry | Private container image storage |
| | FastAPI Backend | High-performance Python REST API |
| **AI Core** | Azure OpenAI (GPT-4o) | Natural language processing with function calling |
| | Intelligent Agent | Context-aware decision making and query routing |
| **Data Sources** | Azure Resource Graph | KQL-based resource inventory queries |
| | Azure Cost Management | Cost analysis and optimization data |
| | Cosmos DB | Conversation history and state management |
| **Deployment Layer** | Logic Apps | Human-in-the-loop approval workflows |
| | Azure Resource Manager | ARM/Bicep template deployments |
| | Managed Identity | Secure, credential-free Azure access |

---

## ✨ Key Features

### 💰 Cost Intelligence & Optimization
- **Real-time Cost Analysis** - Current month costs, daily trends, and forecasts
- **Cost Breakdown** - By service, resource group, subscription, and tags
- **Savings Opportunities** - Identify orphaned disks, deallocated VMs, unutilized resources
- **Business Unit Filtering** - Filter costs by tags, resource groups, or custom dimensions
- **CSV Export** - Export all query results for reporting and analysis

### 🔒 Security & Compliance
- **Defender for Cloud Integration** - Security recommendations and scores
- **Policy Compliance** - Azure Policy status across all subscriptions
- **Non-Compliant Resources** - Detailed violation reports with remediation guidance
- **Public Access Audit** - Identify publicly accessible storage, databases, and services

### 🖥️ Resource Management
- **Full Inventory** - All Azure resources across subscriptions
- **Multi-Subscription Support** - Query across your entire Azure estate
- **Resource Search** - Natural language resource discovery
- **Tag Management** - Inventory and compliance for tagging standards

### 🚀 Automated Deployments (with Approval Workflow)
- **Natural Language Deployments** - "Create a VM named prod-web-01 in West Europe"
- **Human-in-the-Loop Approval** - Email-based approval workflow via Logic Apps
- **Supported Resources**: VMs, Storage, SQL, VNets, Disks, Resource Groups

### 📊 Additional Capabilities
- **Monitoring & Alerts** - VM Insights, App Insights coverage
- **Update Management** - Pending updates, patch compliance
- **Azure Arc** - Hybrid infrastructure management
- **Microsoft Entra ID** - Identity management and security posture
- **Database Management** - SQL, PostgreSQL, MySQL, Cosmos DB

---

## 🛠️ Technology Stack

| Category | Technology |
|----------|------------|
| **AI/ML** | Azure OpenAI GPT-4o, Function Calling |
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Frontend** | HTML5, CSS3, JavaScript, Marked.js |
| **Authentication** | Microsoft Entra ID, MSAL, JWT |
| **Infrastructure** | Azure Container Apps, Container Registry |
| **Data** | Azure Resource Graph (KQL), Cost Management API |
| **Identity** | Microsoft Graph API |
| **Deployment** | ARM Templates, Azure CLI |

---

## 📋 Prerequisites

### Requirements for Deployment

| Requirement | Description | How to Check/Get |
|-------------|-------------|------------------|
| **Azure Subscription** | With Owner or Contributor + User Access Administrator | `az account show` |
| **Azure CLI** | Version 2.50 or later | `az --version` |
| **Azure OpenAI Access** | Your subscription must have OpenAI access approved | [Request access here](https://aka.ms/oai/access) |
| **Git** | For cloning the repository | `git --version` |
| **PowerShell 5.1+** | For running the deployment script (Windows) | `$PSVersionTable.PSVersion` |

### Deployer Role Requirements

The person running the deployment script needs these Azure RBAC roles:

| Role | Scope | Why Required |
|------|-------|--------------|
| **Contributor** | Subscription | Create Resource Group, Azure OpenAI, Container Registry, Container App |
| **User Access Administrator** | Subscription | Assign RBAC roles to the Container App's Managed Identity |

> **Alternative**: The **Owner** role includes both permissions above.

> **Note**: These permissions are only needed during deployment. After deployment completes, the deployer's elevated access is not required for the application to run.

### What You DON'T Need (Script Creates Everything!)

| NOT Required | Why |
|--------------|-----|
| ❌ Pre-created Azure OpenAI | Script creates it automatically |
| ❌ Pre-created Container Registry | Script creates it automatically |
| ❌ API keys or secrets | Uses Managed Identity (no keys needed) |
| ❌ `.env` file for Azure deployment | Only needed for local development |
| ❌ Docker installed | ACR Tasks builds the image in the cloud |

---

## � Application Identity & Permissions (How Chat Queries Azure)

> ⚠️ **IMPORTANT**: This section explains what permissions the **running application** needs to query your Azure resources. This is **separate** from the deployer permissions above (which are only needed during deployment).

### How the Application Accesses Azure Resources

When you chat with the agent (e.g., "Show me all VMs" or "What's my cost this month?"), the application needs to authenticate to Azure APIs. There are **two options**:

| Method | Used By | Secrets Required | Recommended For |
|--------|---------|------------------|-----------------|
| **System-Assigned Managed Identity** | Automated Deployment | ❌ None | Azure deployment (most secure) |
| **App Registration (Service Principal)** | Manual Deployment | ✅ Client ID + Secret | Local dev / custom scenarios |

---

### Option A: System-Assigned Managed Identity (Automated Deployment)

The **automated deployment script** creates a **System-Assigned Managed Identity** and assigns these roles:

#### Application Runtime Permissions (READ-ONLY)

| Role | Scope | Purpose | What It CAN Do | What It CANNOT Do |
|------|-------|---------|----------------|-------------------|
| **Reader** | Subscription | Query Azure resources via Resource Graph API | Read VMs, networks, storage, disks, all resource metadata | ❌ Create, modify, or delete ANY resource |
| **Cost Management Reader** | Subscription | Read billing and cost data | Read costs, spending trends, budgets (read-only) | ❌ Modify budgets, billing, or make financial changes |
| **Cognitive Services OpenAI User** | OpenAI Resource ONLY | Use GPT-4o for chat | Send prompts and receive responses | ❌ Create/delete models, modify OpenAI settings |

#### Key Security Points:
- ✅ **100% Read-Only** - Application cannot create, modify, or delete any Azure resources
- ✅ **No Secrets Stored** - Managed Identity handles authentication automatically
- ✅ **Principle of Least Privilege** - Minimum permissions required for functionality
- ✅ **Scoped OpenAI Access** - OpenAI role is limited to the specific resource, not subscription-wide

---

### Option B: App Registration (Manual Deployment / Local Development)

If you prefer to use an **App Registration (Service Principal)** instead of Managed Identity, follow these steps:

#### Step 1: Create App Registration in Azure Portal

1. Go to **Azure Portal** → **Microsoft Entra ID** → **App registrations**
2. Click **New registration**
3. Enter a name: `CloudOps-Intelligence-Agent`
4. Select **Accounts in this organizational directory only**
5. Click **Register**
6. Note the **Application (client) ID** and **Directory (tenant) ID**

#### Step 2: Create Client Secret

1. In the App Registration, go to **Certificates & secrets**
2. Click **New client secret**
3. Add description: `CloudOps Agent Secret`
4. Select expiration (recommended: 12 months)
5. Click **Add**
6. **COPY THE SECRET VALUE IMMEDIATELY** (it won't be shown again)

#### Step 3: Assign RBAC Roles (Least-Privilege)

Assign these roles to the App Registration's Service Principal:

```bash
# Get the App Registration's Object ID (Service Principal)
APP_ID="<your-application-client-id>"
SP_OBJECT_ID=$(az ad sp show --id $APP_ID --query "id" -o tsv)

# Assign READ-ONLY roles at subscription scope
az role assignment create --assignee $SP_OBJECT_ID --role "Reader" --scope /subscriptions/<subscription-id>
az role assignment create --assignee $SP_OBJECT_ID --role "Cost Management Reader" --scope /subscriptions/<subscription-id>

# Assign OpenAI access (scoped to specific resource for least-privilege)
az role assignment create --assignee $SP_OBJECT_ID --role "Cognitive Services OpenAI User" \
    --scope /subscriptions/<subscription-id>/resourceGroups/<rg-name>/providers/Microsoft.CognitiveServices/accounts/<openai-name>
```

#### Step 4: Configure Environment Variables

Set these environment variables in your Container App or `.env` file:

| Variable | Value | Description |
|----------|-------|-------------|
| `AZURE_CLIENT_ID` | `<application-client-id>` | From App Registration |
| `AZURE_TENANT_ID` | `<directory-tenant-id>` | From App Registration |
| `AZURE_CLIENT_SECRET` | `<client-secret-value>` | From Step 2 |
| `USE_MANAGED_IDENTITY` | `false` | Use Service Principal instead |

#### Example `.env` file for App Registration:

```env
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-openai-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# App Registration (Service Principal) Authentication
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=your-client-secret-value
USE_MANAGED_IDENTITY=false

# Subscription
AZURE_SUBSCRIPTION_ID=your-subscription-id
```

---

### Summary: Deployer vs Application Permissions

| Permission Type | Who/What | When Needed | Permissions |
|-----------------|----------|-------------|-------------|
| **Deployer Permissions** | Person running deployment script | During deployment ONLY | Contributor + User Access Administrator |
| **Application Permissions** | Managed Identity or App Registration | Runtime (when app is running) | Reader + Cost Management Reader + OpenAI User |

> 📝 **The application permissions are READ-ONLY**. The chat agent cannot create, modify, or delete any Azure resources. It can only read resource information and cost data.

---

## �🚀 Deployment Guide

### Option 1: Fully Automated Deployment (Recommended) ⭐

The automated script creates **ALL** Azure resources from scratch - no manual configuration required!

#### What the Script Creates Automatically:

| Resource | Purpose |
|----------|---------|
| **Resource Group** | Contains all deployment resources |
| **Azure OpenAI (AI Foundry)** | GPT-4o language model service |
| **GPT-4o Model Deployment** | AI model for natural language processing |
| **Container Registry** | Stores the application container image |
| **Container Apps Environment** | Serverless hosting environment |
| **Container App** | The running application |
| **Managed Identity** | Secure, credential-free Azure access |
| **RBAC Assignments** | Reader, Cost Management Reader, OpenAI User roles |

#### Step 1: Clone the Repository

```powershell
git clone https://github.com/zhshah/AzureCloudOpsIntelligenceAgent-PRD.git
cd AzureCloudOpsIntelligenceAgent-PRD
```

#### Step 2: Run the Automated Deployment Script

```powershell
.\deploy-automated.ps1 -ResourceGroupName "rg-cloudops-agent" `
                       -Location "westeurope" `
                       -ContainerRegistryName "yourcrname"
```

**Parameters:**

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `-ResourceGroupName` | Yes | Name for the resource group | `rg-cloudops-agent` |
| `-Location` | No | Azure region (default: westeurope) | `eastus`, `westeurope` |
| `-ContainerRegistryName` | Yes | Globally unique name (lowercase, no dashes) | `mycompanyacr` |
| `-ContainerAppName` | No | Name for the app (default: cloudops-agent) | `cloudops-agent` |
| `-OpenAIResourceName` | No | Name for OpenAI resource (auto-generated) | `openai-prod` |

#### Step 3: Wait for Deployment (10-15 minutes)

The script will:
1. ✅ Create Resource Group
2. ✅ Create Azure OpenAI resource
3. ✅ Deploy GPT-4o model
4. ✅ Create Container Registry
5. ✅ Build and push container image
6. ✅ Create Container Apps Environment
7. ✅ Deploy Container App with all environment variables
8. ✅ Enable Managed Identity
9. ✅ Assign all required RBAC roles
10. ✅ Output the application URL

#### Step 4: Access Your Application

Once complete, the script outputs your application URL:
```
🌐 APPLICATION URL
─────────────────────────────────────────────────────────────────
  https://cloudops-agent.randomname.westeurope.azurecontainerapps.io
```

Open the URL in your browser and start chatting with your Azure infrastructure!

---

### Option 2: Manual Deployment (Step-by-Step)

For those who prefer manual control or need to customize the deployment.

#### Step 1: Clone the Repository

```bash
git clone https://github.com/zhshah/AzureCloudOpsIntelligenceAgent-PRD.git
cd AzureCloudOpsIntelligenceAgent-PRD
```

#### Step 2: Set Variables

```bash
# Configuration variables
RESOURCE_GROUP="rg-cloudops-agent"
LOCATION="westeurope"
OPENAI_NAME="openai-cloudops-$(openssl rand -hex 4)"
ACR_NAME="yourcrname"
CONTAINER_APP_NAME="cloudops-agent"
ENVIRONMENT_NAME="cloudops-env"
```

#### Step 3: Create Resource Group

```bash
az group create --name $RESOURCE_GROUP --location $LOCATION
```

#### Step 4: Create Azure OpenAI Resource

```bash
# Create Azure OpenAI (AI Foundry) resource
az cognitiveservices account create \
    --name $OPENAI_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --kind "OpenAI" \
    --sku "S0" \
    --custom-domain $OPENAI_NAME

# Get the endpoint
OPENAI_ENDPOINT=$(az cognitiveservices account show \
    --name $OPENAI_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "properties.endpoint" -o tsv)

echo "OpenAI Endpoint: $OPENAI_ENDPOINT"
```

#### Step 5: Deploy GPT-4o Model

```bash
# Deploy the GPT-4o model
az cognitiveservices account deployment create \
    --name $OPENAI_NAME \
    --resource-group $RESOURCE_GROUP \
    --deployment-name "gpt-4o" \
    --model-name "gpt-4o" \
    --model-version "2024-08-06" \
    --model-format "OpenAI" \
    --sku-capacity 30 \
    --sku-name "GlobalStandard"
```

#### Step 6: Create Container Registry

```bash
az acr create \
    --name $ACR_NAME \
    --resource-group $RESOURCE_GROUP \
    --sku Basic \
    --admin-enabled true

# Get credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query "username" -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)
```

#### Step 7: Build and Push Container Image

```bash
az acr build \
    --registry $ACR_NAME \
    --image cloudops-agent:latest \
    --file Dockerfile .
```

#### Step 8: Create Container Apps Environment

```bash
az containerapp env create \
    --name $ENVIRONMENT_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION
```

#### Step 9: Deploy Container App

```bash
SUBSCRIPTION_ID=$(az account show --query "id" -o tsv)

az containerapp create \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --environment $ENVIRONMENT_NAME \
    --image $ACR_NAME.azurecr.io/cloudops-agent:latest \
    --target-port 8000 \
    --ingress external \
    --min-replicas 1 \
    --max-replicas 3 \
    --cpu 1.0 \
    --memory 2.0Gi \
    --registry-server $ACR_NAME.azurecr.io \
    --registry-username $ACR_USERNAME \
    --registry-password $ACR_PASSWORD \
    --env-vars \
        AZURE_OPENAI_ENDPOINT=$OPENAI_ENDPOINT \
        AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o \
        AZURE_OPENAI_API_VERSION=2024-02-15-preview \
        AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID \
        USE_MANAGED_IDENTITY=true
```

#### Step 10: Configure Managed Identity & RBAC

```bash
# Enable managed identity
az containerapp identity assign \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --system-assigned

# Get principal ID
PRINCIPAL_ID=$(az containerapp show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "identity.principalId" -o tsv)

# Assign roles
az role assignment create --assignee $PRINCIPAL_ID --role "Reader" --scope /subscriptions/$SUBSCRIPTION_ID
az role assignment create --assignee $PRINCIPAL_ID --role "Cost Management Reader" --scope /subscriptions/$SUBSCRIPTION_ID
az role assignment create --assignee $PRINCIPAL_ID --role "Cognitive Services OpenAI User" --scope /subscriptions/$SUBSCRIPTION_ID
```

#### Step 11: Get Application URL

```bash
az containerapp show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "properties.configuration.ingress.fqdn" -o tsv
```

---

### Option 3: Local Development

Run the application locally for development and testing.

#### Step 1: Clone and Setup

```bash
git clone https://github.com/zhshah/AzureCloudOpsIntelligenceAgent-PRD.git
cd AzureCloudOpsIntelligenceAgent-PRD

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\Activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

#### Step 2: Create Environment File

For local development only, create a `.env` file in the root directory:

```env
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-openai-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Azure Configuration
AZURE_SUBSCRIPTION_ID=your-subscription-id

# For local development, use CLI authentication (not managed identity)
USE_MANAGED_IDENTITY=false
```

> **Note**: The `.env` file is ONLY needed for local development. For Azure deployment, the automated script configures everything automatically.

#### Step 3: Run the Application

```bash
python main.py
```

Access the dashboard at: `http://localhost:8000`

---

## ❓ Frequently Asked Questions

### Q: Do I need to create Azure OpenAI manually before deployment?
**A: No!** The automated deployment script creates the Azure OpenAI resource and deploys the GPT-4o model automatically. You just need Azure OpenAI access approved for your subscription.

### Q: What is the `.env` file for?
**A: The `.env` file is ONLY needed for local development.** When deploying to Azure using the automated script, all environment variables are configured automatically in the Container App settings.

### Q: How does the application authenticate without API keys?
**A: Managed Identity.** The Container App uses a system-assigned managed identity to authenticate with Azure services (OpenAI, Resource Graph, Cost Management). No API keys are stored in the application.

### Q: What RBAC roles does the application need?
**A: Three roles with least-privilege:**
- **Reader** (Subscription) - Query resources via Resource Graph
- **Cost Management Reader** (Subscription) - Read cost data
- **Cognitive Services OpenAI User** (OpenAI resource only) - Use GPT-4o

### Q: Can the application modify or delete my Azure resources?
**A: No!** The Managed Identity only has **Reader** role. It cannot create, modify, or delete any Azure resources. It's read-only.

### Q: How do I enable access to multiple subscriptions?
**A: Assign roles to additional subscriptions:**
```bash
PRINCIPAL_ID=$(az containerapp show --name cloudops-agent --resource-group rg-cloudops-agent --query "identity.principalId" -o tsv)
az role assignment create --assignee $PRINCIPAL_ID --role "Reader" --scope /subscriptions/<other-sub-id>
az role assignment create --assignee $PRINCIPAL_ID --role "Cost Management Reader" --scope /subscriptions/<other-sub-id>
```

### Q: What permissions does the DEPLOYER need (not the app)?
**A: Owner, or Contributor + User Access Administrator** at subscription level. This is only needed during deployment to create resources and assign RBAC roles.

### Q: How long does deployment take?
**A: Approximately 10-15 minutes.** The longest steps are creating Azure OpenAI (~3 min), deploying GPT-4o model (~3 min), and building the container image (~3-5 min).

### Q: Why is Cognitive Services OpenAI User role scoped to resource only?
**A: Least-privilege principle.** The app only needs OpenAI access to its specific resource, not to all OpenAI resources in the subscription.

---

## 💡 Usage Examples

### Cost Analysis
```
"Show me cost breakdown by service for this month"
"What are my top 10 most expensive resources?"
"Find cost savings opportunities"
```

### Security & Compliance
```
"Show security recommendations"
"List non-compliant resources"
"What policies are failing?"
```

### Resource Management
```
"Show all virtual machines"
"List storage accounts without private endpoints"
"Find resources tagged with Environment=Production"
```

### Deployments (with Approval Workflow)
```
"Create a Windows VM named prod-web-01 in West Europe"
"Deploy a storage account named stproddata in East US"
```

---

## 🔐 Security Architecture (Least-Privilege Principle)

This application follows Azure security best practices with **zero credentials stored** and **minimum required permissions**.

### System-Assigned Managed Identity

The application uses a **System-Assigned Managed Identity** instead of API keys or App Registrations:

| Feature | Benefit |
|---------|---------|
| **Auto-lifecycle** | Created/deleted with the Container App |
| **No secrets** | No passwords, keys, or certificates to manage |
| **No rotation** | Credentials are handled automatically by Azure AD |
| **Audit trail** | All access is logged in Azure Activity Log |

### RBAC Roles Assigned (Least-Privilege)

The Managed Identity is granted **only the minimum permissions required**:

| Role | Scope | Purpose | Restrictions |
|------|-------|---------|--------------|
| **Reader** | Subscription | Query Azure resources via Resource Graph | ❌ Cannot create, modify, or delete resources |
| **Cost Management Reader** | Subscription | Read cost and billing data | ❌ Cannot modify budgets or billing settings |
| **Cognitive Services OpenAI User** | OpenAI Resource Only | Use GPT-4o for chat completions | ❌ Cannot create/delete deployments or modify settings |

### What the Application CAN Do
- ✅ Read resource inventory (VMs, storage, networks, etc.)
- ✅ Query cost data and spending trends
- ✅ Send prompts to Azure OpenAI GPT-4o
- ✅ List security recommendations (if Defender enabled)
- ✅ Check policy compliance status

### What the Application CANNOT Do
- ❌ Create, modify, or delete any Azure resources
- ❌ Access secrets in Key Vault
- ❌ Modify billing or cost settings
- ❌ Change Azure OpenAI deployments or settings
- ❌ Access other subscriptions (unless explicitly granted)

### Multi-Subscription Access

To query resources across multiple subscriptions, grant the Managed Identity access to additional subscriptions:

```bash
# Get the Principal ID of your Container App
PRINCIPAL_ID=$(az containerapp show --name cloudops-agent --resource-group rg-cloudops-agent --query "identity.principalId" -o tsv)

# Grant access to another subscription (Reader + Cost Management Reader only)
az role assignment create --assignee $PRINCIPAL_ID --role "Reader" --scope /subscriptions/<other-sub-id>
az role assignment create --assignee $PRINCIPAL_ID --role "Cost Management Reader" --scope /subscriptions/<other-sub-id>
```

### Prerequisites for the Deployer

The **user running the deployment script** needs these permissions (temporary, only during deployment):

| Permission | Reason |
|------------|--------|
| **Contributor** | Create resource group, OpenAI, ACR, Container App |
| **User Access Administrator** | Assign RBAC roles to the Managed Identity |

> **Tip**: After deployment, the deployer's elevated permissions are not needed for the application to run.

### Security Features Summary

- **Managed Identity** - No API keys or credentials stored anywhere
- **Resource-Scoped OpenAI** - OpenAI access limited to specific resource, not subscription
- **Read-Only Access** - Cannot modify any Azure resources
- **Data Integrity** - Only displays real data from Azure APIs, never fabricated
- **HTTPS Only** - All communication encrypted
- **No Sensitive Logging** - Credentials never appear in logs

---

## 🐛 Troubleshooting

### Azure OpenAI Creation Fails
- **Cause**: Your subscription may not have Azure OpenAI access approved
- **Solution**: Request access at [https://aka.ms/oai/access](https://aka.ms/oai/access)

### GPT-4o Model Deployment Fails
- **Cause**: Model may not be available in your region
- **Solution**: Try a different region (e.g., `eastus`, `westeurope`, `swedencentral`)

### Container App Not Starting
```bash
# Check logs
az containerapp logs show --name cloudops-agent --resource-group rg-cloudops-agent --follow
```

### No Cost Data Showing
- Cost data may take 24-48 hours to appear for new subscriptions
- Ensure "Cost Management Reader" role is assigned

---

## 📈 Roadmap

- [ ] Natural language to KQL query generation
- [ ] Custom dashboards and saved queries
- [ ] Scheduled reports via email
- [ ] Cost anomaly detection
- [ ] Terraform/Bicep code generation
- [ ] Multi-tenant support
- [ ] Power BI integration

---

## 👤 Author

**Zahir Hussain Shah**

| | |
|---|---|
| 🌐 Website | [www.zahir.cloud](https://www.zahir.cloud) |
| 📧 Email | [zahir@zahir.cloud](mailto:zahir@zahir.cloud) |
| 💼 GitHub | [@zhshah](https://github.com/zhshah) |

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

---

**Built with ❤️ for Azure Cloud Operations**

*Empowering IT teams to manage Azure infrastructure through natural language*
