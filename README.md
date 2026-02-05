# Azure AI Cost & Deployment Agent - Phase 2

## 🚀 Overview

Phase 2 is a **clean, isolated build** of the Azure AI Cost Management and Resource Deployment Agent with full Logic App integration and subscription-level resource group deployment support.

## ✨ Features

- ✅ **AI-Powered Chat Interface** - Natural language interaction with Azure
- ✅ **Resource Deployment** - Deploy VMs, Storage, SQL Databases, and Resource Groups
- ✅ **Approval Workflow** - Email approval via Azure Logic Apps
- ✅ **Subscription-Level Deployments** - Resource groups deploy correctly at subscription scope
- ✅ **Cost Analysis** - Azure cost breakdown and recommendations
- ✅ **Resource Management** - Query and list Azure resources
- ✅ **Beautiful UI** - Modern, responsive interface with gradient design

## 📁 Directory Structure

```
Phase-2/
├── main.py                          # FastAPI application entry point
├── openai_agent.py                  # OpenAI GPT-4o agent with function calling
├── modern_resource_deployment.py    # Resource deployment with Logic App integration
├── logic_app_client.py              # Logic App webhook client
├── azure_cost_manager.py            # Azure cost analysis
├── azure_resource_manager.py        # Azure resource queries
├── auth_manager.py                  # Authentication manager
├── .env                             # Environment configuration
├── requirements.txt                 # Python dependencies
├── static/
│   └── index.html                   # Clean web interface
└── README.md                        # This file
```

## 🛠️ Setup & Installation

### Prerequisites

- Python 3.8+
- Azure subscription with appropriate permissions
- Azure OpenAI deployment (GPT-4o)
- Azure Logic App (logagzs0230) deployed

### Step 1: Install Dependencies

```powershell
cd Phase-2
pip install -r requirements.txt
```

### Step 2: Configure Environment

Edit `.env` file with your configuration:

```env
AZURE_SUBSCRIPTION_ID=your-subscription-id
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_KEY=your-api-key
ENABLE_APPROVAL_WORKFLOW=true
LOGIC_APP_WEBHOOK_URL=https://prod-08.westeurope.logic.azure.com/workflows/.../triggers/manual/...
USER_EMAIL=admin@example.com
USER_NAME=Azure Admin
USE_MANAGED_IDENTITY=true
```

### Step 3: Start the Server

```powershell
python main.py
```

Server will start on: **http://localhost:8000**

## 🧪 Testing

### Test Resource Group Deployment

1. Open http://localhost:8000
2. Try: `"Create a resource group named test-rg-phase2 in west europe"`
3. Check email for approval request
4. Click **Approve**
5. Verify resource group created in Azure Portal

### Test Cost Analysis

```
Show me cost breakdown for my subscription
```

### Test Resource Listing

```
List all my Azure resources
```

## 📋 Logic App Workflow

The integrated Logic App (`logagzs0230`) handles:

1. **Receive deployment request** from Python application
2. **Send approval email** to user with resource details
3. **Check deployment scope**:
   - Resource Groups → Subscription-level deployment
   - Other resources → Resource group-level deployment
4. **Deploy resource** after approval
5. **Send success/failure notification** email

### Key Features

- ✅ Dynamic user emails (extracted from request)
- ✅ Beautiful HTML email templates
- ✅ Subscription-level deployment for resource groups
- ✅ Error handling with failure notifications
- ✅ Managed Service Identity authentication

## 🔧 Architecture

```
User → Web UI (index.html)
         ↓
    FastAPI (main.py)
         ↓
    OpenAI Agent (openai_agent.py)
         ↓
    Modern Resource Deployment (modern_resource_deployment.py)
         ↓
    Logic App Client (logic_app_client.py)
         ↓
    Azure Logic App (logagzs0230)
         ↓
    Email Approval → ARM Deployment → Success/Failure Email
```

## 📊 Supported Resources

| Resource Type | Deployment Level | Approval Required |
|--------------|------------------|-------------------|
| Resource Group | Subscription | ✅ Yes |
| Virtual Machine | Resource Group | ✅ Yes |
| Storage Account | Resource Group | ✅ Yes |
| SQL Database | Resource Group | ✅ Yes |

## 🐛 Troubleshooting

### No Approval Email Received

- Check `USER_EMAIL` in `.env`
- Verify Logic App run history in Azure Portal
- Check spam folder

### Deployment Fails

- Check Logic App error details
- Verify Managed Identity has Contributor role on subscription
- Review failure email for specific error

### Server Won't Start

```powershell
# Kill existing Python processes
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Restart server
python main.py
```

### Browser Shows Old Version

- Clear browser cache (Ctrl+Shift+Delete)
- Use Incognito/Private window
- Hard refresh (Ctrl+F5)

## 📝 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AZURE_SUBSCRIPTION_ID` | Your Azure subscription ID | ✅ Yes |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | ✅ Yes |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | GPT model deployment name | ✅ Yes |
| `AZURE_OPENAI_API_KEY` | OpenAI API key | ✅ Yes |
| `LOGIC_APP_WEBHOOK_URL` | Logic App webhook URL with SAS token | ✅ Yes |
| `ENABLE_APPROVAL_WORKFLOW` | Enable/disable approval workflow | No (default: false) |
| `USER_EMAIL` | Default user email for approvals | No (default: admin@example.com) |
| `USER_NAME` | Default user name | No (default: Azure Admin) |
| `USE_MANAGED_IDENTITY` | Use managed identity for Azure auth | No (default: false) |

## 🎯 Quick Start Commands

```powershell
# Navigate to Phase-2
cd Phase-2

# Install dependencies
pip install -r requirements.txt

# Start server
python main.py

# In another terminal - test deployment
curl -X POST http://localhost:8000/api/chat `
  -H "Content-Type: application/json" `
  -d '{"message": "Create a resource group named test-rg in west europe"}'
```

## ✅ Success Criteria

Phase 2 is working correctly when:

1. ✅ Server starts on port 8000
2. ✅ Web interface loads at http://localhost:8000
3. ✅ Chat responds to messages
4. ✅ Resource group deployment returns `requestId` and `pending_approval` status
5. ✅ Approval email arrives within 2 minutes
6. ✅ After approval, resource deploys to Azure
7. ✅ Success email received

## 🔐 Security Notes

- Logic App webhook URL contains SAS token - keep `.env` secure
- Use managed identity in production
- Approval emails should only go to authorized users
- Review Logic App access policies

## 📞 Support

For issues or questions:
1. Check Logic App run history in Azure Portal
2. Review server logs in terminal
3. Verify all environment variables are set correctly

---

**Built with ❤️ for Azure resource management automation**
