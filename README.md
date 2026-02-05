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
- **Conditional Access Policies** - Entra ID security posture

### 🖥️ Resource Management
- **Full Inventory** - All Azure resources across subscriptions
- **Multi-Subscription Support** - Query across your entire Azure estate
- **Resource Search** - Natural language resource discovery
- **Tag Management** - Inventory and compliance for tagging standards
- **Resource Health** - Status monitoring for all resource types

### 🚀 Automated Deployments
- **Natural Language Deployments** - "Create a VM named prod-web-01 in West Europe"
- **Human-in-the-Loop Approval** - Email-based approval workflow via Logic Apps
- **Supported Resources**:
  - Virtual Machines (Windows/Linux)
  - Storage Accounts
  - SQL Databases
  - Resource Groups
  - Virtual Networks
  - Managed Disks
  - Availability Sets

### 📊 Monitoring & Alerts
- **VM Insights** - Monitoring status and gaps
- **App Insights Coverage** - Applications without monitoring
- **Azure Monitor Agent** - Deployment status for VMs and Arc machines
- **Alert Rules** - Inventory of active monitoring alerts

### 🔄 Update Management
- **Pending Updates** - Critical, security, and other updates
- **Patch Compliance** - VMs and Arc machines compliance status
- **Failed Updates** - Troubleshooting for deployment failures
- **Reboot Status** - Machines requiring restart

### 🌐 Azure Arc (Hybrid Management)
- **Arc-Enabled Servers** - On-premises and multi-cloud machines
- **Arc SQL Servers** - Hybrid SQL Server management
- **Agent Status** - Connected, disconnected, and error states
- **Extension Management** - Deployed extensions inventory

### 👥 Microsoft Entra ID (Identity)
- **Tenant Overview** - Users, groups, apps, and devices
- **Inactive Users** - Users not signed in for 30+ days
- **Guest Users** - External identity management
- **Privileged Roles** - Global Admins and high-privilege accounts
- **App Registrations** - Application inventory and expiring credentials
- **Conditional Access** - Policy inventory and coverage

### 🗄️ Database Management
- **Azure SQL** - Databases and managed instances
- **PostgreSQL** - Flexible and single servers
- **MySQL** - Database inventory and configuration
- **Cosmos DB** - Account details and public access status

### 📦 Additional Capabilities
- **App Services** - Web apps, function apps, monitoring status
- **AKS Clusters** - Kubernetes inventory, networking, monitoring
- **Storage Accounts** - Capacity, access tiers, lifecycle policies
- **API Management** - APIM instances and configuration
- **Virtual Machine Scale Sets** - VMSS inventory and scaling

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
| **Workflow** | Azure Logic Apps |
| **Deployment** | ARM Templates, Azure CLI |

---

## 📋 Prerequisites

Before deploying, ensure you have:

- **Azure Subscription** with Owner or Contributor access
- **Azure OpenAI Service** with GPT-4o model deployed
- **Azure Container Registry** (or create during deployment)
- **Azure CLI** installed and logged in (`az login`)
- **Git** installed for cloning the repository

### Required Azure RBAC Roles

| Role | Scope | Purpose |
|------|-------|---------|
| `Reader` | Subscription | Resource inventory queries |
| `Cost Management Reader` | Subscription | Cost analysis data |
| `Contributor` | Subscription | Resource deployments (optional) |
| `User Access Administrator` | Subscription | Managed identity assignment |

---

## 🚀 Deployment Guide

### Option 1: Automated Deployment (Recommended)

Use the provided PowerShell script for a fully automated deployment.

#### Step 1: Clone the Repository

```powershell
git clone https://github.com/zhshah/AzureCloudOpsIntelligenceAgent-PRD.git
cd AzureCloudOpsIntelligenceAgent-PRD
```

#### Step 2: Configure Environment Variables

Create a `.env` file in the root directory:

```env
# Azure OpenAI Configuration (Required)
AZURE_OPENAI_ENDPOINT=https://your-openai-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Azure Configuration (Required)
AZURE_SUBSCRIPTION_ID=your-subscription-id

# Authentication
USE_MANAGED_IDENTITY=true

# Approval Workflow (Optional)
ENABLE_APPROVAL_WORKFLOW=true
LOGIC_APP_WEBHOOK_URL=https://your-logic-app-url

# User Context (Optional)
USER_EMAIL=admin@yourdomain.com
USER_NAME=Azure Admin
```

#### Step 3: Run Automated Deployment Script

```powershell
# Make script executable and run
.\deploy-complete.ps1 -ResourceGroupName "rg-cloudops-agent" `
                      -Location "westeurope" `
                      -ContainerRegistryName "yourcrname" `
                      -ContainerAppName "cloudops-agent"
```

The script will:
1. ✅ Create Resource Group (if not exists)
2. ✅ Create Azure Container Registry
3. ✅ Build and push container image
4. ✅ Create Container Apps Environment
5. ✅ Deploy Container App with Managed Identity
6. ✅ Configure environment variables
7. ✅ Assign required RBAC roles
8. ✅ Output the application URL

#### Step 4: Verify Deployment

```powershell
# Get the application URL
az containerapp show --name cloudops-agent --resource-group rg-cloudops-agent --query "properties.configuration.ingress.fqdn" -o tsv
```

---

### Option 2: Manual Deployment (Step-by-Step)

For more control over the deployment process, follow these manual steps.

#### Step 1: Clone the Repository

```bash
git clone https://github.com/zhshah/AzureCloudOpsIntelligenceAgent-PRD.git
cd AzureCloudOpsIntelligenceAgent-PRD
```

#### Step 2: Create Azure Resources

```bash
# Set variables
RESOURCE_GROUP="rg-cloudops-agent"
LOCATION="westeurope"
ACR_NAME="yourcrname"
CONTAINER_APP_NAME="cloudops-agent"
ENVIRONMENT_NAME="cloudops-env"

# Create Resource Group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Azure Container Registry
az acr create --name $ACR_NAME --resource-group $RESOURCE_GROUP --sku Basic --admin-enabled true

# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query "username" -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)
```

#### Step 3: Build and Push Container Image

```bash
# Build using ACR Tasks (no local Docker required)
az acr build --registry $ACR_NAME --image cloudops-agent:latest --file Dockerfile .

# Verify image
az acr repository list --name $ACR_NAME --output table
```

#### Step 4: Create Container Apps Environment

```bash
# Create Container Apps Environment
az containerapp env create \
  --name $ENVIRONMENT_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION
```

#### Step 5: Deploy Container App

```bash
# Deploy the container app
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
    AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/ \
    AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o \
    AZURE_OPENAI_API_VERSION=2024-02-15-preview \
    AZURE_SUBSCRIPTION_ID=your-subscription-id \
    USE_MANAGED_IDENTITY=true
```

#### Step 6: Enable Managed Identity

```bash
# Enable system-assigned managed identity
az containerapp identity assign \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --system-assigned

# Get the principal ID
PRINCIPAL_ID=$(az containerapp show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --query "identity.principalId" -o tsv)
SUBSCRIPTION_ID=$(az account show --query "id" -o tsv)

# Assign Reader role for resource queries
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Reader" \
  --scope /subscriptions/$SUBSCRIPTION_ID

# Assign Cost Management Reader role
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Cost Management Reader" \
  --scope /subscriptions/$SUBSCRIPTION_ID

# (Optional) Assign Contributor role for deployments
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Contributor" \
  --scope /subscriptions/$SUBSCRIPTION_ID
```

#### Step 7: Get Application URL

```bash
# Get the FQDN
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

#### Step 2: Configure Environment

Create `.env` file with your Azure credentials:

```env
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_SUBSCRIPTION_ID=your-subscription-id
USE_MANAGED_IDENTITY=false
```

#### Step 3: Run the Application

```bash
python main.py
```

Access the dashboard at: `http://localhost:8000`

---

## 💡 Usage Examples

### Cost Analysis
```
"Show me cost breakdown by service for this month"
"What are my top 10 most expensive resources?"
"Find cost savings opportunities"
"Show costs by resource group for the last 30 days"
```

### Security & Compliance
```
"Show security recommendations"
"List non-compliant resources"
"What policies are failing?"
"Show resources with public access"
```

### Resource Management
```
"Show all virtual machines"
"List storage accounts without private endpoints"
"Find resources tagged with Environment=Production"
"Show VMs without backup"
```

### Deployments
```
"Create a Windows VM named prod-web-01 in West Europe"
"Deploy a storage account named stproddata in East US"
"Create a resource group named rg-production in UK South"
```

### Identity & Access
```
"Show Entra ID overview"
"List users who haven't signed in for 30 days"
"Show Global Administrators"
"List expiring app credentials"
```

---

## 📊 Dashboard Features

- **Quick Start Cards** - One-click access to common operations
- **Category Tiles** - Organized access to all capabilities
- **Multi-Subscription Selector** - Query across subscriptions
- **Real-time Stats** - Health score, monthly cost, resource count
- **Export to CSV** - Download full query results
- **Responsive Design** - Works on desktop, tablet, and mobile

---

## 🔐 Security Features

- **Managed Identity** - No stored credentials in the application
- **Entra ID Authentication** - Enterprise SSO integration
- **JWT Token Validation** - Secure API access
- **RBAC Integration** - Azure role-based permissions
- **Audit Logging** - Track all operations
- **Data Integrity** - Only real Azure API data, never fabricated

---

## 🔧 Configuration Options

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Yes | Azure OpenAI service endpoint |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Yes | GPT-4o deployment name |
| `AZURE_OPENAI_API_VERSION` | Yes | API version (e.g., 2024-02-15-preview) |
| `AZURE_SUBSCRIPTION_ID` | Yes | Default Azure subscription ID |
| `USE_MANAGED_IDENTITY` | Yes | Enable managed identity auth (true/false) |
| `ENABLE_APPROVAL_WORKFLOW` | No | Enable deployment approvals (true/false) |
| `LOGIC_APP_WEBHOOK_URL` | No | Logic App URL for approvals |
| `USER_EMAIL` | No | Default user email for notifications |
| `USER_NAME` | No | Default user display name |
| `COSMOS_ENDPOINT` | No | Cosmos DB endpoint for state storage |
| `COSMOS_KEY` | No | Cosmos DB access key |

---

## 🐛 Troubleshooting

### Common Issues

**Container App not starting:**
```bash
# Check container logs
az containerapp logs show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP
```

**Authentication errors:**
```bash
# Verify managed identity assignment
az containerapp identity show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP

# Check role assignments
az role assignment list --assignee $PRINCIPAL_ID --output table
```

**Cost data not showing:**
- Ensure `Cost Management Reader` role is assigned
- Cost data may take 24-48 hours to appear for new subscriptions

**Resource queries failing:**
- Verify `Reader` role on the subscription
- Check if Azure Resource Graph is enabled

---

## 📈 Roadmap

- [ ] Natural language to KQL query generation
- [ ] Custom dashboards and saved queries
- [ ] Scheduled reports via email
- [ ] Cost anomaly detection with alerts
- [ ] Terraform and Bicep code generation
- [ ] Multi-tenant support
- [ ] Power BI integration
- [ ] Teams/Slack integration

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Zahir Hussain Shah**

- 🌐 Website: [www.zahir.cloud](https://www.zahir.cloud)
- 📧 Email: [zahir@zahir.cloud](mailto:zahir@zahir.cloud)
- 💼 GitHub: [@zhshah](https://github.com/zhshah)

---

## 🙏 Acknowledgments

- Microsoft Azure for the cloud platform
- OpenAI for the GPT-4o language model
- FastAPI community for the excellent web framework

---

**Built with ❤️ for Azure Cloud Operations**

*Empowering IT teams to manage Azure infrastructure through natural language*
