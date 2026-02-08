# Azure AD App Registration Setup Guide

This guide explains how to create and configure an Azure AD (Entra ID) App Registration for the Azure CloudOps Intelligence Agent.

## Prerequisites

- Azure subscription with Owner or Co-administrator role
- Access to Azure Portal or Azure CLI
- Azure AD tenant admin permissions (or the ability to request admin consent)

## Step 1: Create App Registration

### Using Azure Portal

1. Navigate to [Azure Portal](https://portal.azure.com)
2. Go to **Azure Active Directory** > **App registrations**
3. Click **+ New registration**
4. Fill in the details:
   - **Name**: `CloudOps Intelligence Agent`
   - **Supported account types**: Select based on your needs:
     - `Accounts in this organizational directory only` (recommended for enterprise)
   - **Redirect URI**: 
     - Platform: `Single-page application (SPA)`
     - URI: `https://your-app-url/login.html`
5. Click **Register**

### Using Azure CLI

```bash
# Create the app registration
az ad app create \
    --display-name "CloudOps Intelligence Agent" \
    --sign-in-audience "AzureADMyOrg" \
    --web-redirect-uris "https://your-app-url/login.html"

# Get the Application (client) ID
az ad app list --display-name "CloudOps Intelligence Agent" --query "[0].appId" -o tsv
```

## Step 2: Note Your Configuration Values

After creating the app registration, note these values:

| Setting | Where to Find | Used In |
|---------|---------------|---------|
| **Application (client) ID** | Overview blade | `login.html`, `.env` |
| **Directory (tenant) ID** | Overview blade | `login.html`, `.env` |
| **Client Secret** | Certificates & secrets | `.env` (if using in backend) |

## Step 3: Configure API Permissions

### Required Permissions

| API | Permission | Type | Purpose |
|-----|------------|------|---------|
| Microsoft Graph | `User.Read` | Delegated | Read user profile |
| Microsoft Graph | `User.ReadBasic.All` | Delegated | List users |
| Microsoft Graph | `Directory.Read.All` | Delegated | Read directory data |
| Microsoft Graph | `Group.Read.All` | Delegated | List groups |
| Microsoft Graph | `Application.Read.All` | Delegated | List applications |
| Microsoft Graph | `Device.Read.All` | Delegated | List devices |
| Microsoft Graph | `Policy.Read.All` | Delegated | Read conditional access |

### Adding Permissions in Portal

1. Go to your App Registration
2. Click **API permissions** > **+ Add a permission**
3. Select **Microsoft Graph** > **Delegated permissions**
4. Search for and add each permission listed above
5. Click **Grant admin consent for [your organization]**

### Adding Permissions via CLI

```bash
APP_ID="your-app-client-id"

# Add Microsoft Graph permissions
az ad app permission add \
    --id $APP_ID \
    --api 00000003-0000-0000-c000-000000000000 \
    --api-permissions e1fe6dd8-ba31-4d61-89e7-88639da4683d=Scope \
    b340eb25-3456-403f-be2f-af7a0d370277=Scope \
    7ab1d382-f21e-4acd-a863-ba3e13f7da61=Scope \
    5b567255-7703-4780-807c-7be8301ae99b=Scope \
    c79f8feb-a9db-4090-85f9-90d820caa0eb=Scope \
    7a6ee1e7-141e-4cec-ae74-d9db155731ff=Scope \
    246dd0d5-5bd0-4def-940b-0421030a5b68=Scope

# Grant admin consent
az ad app permission admin-consent --id $APP_ID
```

## Step 4: Configure Authentication Platform

1. Go to **Authentication** blade
2. Under **Single-page application**, add redirect URIs:
   ```
   https://your-container-app-url/login.html
   http://localhost:8000/login.html  (for local development)
   ```
3. Under **Implicit grant and hybrid flows**, enable:
   - ✅ Access tokens
   - ✅ ID tokens
4. Click **Save**

## Step 5: Update Application Files

### Update `static/login.html`

Replace the placeholders in the MSAL configuration:

```javascript
const msalConfig = {
    auth: {
        clientId: 'YOUR_APP_CLIENT_ID',  // Replace with Application (client) ID
        authority: 'https://login.microsoftonline.com/YOUR_TENANT_ID',  // Replace with Directory (tenant) ID
        redirectUri: window.location.origin + '/login.html'
    },
    // ... rest of config
};
```

### Update `.env` File

```env
AZURE_TENANT_ID=your-tenant-id-here
AZURE_CLIENT_ID=your-client-id-here
```

## Step 6: Create Service Principal (Optional)

For backend authentication with Azure resources:

```bash
# Create service principal
az ad sp create-for-rbac \
    --name "CloudOps-Agent-SP" \
    --role "Reader" \
    --scopes "/subscriptions/YOUR_SUBSCRIPTION_ID"
```

Save the output - you'll need:
- `appId` → `AZURE_CLIENT_ID`
- `password` → `AZURE_CLIENT_SECRET`
- `tenant` → `AZURE_TENANT_ID`

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| AADSTS50011 (redirect URI mismatch) | Add exact redirect URI to app registration |
| AADSTS65001 (consent required) | Grant admin consent in API permissions |
| AADSTS700016 (app not found) | Verify client ID matches app registration |
| AADSTS90002 (tenant not found) | Verify tenant ID is correct |

### Additional Resources

- [Microsoft Identity Platform Documentation](https://docs.microsoft.com/azure/active-directory/develop/)
- [MSAL.js Documentation](https://docs.microsoft.com/azure/active-directory/develop/msal-js-initializing-client-applications)
- [Azure AD App Roles](https://docs.microsoft.com/azure/active-directory/develop/howto-add-app-roles-in-azure-ad-apps)
