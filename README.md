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

### 📸 Dashboard Preview

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

- Azure subscription with appropriate permissions
- Azure OpenAI service with GPT-4o deployment
- Azure Container Registry
- Azure Container Apps environment
- Logic App for approval workflows (optional)
- Required Azure RBAC roles:
  - `Reader` - For resource queries
  - `Cost Management Reader` - For cost data
  - `Contributor` - For resource deployments (optional)

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/zhshah/AzureCloudOpsIntelligenceAgent.git
cd AzureCloudOpsIntelligenceAgent
```

### 2. Configure Environment Variables

Create a `.env` file:

```env
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Azure Configuration
AZURE_SUBSCRIPTION_ID=your-default-subscription-id
USE_MANAGED_IDENTITY=true

# Approval Workflow (Optional)
ENABLE_APPROVAL_WORKFLOW=true
LOGIC_APP_WEBHOOK_URL=https://your-logic-app-url

# User Context
USER_EMAIL=admin@yourdomain.com
USER_NAME=Azure Admin
```

### 3. Run Locally

```bash
pip install -r requirements.txt
python main.py
```

Access the dashboard at: `http://localhost:8000`

### 4. Deploy to Azure Container Apps

```bash
# Build and push to ACR
az acr build --registry your-acr --image ai-agent-infra:latest .

# Update Container App
az containerapp update --name your-app --resource-group your-rg \
  --image your-acr.azurecr.io/ai-agent-infra:latest
```

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

- **Managed Identity** - No stored credentials
- **Entra ID Authentication** - Enterprise SSO
- **JWT Token Validation** - Secure API access
- **RBAC Integration** - Azure role-based permissions
- **Audit Logging** - Track all operations
- **No Fake Data** - Always returns real Azure API data

---

## 📈 Roadmap

- [ ] Natural language to KQL query generation
- [ ] Custom dashboards and saved queries
- [ ] Scheduled reports via email
- [ ] Cost anomaly detection with alerts
- [ ] Terraform and Bicep code generation
- [ ] Multi-tenant support
- [ ] Power BI integration

---

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📧 Contact

- **Author**: Zahir Hussain Shah
- **Email**: zahir@zahir.cloud
- **GitHub**: [@zhshah](https://github.com/zhshah)

---

**Built with ❤️ for Azure Cloud Operations**
