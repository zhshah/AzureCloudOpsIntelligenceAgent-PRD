# Entra ID App Registration Setup Guide

This guide explains how to create and configure an Entra ID (Azure AD) App Registration for the Azure CloudOps Intelligence Agent.

## Step 1: Create App Registration

1. Go to [Azure Portal](https://portal.azure.com) → **Microsoft Entra ID** → **App registrations**
2. Click **New registration**
3. Configure:
   - **Name**: `CloudOps Intelligence Agent` (or your preferred name)
   - **Supported account types**: Accounts in this organizational directory only
   - **Redirect URI**: Select **Single-page application (SPA)** — leave URL blank for now
4. Click **Register**

## Step 2: Note These Values (Required for Deployment Script)

After registration, find these values on the **Overview** page:

| Value | Where to Find | Script Parameter |
|-------|---------------|------------------|
| Application (client) ID | Overview → Application (client) ID | `-EntraAppClientId` |
| Directory (tenant) ID | Overview → Directory (tenant) ID | `-EntraTenantId` |

## Step 3: Configure API Permissions

1. Go to **API permissions** in your App Registration
2. Click **Add a permission** → **Microsoft Graph** → **Delegated permissions**
3. Select these permissions:
   - `openid`
   - `profile`
   - `email`
   - `User.Read`
4. Click **Add permissions**
5. Click **Grant admin consent for [Your Organization]** (requires admin)

## Step 4: After Deployment — Add Redirect URI

After deployment completes, you'll receive the application URL. Then:

1. Go back to **App Registration** → **Authentication**
2. Under **Single-page application** → **Redirect URIs**, add:
   ```
   https://<your-app-url>/login.html
   ```
   For local development, also add:
   ```
   http://localhost:8000/login.html
   ```
3. Click **Save**

## Troubleshooting

| Issue | Solution |
|-------|----------|
| AADSTS50011 (redirect URI mismatch) | Add exact redirect URI to app registration |
| AADSTS65001 (consent required) | Grant admin consent in API permissions |
| AADSTS700016 (app not found) | Verify client ID matches app registration |
| AADSTS90002 (tenant not found) | Verify tenant ID is correct |
