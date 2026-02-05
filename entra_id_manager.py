"""
Microsoft Entra ID (Azure AD) Integration
Uses Microsoft Graph API for identity and access management queries
"""

import os
import requests
from typing import Dict, Any, List, Optional
from azure.identity import DefaultAzureCredential
from datetime import datetime, timedelta
import json


class EntraIDManager:
    """Manager for Microsoft Entra ID (Azure AD) queries using Microsoft Graph API"""
    
    def __init__(self):
        """Initialize Entra ID Manager with Graph API access"""
        self.credential = DefaultAzureCredential()
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"
        self.graph_beta_endpoint = "https://graph.microsoft.com/beta"
        self._access_token = None
        self._token_expiry = None
    
    def _get_access_token(self) -> str:
        """Get access token for Microsoft Graph API"""
        try:
            # Check if we have a valid cached token
            if self._access_token and self._token_expiry and datetime.utcnow() < self._token_expiry:
                return self._access_token
            
            # Get new token
            token = self.credential.get_token("https://graph.microsoft.com/.default")
            self._access_token = token.token
            # Set expiry 5 minutes before actual expiry
            self._token_expiry = datetime.utcnow() + timedelta(minutes=55)
            return self._access_token
        except Exception as e:
            print(f"Error getting Graph API token: {e}")
            raise
    
    def _make_graph_request(self, endpoint: str, params: Optional[Dict] = None, use_beta: bool = False) -> Dict[str, Any]:
        """Make a request to Microsoft Graph API"""
        try:
            token = self._get_access_token()
            base_url = self.graph_beta_endpoint if use_beta else self.graph_endpoint
            url = f"{base_url}{endpoint}"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "ConsistencyLevel": "eventual"  # Required for $count and advanced queries
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                # Token expired, retry once
                self._access_token = None
                token = self._get_access_token()
                headers["Authorization"] = f"Bearer {token}"
                response = requests.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    return response.json()
            
            return {"error": f"Graph API error: {response.status_code} - {response.text}"}
        except Exception as e:
            return {"error": f"Graph API request failed: {str(e)}"}
    
    def _get_all_pages(self, endpoint: str, params: Optional[Dict] = None, use_beta: bool = False) -> List[Dict]:
        """Get all pages of results from a paginated Graph API endpoint"""
        all_results = []
        try:
            result = self._make_graph_request(endpoint, params, use_beta)
            if "error" in result:
                return [result]
            
            all_results.extend(result.get("value", []))
            
            # Handle pagination
            next_link = result.get("@odata.nextLink")
            while next_link:
                token = self._get_access_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "ConsistencyLevel": "eventual"
                }
                response = requests.get(next_link, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    all_results.extend(data.get("value", []))
                    next_link = data.get("@odata.nextLink")
                else:
                    break
            
            return all_results
        except Exception as e:
            return [{"error": str(e)}]
    
    def _get_count(self, endpoint: str, use_beta: bool = False) -> int:
        """Get count from a Graph API endpoint using $count"""
        try:
            token = self._get_access_token()
            base_url = self.graph_beta_endpoint if use_beta else self.graph_endpoint
            
            # For count endpoint, append /$count
            url = f"{base_url}{endpoint}/$count"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "ConsistencyLevel": "eventual"
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                return int(response.text)
            else:
                # Fallback: get items with $top=1 and $count=true
                result = self._make_graph_request(endpoint, {"$top": "1", "$count": "true"}, use_beta)
                if "@odata.count" in result:
                    return result["@odata.count"]
                return 0
        except Exception as e:
            print(f"Error getting count for {endpoint}: {e}")
            return 0
    
    # ============================================
    # ENTRA ID OVERVIEW
    # ============================================
    
    def get_entra_id_overview(self) -> Dict[str, Any]:
        """Get overview of Entra ID tenant - users, groups, apps, policies, devices counts"""
        try:
            overview = {}
            
            # Get counts using direct $count endpoint
            overview["TotalUsers"] = self._get_count("/users")
            overview["TotalGroups"] = self._get_count("/groups") 
            overview["TotalApplications"] = self._get_count("/applications")
            overview["TotalDevices"] = self._get_count("/devices")
            overview["TotalServicePrincipals"] = self._get_count("/servicePrincipals")
            
            # Get guest user count
            guests = self._make_graph_request("/users", {"$filter": "userType eq 'Guest'", "$count": "true", "$top": "1"})
            overview["GuestUsers"] = guests.get("@odata.count", 0)
            
            # Get conditional access policies count (beta endpoint)
            policies_result = self._make_graph_request("/identity/conditionalAccess/policies", use_beta=True)
            if "error" not in policies_result:
                overview["ConditionalAccessPolicies"] = len(policies_result.get("value", []))
            else:
                overview["ConditionalAccessPolicies"] = "N/A (requires Azure AD Premium)"
            
            return {
                "count": 1,
                "data": [overview],
                "summary": f"Tenant Overview: {overview['TotalUsers']} users ({overview['GuestUsers']} guests), {overview['TotalGroups']} groups, {overview['TotalApplications']} app registrations, {overview['TotalServicePrincipals']} enterprise apps, {overview['TotalDevices']} devices"
            }
        except Exception as e:
            return {"error": str(e), "count": 0, "data": []}
    
    # ============================================
    # USER QUERIES
    # ============================================
    
    def get_users_not_signed_in_30_days(self) -> Dict[str, Any]:
        """Get users who haven't signed in for 30+ days"""
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Get all users with sign-in activity (beta endpoint required for signInActivity)
            users = self._get_all_pages(
                "/users",
                {
                    "$select": "displayName,userPrincipalName,mail,accountEnabled,createdDateTime,userType,signInActivity",
                    "$filter": f"signInActivity/lastSignInDateTime le {cutoff_date}"
                },
                use_beta=True
            )
            
            if users and "error" in users[0]:
                # Fallback: Get all users and filter client-side
                all_users = self._get_all_pages(
                    "/users",
                    {"$select": "displayName,userPrincipalName,mail,accountEnabled,createdDateTime,userType,signInActivity"},
                    use_beta=True
                )
                
                result = []
                for user in all_users:
                    if "error" in user:
                        continue
                    sign_in_activity = user.get("signInActivity", {})
                    last_sign_in = sign_in_activity.get("lastSignInDateTime")
                    if last_sign_in:
                        last_sign_in_dt = datetime.fromisoformat(last_sign_in.replace("Z", "+00:00"))
                        if last_sign_in_dt < datetime.now(last_sign_in_dt.tzinfo) - timedelta(days=30):
                            result.append({
                                "DisplayName": user.get("displayName", "N/A"),
                                "UserPrincipalName": user.get("userPrincipalName", "N/A"),
                                "Email": user.get("mail", "N/A"),
                                "AccountEnabled": user.get("accountEnabled", False),
                                "UserType": user.get("userType", "N/A"),
                                "LastSignIn": last_sign_in,
                                "DaysSinceLastSignIn": (datetime.utcnow() - last_sign_in_dt.replace(tzinfo=None)).days,
                                "Recommendation": "Review account activity and consider disabling if inactive"
                            })
                users = result
            else:
                users = [{
                    "DisplayName": u.get("displayName", "N/A"),
                    "UserPrincipalName": u.get("userPrincipalName", "N/A"),
                    "Email": u.get("mail", "N/A"),
                    "AccountEnabled": u.get("accountEnabled", False),
                    "UserType": u.get("userType", "N/A"),
                    "LastSignIn": u.get("signInActivity", {}).get("lastSignInDateTime", "Never"),
                    "Recommendation": "Review account activity and consider disabling if inactive"
                } for u in users if "error" not in u]
            
            return {"count": len(users), "data": users}
        except Exception as e:
            return {"error": str(e)}
    
    def get_users_sync_stopped(self) -> Dict[str, Any]:
        """Get users that stopped synchronizing from on-premises AD"""
        try:
            # Get users that are marked as synced from on-prem but may have sync issues
            users = self._get_all_pages(
                "/users",
                {
                    "$select": "displayName,userPrincipalName,mail,onPremisesSyncEnabled,onPremisesLastSyncDateTime,onPremisesDomainName,accountEnabled",
                    "$filter": "onPremisesSyncEnabled eq true"
                }
            )
            
            result = []
            cutoff_date = datetime.utcnow() - timedelta(hours=24)  # Sync should happen within 24 hours
            
            for user in users:
                if "error" in user:
                    continue
                last_sync = user.get("onPremisesLastSyncDateTime")
                if last_sync:
                    last_sync_dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
                    if last_sync_dt.replace(tzinfo=None) < cutoff_date:
                        result.append({
                            "DisplayName": user.get("displayName", "N/A"),
                            "UserPrincipalName": user.get("userPrincipalName", "N/A"),
                            "Email": user.get("mail", "N/A"),
                            "OnPremisesDomain": user.get("onPremisesDomainName", "N/A"),
                            "LastSyncDateTime": last_sync,
                            "HoursSinceLastSync": int((datetime.utcnow() - last_sync_dt.replace(tzinfo=None)).total_seconds() / 3600),
                            "AccountEnabled": user.get("accountEnabled", False),
                            "Status": "Sync Delayed",
                            "Recommendation": "Check Azure AD Connect sync status"
                        })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_orphaned_guest_accounts(self) -> Dict[str, Any]:
        """Get guest accounts that haven't signed in for 90+ days"""
        try:
            # Get guest users
            guests = self._get_all_pages(
                "/users",
                {
                    "$select": "displayName,userPrincipalName,mail,createdDateTime,signInActivity,accountEnabled,externalUserState",
                    "$filter": "userType eq 'Guest'"
                },
                use_beta=True
            )
            
            result = []
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            
            for guest in guests:
                if "error" in guest:
                    continue
                sign_in_activity = guest.get("signInActivity", {})
                last_sign_in = sign_in_activity.get("lastSignInDateTime")
                
                is_orphaned = False
                days_since_signin = None
                
                if not last_sign_in:
                    # Never signed in
                    created_date = guest.get("createdDateTime")
                    if created_date:
                        created_dt = datetime.fromisoformat(created_date.replace("Z", "+00:00"))
                        if created_dt.replace(tzinfo=None) < cutoff_date:
                            is_orphaned = True
                            days_since_signin = (datetime.utcnow() - created_dt.replace(tzinfo=None)).days
                else:
                    last_sign_in_dt = datetime.fromisoformat(last_sign_in.replace("Z", "+00:00"))
                    if last_sign_in_dt.replace(tzinfo=None) < cutoff_date:
                        is_orphaned = True
                        days_since_signin = (datetime.utcnow() - last_sign_in_dt.replace(tzinfo=None)).days
                
                if is_orphaned:
                    result.append({
                        "DisplayName": guest.get("displayName", "N/A"),
                        "UserPrincipalName": guest.get("userPrincipalName", "N/A"),
                        "Email": guest.get("mail", "N/A"),
                        "ExternalUserState": guest.get("externalUserState", "N/A"),
                        "AccountEnabled": guest.get("accountEnabled", False),
                        "LastSignIn": last_sign_in or "Never",
                        "DaysSinceActivity": days_since_signin,
                        "CreatedDate": guest.get("createdDateTime", "N/A"),
                        "Recommendation": "Review and consider removing orphaned guest account"
                    })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_privileged_role_users(self) -> Dict[str, Any]:
        """Get users with privileged directory roles"""
        try:
            # Get all directory role assignments
            role_assignments = self._get_all_pages(
                "/roleManagement/directory/roleAssignments",
                {"$expand": "principal"}
            )
            
            # Get role definitions
            role_definitions = self._get_all_pages("/roleManagement/directory/roleDefinitions")
            role_map = {r.get("id"): r.get("displayName") for r in role_definitions if "error" not in r}
            
            # Privileged roles to highlight
            privileged_roles = [
                "Global Administrator", "Privileged Role Administrator", 
                "Security Administrator", "Exchange Administrator",
                "SharePoint Administrator", "User Administrator",
                "Application Administrator", "Cloud Application Administrator",
                "Conditional Access Administrator", "Intune Administrator"
            ]
            
            result = []
            for assignment in role_assignments:
                if "error" in assignment:
                    continue
                role_id = assignment.get("roleDefinitionId")
                role_name = role_map.get(role_id, "Unknown Role")
                
                if role_name in privileged_roles:
                    principal = assignment.get("principal", {})
                    result.append({
                        "UserDisplayName": principal.get("displayName", "N/A"),
                        "UserPrincipalName": principal.get("userPrincipalName", "N/A"),
                        "RoleName": role_name,
                        "RoleId": role_id,
                        "AssignmentScope": assignment.get("directoryScopeId", "/"),
                        "PrincipalType": assignment.get("principal", {}).get("@odata.type", "N/A").replace("#microsoft.graph.", ""),
                        "RiskLevel": "High" if role_name == "Global Administrator" else "Medium",
                        "Recommendation": "Ensure MFA enabled and review necessity of privileged access"
                    })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_global_admins(self) -> Dict[str, Any]:
        """Get users with Global Administrator role"""
        try:
            # Get Global Administrator role
            ga_role = self._make_graph_request(
                "/directoryRoles",
                {"$filter": "displayName eq 'Global Administrator'"}
            )
            
            if "error" in ga_role or not ga_role.get("value"):
                return {"error": "Could not find Global Administrator role", "data": []}
            
            role_id = ga_role["value"][0].get("id")
            
            # Get members of Global Admin role
            members = self._get_all_pages(f"/directoryRoles/{role_id}/members")
            
            result = []
            for member in members:
                if "error" in member:
                    continue
                result.append({
                    "DisplayName": member.get("displayName", "N/A"),
                    "UserPrincipalName": member.get("userPrincipalName", "N/A"),
                    "Email": member.get("mail", "N/A"),
                    "AccountEnabled": member.get("accountEnabled", True),
                    "ObjectType": member.get("@odata.type", "").replace("#microsoft.graph.", ""),
                    "RiskLevel": "Critical",
                    "Recommendation": "Ensure MFA, PIM activated, and break-glass accounts are documented"
                })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_custom_roles(self) -> Dict[str, Any]:
        """Get custom directory roles defined in the tenant"""
        try:
            roles = self._get_all_pages("/roleManagement/directory/roleDefinitions")
            
            result = []
            for role in roles:
                if "error" in role:
                    continue
                if role.get("isBuiltIn") == False:  # Custom roles only
                    result.append({
                        "RoleName": role.get("displayName", "N/A"),
                        "RoleId": role.get("id", "N/A"),
                        "Description": role.get("description", "N/A"),
                        "IsEnabled": role.get("isEnabled", False),
                        "PermissionCount": len(role.get("rolePermissions", [{}])[0].get("allowedResourceActions", [])),
                        "TemplateId": role.get("templateId", "N/A"),
                        "Recommendation": "Review custom role permissions regularly"
                    })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_unused_applications(self) -> Dict[str, Any]:
        """Get applications that appear to be unused (no recent sign-ins)"""
        try:
            # Get all applications
            apps = self._get_all_pages(
                "/applications",
                {"$select": "id,displayName,appId,createdDateTime,signInAudience,tags"}
            )
            
            # Get service principal sign-in activity (beta)
            sp_signins = self._make_graph_request(
                "/reports/servicePrincipalSignInActivities",
                use_beta=True
            )
            
            # Build map of app IDs with recent activity
            active_apps = set()
            if "value" in sp_signins:
                for signin in sp_signins["value"]:
                    last_signin = signin.get("lastSignInActivity", {}).get("lastSignInDateTime")
                    if last_signin:
                        last_dt = datetime.fromisoformat(last_signin.replace("Z", "+00:00"))
                        if last_dt.replace(tzinfo=None) > datetime.utcnow() - timedelta(days=90):
                            active_apps.add(signin.get("appId"))
            
            result = []
            for app in apps:
                if "error" in app:
                    continue
                app_id = app.get("appId")
                created_date = app.get("createdDateTime", "")
                
                # Check if created more than 90 days ago and no recent activity
                if created_date:
                    created_dt = datetime.fromisoformat(created_date.replace("Z", "+00:00"))
                    days_old = (datetime.utcnow() - created_dt.replace(tzinfo=None)).days
                    
                    if days_old > 90 and app_id not in active_apps:
                        result.append({
                            "AppName": app.get("displayName", "N/A"),
                            "AppId": app_id,
                            "CreatedDate": created_date,
                            "DaysOld": days_old,
                            "SignInAudience": app.get("signInAudience", "N/A"),
                            "LastActivity": "No recent activity (90+ days)",
                            "Status": "Potentially Unused",
                            "Recommendation": "Review if application is still needed and consider cleanup"
                        })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    # ============================================
    # DEVICES
    # ============================================
    
    def get_devices(self) -> Dict[str, Any]:
        """Get all registered devices"""
        try:
            devices = self._get_all_pages(
                "/devices",
                {"$select": "displayName,deviceId,operatingSystem,operatingSystemVersion,trustType,isCompliant,isManaged,registrationDateTime,approximateLastSignInDateTime"}
            )
            
            result = []
            for device in devices:
                if "error" in device:
                    continue
                result.append({
                    "DeviceName": device.get("displayName", "N/A"),
                    "DeviceId": device.get("deviceId", "N/A"),
                    "OS": device.get("operatingSystem", "N/A"),
                    "OSVersion": device.get("operatingSystemVersion", "N/A"),
                    "TrustType": device.get("trustType", "N/A"),
                    "IsCompliant": device.get("isCompliant", False),
                    "IsManaged": device.get("isManaged", False),
                    "RegisteredDate": device.get("registrationDateTime", "N/A"),
                    "LastSignIn": device.get("approximateLastSignInDateTime", "N/A")
                })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_stale_devices(self) -> Dict[str, Any]:
        """Get devices that haven't been active in 90+ days"""
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            devices = self._get_all_pages(
                "/devices",
                {
                    "$select": "displayName,deviceId,operatingSystem,operatingSystemVersion,trustType,isCompliant,isManaged,registrationDateTime,approximateLastSignInDateTime",
                    "$filter": f"approximateLastSignInDateTime le {cutoff_date}"
                }
            )
            
            result = []
            for device in devices:
                if "error" in device:
                    continue
                last_signin = device.get("approximateLastSignInDateTime")
                days_inactive = None
                if last_signin:
                    last_dt = datetime.fromisoformat(last_signin.replace("Z", "+00:00"))
                    days_inactive = (datetime.utcnow() - last_dt.replace(tzinfo=None)).days
                
                result.append({
                    "DeviceName": device.get("displayName", "N/A"),
                    "DeviceId": device.get("deviceId", "N/A"),
                    "OS": device.get("operatingSystem", "N/A"),
                    "TrustType": device.get("trustType", "N/A"),
                    "LastSignIn": last_signin or "Never",
                    "DaysInactive": days_inactive or "Unknown",
                    "Recommendation": "Review and consider removing stale device"
                })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    # ============================================
    # APPLICATIONS & SERVICE PRINCIPALS
    # ============================================
    
    def get_app_registrations(self) -> Dict[str, Any]:
        """Get all app registrations"""
        try:
            apps = self._get_all_pages(
                "/applications",
                {"$select": "id,displayName,appId,createdDateTime,signInAudience,identifierUris,web,publicClient"}
            )
            
            result = []
            for app in apps:
                if "error" in app:
                    continue
                result.append({
                    "AppName": app.get("displayName", "N/A"),
                    "AppId": app.get("appId", "N/A"),
                    "ObjectId": app.get("id", "N/A"),
                    "CreatedDate": app.get("createdDateTime", "N/A"),
                    "SignInAudience": app.get("signInAudience", "N/A"),
                    "IdentifierUris": ", ".join(app.get("identifierUris", [])) or "None",
                    "HasWebRedirect": bool(app.get("web", {}).get("redirectUris")),
                    "HasPublicClient": bool(app.get("publicClient", {}).get("redirectUris"))
                })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_enterprise_apps(self) -> Dict[str, Any]:
        """Get enterprise applications (service principals)"""
        try:
            sps = self._get_all_pages(
                "/servicePrincipals",
                {"$select": "id,displayName,appId,servicePrincipalType,accountEnabled,appOwnerOrganizationId,tags,createdDateTime"}
            )
            
            result = []
            for sp in sps:
                if "error" in sp:
                    continue
                result.append({
                    "AppName": sp.get("displayName", "N/A"),
                    "AppId": sp.get("appId", "N/A"),
                    "ObjectId": sp.get("id", "N/A"),
                    "Type": sp.get("servicePrincipalType", "N/A"),
                    "Enabled": sp.get("accountEnabled", True),
                    "OwnerTenantId": sp.get("appOwnerOrganizationId", "N/A"),
                    "Tags": ", ".join(sp.get("tags", [])) or "None",
                    "CreatedDate": sp.get("createdDateTime", "N/A")
                })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    # ============================================
    # GROUPS
    # ============================================
    
    def get_groups(self) -> Dict[str, Any]:
        """Get all groups"""
        try:
            groups = self._get_all_pages(
                "/groups",
                {"$select": "id,displayName,groupTypes,securityEnabled,mailEnabled,membershipRule,createdDateTime,description"}
            )
            
            result = []
            for group in groups:
                if "error" in group:
                    continue
                group_types = group.get("groupTypes", [])
                group_type = "Dynamic" if "DynamicMembership" in group_types else "Assigned"
                if "Unified" in group_types:
                    group_type = "Microsoft 365"
                elif group.get("securityEnabled") and not group.get("mailEnabled"):
                    group_type = "Security"
                elif group.get("mailEnabled"):
                    group_type = "Mail-enabled Security" if group.get("securityEnabled") else "Distribution"
                
                result.append({
                    "GroupName": group.get("displayName", "N/A"),
                    "GroupId": group.get("id", "N/A"),
                    "GroupType": group_type,
                    "SecurityEnabled": group.get("securityEnabled", False),
                    "MailEnabled": group.get("mailEnabled", False),
                    "MembershipType": "Dynamic" if group.get("membershipRule") else "Assigned",
                    "Description": group.get("description", "N/A")[:100] if group.get("description") else "N/A",
                    "CreatedDate": group.get("createdDateTime", "N/A")
                })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_empty_groups(self) -> Dict[str, Any]:
        """Get groups with no members"""
        try:
            groups = self._get_all_pages(
                "/groups",
                {"$select": "id,displayName,groupTypes,securityEnabled,createdDateTime"}
            )
            
            result = []
            for group in groups:
                if "error" in group:
                    continue
                group_id = group.get("id")
                
                # Get member count
                members = self._make_graph_request(f"/groups/{group_id}/members/$count")
                member_count = members if isinstance(members, int) else 0
                
                if member_count == 0:
                    group_types = group.get("groupTypes", [])
                    group_type = "Dynamic" if "DynamicMembership" in group_types else "Assigned"
                    
                    result.append({
                        "GroupName": group.get("displayName", "N/A"),
                        "GroupId": group_id,
                        "GroupType": group_type,
                        "MemberCount": 0,
                        "CreatedDate": group.get("createdDateTime", "N/A"),
                        "Recommendation": "Review if group is still needed"
                    })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    # ============================================
    # CONDITIONAL ACCESS POLICIES
    # ============================================
    
    def get_conditional_access_policies(self) -> Dict[str, Any]:
        """Get all Conditional Access policies"""
        try:
            policies = self._get_all_pages(
                "/identity/conditionalAccess/policies",
                use_beta=True
            )
            
            result = []
            for policy in policies:
                if "error" in policy:
                    continue
                
                conditions = policy.get("conditions", {})
                grant_controls = policy.get("grantControls", {})
                
                result.append({
                    "PolicyName": policy.get("displayName", "N/A"),
                    "PolicyId": policy.get("id", "N/A"),
                    "State": policy.get("state", "N/A"),
                    "CreatedDateTime": policy.get("createdDateTime", "N/A"),
                    "ModifiedDateTime": policy.get("modifiedDateTime", "N/A"),
                    "IncludeUsers": conditions.get("users", {}).get("includeUsers", []),
                    "IncludeApps": conditions.get("applications", {}).get("includeApplications", []),
                    "GrantControls": grant_controls.get("builtInControls", []) if grant_controls else []
                })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_conditional_access_policies_disabled(self) -> Dict[str, Any]:
        """Get disabled Conditional Access policies"""
        try:
            policies = self._get_all_pages(
                "/identity/conditionalAccess/policies",
                {"$filter": "state eq 'disabled'"},
                use_beta=True
            )
            
            result = []
            for policy in policies:
                if "error" in policy:
                    continue
                result.append({
                    "PolicyName": policy.get("displayName", "N/A"),
                    "PolicyId": policy.get("id", "N/A"),
                    "State": policy.get("state", "N/A"),
                    "ModifiedDateTime": policy.get("modifiedDateTime", "N/A"),
                    "Recommendation": "Review if policy should be enabled or removed"
                })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_conditional_access_without_mfa(self) -> Dict[str, Any]:
        """Get Conditional Access policies that don't require MFA"""
        try:
            policies = self._get_all_pages(
                "/identity/conditionalAccess/policies",
                {"$filter": "state eq 'enabled'"},
                use_beta=True
            )
            
            result = []
            for policy in policies:
                if "error" in policy:
                    continue
                
                grant_controls = policy.get("grantControls", {})
                built_in_controls = grant_controls.get("builtInControls", []) if grant_controls else []
                
                if "mfa" not in built_in_controls:
                    result.append({
                        "PolicyName": policy.get("displayName", "N/A"),
                        "PolicyId": policy.get("id", "N/A"),
                        "State": policy.get("state", "N/A"),
                        "CurrentControls": ", ".join(built_in_controls) or "None",
                        "Recommendation": "Consider adding MFA requirement for enhanced security"
                    })
            
            return {"count": len(result), "data": result}
        except Exception as e:
            return {"error": str(e)}
