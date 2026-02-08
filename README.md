# Azure CloudOps Intelligence Agent

[![Azure](https://img.shields.io/badge/Azure-Powered-0078D4?style=for-the-badge&logo=microsoft-azure)](https://azure.microsoft.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=for-the-badge&logo=openai)](https://openai.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Container](https://img.shields.io/badge/Container-Ready-2496ED?style=for-the-badge&logo=docker)](https://www.docker.com)

> **AI-Powered Azure Infrastructure Operations & Cloud Management Platform**

An enterprise-grade AI agent that transforms Azure cloud operations through natural language conversations. Built on **Azure OpenAI GPT-4o** with **119 function-calling tools** across **29 operational categories**, it delivers real-time infrastructure insights, security posture assessment, cost optimization, and orphaned resource detection — all through an intuitive chat interface.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Live Dashboard Widgets](#-live-dashboard-widgets)
- [29 Operational Categories](#-29-operational-categories)
- [Prerequisites](#-prerequisites)
- [Quick Start — Automated Deployment](#-quick-start--automated-deployment)
- [Manual Deployment](#-manual-deployment)
- [Configuration](#-configuration)
- [Post-Deployment RBAC](#-post-deployment-rbac)
- [Security & Data Privacy](#-security--data-privacy)
- [Sample Prompts](#-sample-prompts)
- [API Reference](#-api-reference)
- [Project Structure](#-project-structure)
- [Troubleshooting](#-troubleshooting)
- [About the Author](#-about-the-author)
- [License](#-license)

---

## Overview

Azure CloudOps Intelligence Agent is an AI-powered platform that enables natural language interaction for Azure infrastructure management. Built on Azure OpenAI GPT-4o with 119 tools, it provides:

- **Cost Intelligence** — Real-time cost analysis, month-over-month trends, potential savings, and optimization recommendations
- **Security & Compliance** — Defender for Cloud security score, Azure Policy compliance monitoring, public access exposure detection
- **Resource Management** — Full inventory across multi-subscription environments with management group hierarchy navigation
- **Orphaned Resource Detection** — Identifies 24 types of unused resources (disks, IPs, NICs, NSGs, etc.) costing money
- **Identity & Access** — Entra ID user/group management, conditional access policies, RBAC role assignment audits
- **Zero Hardcoded Secrets** — Uses Azure Managed Identity for all service authentication; no keys stored in code

---

## 🚀 Key Features

### Intelligent Chat Interface
Ask questions in plain English — no need to learn KQL, Azure CLI, or PowerShell. The agent translates your intent into the right Azure API calls automatically.

### Multi-Subscription & Management Group Support
- **Subscription context switching** — Switch between subscriptions dynamically from the UI dropdown
- **Management Group hierarchy** — Browse subscriptions organized by management group structure, enabling tenant-wide visibility

### Live Dashboard Widgets
Real-time sidebar widgets that refresh automatically:
- **Security Score** — Microsoft Defender for Cloud secure score percentage
- **Resources Count** — Total Azure resources via Resource Graph
- **Public Access Exposure** — Count of publicly accessible resources (Storage, SQL, App Services, Key Vaults, Container Registries)

### Orphaned Resource Detection (24 Types)
Based on [Azure Orphan Resources](https://github.com/dolevshor/azure-orphan-resources) methodology:
- **Compute** — Unattached App Service Plans, orphaned Availability Sets
- **Storage** — Unattached Managed Disks
- **Database** — Empty SQL Elastic Pools
- **Networking** — Unassociated Public IPs, detached NICs, unused NSGs, empty Route Tables, idle Load Balancers, Front Door WAF policies, Traffic Manager profiles, Application Gateways, empty VNets/Subnets, NAT Gateways, IP Groups, Private DNS Zones, orphaned Private Endpoints, VNet Gateways, DDoS Protection Plans
- **Other** — Empty Resource Groups, unused API Connections, expired Certificates

### Cost Optimization & Potential Savings
- Current month and historical cost analysis
- Month-over-month cost comparison and trends
- Cost breakdown by resource group, resource type, and region
- Identification of cost-saving opportunities

### Security Posture & Public Exposure
- Microsoft Defender for Cloud integration with real-time secure score
- Public access detection across Storage Accounts, SQL Servers, App Services, Key Vaults, and Container Registries
- Azure Policy compliance status and non-compliant resource identification
- Security recommendations and alert monitoring

### Entra ID Integration & Conditional Access
- Full Entra ID (Azure AD) management — users, groups, applications, service principals, devices
- Conditional access policy audit (e.g., policies without MFA enforcement)
- Inactive user detection, stale device identification
- RBAC role assignment audit across subscriptions

### Private Endpoint Support
- Private endpoint inventory and connectivity status
- PaaS resources without private endpoints (security gap detection)
- Private DNS zone configuration and VNet link analysis
- Container App and Azure OpenAI resources support private endpoint connectivity

### Managed Identity — Zero Hardcoded Keys
- All Azure API calls use `DefaultAzureCredential` (Managed Identity)
- No API keys, subscription IDs, or tenant IDs hardcoded in source code
- Configuration via environment variables only
- Cached credential singleton for performance

### Additional Capabilities
- **Export to CSV** — Download any query result for reporting and offline analysis
- **Azure Native Icons** — 700+ official Azure service SVG icons for intuitive category navigation
- **Well-Architected Framework** — Assess workloads against WAF pillars (Reliability, Security, Cost, Operations, Performance)
- **Landing Zone (CAF)** — Cloud Adoption Framework assessment and landing zone review
- **Azure Arc** — Hybrid and multi-cloud server management
- **API Management** — APIM instance monitoring, API inventory, policy diagnostics

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Azure CloudOps Intelligence Agent                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐     ┌──────────────────┐     ┌──────────────────────┐    │
│  │   Frontend   │────▶│   FastAPI         │────▶│   Azure OpenAI       │    │
│  │  (HTML/JS)   │     │   Backend         │     │   GPT-4o (119 Tools) │    │
│  │  MSAL.js     │◀────│   Python 3.11     │◀────│   Function Calling   │    │
│  └──────────────┘     └────────┬──────────┘     └──────────────────────┘    │
│        │                       │                                            │
│   Entra ID SSO          Managed Identity                                    │
│                                │                                            │
│  ┌─────────────────────────────┴────────────────────────────────────────┐   │
│  │                          Azure APIs                                  │   │
│  ├──────────────┬──────────────┬──────────────┬────────────────────────┤   │
│  │  Resource    │  Microsoft   │     Cost     │     Azure Resource     │   │
│  │  Graph       │  Graph       │  Management  │     Manager (ARM)      │   │
│  ├──────────────┼──────────────┼──────────────┼────────────────────────┤   │
│  │  Defender    │  Management  │   Entra ID   │   Azure Policy         │   │
│  │  for Cloud   │  Groups API  │   (Graph)    │   Compliance           │   │
│  └──────────────┴──────────────┴──────────────┴────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Your Azure Environment                               │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────────────┤
│   VMs    │ Storage  │ Networks │ Entra ID │ Databases│ All Other Resources  │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────────────────┘
```

### Technology Stack

| Component | Technology |
|-----------|------------|
| **Frontend** | HTML5, CSS3, JavaScript, MSAL.js 2.x |
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **AI Engine** | Azure OpenAI GPT-4o (119 function-calling tools) |
| **Azure APIs** | Resource Graph, Microsoft Graph, Cost Management, ARM, Defender, Management Groups |
| **Container** | Docker, Azure Container Apps |
| **Authentication** | Entra ID (Azure AD) via MSAL.js + Managed Identity for backend |
| **Icons** | 700+ official Azure service SVG icons |

---

## 📊 Live Dashboard Widgets

The dashboard includes real-time sidebar widgets that automatically load when a subscription is selected:

| Widget | Data Source | Description |
|--------|------------|-------------|
| **Security Score** | Microsoft Defender for Cloud | Displays the secure score percentage with color-coded status (green/yellow/red) |
| **Resources Count** | Azure Resource Graph | Total count of all resources in the selected subscription |
| **Public Access Exposure** | ARM API scan | Number of resources with public network access enabled (Storage, SQL, App Services, Key Vaults, Container Registries) |

---

## 📋 29 Operational Categories

The agent organizes **249+ pre-built prompts** across **29 categories**, each with dedicated Azure-native icons:

| # | Category | Quick Actions | Description |
|---|----------|:---:|-------------|
| 1 | **Entra ID (Azure AD)** | 14 | Users, groups, apps, devices, conditional access |
| 2 | **Access Control (IAM)** | 6 | RBAC role assignments, privileged access audit |
| 3 | **Landing Zone (CAF)** | 22 | CAF assessment, Platform & Application LZ review |
| 4 | **Well-Architected Framework** | 8 | Reliability, Security, Cost, Operations, Performance |
| 5 | **Networking** | 32 | VNets, NSGs, Firewalls, Load Balancers, WAF, vWAN |
| 6 | **Azure Private Link** | 14 | Private endpoints, PaaS security, connections |
| 7 | **Private DNS Zones** | 14 | DNS zones, VNet links, resolution issues |
| 8 | **Virtual Machines** | 15 | VM health, backup, monitoring, cost optimization |
| 9 | **Resource Management** | 6 | Inventory, search, and filter Azure resources |
| 10 | **Cost Optimization** | 7 | Cost analysis, comparisons, savings opportunities |
| 11 | **Security & Compliance** | 10 | Defender, security score, alerts, compliance |
| 12 | **Azure Policy** | 5 | Policy compliance and exemptions |
| 13 | **Monitoring & Alerts** | 11 | Alerts, monitoring gaps, VM Insights status |
| 14 | **Azure Backup** | 12 | VMs, disks, files, SQL backup protection status |
| 15 | **Update Management** | 6 | VM and Arc machine patches and compliance |
| 16 | **Tags Management** | 5 | Tag inventory and compliance |
| 17 | **Azure Arc** | 3 | Hybrid infrastructure management |
| 18 | **Azure Kubernetes (AKS)** | 5 | AKS clusters, monitoring, security posture |
| 19 | **VM Scale Sets** | 4 | Scale set monitoring and configuration |
| 20 | **App Services** | 5 | Web apps, monitoring, public access |
| 21 | **Azure SQL PaaS** | 7 | SQL Database, Managed Instance optimization |
| 22 | **PostgreSQL Servers** | 4 | PostgreSQL flexible servers management |
| 23 | **MySQL Servers** | 4 | MySQL flexible servers management |
| 24 | **Cosmos DB** | 4 | NoSQL database optimization |
| 25 | **Storage Accounts** | 10 | Capacity, security, file shares, cost optimization |
| 26 | **Orphaned Resources** | 24 | Unused disks, IPs, NICs, NSGs, empty RGs, and more |
| 27 | **API Management** | 5 | APIM instances, APIs, policies, diagnostics |
| 28 | **Automation** | 4 | Runbooks, automation accounts, scheduled tasks |
| 29 | **About** | — | Agent capabilities, version info, help |

---

## 📌 Prerequisites

Before deploying the solution, ensure you have:

| Requirement | Details |
|-------------|---------|
| **Azure Subscription** | With Contributor access |
| **Azure CLI** | Installed and logged in (`az login`) |
| **Docker Desktop** | Installed and running |
| **PowerShell 5.1+** | Or PowerShell Core 7.x |
| **Entra ID App Registration** | For user authentication (see [Entra ID Setup](docs/AZURE_AD_SETUP.md)) |
| **Azure OpenAI Resource** | With GPT-4o model deployed (Standard SKU — no PTU required) |

---

## 🚀 Quick Start — Automated Deployment

The fastest way to deploy is using the included PowerShell automation script that handles everything end-to-end.

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd AzureCloudOpsIntelligenceAgent
```

### Step 2: Create App Registration

1. Go to **Azure Portal** → **Microsoft Entra ID** → **App registrations**
2. Click **New registration**
3. Configure:
   - **Name**: `CloudOps Intelligence Agent` (or your preferred name)
   - **Supported account types**: Accounts in this organizational directory only
   - **Redirect URI**: Select **Single-page application (SPA)** — leave URL blank for now
4. Click **Register**

#### Note These Values (Required for Deployment Script)

After registration, find these values on the **Overview** page:

| Value | Where to Find | Script Parameter |
|-------|---------------|------------------|
| Application (client) ID | Overview → Application (client) ID | `-EntraAppClientId` |
| Directory (tenant) ID | Overview → Directory (tenant) ID | `-EntraTenantId` |

#### Configure API Permissions

1. Go to **API permissions** in your App Registration
2. Click **Add a permission** → **Microsoft Graph** → **Delegated permissions**
3. Select these permissions:
   - `openid`
   - `profile`
   - `email`
   - `User.Read`
4. Click **Add permissions**
5. Click **Grant admin consent for [Your Organization]** (requires admin)

### Step 3: Run Automated Deployment

```powershell
.\deploy-automated.ps1 `
    -ResourceGroupName "rg-cloudops-agent" `
    -Location "westeurope" `
    -ContainerRegistryName "youracrname" `
    -EntraAppClientId "<your-entra-app-client-id>" `
    -EntraTenantId "<your-entra-tenant-id>" `
    -SubscriptionId "<your-subscription-id>"
```

The script automatically:
1. ✅ **Validates subscription** — displays target subscription name & ID, prompts for confirmation before deploying
2. ✅ Registers all required Azure resource providers
3. ✅ Creates Azure Container Registry
4. ✅ Deploys Azure OpenAI (AI Foundry) with **smart TPM capacity negotiation** (see below)
5. ✅ Builds and pushes the Docker image
6. ✅ Creates Container App Environment
7. ✅ Deploys the Container App with System-Assigned Managed Identity
8. ✅ Assigns all required RBAC roles (Least-Privilege, READ-ONLY)
9. ✅ Configures all environment variables automatically

**No manual configuration required — everything is 100% automated!**

**Estimated deployment time: 10–15 minutes**

#### Subscription Validation

When `-SubscriptionId` is provided, the script explicitly sets the Azure context to that subscription. If omitted, it uses the currently active subscription. In **both** cases, the script displays the target subscription name and ID in a highlighted box and asks for explicit confirmation (`Y/N`) before proceeding — preventing accidental deployments to the wrong subscription.

#### Smart TPM Capacity Negotiation

The solution requires high Tokens-Per-Minute (TPM) throughput for optimal performance. The script implements a two-phase strategy:

**Phase 1 — Initial Deployment (step-down by 2K)**
The script starts at **80K TPM** and tries decreasing by **2K** increments until it finds available quota (minimum 10K). SKU priority order:
1. **GlobalStandard** (best latency — global routing)
2. **DataZoneStandard** (fallback — regional constraints)
3. **Standard** (legacy regions)
4. **GPT-4o-mini** (last resort if GPT-4o unavailable)

**Phase 2 — Post-Deployment Scale-Up (find the sweet spot)**
After the model is deployed, the script waits for stabilisation and then attempts to **scale UP** the TPM from the initial value back toward **80K**, stepping down by **2K** until it finds the highest available quota. This two-phase approach ensures:
- Deployment always succeeds (even with limited quota)
- The final TPM is maximised to the highest value the subscription supports
- If scale-up fails, a manual command is printed for later use when quota becomes available

### Deployment Parameters

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| `-ResourceGroupName` | ✅ | — | Name of the resource group to create/use |
| `-ContainerRegistryName` | ✅ | — | Globally unique ACR name (lowercase, no dashes) |
| `-EntraAppClientId` | ✅ | — | Entra ID Application (Client) ID |
| `-EntraTenantId` | ✅ | — | Azure AD Tenant ID |
| `-Location` | ❌ | `westeurope` | Azure region (e.g., `qatarcentral`, `eastus`) |
| `-OpenAIResourceName` | ❌ | Auto-generated | Custom name for the OpenAI resource |
| `-ContainerAppName` | ❌ | `cloudops-agent` | Custom name for the Container App |
| `-SubscriptionId` | ❌ | Current context | Target subscription — script validates and asks for confirmation before deploying |
| `-EnableLogAnalytics` | ❌ | `$false` | Enable Log Analytics workspace |

### Step 4: After Deployment — Add Redirect URI

After deployment completes, you'll receive the application URL. Then:

1. Go back to **App Registration** → **Authentication**
2. Under **Single-page application** → **Redirect URIs**, add:
   ```
   https://<your-container-app>.azurecontainerapps.io/login.html
   ```
3. Click **Save**
4. Access your application at `https://<your-container-app>.azurecontainerapps.io`

---

## 📋 Manual Deployment

For environments where the automated script cannot be used, follow these manual steps.

### Step 1: Create Azure Resources

```bash
# Set variables
RESOURCE_GROUP="rg-cloudops-agent"
LOCATION="westeurope"
ACR_NAME="cloudopsagentacr"
OPENAI_NAME="cloudops-openai"

# Create Resource Group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Azure Container Registry
az acr create --name $ACR_NAME --resource-group $RESOURCE_GROUP --sku Basic --admin-enabled true

# Create Azure OpenAI
az cognitiveservices account create \
    --name $OPENAI_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --kind OpenAI \
    --sku S0

# Deploy GPT-4o model (start with highest TPM your quota allows; 80K recommended)
az cognitiveservices account deployment create \
    --name $OPENAI_NAME \
    --resource-group $RESOURCE_GROUP \
    --deployment-name "gpt-4o" \
    --model-name "gpt-4o" \
    --model-version "2024-08-06" \
    --model-format OpenAI \
    --sku-capacity 80 \
    --sku-name "GlobalStandard"
# If capacity errors occur, reduce --sku-capacity (try 60, 40, 30, 20, 10)
# or change --sku-name to "DataZoneStandard" / "Standard"
```

### Step 2: Build and Deploy Container

```bash
# Build Docker image
docker build -t cloudops-agent:latest .

# Tag and push to ACR
az acr login --name $ACR_NAME
docker tag cloudops-agent:latest $ACR_NAME.azurecr.io/cloudops-agent:latest
docker push $ACR_NAME.azurecr.io/cloudops-agent:latest

# Deploy to Azure Container Apps
az containerapp up \
    --name cloudops-agent \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --image $ACR_NAME.azurecr.io/cloudops-agent:latest \
    --ingress external \
    --target-port 8000
```

### Step 3: Configure Environment Variables

Set the required environment variables on the Container App (see [Configuration](#-configuration) section below).

---

## ⚙️ Configuration

### Environment Variables

These are configured automatically by the deployment script. For manual setup or troubleshooting:

| Variable | Required | Description |
|----------|:--------:|-------------|
| `AZURE_OPENAI_ENDPOINT` | ✅ | Azure OpenAI resource endpoint URL |
| `AZURE_OPENAI_API_KEY` | ✅ | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | ✅ | GPT-4o deployment name (default: `gpt-4o`) |
| `AZURE_OPENAI_API_VERSION` | ❌ | API version (default: `2024-12-01-preview`) |
| `ENTRA_APP_CLIENT_ID` | ✅ | Entra ID Application (Client) ID |
| `ENTRA_TENANT_ID` | ✅ | Entra ID Tenant ID |
| `AZURE_SUBSCRIPTION_ID` | ❌ | Default subscription (user can switch in UI) |
| `USE_MANAGED_IDENTITY` | ❌ | Set to `true` for production (default) |

---

## 🔐 Post-Deployment RBAC

Assign the following roles to the Container App's **Managed Identity** at the subscription scope:

| Role | Scope | Purpose |
|------|-------|---------|
| **Reader** | Subscription(s) | Query all Azure resources |
| **Cost Management Reader** | Subscription(s) | Access cost and billing data |
| **Security Reader** | Subscription(s) | Read Defender for Cloud secure scores and alerts |
| **Management Group Reader** | Tenant Root Group | Browse management group hierarchy for subscription dropdown |
| **Directory Readers** | Entra ID | Query users, groups, devices, conditional access policies |

```bash
# Example: Assign Reader role to the Container App managed identity
MANAGED_IDENTITY_PRINCIPAL_ID=$(az containerapp show \
    --name cloudops-agent \
    --resource-group rg-cloudops-agent \
    --query identity.principalId -o tsv)

az role assignment create \
    --assignee $MANAGED_IDENTITY_PRINCIPAL_ID \
    --role "Reader" \
    --scope "/subscriptions/<your-subscription-id>"

az role assignment create \
    --assignee $MANAGED_IDENTITY_PRINCIPAL_ID \
    --role "Cost Management Reader" \
    --scope "/subscriptions/<your-subscription-id>"

az role assignment create \
    --assignee $MANAGED_IDENTITY_PRINCIPAL_ID \
    --role "Security Reader" \
    --scope "/subscriptions/<your-subscription-id>"

# Management Group Reader at tenant root (for subscription hierarchy dropdown)
az role assignment create \
    --assignee $MANAGED_IDENTITY_PRINCIPAL_ID \
    --role "Management Group Reader" \
    --scope "/providers/Microsoft.Management/managementGroups/<tenant-root-group-id>"
```

---

## 🔒 Security & Data Privacy

### Zero Trust Architecture

| Aspect | Details |
|--------|---------|
| **Data Storage** | ❌ Zero customer data stored — all queries are real-time |
| **Data Transmission** | ✅ All communication over HTTPS/TLS 1.2+ |
| **Query Processing** | ✅ Direct Azure API calls — no intermediate storage |
| **AI Processing** | ✅ Azure OpenAI (your tenant) — data stays in your Azure |
| **Credentials** | ✅ Managed Identity only — no hardcoded keys or secrets |

### Security Features

- **Entra ID Authentication** — Enterprise SSO with MFA support via MSAL.js
- **Managed Identity** — All Azure API calls use `DefaultAzureCredential`; zero stored credentials
- **Conditional Access** — Supports Entra ID conditional access policies
- **Audit Logging** — Full audit trail via Azure Monitor and Log Analytics
- **Private Endpoint Ready** — Container App and Azure OpenAI can be deployed with private endpoints for network isolation
- **RBAC** — Fine-grained access control via Azure role assignments

### Network Architecture Options

```
Option 1: Public Endpoint (Default)
┌──────────────┐     ┌──────────────────┐
│   Users      │────▶│  Container App   │
│  (Internet)  │     │  (Public FQDN)   │
└──────────────┘     └──────────────────┘

Option 2: Private Endpoint (Enterprise)
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Users      │────▶│  App Gateway /   │────▶│  Container App   │
│  (VPN/ER)    │     │  Front Door      │     │  (Private VNet)  │
└──────────────┘     └──────────────────┘     └──────────────────┘
```

### Compliance & Regional Deployment

- **Regional Availability** — Deploy in any Azure region including **Qatar Central**
- **Data Residency** — All data processing occurs within your Azure tenant
- **No PTU Required** — Works with Azure OpenAI Standard (On-Demand) SKU
- **IT Workload Optimized** — Designed for IT operations, no high-throughput AI requirements

---

## 📊 Sample Prompts

### Cost Optimization
```
"What is my current month cost?"
"Compare costs between this month and last month"
"Show cost breakdown by resource group"
"What are the potential savings opportunities?"
```

### Security & Public Exposure
```
"Show my Defender for Cloud secure score"
"List resources with public access enabled"
"Show PaaS resources without private endpoints"
"What policies are being violated?"
```

### Orphaned Resources
```
"Find all orphaned resources in my subscription"
"Show unattached managed disks"
"List orphaned public IP addresses"
"Find empty resource groups with no resources"
```

### Entra ID & Conditional Access
```
"Show users inactive for 30 days"
"List all global administrators"
"Show conditional access policies without MFA"
"List app registrations with expiring credentials"
```

### Resource Management
```
"Show all virtual machines across subscriptions"
"List resources without tags"
"What resources are in each region?"
"Show all AKS clusters and their status"
```

### Networking & Private Link
```
"Show VNets and their peering status"
"List NSGs with overly permissive rules"
"Show private endpoints and their connections"
"Find resources missing private endpoints"
```

---

## 🔌 API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard (HTML) |
| `/login.html` | GET | Entra ID login page |
| `/health` | GET | Health check |
| `/api/auth-config` | GET | Authentication configuration for MSAL.js |
| `/api/chat` | POST | Main AI chat endpoint (119 tools) |
| `/api/subscriptions` | GET | List accessible subscriptions |
| `/api/subscriptions-hierarchy` | GET | Subscriptions organized by management group |
| `/api/security-score/{subscription_id}` | GET | Defender for Cloud secure score |
| `/api/resource-count/{subscription_id}` | GET | Total resource count via Resource Graph |
| `/api/public-access-exposure/{subscription_id}` | GET | Public access exposure scan |
| `/api/export-csv/{query_id}` | GET | Export query results as CSV |

---

## 📁 Project Structure

```
├── main.py                          # FastAPI application entry point
├── openai_agent.py                  # Azure OpenAI GPT-4o with 119 tools
├── azure_resource_manager.py        # Resource Graph, Management Groups, Defender
├── azure_cost_manager.py            # Cost Management API integration
├── auth_manager.py                  # Entra ID token validation & Managed Identity
├── entra_id_manager.py              # Microsoft Graph API (users, groups, policies)
├── universal_azure_operations.py    # Universal Azure REST API operations
├── universal_cli_deployment.py      # Azure CLI deployment operations
├── azure_cli_operations.py          # Azure CLI command execution
├── modern_resource_deployment.py    # ARM template deployment engine
├── intelligent_template_generator.py # Dynamic ARM template generation
├── intelligent_parameter_collector.py# Smart parameter collection
├── azure_schema_provider.py         # Azure resource schema provider
├── logic_app_client.py              # Logic App integration
├── api_version_overrides.py         # Azure API version management
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Container image definition
├── deploy-automated.ps1             # One-touch deployment script
├── static/
│   ├── index.html                   # Main dashboard (29 categories, live widgets)
│   ├── login.html                   # Entra ID login page with MSAL.js
│   └── logout.js                    # Secure logout handler
├── Icons/                           # 700+ official Azure service SVG icons
│   ├── compute/                     # VM, AKS, App Service, VMSS icons
│   ├── networking/                  # VNet, NSG, Load Balancer, Private Link icons
│   ├── databases/                   # SQL, PostgreSQL, MySQL, Cosmos DB icons
│   ├── storage/                     # Storage Account, Recovery Vault icons
│   ├── security/                    # Defender, Key Vault, Sentinel icons
│   ├── identity/                    # Entra ID, IAM icons
│   ├── management + governance/     # Monitor, Policy, Arc, Advisor icons
│   └── ...                          # 20+ Azure service categories
└── docs/
    └── AZURE_AD_SETUP.md            # Entra ID app registration guide
```

---

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| **401 Unauthorized** | Verify Entra ID App Registration redirect URI matches your Container App URL |
| **No subscriptions in dropdown** | Assign **Reader** role to Managed Identity on target subscriptions |
| **Management groups not showing** | Assign **Management Group Reader** at Tenant Root Group scope |
| **Security Score shows N/A** | Assign **Security Reader** role and ensure Defender for Cloud is enabled |
| **No cost data** | Assign **Cost Management Reader** role on subscriptions |
| **Public exposure widget empty** | Ensure **Reader** role covers all subscriptions to scan |
| **OpenAI timeout** | Verify Azure OpenAI resource is deployed and GPT-4o model is available |
| **Container not starting** | Check logs: `az containerapp logs show --name <app> --resource-group <rg>` |
| **Orphaned resource scan slow** | Large subscriptions may take 30–60s; the agent scans 24 resource types |
| **Entra ID queries failing** | Grant **Directory Readers** role to the Managed Identity in Entra ID |

### View Container App Logs

```bash
az containerapp logs show \
    --name cloudops-agent \
    --resource-group rg-cloudops-agent \
    --follow
```

---

## 👨‍💻 About the Author

**Zahir Shah**

- Senior Cloud & AI Solutions Architect
- Based in Qatar
- Specializing in Azure, AI/ML, and Enterprise Architecture

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?style=flat-square&logo=linkedin)](https://linkedin.com/in/yourprofile)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?style=flat-square&logo=github)](https://github.com/zhshah)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Made with ❤️ for the Azure Community
</p>

<p align="center">
  <a href="#azure-cloudops-intelligence-agent">Back to Top ⬆️</a>
</p>
