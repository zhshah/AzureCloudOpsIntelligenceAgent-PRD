# Azure CloudOps Intelligence Agent

[![Azure](https://img.shields.io/badge/Azure-Powered-0078D4?style=for-the-badge&logo=microsoft-azure)](https://azure.microsoft.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=for-the-badge&logo=openai)](https://openai.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Container](https://img.shields.io/badge/Container-Ready-2496ED?style=for-the-badge&logo=docker)](https://www.docker.com)

> **AI-Powered Azure Infrastructure Operations & Cloud Management Platform**

An enterprise-grade AI agent that transforms Azure cloud operations through natural language conversations. Built on **Azure OpenAI GPT-4o** with **120+ function-calling tools** across **30 operational categories**, it delivers real-time infrastructure insights, **Cloud Operations Health scoring** across 6 management pillars, **AI-generated architecture diagrams**, security posture assessment, cost optimization, and orphaned resource detection — all through an intuitive chat interface.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Live Dashboard Widgets](#-live-dashboard-widgets)
- [29 Operational Categories](#-29-operational-categories)
- [Cloud Ops Health Assessment](#-cloud-ops-health-assessment)
- [Architecture Diagram Generation](#-architecture-diagram-generation)
- [Prerequisites](#-prerequisites)
- [Quick Start — Automated Deployment](#-quick-start--automated-deployment)
- [Private (Internal-Only) Deployment — Zero-Trust](#-private-internal-only-deployment--zero-trust-end-to-end-private)
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

Azure CloudOps Intelligence Agent is an AI-powered platform that enables natural language interaction for Azure infrastructure management. Built on Azure OpenAI GPT-4o with 120+ tools, it provides:

- **Cloud Ops Health Assessment** — Real-time scoring across 6 management pillars (Advisor, Backup, Monitor, Defender, Update, Policy) with resource-level detail and AI-driven remediation guidance
- **Architecture Diagrams** — AI-generated Azure architecture diagrams from descriptions or actual deployed resources with 700+ Azure-native icons
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
- **Cloud Ops Health Assessment** — 6-pillar scoring engine (Advisor, Backup, Monitor, Defender, Update, Policy) with resource-level details, health grading (A–F), and AI-driven prioritized remediation
- **Architecture Diagram Generation** — AI-powered diagrams from natural language or live Azure resources using Graphviz with 700+ Azure-native SVG icons
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
| **AI Engine** | Azure OpenAI GPT-4o (120+ function-calling tools) |
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

The agent organizes **260+ pre-built prompts** across **30 categories**, each with dedicated Azure-native icons:

| # | Category | Quick Actions | Description |
|---|----------|:---:|-------------|
| 1 | **Entra ID (Azure AD)** | 14 | Users, groups, apps, devices, conditional access |
| 2 | **Access Control (IAM)** | 6 | RBAC role assignments, privileged access audit |
| 3 | **Landing Zone (CAF)** | 22 | CAF assessment, Platform & Application LZ review |
| 4 | **Well-Architected Framework** | 8 | Reliability, Security, Cost, Operations, Performance |
| 5 | **Cloud Ops Health** | 12 | 6-pillar health scoring: Advisor, Backup, Monitor, Defender, Updates, Policy |
| 6 | **Architecture Diagrams** | 5 | AI-generated diagrams from descriptions or live Azure resources |
| 7 | **Networking** | 32 | VNets, NSGs, Firewalls, Load Balancers, WAF, vWAN |
| 8 | **Azure Private Link** | 14 | Private endpoints, PaaS security, connections |
| 9 | **Private DNS Zones** | 14 | DNS zones, VNet links, resolution issues |
| 10 | **Virtual Machines** | 15 | VM health, backup, monitoring, cost optimization |
| 11 | **Resource Management** | 6 | Inventory, search, and filter Azure resources |
| 12 | **Cost Optimization** | 7 | Cost analysis, comparisons, savings opportunities |
| 13 | **Security & Compliance** | 10 | Defender, security score, alerts, compliance |
| 14 | **Azure Policy** | 5 | Policy compliance and exemptions |
| 15 | **Monitoring & Alerts** | 11 | Alerts, monitoring gaps, VM Insights status |
| 16 | **Azure Backup** | 12 | VMs, disks, files, SQL backup protection status |
| 17 | **Update Management** | 6 | VM and Arc machine patches and compliance |
| 18 | **Tags Management** | 5 | Tag inventory and compliance |
| 19 | **Azure Arc** | 3 | Hybrid infrastructure management |
| 20 | **Azure Kubernetes (AKS)** | 5 | AKS clusters, monitoring, security posture |
| 21 | **VM Scale Sets** | 4 | Scale set monitoring and configuration |
| 22 | **App Services** | 5 | Web apps, monitoring, public access |
| 23 | **Azure SQL PaaS** | 7 | SQL Database, Managed Instance optimization |
| 24 | **PostgreSQL Servers** | 4 | PostgreSQL flexible servers management |
| 25 | **MySQL Servers** | 4 | MySQL flexible servers management |
| 26 | **Cosmos DB** | 4 | NoSQL database optimization |
| 27 | **Storage Accounts** | 10 | Capacity, security, file shares, cost optimization |
| 28 | **Orphaned Resources** | 24 | Unused disks, IPs, NICs, NSGs, empty RGs, and more |
| 29 | **API Management** | 5 | APIM instances, APIs, policies, diagnostics |
| 30 | **Automation** | 4 | Runbooks, automation accounts, scheduled tasks |

---

## 🏥 Cloud Ops Health Assessment

A comprehensive, real-time Cloud Operations Health scoring engine based on the [Azure Cloud Roles & Operations Management](https://github.com/Azure/cloud-rolesandops) framework. Scores your environment across **6 management pillars** with an overall health grade (A–F).

### 6 Management Pillars

| Pillar | What It Measures | Key Data Points |
|--------|-----------------|-----------------|
| **Azure Advisor** | Recommendation coverage across Cost, Security, Reliability, Performance, Operational Excellence | Resource name, RG, location, specific problem & solution per resource |
| **Azure Backup** | VM backup protection percentage | Every unprotected VM listed by name, RG, location, subscription |
| **Azure Monitor** | Alert response effectiveness (fired vs. acknowledged vs. closed) | Active alerts with severity, target resource, RG, and trigger time |
| **Defender for Cloud** | Security assessment health (healthy vs. unhealthy recommendations) | Specific findings per resource with parsed name, severity, and remediation steps |
| **Update Management** | System update compliance across VMs | Machines needing updates with name, RG, location, cause, and description |
| **Azure Policy** | Policy compliance percentage (compliant vs. noncompliant resources) | Non-compliant resources by name, RG, location, and violating policy |

### What Makes It Different

- **Resource-Level Detail** — Every pillar returns specific resource names, resource groups, locations, and subscription IDs — not just aggregate scores
- **AI-Driven Analysis** — GPT-4o analyzes the raw data and produces executive-grade reports with prioritized remediation actions per resource
- **Health Grading** — Overall A–F grade with automatic priority actions for the weakest pillars
- **Subscription-Scoped** — Automatically respects the subscription/management group selected in the UI dropdown

### Sample Prompts
```
"Run a full Cloud Operations Health Assessment"
"What is my Azure Advisor health score?"
"Show my backup protection status — which VMs are unprotected?"
"What is my Defender for Cloud security posture score?"
"Show Azure Policy compliance — which resources are non-compliant?"
"Assess my monitoring health — show active unresolved alerts"
"What is my update compliance score?"
"Show resource tagging governance health"
"Assess disaster recovery readiness"
"Show network security health posture"
```

---

## 📐 Architecture Diagram Generation

AI-powered Azure architecture diagram generation using actual Azure-native SVG icons. Generate diagrams from natural language descriptions or from your **actual deployed Azure resources**.

### Diagram Types

| Type | Description |
|------|-------------|
| **Environment Overview** | High-level estate view across all subscriptions, regions, and resource groups |
| **Subscription Overview** | Resource group-level view with categorized resource icons |
| **From Resources** | Diagram your ACTUAL Azure resources with dependencies auto-detected |
| **Pre-Built Patterns** | Hub-spoke, microservices, serverless, 3-tier web, data platform, multi-region, zero-trust, IoT, DevOps CI/CD, AI/ML, hybrid-cloud, API management |
| **Custom** | Describe any architecture in natural language and the AI generates it |

### Key Capabilities

- **700+ Azure-native SVG icons** — Official Microsoft Azure icons for accurate visual representation
- **Live resource discovery** — Query your actual Azure environment and diagram what's deployed
- **Dependency mapping** — Auto-detects relationships between VNets, subnets, VMs, databases, and more
- **Inline rendering** — Diagrams render directly in the chat interface as downloadable images
- **Sandboxed execution** — All diagram code runs in a security sandbox with restricted imports

### Sample Prompts
```
"Generate a hub-spoke network architecture diagram"
"Draw my actual Azure environment as a diagram"
"Create a 3-tier web application architecture diagram"
"Show my resource group 'production-rg' as an architecture diagram"
"Generate a zero-trust network architecture for Azure"
```

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
git clone https://github.com/zhshah/AzureCloudOpsIntelligenceAgent-PRD
cd AzureCloudOpsIntelligenceAgent-PRD
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

> **⚠️ ACR Naming Rule:** The `-ContainerRegistryName` must be **alphanumeric only** (lowercase letters and numbers). Azure Container Registry does **not** allow hyphens (`-`), dots (`.`), or underscores (`_`). If you provide a name with these characters (e.g., `my-acr-name`), the script will automatically strip them and prompt you to confirm the adjusted name (e.g., `myacrname`).

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
| `-ContainerRegistryName` | ✅ | — | Globally unique ACR name — **alphanumeric only**, no hyphens/dots/underscores (e.g., `cloudopsacr2024`) |
| `-EntraAppClientId` | ✅ | — | Entra ID Application (Client) ID |
| `-EntraTenantId` | ✅ | — | Azure AD Tenant ID |
| `-Location` | ❌ | `westeurope` | Azure region (e.g., `qatarcentral`, `eastus`) |
| `-OpenAIResourceName` | ❌ | Auto-generated | Custom name for the OpenAI resource |
| `-ContainerAppName` | ❌ | `cloudops-agent` | Custom name for the Container App |
| `-SubscriptionId` | ❌ | Current context | Target subscription — script validates and asks for confirmation before deploying |
| `-EnableLogAnalytics` | ❌ | `$false` | Enable Log Analytics workspace |
| `-DeploymentMode` | ❌ | `Public` | `Public` (internet-accessible) or `Private` (VNet-integrated, internal-only) |
| `-VNetResourceGroupName` | ⚠️ | — | Resource group containing the existing VNet (**required for Private mode**) |
| `-VNetName` | ⚠️ | — | Existing VNet name to deploy into (**required for Private mode**) |
| `-SubnetName` | ⚠️ | — | Subnet for Container Apps Environment (**required for Private mode**, see subnet requirements below) |
| `-PrivateEndpointSubnetName` | ❌ | `pe-subnet` | Subnet for Private Endpoints (ACR, OpenAI) — auto-created if absent |
| `-PrivateDnsZoneSubscriptionId` | ❌ | Deployment sub | Centralized subscription for Private DNS Zones (enterprise hub/connectivity sub) |
| `-PrivateDnsZoneResourceGroupName` | ❌ | Deployment RG | Resource group for Private DNS Zones in the centralized subscription |

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

## 🔒 Private (Internal-Only) Deployment — Zero-Trust, End-to-End Private

For enterprise customers who require **zero public exposure** — the deployment script supports a fully automated **Private deployment mode** that deploys **every resource privately** with Private Endpoints, disables public network access on all PaaS services, and configures Private DNS Zones (with support for centralized DNS subscriptions).

> **🔑 Key Point:** In Private mode, **all** resources are private. Azure OpenAI and ACR get Private Endpoints with public access disabled. The Container App runs inside your VNet with internal-only ingress. Private DNS Zones are auto-created and linked. Zero manual network configuration required.

### What Gets Deployed Privately?

| Resource | Private Mechanism | Public Access |
|----------|-------------------|---------------|
| **Azure Container App** | VNet injection + internal-only ingress | ❌ Disabled |
| **Azure OpenAI (GPT-4o)** | Private Endpoint (`privatelink.openai.azure.com`) | ❌ Disabled |
| **Azure Container Registry** | Private Endpoint (`privatelink.azurecr.io`) | ❌ Disabled |
| **Private DNS Zones** | Auto-created in centralized or deployment subscription | N/A |
| **DNS → VNet Links** | Auto-linked to your VNet for name resolution | N/A |

### Why Private Deployment?

| Concern | Private Mode Solution |
|---------|----------------------|
| **Data Sovereignty** | All traffic stays within your Azure VNet — no public internet |
| **Compliance** | Meets regulatory requirements (ISO 27001, SOC 2, HIPAA) for internal-only access |
| **Zero Public Exposure** | Public network access **disabled** on OpenAI, ACR, and Container App |
| **Network Isolation** | Private Endpoints + VNet injection — all communication over Azure backbone |
| **Enterprise DNS** | Supports centralized Private DNS Zones in hub/connectivity subscription |
| **Zero-Touch** | Fully automated — no manual PE, DNS zone, or VNet link creation |

### Prerequisites for Private Deployment

Before running the script in Private mode, ensure you have:

1. **An existing VNet** in the same region as your deployment
2. **A dedicated subnet for Container Apps** with:
   - Minimum size: `/27` (32 addresses) — **Recommended: `/23`** (512 addresses) for production
   - No other resources deployed in the subnet
   - Subnet delegation to `Microsoft.App/environments` (the script can apply this automatically)
3. **A subnet for Private Endpoints** (optional — script auto-creates `pe-subnet` /27 if not provided)
   - Must be a **different** subnet from the Container Apps subnet (delegated subnets cannot host PEs)
4. **Network connectivity** from your users to the VNet (VPN Gateway, ExpressRoute, or peered VNets)
5. **(Optional) Centralized DNS subscription** — If your organization keeps Private DNS Zones in a hub/connectivity subscription, provide `-PrivateDnsZoneSubscriptionId` and `-PrivateDnsZoneResourceGroupName`

### Private Deployment Command

**Basic** (PE subnet auto-created, DNS zones in deployment subscription):
```powershell
.\deploy-automated.ps1 `
    -ResourceGroupName "rg-cloudops-agent" `
    -Location "westeurope" `
    -ContainerRegistryName "youracrname" `
    -EntraAppClientId "<your-entra-app-client-id>" `
    -EntraTenantId "<your-entra-tenant-id>" `
    -SubscriptionId "<your-subscription-id>" `
    -DeploymentMode "Private" `
    -VNetResourceGroupName "rg-networking" `
    -VNetName "corp-vnet" `
    -SubnetName "container-apps-subnet"
```

**Enterprise** (existing PE subnet, centralized DNS subscription):
```powershell
.\deploy-automated.ps1 `
    -ResourceGroupName "rg-cloudops-agent" `
    -Location "westeurope" `
    -ContainerRegistryName "youracrname" `
    -EntraAppClientId "<your-entra-app-client-id>" `
    -EntraTenantId "<your-entra-tenant-id>" `
    -SubscriptionId "<your-subscription-id>" `
    -DeploymentMode "Private" `
    -VNetResourceGroupName "rg-networking" `
    -VNetName "corp-vnet" `
    -SubnetName "container-apps-subnet" `
    -PrivateEndpointSubnetName "pe-subnet" `
    -PrivateDnsZoneSubscriptionId "<hub-subscription-id>" `
    -PrivateDnsZoneResourceGroupName "rg-private-dns-zones"
```

### What the Script Does in Private Mode

The script performs **18 automated steps** for a complete zero-trust deployment:

| Step | Action |
|------|--------|
| **VNet Validation** | Verifies the VNet exists and is accessible |
| **CA Subnet Validation** | Checks Container Apps subnet exists, verifies size (min /27, recommends /23) |
| **PE Subnet Validation** | Validates or auto-creates the Private Endpoint subnet (`pe-subnet` /27) |
| **PE Network Policies** | Disables private endpoint network policies on the PE subnet |
| **Region Matching** | Auto-adjusts deployment location if VNet is in a different region |
| **Subnet Delegation** | Checks for `Microsoft.App/environments` delegation — auto-applies if missing |
| **DNS Subscription** | Validates access to centralized DNS subscription (if provided) |
| **Create OpenAI** | Creates Azure OpenAI resource + deploys GPT-4o model |
| **OpenAI PE** | Creates Private Endpoint for OpenAI → `privatelink.openai.azure.com` |
| **OpenAI DNS** | Creates/finds Private DNS Zone, links to VNet, auto-registers A records |
| **OpenAI Lockdown** | Disables public network access on Azure OpenAI |
| **Create ACR** | Creates Azure Container Registry (Premium SKU for PE support) |
| **Build Image** | Builds and pushes container image **before** disabling public ACR access |
| **ACR PE** | Creates Private Endpoint for ACR → `privatelink.azurecr.io` |
| **ACR DNS** | Creates/finds Private DNS Zone, links to VNet, auto-registers A records |
| **ACR Lockdown** | Disables public network access on ACR |
| **Internal Env** | Creates Container Apps Environment with `--internal-only` + VNet integration |
| **Env DNS** | Creates Private DNS Zone for Container App Env domain + wildcard A record + VNet link |

> **💡 Build-Before-Lockdown Pattern:** The script intentionally builds and pushes the container image to ACR **before** disabling public access. After the Private Endpoint and DNS zone are configured, the Container App pulls images through the private network.

### Centralized Private DNS Zones (Enterprise Pattern)

Most enterprises follow a **hub-spoke** topology where Private DNS Zones live in a centralized "connectivity" or "shared services" subscription — not in individual workload (spoke) subscriptions. The script fully supports this pattern:

```
┌──────────────────────────────────────────────────────┐
│  Hub / Connectivity Subscription                      │
│  (-PrivateDnsZoneSubscriptionId)                      │
│                                                       │
│  ┌─────────────────────────────────────────────────┐  │
│  │  RG: rg-private-dns-zones                       │  │
│  │  (-PrivateDnsZoneResourceGroupName)             │  │
│  │                                                 │  │
│  │  privatelink.openai.azure.com  ← VNet linked    │  │
│  │  privatelink.azurecr.io        ← VNet linked    │  │
│  │  <cae-default-domain>          ← VNet linked    │  │
│  └─────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
                        │
                   VNet Links
                        │
┌──────────────────────────────────────────────────────┐
│  Spoke / Workload Subscription                        │
│  (-SubscriptionId)                                    │
│                                                       │
│  ┌─── corp-vnet ──────────────────────────────────┐  │
│  │  container-apps-subnet  →  Container App (PE)  │  │
│  │  pe-subnet              →  OpenAI PE, ACR PE   │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

If `-PrivateDnsZoneSubscriptionId` is **not** provided, the script creates DNS zones in the deployment subscription — suitable for single-subscription environments.

### Subnet Delegation

Azure Container Apps requires the subnet to be **delegated** to `Microsoft.App/environments`. The script will:

- ✅ **Detect** if the delegation already exists → proceed automatically
- ⚠️ **Prompt to apply** if no delegation exists → applies with your confirmation
- ❌ **Block** if the subnet has a different delegation → asks you to use another subnet

To apply delegation manually:
```bash
az network vnet subnet update \
    --name container-apps-subnet \
    --vnet-name corp-vnet \
    --resource-group rg-networking \
    --delegations Microsoft.App/environments
```

### Accessing the Application (Private Mode)

After private deployment, the app URL (e.g., `https://cloudops-agent.internal.<domain>`) is **only resolvable from within the VNet**.

> **✅ DNS is fully automated.** The deployment script automatically creates Private DNS Zones for all resources (OpenAI, ACR, Container Apps Environment), adds the required A records, and links them to your VNet. No manual DNS configuration is needed.

Choose one of these methods to access the application from your network:

#### Option 1: Jumpbox / Bastion (Quickest for Testing)

- RDP/SSH to a VM (jumpbox) in the same VNet or a peered VNet
- Open a browser and navigate to the internal URL shown in the deployment output
- Azure Bastion can provide secure browser-based access without public IPs

#### Option 2: VPN / ExpressRoute (Production Access)

- Connect from your on-premises network via VPN Gateway or ExpressRoute
- DNS forwarding to Azure Private DNS is required for name resolution
- Users on the corporate network can access the app as if it were an internal application

#### Option 3: Manual DNS (Only If Not Using Script Automation)

If you need to create DNS zones manually (e.g., for custom configurations):

```bash
# The deployment script does this automatically — only use if needed
az network private-dns zone create \
    --resource-group rg-networking \
    --name "<environment-default-domain>"

az network private-dns record-set a add-record \
    --resource-group rg-networking \
    --zone-name "<environment-default-domain>" \
    --record-set-name "*" \
    --ipv4-address "<environment-static-ip>"

az network private-dns link vnet create \
    --resource-group rg-networking \
    --zone-name "<environment-default-domain>" \
    --name vnet-dns-link \
    --virtual-network <vnet-resource-id> \
    --registration-enabled false
```

### Network Architecture — Private Deployment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Your Corporate VNet                                │
│                                                                             │
│  ┌──────────────────────┐   ┌──────────────────────────────────────────┐   │
│  │  Subnet: pe-subnet   │   │  Subnet: container-apps-subnet           │   │
│  │  (Private Endpoints) │   │  (Delegated: Microsoft.App/environments) │   │
│  │                      │   │                                          │   │
│  │  ┌────────────────┐  │   │  ┌──────────────────────────────────┐   │   │
│  │  │ OpenAI PE      │──│───│──│  Container Apps Environment      │   │   │
│  │  │ (privatelink)  │  │   │  │  (Internal Only)                 │   │   │
│  │  └────────────────┘  │   │  │                                  │   │   │
│  │                      │   │  │  ┌────────────────────────────┐  │   │   │
│  │  ┌────────────────┐  │   │  │  │  CloudOps Intelligence     │  │   │   │
│  │  │ ACR PE         │──│───│──│  │  Agent (Container App)     │  │   │   │
│  │  │ (privatelink)  │  │   │  │  │  Internal Ingress Only     │  │   │   │
│  │  └────────────────┘  │   │  │  └────────────────────────────┘  │   │   │
│  └──────────────────────┘   │  └──────────────────────────────────┘   │   │
│                              └──────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Private DNS Zones (Centralized or Local)                            │   │
│  │  privatelink.openai.azure.com  → OpenAI Private IP                  │   │
│  │  privatelink.azurecr.io        → ACR Private IP                     │   │
│  │  <cae-default-domain>          → * → Environment Static IP          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
               ┌────────────────┴───────────────────┐
               │   VPN Gateway / ExpressRoute        │
               │   (On-Premises Connectivity)        │
               └────────────────┬───────────────────┘
                                │
               ┌────────────────┴───────────────────┐
               │   Corporate Users                   │
               │   (Internal Network Access Only)    │
               └────────────────────────────────────┘

PaaS Resources (Public Access DISABLED):
┌──────────────────┐ ┌──────────────────┐
│  Azure OpenAI    │ │  Azure Container │
│  (GPT-4o)        │ │  Registry (ACR)  │
│  Public: ❌       │ │  Public: ❌       │
│  PE: ✅ via VNet  │ │  PE: ✅ via VNet  │
└──────────────────┘ └──────────────────┘
```

---

## �📋 Manual Deployment

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
- **Private Endpoint Ready** — Full zero-trust private deployment with Private Endpoints for Azure OpenAI, ACR, and Container Apps. Public access **disabled** on all PaaS resources. Supports centralized Private DNS Zones. See [Private (Internal-Only) Deployment](#-private-internal-only-deployment--zero-trust-end-to-end-private) for fully automated deployment.
- **RBAC** — Fine-grained access control via Azure role assignments

### Network Architecture Options

The deployment script supports both modes natively via the `-DeploymentMode` parameter:

```
Option 1: Public Endpoint (-DeploymentMode "Public" — Default)
┌──────────────┐     ┌──────────────────┐
│   Users      │────▶│  Container App   │
│  (Internet)  │     │  (Public FQDN)   │
└──────────────┘     └──────────────────┘

Option 2: Private / Zero-Trust (-DeploymentMode "Private")
┌──────────────┐     ┌──────────────────┐     ┌──────────────────────────────┐
│  Corporate   │────▶│  VPN Gateway /   │────▶│  Container App               │
│  Users       │     │  ExpressRoute    │     │  (Internal Ingress Only)     │
│  (Internal)  │     │                  │     │  Inside Customer VNet        │
└──────────────┘     └──────────────────┘     │                              │
                                               │  Private Endpoints:          │
                                               │  • Azure OpenAI (PE)         │
                                               │  • ACR (PE)                  │
                                               │  Public Access: ❌ DISABLED   │
                                               └──────────────────────────────┘
```

See [Private (Internal-Only) Deployment](#-private-internal-only-deployment--zero-trust-end-to-end-private) for full setup instructions.

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

### Cloud Ops Health
```
"Run a full Cloud Operations Health Assessment"
"What is my Azure Advisor health score? Show affected resources"
"Show backup protection status — which VMs are unprotected?"
"Assess my Defender for Cloud security posture with resource details"
"Show Azure Policy compliance — which resources violate which policies?"
"What is my update compliance score?"
```

### Architecture Diagrams
```
"Generate a hub-spoke network architecture diagram"
"Draw my actual Azure resources in production-rg as a diagram"
"Create a 3-tier web app architecture diagram"
"Generate a zero-trust network architecture"
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
├── openai_agent.py                  # Azure OpenAI GPT-4o with 120+ tools
├── azure_resource_manager.py        # Resource Graph, Management Groups, Defender, Cloud Ops Health
├── azure_diagram_generator.py       # AI-powered architecture diagram generation (Graphviz + diagrams)
├── azure_cost_manager.py            # Cost Management API integration
├── conversation_manager.py          # Chat conversation history management
├── deployment_manager.py            # Resource deployment orchestration
├── resource_creator.py              # Azure resource creation helpers
├── bicep_template_generator.py      # Bicep/ARM template generation
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
| **Cloud Ops Health score N/A** | Ensure **Reader** and **Security Reader** roles on target subscriptions; some pillars require Defender for Cloud enabled |
| **Diagrams not rendering** | Graphviz must be installed in the container; verify Dockerfile includes `apt-get install graphviz` |
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
