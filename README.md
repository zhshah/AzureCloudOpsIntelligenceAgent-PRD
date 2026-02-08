# Azure CloudOps Intelligence Agent

**AI-Powered Azure Infrastructure Management Platform**

[![Azure](https://img.shields.io/badge/Azure-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com)
[![OpenAI](https://img.shields.io/badge/Azure%20OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Container Apps](https://img.shields.io/badge/Container%20Apps-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com/en-us/products/container-apps)

---

## Overview

Azure CloudOps Intelligence Agent is an AI-powered platform that enables natural language interaction for Azure infrastructure management. Built on Azure OpenAI GPT-4o with **119 integrated tools** and **29 operational categories**, it provides comprehensive cloud operations capabilities through a single conversational interface.

---

## Dashboard Preview

![Agent Dashboard](Agent%20Screenshot.png)

---

## Architecture

![Solution Architecture](Architecture%20Image%20for%20Github.png)

### Component Architecture

| Component | Purpose |
|-----------|---------|
| **Azure Container Apps** | Hosts the application with auto-scaling and managed identity |
| **Azure OpenAI (GPT-4o)** | Natural language processing with 119 function-calling tools |
| **Microsoft Entra ID** | User authentication via MSAL.js (SPA flow) |
| **Managed Identity** | Secure, credential-free Azure API access (zero hardcoded secrets) |
| **Azure Resource Graph** | KQL-based resource queries across subscriptions |
| **Cost Management API** | Billing and cost data with trend analysis |
| **Management Groups API** | Subscription hierarchy with management group tree |
| **Azure Container Registry** | Private container image storage |

---

## Key Features

### 29 Operational Categories

| # | Category | Description |
|---|----------|-------------|
| 1 | **Entra ID & Identity** | Users, groups, roles, service principals, app registrations |
| 2 | **IAM & Access Control** | RBAC assignments, role definitions, PIM, access reviews |
| 3 | **Landing Zones** | Subscription hierarchy, management groups, governance |
| 4 | **Well-Architected** | WAF pillars assessment, reliability, security, cost optimization |
| 5 | **Azure Resources** | Full inventory, resource details, types, locations |
| 6 | **Virtual Machines** | VM status, sizes, configurations, performance |
| 7 | **Security & Compliance** | Defender for Cloud, policy compliance, secure score |
| 8 | **Tags & Governance** | Tag compliance, untagged resources, tag policies |
| 9 | **Networking** | VNets, NSGs, load balancers, DNS, peering |
| 10 | **Storage** | Storage accounts, blobs, access tiers, lifecycle |
| 11 | **Databases** | SQL, Cosmos DB, PostgreSQL, MySQL instances |
| 12 | **Cost Analysis** | Current month costs, daily trends, service breakdown |
| 13 | **Cost Optimization** | Savings recommendations, reserved instances, right-sizing |
| 14 | **Budgets & Alerts** | Budget status, cost alerts, spending thresholds |
| 15 | **Container Services** | AKS, Container Apps, Container Instances, ACR |
| 16 | **App Services** | Web Apps, Function Apps, App Service Plans |
| 17 | **Monitoring** | Azure Monitor, Log Analytics, Application Insights |
| 18 | **DevOps** | Azure DevOps, pipelines, repos, boards integration |
| 19 | **Backup & DR** | Recovery Services, backup policies, replication |
| 20 | **Load Testing** | Azure Load Testing, performance benchmarks |
| 21 | **Azure Policy** | Policy assignments, compliance reports, definitions |
| 22 | **Advisor** | Azure Advisor recommendations across all pillars |
| 23 | **Activity Logs** | Audit logs, operations history, change tracking |
| 24 | **Resource Deployment** | Natural language resource creation with approval workflows |
| 25 | **Resource Health** | Service health, planned maintenance, health alerts |
| 26 | **Subscriptions** | Multi-subscription management, hierarchy navigation |
| 27 | **Management Groups** | Group hierarchy, governance scope, policy inheritance |
| 28 | **Private Endpoints** | Private link connectivity, DNS resolution |
| 29 | **Orphaned Resources** | 24 resource types: unused disks, NICs, IPs, NSGs, and more |

### 119 AI-Powered Tools

The agent includes 119 Azure OpenAI function-calling tools covering:
- Resource inventory and querying (Azure Resource Graph)
- Cost management and optimization
- Security posture and compliance
- Network topology analysis
- Identity and access management
- Resource deployment with approval workflows
- Orphaned resource detection (based on [Azure Orphan Resources](https://github.com/dolevshor/azure-orphan-resources))

### Live Dashboard Widgets

| Widget | Description |
|--------|-------------|
| **Security Score** | Real-time Microsoft Defender for Cloud secure score |
| **Monthly Cost** | Current month's Azure spending |
| **Resource Count** | Total resources via Azure Resource Graph (direct API) |
| **Public Exposure** | Count of publicly accessible resources (IPs, open ports, public storage) |

### Subscription Hierarchy with Management Groups

- **Management Group tree view** in sidebar dropdown
- Nested hierarchy showing Tenant Root Group → child groups → subscriptions
- Auto-selects subscription context for all queries
- Works across multi-subscription environments

---

## Prerequisites

### Azure Requirements

| Requirement | Description | Verification |
|-------------|-------------|--------------|
| **Azure Subscription** | With Contributor or Owner permissions | `az account show` |
| **Azure CLI** | Version 2.50+ | `az --version` |
| **Azure OpenAI Access** | Subscription must have OpenAI approved | [Request access](https://aka.ms/oai/access) |
| **PowerShell 5.1+** | For deployment script | `$PSVersionTable.PSVersion` |
| **Docker** (optional) | For local container builds | `docker --version` |

### Required Permissions

| Role | Scope | Purpose |
|------|-------|---------|
| **Contributor** | Subscription | Create resources (OpenAI, ACR, Container App) |
| **User Access Administrator** | Subscription | Assign RBAC roles to Managed Identity |

> **Alternative**: **Owner** role includes both permissions.

### Entra ID App Registration

An App Registration is required for user authentication. See [docs/AZURE_AD_SETUP.md](docs/AZURE_AD_SETUP.md) for detailed setup instructions.

**Quick steps:**
1. Azure Portal → Microsoft Entra ID → App registrations → New registration
2. Name: `CloudOps Intelligence Agent`
3. Redirect URI: `Single-page application (SPA)` → `https://<your-app-url>/login.html`
4. Note the **Application (client) ID** and **Tenant ID**

---

## Deployment

### Automated Deployment (Recommended)

The included `deploy-automated.ps1` script handles end-to-end setup:

```powershell
.\deploy-automated.ps1 `
  -EntraAppClientId "<your-client-id>" `
  -EntraTenantId "<your-tenant-id>" `
  -SubscriptionId "<your-subscription-id>" `
  -ContainerRegistryName "<your-acr-name>"
```

**What the script creates:**
1. Azure Resource Group
2. Azure OpenAI service with GPT-4o deployment
3. Azure Container Registry
4. Docker image build and push
5. Azure Container App with managed identity
6. RBAC role assignments (Reader, Cost Management Reader, Security Reader)
7. Environment variable configuration

### Manual Deployment

#### 1. Clone the Repository
```bash
git clone <repository-url>
cd AzureCloudOpsIntelligenceAgent
```

#### 2. Build Docker Image
```bash
docker build -t cloudops-agent .
```

#### 3. Push to Azure Container Registry
```bash
az acr login --name <your-acr>
docker tag cloudops-agent <your-acr>.azurecr.io/cloudops-agent:latest
docker push <your-acr>.azurecr.io/cloudops-agent:latest
```

#### 4. Deploy to Azure Container Apps
```bash
az containerapp create \
  --name cloudops-agent \
  --resource-group <your-rg> \
  --image <your-acr>.azurecr.io/cloudops-agent:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3
```

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | `https://your-openai.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | `(from Azure Portal)` |
| `AZURE_OPENAI_DEPLOYMENT` | GPT-4o deployment name | `gpt-4o` |
| `ENTRA_APP_CLIENT_ID` | Entra ID App Registration client ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `ENTRA_TENANT_ID` | Entra ID tenant ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `AZURE_SUBSCRIPTION_ID` | Default Azure subscription | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |

### Post-Deployment RBAC

The Container App's managed identity requires these roles:

| Role | Scope | Purpose |
|------|-------|---------|
| **Reader** | Subscription | Read all resource metadata |
| **Cost Management Reader** | Subscription | Access cost and billing data |
| **Security Reader** | Subscription | Access Defender for Cloud data |
| **Management Group Reader** | Tenant Root Group | Read management group hierarchy |

```bash
# Get the Container App's managed identity principal ID
PRINCIPAL_ID=$(az containerapp show --name cloudops-agent --resource-group <your-rg> --query identity.principalId -o tsv)

# Assign required roles
az role assignment create --assignee $PRINCIPAL_ID --role "Reader" --scope /subscriptions/<sub-id>
az role assignment create --assignee $PRINCIPAL_ID --role "Cost Management Reader" --scope /subscriptions/<sub-id>
az role assignment create --assignee $PRINCIPAL_ID --role "Security Reader" --scope /subscriptions/<sub-id>
```

---

## Project Structure

```
├── main.py                           # FastAPI application (API endpoints, live widgets)
├── openai_agent.py                   # Azure OpenAI integration (119 tools, function calling)
├── azure_resource_manager.py         # Resource Graph queries & management group hierarchy
├── azure_cost_manager.py             # Cost Management API integration
├── auth_manager.py                   # Entra ID authentication handler
├── entra_id_manager.py               # Entra ID operations (users, groups, roles)
├── universal_azure_operations.py     # Cross-service Azure operations
├── universal_cli_deployment.py       # CLI-based resource deployment
├── azure_cli_operations.py           # Azure CLI command execution
├── modern_resource_deployment.py     # Resource deployment engine
├── intelligent_template_generator.py # ARM/Bicep template generation
├── intelligent_parameter_collector.py# Smart parameter collection
├── azure_schema_provider.py          # Azure resource schema provider
├── api_version_overrides.py          # API version management
├── logic_app_client.py               # Logic App approval workflow integration
├── requirements.txt                  # Python dependencies
├── Dockerfile                        # Container build configuration
├── deploy-automated.ps1              # Automated deployment script (PowerShell)
├── static/
│   ├── index.html                    # Main dashboard (29 categories, live widgets)
│   ├── login.html                    # Entra ID login page (MSAL.js)
│   └── logout.js                     # Logout handler
├── Icons/                            # Official Azure service icons (500+ SVGs)
│   ├── ai + machine learning/
│   ├── analytics/
│   ├── compute/
│   ├── containers/
│   ├── databases/
│   ├── networking/
│   ├── security/
│   ├── storage/
│   └── ... (20+ categories)
├── azure_function/                   # Azure Function for approval webhooks
│   ├── function_app.py
│   ├── function.json
│   ├── host.json
│   └── requirements.txt
└── docs/
    └── AZURE_AD_SETUP.md             # Entra ID App Registration setup guide
```

---

## Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Backend runtime |
| FastAPI | 0.100+ | Web framework with async support |
| Azure OpenAI SDK | Latest | GPT-4o function calling |
| Azure Identity | Latest | DefaultAzureCredential / Managed Identity |
| Azure Resource Graph | Latest | Cross-subscription resource queries |
| Azure Cost Management | Latest | Billing and cost APIs |
| Azure Management Groups | 1.0.0 | Subscription hierarchy |
| MSAL.js | 2.x | Frontend Entra ID authentication |
| Docker | Latest | Containerization |
| Azure Container Apps | Latest | Hosting platform |

---

## Security

- **Zero hardcoded secrets** — All credentials via environment variables or Managed Identity
- **DefaultAzureCredential** — Automatic credential chain (Managed Identity → Azure CLI → Environment)
- **Entra ID SSO** — Enterprise single sign-on via MSAL.js
- **RBAC-based access** — Principle of least privilege for managed identity
- **No API keys in code** — All sensitive values sourced from environment variables

---

## Troubleshooting

### Subscription Dropdown Not Loading
- Verify **Management Group Reader** role is assigned at Tenant Root Group scope
- Check Container App logs: `az containerapp logs show --name <app> --resource-group <rg>`
- Ensure `azure-mgmt-managementgroups==1.0.0` is in requirements.txt

### Widgets Showing N/A
- Confirm **Reader**, **Cost Management Reader**, **Security Reader** roles are assigned
- Check the managed identity has access to the selected subscription
- Review browser console (F12) for API errors

### Authentication Issues
- Verify Entra ID App Registration redirect URI matches your deployment URL
- Ensure `ENTRA_APP_CLIENT_ID` and `ENTRA_TENANT_ID` environment variables are set
- Check that the App Registration has `User.Read` API permission

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
