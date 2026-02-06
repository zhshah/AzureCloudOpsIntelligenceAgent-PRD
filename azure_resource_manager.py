"""
Azure Resource Management Integration
Handles resource queries using Azure Resource Graph API
"""

import os
from typing import Dict, Any, List, Optional
from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest, QueryRequestOptions
from azure.mgmt.resource import SubscriptionClient
from azure.mgmt.managementgroups import ManagementGroupsAPI
import json
from azure_cost_manager import AzureCostManager


class AzureResourceManager:
    def __init__(self):
        """Initialize Azure Resource Graph client"""
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        
        use_managed_identity = os.getenv("USE_MANAGED_IDENTITY", "false").lower() == "true"
        
        if use_managed_identity:
            self.credential = DefaultAzureCredential()
        else:
            self.credential = DefaultAzureCredential()
        
        self.rg_client = ResourceGraphClient(self.credential)
        self.sub_client = SubscriptionClient(self.credential)
        self.mg_client = ManagementGroupsAPI(self.credential)  # Management Groups client
        self.cost_manager = AzureCostManager()  # Initialize Cost Management client
        self._subscription_cache = {}  # Cache for subscription name lookups
        self._management_group_cache = {}  # Cache for management group lookups
    
    def _get_subscription_names(self) -> Dict[str, str]:
        """Get mapping of subscription ID to display name"""
        if not self._subscription_cache:
            try:
                for sub in self.sub_client.subscriptions.list():
                    self._subscription_cache[sub.subscription_id] = sub.display_name
            except Exception as e:
                print(f"Warning: Could not fetch subscription names: {e}")
        return self._subscription_cache
    
    async def get_subscriptions(self) -> List[Dict[str, Any]]:
        """Get all accessible subscriptions"""
        try:
            subscriptions = []
            for sub in self.sub_client.subscriptions.list():
                subscriptions.append({
                    "id": sub.subscription_id,
                    "name": sub.display_name,
                    "state": sub.state
                })
            return subscriptions
        except Exception as e:
            return [{"error": str(e)}]
    
    async def get_management_groups(self) -> List[Dict[str, Any]]:
        """Get all accessible management groups with hierarchy"""
        try:
            management_groups = []
            for mg in self.mg_client.management_groups.list():
                # Get detailed info including children
                mg_detail = self.mg_client.management_groups.get(
                    group_id=mg.name,
                    expand="children",
                    recurse=True
                )
                mg_data = {
                    "id": mg.name,
                    "name": mg_detail.display_name or mg.name,
                    "type": "managementGroup",
                    "tenantId": mg_detail.tenant_id if hasattr(mg_detail, 'tenant_id') else None,
                    "children": self._extract_children(mg_detail.children) if hasattr(mg_detail, 'children') and mg_detail.children else []
                }
                management_groups.append(mg_data)
            return management_groups
        except Exception as e:
            print(f"Error fetching management groups: {e}")
            return []
    
    def _extract_children(self, children) -> List[Dict[str, Any]]:
        """Recursively extract children from management group hierarchy"""
        result = []
        if not children:
            return result
        for child in children:
            child_data = {
                "id": child.name,
                "name": child.display_name or child.name,
                "type": "managementGroup" if "/managementGroups/" in (child.id or "") else "subscription"
            }
            if hasattr(child, 'children') and child.children:
                child_data["children"] = self._extract_children(child.children)
            result.append(child_data)
        return result
    
    async def get_subscriptions_with_hierarchy(self) -> Dict[str, Any]:
        """Get subscriptions with management group hierarchy"""
        try:
            # Get subscriptions
            subscriptions = await self.get_subscriptions()
            
            # Get management groups
            management_groups = await self.get_management_groups()
            
            return {
                "subscriptions": subscriptions,
                "managementGroups": management_groups
            }
        except Exception as e:
            return {
                "subscriptions": await self.get_subscriptions(),
                "managementGroups": [],
                "error": str(e)
            }
    
    def query_resources(self, query: str, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute a Resource Graph query
        
        Args:
            query: KQL query string
            subscriptions: List of subscription IDs to query
        """
        try:
            if not subscriptions:
                # If no subscription provided, try to get from env or use cached list
                if self.subscription_id:
                    subscriptions = [self.subscription_id]
                elif hasattr(self, '_cached_subscriptions') and self._cached_subscriptions:
                    subscriptions = self._cached_subscriptions
                else:
                    # Get all accessible subscriptions and cache them
                    all_subs = []
                    try:
                        for sub in self.sub_client.subscriptions.list():
                            if sub.state == "Enabled":
                                all_subs.append(sub.subscription_id)
                    except Exception as sub_err:
                        return {"error": f"Failed to fetch subscriptions: {str(sub_err)}", "count": 0, "data": []}
                    if not all_subs:
                        return {"error": "No accessible subscriptions found", "count": 0, "data": []}
                    self._cached_subscriptions = all_subs
                    subscriptions = all_subs
            
            request = QueryRequest(
                subscriptions=subscriptions,
                query=query,
                options=QueryRequestOptions(top=5000, skip_token=None)
            )
            
            response = self.rg_client.resources(request)
            
            return {
                "count": response.count,
                "total_records": response.total_records,
                "data": response.data
            }
        except Exception as e:
            return {"error": str(e), "count": 0, "data": []}
    
    def get_storage_accounts_with_private_endpoints(self) -> Dict[str, Any]:
        """Get storage accounts with private endpoints"""
        query = """
        Resources
        | where type == 'microsoft.storage/storageaccounts'
        | project name, resourceGroup, location, 
                  hasPrivateEndpoint = isnotnull(properties.privateEndpointConnections) and array_length(properties.privateEndpointConnections) > 0
        | where hasPrivateEndpoint == true
        """
        return self.query_resources(query)
    
    def get_all_vnets(self) -> Dict[str, Any]:
        """Get all virtual networks"""
        query = """
        Resources
        | where type == 'microsoft.network/virtualnetworks'
        | project name, resourceGroup, location, 
                  addressSpace = properties.addressSpace.addressPrefixes,
                  subnets = array_length(properties.subnets)
        """
        return self.query_resources(query)
    
    def get_vms_without_backup(self) -> Dict[str, Any]:
        """Get VMs that don't have backup configured"""
        query = """
        Resources
        | where type == 'microsoft.compute/virtualmachines'
        | project vmName = name, resourceGroup, location, vmId = id
        | join kind=leftouter (
            Resources
            | where type == 'microsoft.recoveryservices/vaults'
            | extend protectedItems = properties.protectedItemsCount
            | project vaultId = id, protectedItems
        ) on $left.resourceGroup == $right.resourceGroup
        | where isnull(protectedItems) or protectedItems == 0
        | project vmName, resourceGroup, location
        """
        return self.query_resources(query)
    
    def get_resources_by_type(self, resource_type: str) -> Dict[str, Any]:
        """
        Get resources by type
        
        Args:
            resource_type: Azure resource type (e.g., 'microsoft.compute/virtualmachines')
        """
        query = f"""
        Resources
        | where type =~ '{resource_type}'
        | project name, resourceGroup, location, type, id
        """
        return self.query_resources(query)
    
    def get_resources_by_tag(self, tag_name: str, tag_value: Optional[str] = None) -> Dict[str, Any]:
        """
        Get resources by tag (case-insensitive search)
        
        Args:
            tag_name: Tag name to filter by (case-insensitive)
            tag_value: Optional tag value to filter by (case-insensitive)
        """
        # Escape single quotes in input to prevent query injection
        tag_name_safe = tag_name.replace("'", "''")
        
        if tag_value:
            tag_value_safe = tag_value.replace("'", "''")
            query = f"""
            Resources
            | where isnotempty(tags['{tag_name_safe}'])
            | where tags['{tag_name_safe}'] =~ '{tag_value_safe}'
            | project ResourceName=name, ResourceType=type, ResourceGroup=resourceGroup, Location=location, Tags=tags, Status=tostring(properties.provisioningState)
            | order by ResourceType asc, ResourceName asc
            """
        else:
            query = f"""
            Resources
            | where isnotempty(tags['{tag_name_safe}'])
            | project ResourceName=name, ResourceType=type, ResourceGroup=resourceGroup, Location=location, Tags=tags, Status=tostring(properties.provisioningState)
            | order by ResourceType asc, ResourceName asc
            """
        return self.query_resources(query)
    
    def get_resources_by_location(self, location: str) -> Dict[str, Any]:
        """
        Get resources by location
        
        Args:
            location: Azure region (e.g., 'eastus', 'westeurope')
        """
        query = f"""
        Resources
        | where location =~ '{location}'
        | summarize count() by type
        | order by count_ desc
        """
        return self.query_resources(query)
    
    def get_all_resources_detailed(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all resources with detailed information (name, type, RG, location, tags) including subscription name"""
        query = """
        Resources
        | project 
            ResourceName = name,
            ResourceType = type,
            ResourceGroup = resourceGroup,
            Location = location,
            Tags = tags,
            SubscriptionId = subscriptionId,
            Status = tostring(properties.provisioningState)
        | order by ResourceType asc, ResourceName asc
        """
        result = self.query_resources(query, subscriptions)
        
        # Add subscription names to results
        if result and 'data' in result and isinstance(result['data'], list):
            sub_names = self._get_subscription_names()
            for resource in result['data']:
                sub_id = resource.get('SubscriptionId', '')
                resource['SubscriptionName'] = sub_names.get(sub_id, sub_id[:8] + '...' if sub_id else 'Unknown')
        
        return result
    
    def get_resources_by_resource_group(self, resource_group: str, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all resources in a specific resource group"""
        query = f"""
        Resources
        | where resourceGroup =~ '{resource_group}'
        | project 
            ResourceName = name,
            ResourceType = type,
            ResourceGroup = resourceGroup,
            Location = location,
            Tags = tags,
            SubscriptionId = subscriptionId,
            Status = tostring(properties.provisioningState)
        | order by ResourceType asc, ResourceName asc
        """
        result = self.query_resources(query, subscriptions)
        
        # Add subscription names to results
        if result and 'data' in result and isinstance(result['data'], list):
            sub_names = self._get_subscription_names()
            for resource in result['data']:
                sub_id = resource.get('SubscriptionId', '')
                resource['SubscriptionName'] = sub_names.get(sub_id, sub_id[:8] + '...' if sub_id else 'Unknown')
        
        return result
    
    def get_resource_count_by_type(self) -> Dict[str, Any]:
        """Get count of resources grouped by type"""
        query = """
        Resources
        | summarize count() by type
        | order by count_ desc
        """
        return self.query_resources(query)
    
    def get_public_ip_addresses(self) -> Dict[str, Any]:
        """Get all public IP addresses"""
        query = """
        Resources
        | where type == 'microsoft.network/publicipaddresses'
        | project name, resourceGroup, location,
                  ipAddress = properties.ipAddress,
                  allocationMethod = properties.publicIPAllocationMethod,
                  sku = sku.name
        """
        return self.query_resources(query)
    
    def get_nsg_rules(self) -> Dict[str, Any]:
        """Get Network Security Group rules"""
        query = """
        Resources
        | where type == 'microsoft.network/networksecuritygroups'
        | extend rules = properties.securityRules
        | mv-expand rules
        | project nsgName = name, 
                  ruleName = rules.name,
                  priority = rules.properties.priority,
                  direction = rules.properties.direction,
                  access = rules.properties.access,
                  protocol = rules.properties.protocol,
                  sourcePort = rules.properties.sourcePortRange,
                  destinationPort = rules.properties.destinationPortRange
        """
        return self.query_resources(query)
    
    def search_resources(self, search_term: str) -> Dict[str, Any]:
        """
        Search for resources by name
        
        Args:
            search_term: Term to search for in resource names
        """
        query = f"""
        Resources
        | where name contains '{search_term}'
        | project name, type, resourceGroup, location
        """
        return self.query_resources(query)
    
    def get_app_services(self) -> Dict[str, Any]:
        """Get all App Services"""
        query = """
        Resources
        | where type == 'microsoft.web/sites'
        | project name, resourceGroup, location,
                  Kind = kindVal,
                  state = properties.state,
                  defaultHostName = properties.defaultHostName,
                  sku = properties.sku
        """
        return self.query_resources(query)
    
    def get_sql_databases(self) -> Dict[str, Any]:
        """Get all SQL databases"""
        query = """
        Resources
        | where type == 'microsoft.sql/servers/databases'
        | project name, resourceGroup, location,
                  serverName = split(id, '/')[8],
                  sku = sku.name,
                  maxSizeBytes = properties.maxSizeBytes
        """
        return self.query_resources(query)
    
    def get_key_vaults(self) -> Dict[str, Any]:
        """Get all Key Vaults"""
        query = """
        Resources
        | where type == 'microsoft.keyvault/vaults'
        | project name, resourceGroup, location,
                  sku = properties.sku.name,
                  enabledForDeployment = properties.enabledForDeployment,
                  enableRbacAuthorization = properties.enableRbacAuthorization
        """
        return self.query_resources(query)
    
    def get_all_vms(self) -> Dict[str, Any]:
        """Get all virtual machines with detailed information"""
        query = """
        Resources
        | where type == 'microsoft.compute/virtualmachines'
        | project name, resourceGroup, location, 
                  vmSize = properties.hardwareProfile.vmSize,
                  osType = properties.storageProfile.osDisk.osType,
                  powerState = properties.extended.instanceView.powerState.code,
                  tags,
                  id
        """
        return self.query_resources(query)
    
    def get_storage_accounts(self) -> Dict[str, Any]:
        """Get all storage accounts with security settings"""
        query = """
        Resources
        | where type == 'microsoft.storage/storageaccounts'
        | project name, resourceGroup, location,
                  sku = sku.name,
                  allowBlobPublicAccess = properties.allowBlobPublicAccess,
                  supportsHttpsTrafficOnly = properties.supportsHttpsTrafficOnly,
                  hasPrivateEndpoint = isnotnull(properties.privateEndpointConnections) and array_length(properties.privateEndpointConnections) > 0,
                  publicNetworkAccess = properties.publicNetworkAccess,
                  tags,
                  id
        """
        return self.query_resources(query)
    
    def get_paas_without_private_endpoints(self) -> Dict[str, Any]:
        """Get PaaS resources without private endpoints (storage, SQL, Key Vault, Cosmos DB)"""
        query = """
        Resources
        | where type in~ (
            'microsoft.storage/storageaccounts',
            'microsoft.sql/servers',
            'microsoft.keyvault/vaults',
            'microsoft.documentdb/databaseaccounts'
        )
        | extend hasPrivateEndpoint = isnotnull(properties.privateEndpointConnections) and array_length(properties.privateEndpointConnections) > 0
        | extend publicNetworkAccess = properties.publicNetworkAccess
        | where hasPrivateEndpoint == false or publicNetworkAccess =~ 'Enabled'
        | project name, type, resourceGroup, location, 
                  hasPrivateEndpoint,
                  publicNetworkAccess,
                  tags,
                  id
        """
        return self.query_resources(query)
    
    def get_resources_with_public_access(self) -> Dict[str, Any]:
        """Get resources exposed to public internet"""
        query = """
        Resources
        | where type in~ (
            'microsoft.storage/storageaccounts',
            'microsoft.sql/servers',
            'microsoft.network/publicipaddresses',
            'microsoft.compute/virtualmachines'
        )
        | extend publicAccess = case(
            type =~ 'microsoft.storage/storageaccounts', properties.allowBlobPublicAccess,
            type =~ 'microsoft.sql/servers', properties.publicNetworkAccess =~ 'Enabled',
            type =~ 'microsoft.network/publicipaddresses', true,
            type =~ 'microsoft.compute/virtualmachines', isnotnull(properties.networkProfile.networkInterfaces),
            false
        )
        | where publicAccess == true
        | project name, type, resourceGroup, location, tags, id
        """
        return self.query_resources(query)
    
    def get_all_databases(self) -> Dict[str, Any]:
        """Get all database resources (SQL, Cosmos DB, PostgreSQL, MySQL)"""
        query = """
        Resources
        | where type in~ (
            'microsoft.sql/servers/databases',
            'microsoft.documentdb/databaseaccounts',
            'microsoft.dbforpostgresql/servers',
            'microsoft.dbformysql/servers'
        )
        | project name, type, resourceGroup, location,
                  sku = sku.name,
                  tags,
                  id
        """
        return self.query_resources(query)
    
    def get_resources_without_tags(self) -> Dict[str, Any]:
        """Get resources missing required tags (Environment, CostCenter, Owner)"""
        query = """
        Resources
        | extend hasEnvironment = isnotnull(tags['Environment'])
        | extend hasCostCenter = isnotnull(tags['CostCenter'])
        | extend hasOwner = isnotnull(tags['Owner']) or isnotnull(tags['ApplicationOwner'])
        | where hasEnvironment == false or hasCostCenter == false or hasOwner == false
        | project name, type, resourceGroup, location,
                  missingTags = pack_array(
                      iff(hasEnvironment == false, 'Environment', ''),
                      iff(hasCostCenter == false, 'CostCenter', ''),
                      iff(hasOwner == false, 'Owner', '')
                  ),
                  existingTags = tags,
                  id
        """
        return self.query_resources(query)
    
    def get_unused_resources(self) -> Dict[str, Any]:
        """Get potentially unused resources (orphaned disks, unattached IPs, stopped VMs)"""
        query = """
        Resources
        | where (type == 'microsoft.compute/disks' and properties.diskState == 'Unattached')
            or (type == 'microsoft.network/publicipaddresses' and isnull(properties.ipConfiguration))
            or (type == 'microsoft.compute/virtualmachines' and properties.extended.instanceView.powerState.code =~ 'PowerState/deallocated')
        | project name, type, resourceGroup, location,
                  state = case(
                      type == 'microsoft.compute/disks', 'Orphaned Disk',
                      type == 'microsoft.network/publicipaddresses', 'Unattached IP',
                      type == 'microsoft.compute/virtualmachines', 'Deallocated VM',
                      'Unknown'
                  ),
                  tags,
                  id
        """
        return self.query_resources(query)
    
    def get_resources_by_multiple_tags(self, tags: Dict[str, str]) -> Dict[str, Any]:
        """Get resources filtered by multiple tag criteria"""
        # Build where clause for multiple tags
        tag_conditions = []
        for tag_name, tag_value in tags.items():
            tag_conditions.append(f"tags['{tag_name}'] == '{tag_value}'")
        
        where_clause = " and ".join(tag_conditions)
        
        query = f"""
        Resources
        | where {where_clause}
        | project name, type, resourceGroup, location, tags, id
        """
        return self.query_resources(query)
    
    def get_multi_region_distribution(self) -> Dict[str, Any]:
        """Get resource distribution across regions"""
        query = """
        Resources
        | summarize count() by location, type
        | order by location asc, count_ desc
        """
        return self.query_resources(query)
    
    def get_tag_compliance_summary(self) -> Dict[str, Any]:
        """Get tag compliance statistics"""
        query = """
        Resources
        | extend hasEnvironment = isnotnull(tags['Environment'])
        | extend hasCostCenter = isnotnull(tags['CostCenter'])
        | extend hasOwner = isnotnull(tags['Owner']) or isnotnull(tags['ApplicationOwner'])
        | extend fullyTagged = hasEnvironment and hasCostCenter and hasOwner
        | summarize 
            totalResources = count(),
            fullyTaggedCount = countif(fullyTagged == true),
            missingEnvironment = countif(hasEnvironment == false),
            missingCostCenter = countif(hasCostCenter == false),
            missingOwner = countif(hasOwner == false)
        | extend compliancePercentage = round(todouble(fullyTaggedCount) / todouble(totalResources) * 100, 2)
        """
        return self.query_resources(query)
    
    def get_policy_compliance_status(self, scope: str = "subscription", resource_group: str = None, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get Azure Policy compliance status using policyresources
        Returns policy assignments and their compliance state
        
        Args:
            scope: Level of compliance report - 'subscription' or 'resource_group'
            resource_group: Required when scope is 'resource_group' - filter to specific RG
            subscriptions: List of subscription IDs to query
        """
        # Build resource group filter if specified
        rg_filter = ""
        if scope == "resource_group" and resource_group:
            rg_filter = f"| where properties.resourceGroup =~ '{resource_group}'"
        
        query = f"""
        policyresources
        | where type =~ 'microsoft.policyinsights/policystates'
        {rg_filter}
        | extend subId = tostring(subscriptionId)
        | extend rgName = tostring(properties.resourceGroup)
        | summarize 
            TotalResources = count(),
            CompliantResources = countif(properties.complianceState == 'Compliant'),
            NonCompliantResources = countif(properties.complianceState == 'NonCompliant')
            by policyAssignmentName = tostring(properties.policyAssignmentName), 
               policyDefinitionName = tostring(properties.policyDefinitionName),
               policyDefinitionAction = tostring(properties.policyDefinitionAction),
               subscriptionId = subId,
               resourceGroup = rgName
        | extend CompliancePercentage = round(todouble(CompliantResources) / todouble(TotalResources) * 100, 2)
        | project 
            PolicyAssignmentName = policyAssignmentName,
            ComplianceState = case(
                CompliancePercentage == 100, 'Compliant',
                CompliancePercentage >= 80, 'Mostly Compliant',
                CompliancePercentage >= 50, 'Partially Compliant',
                'Non-Compliant'
            ),
            CompliantResources,
            NonCompliantResources,
            CompliancePercentage = strcat(tostring(CompliancePercentage), '%'),
            Severity = case(
                policyDefinitionAction == 'deny', 'High',
                policyDefinitionAction == 'audit', 'Medium',
                'Low'
            ),
            RemediationRequired = case(NonCompliantResources > 0, 'Yes', 'No'),
            SubscriptionId = subscriptionId,
            ResourceGroup = resourceGroup
        | order by NonCompliantResources desc
        """
        return self.query_resources(query, subscriptions)
    
    def get_non_compliant_resources(self, severity: str = "All", subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get non-compliant resources with policy details
        
        Args:
            severity: Filter by severity (Critical/High/Medium/All)
            subscriptions: List of subscription IDs
        """
        query = f"""
        policyresources
        | where type =~ 'microsoft.policyinsights/policystates' 
        | where properties.complianceState == 'NonCompliant'
        | extend resourceIdLower = tolower(tostring(properties.resourceId))
        | extend policyAction = tostring(properties.policyDefinitionAction)
        | extend Severity = case(
            policyAction == 'deny', 'Critical',
            policyAction == 'deployIfNotExists', 'High',
            policyAction == 'audit', 'Medium',
            'Low'
        )
        | join kind=leftouter (
            Resources
            | extend resourceIdLower = tolower(id)
            | project resourceIdLower, resourceName = name, resourceType = type, resourceGroup, location
        ) on resourceIdLower
        | project 
            ResourceName = coalesce(resourceName, tostring(properties.resourceId)),
            Type = coalesce(resourceType, 'Unknown'),
            NonCompliantPolicies = tostring(properties.policyDefinitionName),
            Severity,
            Impact = case(
                policyAction == 'deny', 'Blocks new deployments',
                policyAction == 'deployIfNotExists', 'Requires remediation',
                policyAction == 'audit', 'Audit only',
                'Informational'
            ),
            AutomatedRemediationAvailable = case(
                policyAction == 'deployIfNotExists' or policyAction == 'modify', 'Yes',
                'No'
            ),
            ManualStepsRequired = case(
                policyAction == 'deployIfNotExists' or policyAction == 'modify', 'Review and approve remediation',
                'Manual configuration required'
            ),
            EstimatedFixTime = case(
                policyAction == 'deployIfNotExists', '5-15 minutes',
                policyAction == 'modify', '5-10 minutes',
                '15-30 minutes'
            )
        {f"| where Severity == '{severity}'" if severity.lower() != "all" else ""}
        | order by Severity desc
        | take 500
        """
        return self.query_resources(query, subscriptions)
    
    def get_policy_recommendations(self, focus_area: str = "All", subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get recommended Azure Policies based on environment analysis
        
        Args:
            focus_area: Cost, Security, Operations, Compliance, or All
            subscriptions: List of subscription IDs
        """
        # Analyze current environment to provide recommendations
        recommendations = []
        
        if focus_area.lower() in ["cost", "all"]:
            recommendations.extend([
                {
                    "PolicyName": "Allowed virtual machine size SKUs",
                    "Category": "Cost Optimization",
                    "ImpactLevel": "High",
                    "Benefits": "Prevent over-provisioned VMs, reduce compute costs by 20-40%",
                    "ImplementationEffort": "Low",
                    "ExpectedROI": "15-25% cost reduction on compute",
                    "EnforcementMode": "Deny"
                },
                {
                    "PolicyName": "Configure diagnostic settings for Storage Accounts",
                    "Category": "Cost & Operations",
                    "ImpactLevel": "Medium",
                    "Benefits": "Monitor storage usage, identify cost anomalies early",
                    "ImplementationEffort": "Medium",
                    "ExpectedROI": "10-15% storage cost optimization",
                    "EnforcementMode": "DeployIfNotExists"
                }
            ])
        
        if focus_area.lower() in ["security", "all"]:
            recommendations.extend([
                {
                    "PolicyName": "Storage accounts should restrict network access",
                    "Category": "Security",
                    "ImpactLevel": "Critical",
                    "Benefits": "Prevent data exfiltration, reduce attack surface by 60%",
                    "ImplementationEffort": "Medium",
                    "ExpectedROI": "Prevent security incidents worth $100K+",
                    "EnforcementMode": "Audit"
                },
                {
                    "PolicyName": "Virtual machines should encrypt temp disks, caches, and data flows",
                    "Category": "Security & Compliance",
                    "ImpactLevel": "High",
                    "Benefits": "Meet compliance requirements (HIPAA, PCI-DSS), protect sensitive data",
                    "ImplementationEffort": "High",
                    "ExpectedROI": "Avoid compliance penalties ($50K-$500K)",
                    "EnforcementMode": "Audit"
                }
            ])
        
        if focus_area.lower() in ["operations", "all"]:
            recommendations.extend([
                {
                    "PolicyName": "Require tag and its value on resources",
                    "Category": "Operations & Governance",
                    "ImpactLevel": "High",
                    "Benefits": "Improve resource tracking, cost allocation, operational visibility",
                    "ImplementationEffort": "Low",
                    "ExpectedROI": "30% faster incident resolution, better cost attribution",
                    "EnforcementMode": "Deny"
                },
                {
                    "PolicyName": "Deploy VM backup on VMs without backup",
                    "Category": "Operations & DR",
                    "ImpactLevel": "Critical",
                    "Benefits": "Automated DR, prevent data loss, meet RPO/RTO",
                    "ImplementationEffort": "Medium",
                    "ExpectedROI": "Prevent data loss worth $500K+",
                    "EnforcementMode": "DeployIfNotExists"
                }
            ])
        
        if focus_area.lower() in ["compliance", "all"]:
            recommendations.extend([
                {
                    "PolicyName": "Audit VMs that do not use managed disks",
                    "Category": "Compliance & Operations",
                    "ImpactLevel": "Medium",
                    "Benefits": "Standardize infrastructure, simplify management, meet compliance",
                    "ImplementationEffort": "Low",
                    "ExpectedROI": "20% reduction in operational overhead",
                    "EnforcementMode": "Audit"
                },
                {
                    "PolicyName": "Allowed locations for resources",
                    "Category": "Compliance & Data Sovereignty",
                    "ImpactLevel": "Critical",
                    "Benefits": "Enforce data residency, meet GDPR/regional compliance",
                    "ImplementationEffort": "Low",
                    "ExpectedROI": "Avoid compliance violations and penalties",
                    "EnforcementMode": "Deny"
                }
            ])
        
        return {
            "count": len(recommendations),
            "total_records": len(recommendations),
            "data": recommendations
        }
    
    def get_policy_exemptions(self, show_expired: bool = True, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get policy exemptions and their status
        
        Args:
            show_expired: Include expired exemptions
            subscriptions: List of subscription IDs
        """
        query = f"""
        policyresources
        | where type =~ 'microsoft.authorization/policyexemptions'
        | extend expiresOn = todatetime(properties.expiresOn)
        | extend exemptionCategory = tostring(properties.exemptionCategory)
        | extend policyAssignmentId = tostring(properties.policyAssignmentId)
        | extend metadata = properties.metadata
        | extend isExpired = expiresOn < now()
        | project 
            Resource = name,
            ExemptedPolicy = tostring(array_slice(split(policyAssignmentId, '/'), -1, -1)[0]),
            ExemptionReason = exemptionCategory,
            RequestedBy = tostring(metadata.requestedBy),
            ExpirationDate = format_datetime(expiresOn, 'yyyy-MM-dd'),
            RiskLevel = case(
                exemptionCategory == 'Waiver', 'High',
                exemptionCategory == 'Mitigated', 'Medium',
                'Low'
            ),
            ReviewRecommendation = case(
                isExpired, 'EXPIRED - Remove or renew immediately',
                expiresOn < now() + 30d, 'Expiring soon - Review required',
                'Active - Review before expiration'
            ),
            IsExpired = isExpired
        {'' if show_expired else '| where isExpired == false'}
        | order by ExpirationDate asc
        """
        return self.query_resources(query, subscriptions)
    
    # UPDATE MANAGEMENT FUNCTIONS
    def get_vm_pending_updates(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get Azure VMs with update status using Resources table
        """
        query = """
        Resources
        | where type == 'microsoft.compute/virtualmachines'
        | extend osType = properties.storageProfile.osDisk.osType
        | extend osVersion = properties.storageProfile.imageReference.offer
        | extend powerState = tostring(properties.extended.instanceView.powerState.displayStatus)
        | extend patchMode = properties.osProfile.windowsConfiguration.patchSettings.patchMode
        | project 
            VMName = name,
            ResourceGroup = resourceGroup,
            OSType = osType,
            OSVersion = osVersion,
            PendingCritical = 'Check Azure Update Manager',
            PendingSecurity = 'Check Azure Update Manager',
            PendingOther = 'Check Azure Update Manager',
            TotalPending = 'Check Azure Update Manager',
            LastAssessment = 'Enable Update Manager',
            ComplianceStatus = case(
                powerState contains 'running', 'Running - Check Update Manager',
                powerState contains 'stopped', 'Stopped',
                'Unknown'
            ),
            PowerState = powerState,
            PatchMode = patchMode
        | order by VMName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_arc_pending_updates(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get Azure Arc-enabled servers with update status
        """
        query = """
        Resources
        | where type == 'microsoft.hybridcompute/machines'
        | extend osType = properties.osType
        | extend osVersion = properties.osVersion
        | extend status = properties.status
        | extend agentVersion = properties.agentVersion
        | extend lastStatusChange = properties.lastStatusChange
        | project 
            ServerName = name,
            ResourceGroup = resourceGroup,
            OSType = osType,
            OSVersion = osVersion,
            PendingCritical = 'Check Azure Update Manager',
            PendingSecurity = 'Check Azure Update Manager',
            PendingOther = 'Check Azure Update Manager',
            TotalPending = 'Check Azure Update Manager',
            LastAssessment = lastStatusChange,
            Location = location,
            ComplianceStatus = case(
                status == 'Connected', 'Connected - Check Update Manager',
                status == 'Disconnected', 'Disconnected',
                status == 'Error', 'Error',
                'Unknown'
            ),
            Status = status,
            AgentVersion = agentVersion
        | order by ServerName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_vm_pending_reboot(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get Azure VMs that may require reboot based on power state
        """
        query = """
        Resources
        | where type == 'microsoft.compute/virtualmachines'
        | extend osType = properties.storageProfile.osDisk.osType
        | extend powerState = tostring(properties.extended.instanceView.powerState.displayStatus)
        | extend vmSize = properties.hardwareProfile.vmSize
        | project 
            VMName = name,
            ResourceGroup = resourceGroup,
            OSType = osType,
            PowerState = powerState,
            RebootReason = case(
                powerState contains 'stopped', 'VM is stopped',
                powerState contains 'deallocated', 'VM is deallocated',
                'Check Update Manager for pending reboots'
            ),
            PendingUpdatesRequiringReboot = 'Check Update Manager',
            LastBootTime = 'Check VM diagnostics',
            UptimeDays = 'Check VM diagnostics',
            PriorityLevel = case(
                powerState contains 'stopped', 'High',
                powerState contains 'running', 'Medium',
                'Low'
            ),
            VMSize = vmSize
        | order by PriorityLevel asc, VMName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_arc_pending_reboot(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get Azure Arc-enabled servers status for reboot planning
        """
        query = """
        Resources
        | where type == 'microsoft.hybridcompute/machines'
        | extend osType = properties.osType
        | extend status = properties.status
        | extend agentVersion = properties.agentVersion
        | extend lastStatusChange = properties.lastStatusChange
        | project 
            ServerName = name,
            ResourceGroup = resourceGroup,
            OSType = osType,
            Status = status,
            RebootReason = case(
                status == 'Disconnected', 'Server disconnected - check connectivity',
                status == 'Error', 'Agent error - check logs',
                'Check Update Manager for pending reboots'
            ),
            PendingUpdatesRequiringReboot = 'Check Update Manager',
            LastBootTime = lastStatusChange,
            UptimeDays = datetime_diff('day', now(), todatetime(lastStatusChange)),
            PriorityLevel = case(
                status == 'Disconnected', 'Critical',
                status == 'Error', 'High',
                'Medium'
            ),
            AgentVersion = agentVersion
        | order by PriorityLevel asc, ServerName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_update_compliance_summary(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get overall update compliance summary for both VMs and Arc servers
        """
        # Get counts of VMs and Arc servers
        vm_query = """
        Resources
        | where type == 'microsoft.compute/virtualmachines'
        | extend powerState = tostring(properties.extended.instanceView.powerState.displayStatus)
        | summarize 
            TotalVMs = count(),
            RunningVMs = countif(powerState contains 'running'),
            StoppedVMs = countif(powerState contains 'stopped')
        | extend MachineType = 'Azure VMs'
        """
        
        arc_query = """
        Resources
        | where type == 'microsoft.hybridcompute/machines'
        | extend status = properties.status
        | summarize 
            TotalServers = count(),
            ConnectedServers = countif(status == 'Connected'),
            DisconnectedServers = countif(status == 'Disconnected')
        | extend MachineType = 'Azure Arc Servers'
        """
        
        # For now, return a combined summary
        result = {
            "count": 2,
            "total_records": 2,
            "data": [
                {
                    "MachineType": "Azure VMs",
                    "TotalCount": "Query Azure Update Manager for accurate counts",
                    "FullyUpdated": "Check Update Manager",
                    "PendingCritical": "Check Update Manager",
                    "PendingSecurity": "Check Update Manager",
                    "PendingOther": "Check Update Manager",
                    "RebootRequired": "Check Update Manager",
                    "NonCompliantPercent": "Enable Update Manager for compliance tracking",
                    "OldestAssessment": "Configure Update Manager assessments"
                },
                {
                    "MachineType": "Azure Arc Servers",
                    "TotalCount": "Query Azure Update Manager for accurate counts",
                    "FullyUpdated": "Check Update Manager",
                    "PendingCritical": "Check Update Manager",
                    "PendingSecurity": "Check Update Manager",
                    "PendingOther": "Check Update Manager",
                    "RebootRequired": "Check Update Manager",
                    "NonCompliantPercent": "Enable Update Manager for compliance tracking",
                    "OldestAssessment": "Configure Update Manager assessments"
                }
            ]
        }
        return result
    
    def get_failed_updates(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get machines - use Azure Update Manager portal for failed update details
        """
        # Return guidance to use Update Manager
        result = {
            "count": 1,
            "total_records": 1,
            "data": [
                {
                    "MachineName": "Information",
                    "Type": "Azure Update Manager",
                    "ResourceGroup": "Portal",
                    "FailedUpdate": "For detailed update failure information:",
                    "FailureReason": "1. Navigate to Azure Portal > Update Manager",
                    "AttemptedDate": "2. Select your subscription",
                    "RetryCount": "3. View 'Update deployment history'",
                    "RecommendedAction": "4. Filter by 'Failed' status to see detailed failure reasons",
                    "ImpactLevel": "Update Manager provides comprehensive failure diagnostics"
                }
            ]
        }
        return result
    
    # AZURE ARC / HYBRID MANAGEMENT FUNCTIONS
    def get_arc_machines(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get all Azure Arc-enabled machines with comprehensive details
        """
        query = """
        Resources
        | where type == 'microsoft.hybridcompute/machines'
        | extend osType = tostring(properties.osType)
        | extend osVersion = tostring(properties.osVersion)
        | extend status = tostring(properties.status)
        | extend agentVersion = tostring(properties.agentVersion)
        | extend lastStatusChange = tostring(properties.lastStatusChange)
        | extend extensionCount = array_length(properties.extensions)
        | project 
            MachineName = name,
            ResourceGroup = resourceGroup,
            Subscription = subscriptionId,
            OSType = osType,
            OSVersion = osVersion,
            AgentStatus = status,
            AgentVersion = agentVersion,
            ExtensionCount = extensionCount,
            PendingUpdates = 'Check Update Manager',
            LastStatusChange = lastStatusChange,
            Location = location,
            ComplianceStatus = case(
                status == 'Connected', 'Connected',
                status == 'Disconnected', 'Disconnected - Action Required',
                status == 'Error', 'Error - Check Agent',
                'Unknown'
            )
        | order by ComplianceStatus desc, MachineName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_arc_sql_servers(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get all Azure Arc-enabled SQL Servers
        """
        query = """
        Resources
        | where type == 'microsoft.azurearcdata/sqlserverinstances'
        | extend sqlVersion = properties.version
        | extend edition = properties.edition
        | extend status = properties.status
        | extend hostType = properties.containerResourceId
        | project 
            SQLServerName = name,
            ResourceGroup = resourceGroup,
            SQLVersion = sqlVersion,
            Edition = edition,
            Location = location,
            DatabaseCount = 'Query SQL Server for database count',
            Status = status,
            PatchLevel = properties.patchLevel,
            LicenseType = properties.licenseType,
            LastInventoryUpload = properties.lastInventoryUploadTime,
            ComplianceStatus = case(
                status == 'Connected', 'Connected',
                status == 'Disconnected', 'Disconnected',
                'Unknown'
            )
        | order by SQLServerName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_arc_agents_not_reporting(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get Azure Arc machines with agent not reporting or disconnected
        """
        query = """
        Resources
        | where type == 'microsoft.hybridcompute/machines'
        | extend status = properties.status
        | extend agentVersion = properties.agentVersion
        | extend lastStatusChange = properties.lastStatusChange
        | extend osType = properties.osType
        | where status != 'Connected'
        | extend daysSinceLastReport = datetime_diff('day', now(), todatetime(lastStatusChange))
        | project 
            MachineName = name,
            ResourceGroup = resourceGroup,
            OSType = osType,
            AgentStatus = status,
            AgentVersion = agentVersion,
            LastStatusChange = lastStatusChange,
            DaysSinceLastReport = daysSinceLastReport,
            Location = location,
            IssueLevel = case(
                daysSinceLastReport > 30, 'Critical - Over 30 days',
                daysSinceLastReport > 7, 'High - Over 7 days',
                daysSinceLastReport > 1, 'Medium - Over 1 day',
                'Recent'
            ),
            RecommendedAction = case(
                status == 'Disconnected', 'Check network connectivity and Arc agent service',
                status == 'Error', 'Review agent logs and reinstall if necessary',
                status == 'Expired', 'Reconnect machine to Azure Arc',
                'Check machine status and connectivity'
            )
        | order by DaysSinceLastReport desc, MachineName asc
        """
        return self.query_resources(query, subscriptions)
    
    def _get_all_resource_actual_costs(self, subscriptions: Optional[List[str]] = None, days: int = 30) -> Dict[str, float]:
        """
        Get actual costs for ALL resources from Azure Cost Management API
        
        Args:
            subscriptions: List of subscription IDs (if None, uses default)
            days: Number of days to look back (default 30 for monthly projection)
            
        Returns:
            Dictionary mapping resource name to actual monthly cost
        """
        resource_costs = {}
        
        try:
            # If no subscriptions specified, use default
            if not subscriptions:
                subscriptions = [self.subscription_id]
            
            # Get costs from each subscription
            for sub_id in subscriptions:
                try:
                    # Get actual costs from Cost Management API (without top limit)
                    scope = f"/subscriptions/{sub_id}"
                    
                    # Call Cost Management API to get all resource costs
                    from datetime import datetime, timedelta
                    from azure.mgmt.costmanagement.models import QueryDefinition, QueryTimePeriod, TimeframeType, QueryDataset, QueryAggregation, QueryGrouping
                    
                    end_date = datetime.utcnow()
                    start_date = end_date - timedelta(days=days)
                    
                    query = QueryDefinition(
                        type="ActualCost",
                        timeframe=TimeframeType.CUSTOM,
                        time_period=QueryTimePeriod(
                            from_property=start_date,
                            to=end_date
                        ),
                        dataset=QueryDataset(
                            granularity="None",
                            aggregation={
                                "totalCost": QueryAggregation(name="PreTaxCost", function="Sum")
                            },
                            grouping=[
                                QueryGrouping(type="Dimension", name="ResourceId")
                            ]
                        )
                    )
                    
                    result = self.cost_manager.client.query.usage(scope=scope, parameters=query)
                    
                    # Parse results
                    if hasattr(result, 'rows') and result.rows:
                        # Get column indices
                        columns = result.columns
                        cost_index = next((i for i, col in enumerate(columns) if col.name == "PreTaxCost"), 0)
                        resource_id_index = next((i for i, col in enumerate(columns) if col.name == "ResourceId"), 1)
                        
                        for row in result.rows:
                            try:
                                cost = float(row[cost_index]) if row and len(row) > cost_index else 0.0
                                resource_id = str(row[resource_id_index]) if len(row) > resource_id_index else ""
                                
                                # Extract resource name from resource ID
                                resource_name = resource_id.split('/')[-1].lower() if resource_id and '/' in resource_id else ""
                                
                                if resource_name:
                                    # Project to 30 days if needed
                                    monthly_cost = (cost / days) * 30 if days != 30 else cost
                                    
                                    # Aggregate if resource appears multiple times
                                    if resource_name in resource_costs:
                                        resource_costs[resource_name] += monthly_cost
                                    else:
                                        resource_costs[resource_name] = monthly_cost
                            except Exception as e:
                                continue
                    
                except Exception as e:
                    print(f"Warning: Could not get costs for subscription {sub_id}: {str(e)}")
                    continue
        
        except Exception as e:
            print(f"Warning: Cost Management API failed: {str(e)}. Using estimates.")
        
        return resource_costs
    
    # ENHANCED COST MANAGEMENT FUNCTIONS WITH ACTUAL RESOURCE NAMES
    def get_resources_with_cost_details(self, subscriptions: Optional[List[str]] = None, resource_type: Optional[str] = None, 
                                       resource_group: Optional[str] = None, tag_name: Optional[str] = None, 
                                       tag_value: Optional[str] = None) -> Dict[str, Any]:
        """
        Get ALL resources with detailed information for cost analysis WITH ACTUAL COSTS from Cost Management API
        Includes filters for business units (RG, subscription, resource type, tags)
        
        Args:
            subscriptions: List of subscription IDs
            resource_type: Filter by resource type (e.g., microsoft.compute/virtualmachines)
            resource_group: Filter by resource group
            tag_name: Filter by tag name (e.g., CostCenter, Environment)
            tag_value: Filter by tag value (e.g., IT, Production)
        """
        # Step 1: Get actual costs from Cost Management API
        print("Fetching actual costs from Azure Cost Management API...")
        actual_costs = self._get_all_resource_actual_costs(subscriptions, days=30)
        print(f"Retrieved actual costs for {len(actual_costs)} resources")
        
        # Step 2: Build query filters
        filters = []
        
        if resource_type:
            filters.append(f"| where type =~ '{resource_type}'")
        
        if resource_group:
            filters.append(f"| where resourceGroup =~ '{resource_group}'")
        
        if tag_name:
            if tag_value:
                # Use case-insensitive matching with proper tag syntax
                # Try both direct property access and bracket notation
                filters.append(f"| where tags['{tag_name}'] =~ '{tag_value}'")
                print(f"DEBUG: Filtering by tag '{tag_name}' = '{tag_value}'")
            else:
                # Check if tag exists (any value)
                filters.append(f"| where isnotempty(tags['{tag_name}'])")
                print(f"DEBUG: Filtering by tag '{tag_name}' (any value)")
        
        filter_clause = "\n".join(filters)
        
        # Step 3: Query resources to get metadata
        query = f"""
        Resources
        {filter_clause}
        | extend vmSize = tostring(properties.hardwareProfile.vmSize)
        | extend storageSku = tostring(sku.name)
        | extend diskSku = tostring(sku.name)
        | extend diskSizeGB = toint(properties.diskSizeGB)
        | extend powerState = tostring(properties.extended.instanceView.powerState.displayStatus)
        | extend resourceNameLower = tolower(name)
        | project 
            ResourceName = name,
            ResourceNameLower = resourceNameLower,
            ResourceType = type,
            ResourceGroup = resourceGroup,
            Location = location,
            SKU = case(type =~ 'microsoft.compute/virtualmachines', vmSize, type =~ 'microsoft.storage/storageaccounts', storageSku, type =~ 'microsoft.compute/disks', diskSku, 'N/A'),
            Size = case(type =~ 'microsoft.compute/disks', tostring(diskSizeGB), type =~ 'microsoft.compute/virtualmachines', vmSize, 'N/A'),
            PowerState = powerState,
            Tags = tags,
            SubscriptionId = subscriptionId,
            Status = tostring(properties.provisioningState),
            DiskState = tostring(properties.diskState),
            IpConfiguration = properties.ipConfiguration
        | order by ResourceType asc, ResourceName asc
        """
        
        result = self.query_resources(query, subscriptions)
        
        # Get subscription name mapping for user-friendly display
        sub_names = self._get_subscription_names()
        
        # Step 4: Merge actual costs with resource metadata
        if result and 'data' in result and isinstance(result['data'], list):
            for resource in result['data']:
                resource_name_lower = resource.get('ResourceNameLower', resource.get('ResourceName', '')).lower()
                
                # Add subscription name for user-friendly display
                sub_id = resource.get('SubscriptionId', '')
                resource['SubscriptionName'] = sub_names.get(sub_id, sub_id[:8] + '...' if sub_id else 'Unknown')
                
                # Add the searched tag value as a dynamic column (if tag filtering was used)
                if tag_name:
                    tags_dict = resource.get('Tags', {})
                    tag_value_found = tags_dict.get(tag_name, 'N/A') if isinstance(tags_dict, dict) else 'N/A'
                    # Add as first column after ResourceName for visibility
                    resource[tag_name] = tag_value_found
                
                # Look up actual cost
                actual_cost_value = 0.0
                if resource_name_lower in actual_costs:
                    actual_cost_value = actual_costs[resource_name_lower]
                    resource['Actual Monthly Cost'] = f"${actual_cost_value:.2f}"  # User-friendly column name with spaces
                    resource['Cost Source'] = "Actual (from Cost Management API)"
                else:
                    # No actual cost data found
                    resource['Actual Monthly Cost'] = "$0.00 (No usage in last 30 days)"
                    resource['Cost Source'] = "No cost data available"
                
                # Store numeric cost for sorting (will be removed before returning)
                resource['_cost_sort_value'] = actual_cost_value
                
                # Add cost optimization opportunities
                resource_type = resource.get('ResourceType', '').lower()
                power_state = resource.get('PowerState', '')
                disk_state = resource.get('DiskState', '')
                ip_config = resource.get('IpConfiguration')
                
                if 'virtualmachines' in resource_type and 'stopped' in power_state.lower():
                    resource['Cost Optimization Opportunity'] = 'VM stopped - consider deallocation or deletion'
                elif 'virtualmachines' in resource_type and 'deallocated' in power_state.lower():
                    resource['Cost Optimization Opportunity'] = 'Deallocated VM still incurs disk costs'
                elif 'disks' in resource_type and disk_state == 'Unattached':
                    resource['Cost Optimization Opportunity'] = 'Orphaned disk - safe to delete'
                elif 'publicipaddresses' in resource_type and not ip_config:
                    resource['Cost Optimization Opportunity'] = 'Unattached public IP - wasting money'
                elif 'storageaccounts' in resource_type and 'Premium' in resource.get('SKU', ''):
                    resource['Cost Optimization Opportunity'] = 'Consider Cool tier for infrequent access'
                else:
                    resource['Cost Optimization Opportunity'] = 'Review utilization in Azure Monitor'
                
                # Remove internal fields
                resource.pop('ResourceNameLower', None)
                resource.pop('DiskState', None)
                resource.pop('IpConfiguration', None)
            
            # Sort by cost (highest first)
            result['data'].sort(key=lambda x: x.get('_cost_sort_value', 0), reverse=True)
            
            # Remove the sorting field
            for resource in result['data']:
                resource.pop('_cost_sort_value', None)
        
        return result
    
    def get_cost_savings_opportunities(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Identify actual cost savings opportunities with REAL resource names and ACTUAL costs
        """
        # Step 1: Get actual costs
        print("Fetching actual costs from Azure Cost Management API for savings analysis...")
        actual_costs = self._get_all_resource_actual_costs(subscriptions, days=30)
        
        # Step 2: Query resources with savings opportunities
        query = """
        Resources
        | where 
            (type =~ 'microsoft.compute/virtualmachines' and tostring(properties.extended.instanceView.powerState.code) =~ 'PowerState/deallocated')
            or (type =~ 'microsoft.compute/disks' and tostring(properties.diskState) == 'Unattached')
            or (type =~ 'microsoft.network/publicipaddresses' and isnull(properties.ipConfiguration))
            or (type =~ 'microsoft.storage/storageaccounts' and tostring(sku.name) contains 'Premium')
            or (type =~ 'microsoft.compute/virtualmachines' and tostring(properties.hardwareProfile.vmSize) contains 'Standard_D')
        | extend resourceSku = case(
            type =~ 'microsoft.compute/virtualmachines', tostring(properties.hardwareProfile.vmSize),
            type =~ 'microsoft.storage/storageaccounts', tostring(sku.name),
            type =~ 'microsoft.compute/disks', tostring(sku.name),
            'Standard'
        )
        | extend diskSize = toint(properties.diskSizeGB)
        | extend powerStateCode = tostring(properties.extended.instanceView.powerState.code)
        | extend diskState = tostring(properties.diskState)
        | extend ipConfig = properties.ipConfiguration
        | extend utilizationPercent = case(
            type =~ 'microsoft.compute/virtualmachines' and powerStateCode =~ 'PowerState/deallocated', 0,
            type =~ 'microsoft.compute/disks' and diskState == 'Unattached', 0,
            type =~ 'microsoft.network/publicipaddresses' and isnull(ipConfig), 0,
            type =~ 'microsoft.compute/virtualmachines', 40,
            type =~ 'microsoft.storage/storageaccounts', 60,
            50
        )
        | extend recommendedAction = case(
            type =~ 'microsoft.compute/virtualmachines' and powerStateCode =~ 'PowerState/deallocated', 'Delete deallocated VM or start if needed',
            type =~ 'microsoft.compute/disks' and diskState == 'Unattached', 'Delete orphaned disk',
            type =~ 'microsoft.network/publicipaddresses' and isnull(ipConfig), 'Delete unattached public IP',
            type =~ 'microsoft.storage/storageaccounts' and resourceSku contains 'Premium', 'Move to Standard or Cool tier',
            type =~ 'microsoft.compute/virtualmachines' and resourceSku contains 'Standard_D8', 'Rightsize to Standard_D4s_v3 (50% savings)',
            type =~ 'microsoft.compute/virtualmachines' and resourceSku contains 'Standard_D4', 'Rightsize to Standard_D2s_v3 (50% savings)',
            'Review Azure Advisor for recommendations'
        )
        | extend implementationEffort = case(
            type =~ 'microsoft.compute/disks' or type =~ 'microsoft.network/publicipaddresses', 'Low (1 click delete)',
            type =~ 'microsoft.storage/storageaccounts', 'Low (change tier)',
            type =~ 'microsoft.compute/virtualmachines' and powerStateCode =~ 'PowerState/deallocated', 'Low (delete if not needed)',
            'Medium (VM resize + testing)'
        )
        | project 
            ResourceName = name,
            ResourceNameLower = tolower(name),
            Type = type,
            ResourceGroup = resourceGroup,
            Location = location,
            SubscriptionId = subscriptionId,
            SKU = resourceSku,
            UtilizationPercent = utilizationPercent,
            RecommendedAction = recommendedAction,
            ImplementationEffort = implementationEffort,
            Tags = tags
        | order by ResourceName asc
        """
        
        result = self.query_resources(query, subscriptions)
        
        # Get subscription name mapping
        sub_names = self._get_subscription_names()
        
        # Step 3: Merge actual costs and calculate savings
        if result and 'data' in result and isinstance(result['data'], list):
            for resource in result['data']:
                resource_name_lower = resource.get('ResourceNameLower', resource.get('ResourceName', '')).lower()
                
                # Add subscription name
                sub_id = resource.get('SubscriptionId', '')
                resource['SubscriptionName'] = sub_names.get(sub_id, sub_id[:8] + '...' if sub_id else 'Unknown')
                
                # Look up actual cost
                current_cost = 0.0
                if resource_name_lower in actual_costs:
                    current_cost = actual_costs[resource_name_lower]
                    resource['Current Monthly Cost'] = f"${current_cost:.2f}"
                else:
                    resource['Current Monthly Cost'] = "$0.00 (No usage data)"
                
                # Calculate potential savings based on utilization and action
                utilization = resource.get('UtilizationPercent', 50)
                action = resource.get('RecommendedAction', '')
                
                if utilization == 0:
                    # 100% savings for unused resources
                    potential_savings = current_cost
                elif 'Rightsize' in action and 'D8' in resource.get('SKU', ''):
                    # 50% savings for D8 -> D4
                    potential_savings = current_cost * 0.5
                elif 'Rightsize' in action and 'D4' in resource.get('SKU', ''):
                    # 50% savings for D4 -> D2
                    potential_savings = current_cost * 0.5
                elif 'Premium' in action:
                    # 30-60% savings for storage tier change
                    potential_savings = current_cost * 0.4
                else:
                    # 30% average savings
                    potential_savings = current_cost * 0.3
                
                resource['Potential Monthly Savings'] = f"${potential_savings:.2f}"
                resource['Annual Savings'] = f"${(potential_savings * 12):.2f}"
                
                # Remove internal fields
                resource.pop('ResourceNameLower', None)
                resource.pop('UtilizationPercent', None)
                resource.pop('SKU', None)
        
        return result

    # ============================================================
    # NEW SERVICE-SPECIFIC QUERIES
    # ============================================================
    
    # APP SERVICES
    def get_app_services_detailed(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all App Services with detailed configuration"""
        query = """
        Resources
        | where type =~ 'microsoft.web/sites'
        | extend appServicePlanId = tostring(properties.serverFarmId)
        | extend httpsOnly = tobool(properties.httpsOnly)
        | extend ftpsState = tostring(properties.siteConfig.ftpsState)
        | extend minTlsVersion = tostring(properties.siteConfig.minTlsVersion)
        | project 
            AppName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            Type = kind,
            Status = tostring(properties.state),
            DefaultHostname = tostring(properties.defaultHostName),
            HTTPSOnly = httpsOnly,
            TLSVersion = minTlsVersion,
            FTPSState = ftpsState,
            AppServicePlan = tostring(split(appServicePlanId, '/')[-1]),
            Tags = tags
        | order by AppName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_app_services_without_appinsights(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get App Services not connected to Application Insights"""
        query = """
        Resources
        | where type =~ 'microsoft.web/sites'
        | extend appInsightsKey = properties.siteConfig.appSettings
        | project 
            AppName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            Status = tostring(properties.state),
            AppInsightsStatus = case(
                isnotnull(properties.siteConfig.appSettings) and tostring(properties.siteConfig.appSettings) contains 'APPINSIGHTS_INSTRUMENTATIONKEY', 'Configured',
                'Not Configured'
            ),
            Recommendation = 'Enable Application Insights for monitoring and diagnostics'
        | where AppInsightsStatus == 'Not Configured'
        | order by AppName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_app_services_public_access(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get App Services with public access enabled"""
        query = """
        Resources
        | where type =~ 'microsoft.web/sites'
        | extend publicNetworkAccess = properties.publicNetworkAccess
        | extend ipSecurityRestrictions = array_length(properties.siteConfig.ipSecurityRestrictions)
        | project 
            AppName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            Status = tostring(properties.state),
            PublicAccess = case(
                publicNetworkAccess =~ 'Disabled', 'Disabled',
                'Enabled'
            ),
            IPRestrictions = case(
                ipSecurityRestrictions > 0, strcat(tostring(ipSecurityRestrictions), ' rules'),
                'None'
            ),
            RiskLevel = case(
                publicNetworkAccess =~ 'Disabled', 'Low',
                ipSecurityRestrictions > 0, 'Medium',
                'High'
            ),
            Recommendation = case(
                publicNetworkAccess =~ 'Disabled', 'Good - Public access disabled',
                ipSecurityRestrictions > 0, 'Review IP restrictions',
                'Consider enabling IP restrictions or private endpoints'
            )
        | where PublicAccess == 'Enabled'
        | order by RiskLevel desc, AppName asc
        """
        return self.query_resources(query, subscriptions)
    
    # AKS CLUSTERS
    def get_aks_clusters(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all AKS clusters with detailed information"""
        query = """
        Resources
        | where type =~ 'microsoft.containerservice/managedclusters'
        | extend k8sVersion = tostring(properties.kubernetesVersion)
        | extend networkPlugin = tostring(properties.networkProfile.networkPlugin)
        | extend enableRBAC = tobool(properties.enableRBAC)
        | extend agentPools = properties.agentPoolProfiles
        | extend nodePoolCount = array_length(agentPools)
        | project 
            ClusterName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            KubernetesVersion = k8sVersion,
            NetworkPlugin = networkPlugin,
            NodePools = nodePoolCount,
            RBACEnabled = enableRBAC,
            Status = tostring(properties.provisioningState),
            Tags = tags
        | order by ClusterName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_aks_public_access(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get AKS clusters with public API server access"""
        query = """
        Resources
        | where type =~ 'microsoft.containerservice/managedclusters'
        | extend privateCluster = tobool(properties.apiServerAccessProfile.enablePrivateCluster)
        | extend hasIpRanges = isnotempty(properties.apiServerAccessProfile.authorizedIPRanges)
        | where privateCluster != true
        | project 
            ClusterName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            IsPrivateCluster = privateCluster,
            AuthorizedIPRanges = iff(hasIpRanges, 'Configured', 'None'),
            RiskLevel = case(
                hasIpRanges == true, 'Medium - IP restricted',
                'High - Public access'
            ),
            Recommendation = case(
                hasIpRanges == true, 'Consider private cluster for better security',
                'Enable private cluster or configure authorized IP ranges'
            )
        | order by ClusterName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_aks_private_access(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get AKS clusters with private API server access"""
        query = """
        Resources
        | where type =~ 'microsoft.containerservice/managedclusters'
        | extend privateCluster = tobool(properties.apiServerAccessProfile.enablePrivateCluster)
        | extend privateDnsZone = tostring(properties.apiServerAccessProfile.privateDNSZone)
        | where privateCluster == true
        | project 
            ClusterName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            PrivateClusterEnabled = 'Yes',
            PrivateDNSZone = case(
                isnotempty(privateDnsZone), privateDnsZone,
                'System-managed'
            ),
            SecurityPosture = 'Good - Private cluster'
        | order by ClusterName asc
        """
        return self.query_resources(query, subscriptions)
    
    # SQL DATABASES AND MANAGED INSTANCES
    def get_sql_databases_detailed(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Azure SQL Databases with detailed information"""
        query = """
        Resources
        | where type =~ 'microsoft.sql/servers/databases'
        | where name != 'master'
        | extend serverName = tostring(split(id, '/')[8])
        | project 
            DatabaseName = name,
            ServerName = serverName,
            ResourceGroup = resourceGroup,
            Location = location,
            SKU = tostring(sku.name),
            Tier = tostring(sku.tier),
            Capacity = tostring(sku.capacity),
            MaxSizeGB = tostring(toint(properties.maxSizeBytes) / 1073741824),
            Status = tostring(properties.status),
            Tags = tags
        | order by ServerName asc, DatabaseName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_sql_managed_instances(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Azure SQL Managed Instances"""
        query = """
        Resources
        | where type =~ 'microsoft.sql/managedinstances'
        | project 
            InstanceName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            SKU = tostring(sku.name),
            Tier = tostring(sku.tier),
            vCores = tostring(properties.vCores),
            StorageSizeGB = tostring(properties.storageSizeInGB),
            Status = tostring(properties.state),
            SubnetId = tostring(properties.subnetId),
            Tags = tags
        | order by InstanceName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_sql_public_access(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get SQL Servers with public network access enabled"""
        query = """
        Resources
        | where type =~ 'microsoft.sql/servers'
        | extend publicNetworkAccess = tostring(properties.publicNetworkAccess)
        | extend hasPrivateEndpoint = isnotnull(properties.privateEndpointConnections) and array_length(properties.privateEndpointConnections) > 0
        | project 
            ServerName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            PublicNetworkAccess = case(
                publicNetworkAccess =~ 'Enabled', 'Enabled',
                publicNetworkAccess =~ 'Disabled', 'Disabled',
                'Default (Enabled)'
            ),
            PrivateEndpoint = case(hasPrivateEndpoint, 'Yes', 'No'),
            RiskLevel = case(
                publicNetworkAccess =~ 'Disabled', 'Low',
                hasPrivateEndpoint, 'Medium',
                'High'
            ),
            Recommendation = case(
                publicNetworkAccess =~ 'Disabled', 'Good - Public access disabled',
                hasPrivateEndpoint, 'Consider disabling public access',
                'Configure private endpoints and disable public access'
            )
        | where PublicNetworkAccess != 'Disabled'
        | order by RiskLevel desc, ServerName asc
        """
        return self.query_resources(query, subscriptions)
    
    # VIRTUAL MACHINE SCALE SETS
    def get_vmss(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Virtual Machine Scale Sets"""
        query = """
        Resources
        | where type =~ 'microsoft.compute/virtualmachinescalesets'
        | extend instanceCount = toint(sku.capacity)
        | extend vmSize = tostring(sku.name)
        | extend osType = tostring(properties.virtualMachineProfile.storageProfile.osDisk.osType)
        | extend upgradePolicy = tostring(properties.upgradePolicy.mode)
        | project 
            VMSSName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            VMSize = vmSize,
            InstanceCount = instanceCount,
            OSType = osType,
            UpgradePolicy = upgradePolicy,
            Status = tostring(properties.provisioningState),
            Tags = tags
        | order by VMSSName asc
        """
        return self.query_resources(query, subscriptions)
    
    # POSTGRESQL SERVERS
    def get_postgresql_servers(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Azure Database for PostgreSQL Flexible servers"""
        query = """
        Resources
        | where type =~ 'microsoft.dbforpostgresql/flexibleservers'
        | project 
            ServerName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            Version = tostring(properties.version),
            SKU = tostring(sku.name),
            Tier = tostring(sku.tier),
            StorageGB = tostring(properties.storage.storageSizeGB),
            Status = tostring(properties.state),
            HAMode = tostring(properties.highAvailability.mode),
            Tags = tags
        | order by ServerName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_postgresql_public_access(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get PostgreSQL servers with public network access"""
        query = """
        Resources
        | where type =~ 'microsoft.dbforpostgresql/flexibleservers'
        | extend publicAccess = tostring(properties.network.publicNetworkAccess)
        | project 
            ServerName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            PublicAccess = case(
                publicAccess =~ 'Disabled', 'Disabled',
                'Enabled'
            ),
            SSLMode = tostring(properties.dataEncryption.type),
            RiskLevel = case(
                publicAccess =~ 'Disabled', 'Low',
                'High'
            ),
            Recommendation = case(
                publicAccess =~ 'Disabled', 'Good - Public access disabled',
                'Disable public access and use private endpoints'
            )
        | where PublicAccess == 'Enabled'
        | order by ServerName asc
        """
        return self.query_resources(query, subscriptions)
    
    # MYSQL SERVERS
    def get_mysql_servers(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Azure Database for MySQL Flexible servers"""
        query = """
        Resources
        | where type =~ 'microsoft.dbformysql/flexibleservers'
        | project 
            ServerName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            Version = tostring(properties.version),
            SKU = tostring(sku.name),
            Tier = tostring(sku.tier),
            StorageGB = tostring(properties.storage.storageSizeGB),
            Status = tostring(properties.state),
            Tags = tags
        | order by ServerName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_mysql_public_access(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get MySQL servers with public network access"""
        query = """
        Resources
        | where type =~ 'microsoft.dbformysql/flexibleservers'
        | extend publicAccess = tostring(properties.network.publicNetworkAccess)
        | project 
            ServerName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            PublicAccess = case(
                publicAccess =~ 'Disabled', 'Disabled',
                'Enabled'
            ),
            RiskLevel = case(
                publicAccess =~ 'Disabled', 'Low',
                'High'
            ),
            Recommendation = case(
                publicAccess =~ 'Disabled', 'Good - Public access disabled',
                'Disable public access and use private endpoints'
            )
        | where PublicAccess == 'Enabled'
        | order by ServerName asc
        """
        return self.query_resources(query, subscriptions)
    
    # COSMOS DB
    def get_cosmosdb_accounts(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Cosmos DB accounts"""
        query = """
        Resources
        | where type =~ 'microsoft.documentdb/databaseaccounts'
        | extend apiType = case(
            kind =~ 'MongoDB', 'MongoDB',
            tostring(properties.capabilities) contains 'EnableCassandra', 'Cassandra',
            tostring(properties.capabilities) contains 'EnableGremlin', 'Gremlin',
            tostring(properties.capabilities) contains 'EnableTable', 'Table',
            'SQL'
        )
        | project 
            AccountName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            APIType = apiType,
            ConsistencyLevel = tostring(properties.consistencyPolicy.defaultConsistencyLevel),
            WriteLocations = array_length(properties.writeLocations),
            ReadLocations = array_length(properties.readLocations),
            Status = tostring(properties.provisioningState),
            Tags = tags
        | order by AccountName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_cosmosdb_public_access(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Cosmos DB accounts with public network access"""
        query = """
        Resources
        | where type =~ 'microsoft.documentdb/databaseaccounts'
        | extend publicNetworkAccess = tostring(properties.publicNetworkAccess)
        | extend hasPrivateEndpoint = isnotnull(properties.privateEndpointConnections) and array_length(properties.privateEndpointConnections) > 0
        | project 
            AccountName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            PublicNetworkAccess = case(
                publicNetworkAccess =~ 'Disabled', 'Disabled',
                'Enabled'
            ),
            PrivateEndpoint = case(hasPrivateEndpoint, 'Yes', 'No'),
            RiskLevel = case(
                publicNetworkAccess =~ 'Disabled', 'Low',
                hasPrivateEndpoint, 'Medium',
                'High'
            ),
            Recommendation = case(
                publicNetworkAccess =~ 'Disabled', 'Good - Public access disabled',
                hasPrivateEndpoint, 'Consider disabling public access',
                'Configure private endpoints and disable public access'
            )
        | where PublicNetworkAccess == 'Enabled'
        | order by RiskLevel desc, AccountName asc
        """
        return self.query_resources(query, subscriptions)
    
    # API MANAGEMENT
    def get_apim_instances(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all API Management instances"""
        query = """
        Resources
        | where type =~ 'microsoft.apimanagement/service'
        | project 
            APIMName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            SKU = tostring(sku.name),
            Capacity = tostring(sku.capacity),
            GatewayUrl = tostring(properties.gatewayUrl),
            Status = tostring(properties.provisioningState),
            VNetMode = tostring(properties.virtualNetworkType),
            Tags = tags
        | order by APIMName asc
        """
        return self.query_resources(query, subscriptions)
    
    # TAG INVENTORY
    def get_tag_inventory(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get high-level tag inventory across environment"""
        query = """
        Resources
        | where isnotempty(tags)
        | project name, type, resourceGroup, tags
        | mv-expand tags
        | extend tagKey = tostring(bag_keys(tags)[0])
        | extend tagValue = tostring(tags[tagKey])
        | summarize 
            ResourceCount = count(),
            UniqueValues = dcount(tagValue)
        by tagKey
        | project 
            TagName = tagKey,
            TotalResources = ResourceCount,
            UniqueValueCount = UniqueValues
        | order by TotalResources desc
        | take 50
        """
        return self.query_resources(query, subscriptions)
    
    # MONITORING GAPS - VMs without Azure Monitor
    def get_vms_without_azure_monitor(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get VMs without Azure Monitor Agent extension"""
        query = """
        Resources
        | where type =~ 'microsoft.compute/virtualmachines'
        | extend osType = properties.storageProfile.osDisk.osType
        | extend powerState = tostring(properties.extended.instanceView.powerState.displayStatus)
        | join kind=leftouter (
            Resources
            | where type =~ 'microsoft.compute/virtualmachines/extensions'
            | where name contains 'AzureMonitorAgent' or name contains 'MicrosoftMonitoringAgent' or name contains 'OmsAgentForLinux'
            | extend vmName = tostring(split(id, '/')[8])
            | project vmName, hasMonitoring = true
        ) on $left.name == $right.vmName
        | where isnull(hasMonitoring)
        | project 
            VMName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            OSType = osType,
            PowerState = powerState,
            AgentStatus = 'Not Installed',
            Recommendation = 'Install Azure Monitor Agent for monitoring and log collection'
        | order by VMName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_arc_machines_without_azure_monitor(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Arc machines without Azure Monitor Agent"""
        query = """
        Resources
        | where type =~ 'microsoft.hybridcompute/machines'
        | extend osType = properties.osType
        | extend status = properties.status
        | join kind=leftouter (
            Resources
            | where type =~ 'microsoft.hybridcompute/machines/extensions'
            | where name contains 'AzureMonitorAgent' or name contains 'MicrosoftMonitoringAgent' or name contains 'OmsAgentForLinux'
            | extend machineName = tostring(split(id, '/')[8])
            | project machineName, hasMonitoring = true
        ) on $left.name == $right.machineName
        | where isnull(hasMonitoring)
        | project 
            MachineName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            OSType = osType,
            Status = status,
            AgentStatus = 'Not Installed',
            Recommendation = 'Install Azure Monitor Agent for monitoring'
        | order by MachineName asc
        """
        return self.query_resources(query, subscriptions)
    
    # AKS without monitoring
    def get_aks_without_monitoring(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get AKS clusters without Container Insights enabled"""
        query = """
        Resources
        | where type =~ 'microsoft.containerservice/managedclusters'
        | extend addonProfiles = properties.addonProfiles
        | extend omsAgentEnabled = tobool(addonProfiles.omsagent.enabled)
        | where omsAgentEnabled != true
        | project 
            ClusterName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            KubernetesVersion = tostring(properties.kubernetesVersion),
            MonitoringStatus = 'Not Enabled',
            LogAnalyticsWorkspace = 'Not Configured',
            Recommendation = 'Enable Container Insights for cluster monitoring'
        | order by ClusterName asc
        """
        return self.query_resources(query, subscriptions)

    # ============================================
    # STORAGE ACCOUNTS - COMPREHENSIVE FUNCTIONS
    # ============================================
    
    def get_storage_accounts_detailed(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get comprehensive storage account summary"""
        query = """
        Resources
        | where type =~ 'microsoft.storage/storageaccounts'
        | extend accessTier = tostring(properties.accessTier)
        | extend kindVal = tostring(kind)
        | extend skuName = tostring(sku.name)
        | extend skuTier = tostring(sku.tier)
        | extend replication = case(
            skuName contains 'LRS', 'Locally Redundant',
            skuName contains 'ZRS', 'Zone Redundant',
            skuName contains 'GRS', 'Geo Redundant',
            skuName contains 'GZRS', 'Geo-Zone Redundant',
            skuName contains 'RAGRS', 'Read-Access Geo Redundant',
            skuName contains 'RAGZRS', 'Read-Access Geo-Zone Redundant',
            'Unknown')
        | extend createdTime = tostring(properties.creationTime)
        | extend status = tostring(properties.provisioningState)
        | project 
            StorageAccountName = name,
            ResourceGroup = resourceGroup,
            Subscription = subscriptionId,
            Location = location,
            SKU = skuName,
            Tier = skuTier,
            Kind = kindVal,
            Status = status,
            AccessTier = accessTier,
            Replication = replication,
            CreatedDate = createdTime,
            Tags = tags
        | order by StorageAccountName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_storage_accounts_public_access(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get storage accounts with public access enabled"""
        query = """
        Resources
        | where type =~ 'microsoft.storage/storageaccounts'
        | extend allowBlobPublicAccess = tobool(properties.allowBlobPublicAccess)
        | extend networkDefaultAction = tostring(properties.networkAcls.defaultAction)
        | extend publicNetworkAccess = tostring(properties.publicNetworkAccess)
        | where allowBlobPublicAccess == true or networkDefaultAction == 'Allow' or publicNetworkAccess == 'Enabled'
        | extend riskLevel = case(
            allowBlobPublicAccess == true and networkDefaultAction == 'Allow', 'Critical',
            allowBlobPublicAccess == true, 'High',
            networkDefaultAction == 'Allow', 'Medium',
            'Low')
        | project 
            AccountName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            BlobPublicAccess = allowBlobPublicAccess,
            NetworkDefaultAction = networkDefaultAction,
            PublicNetworkAccess = publicNetworkAccess,
            RiskLevel = riskLevel,
            Recommendation = case(
                allowBlobPublicAccess == true, 'Disable anonymous blob access immediately',
                networkDefaultAction == 'Allow', 'Configure network rules to restrict access',
                'Review and enhance security settings')
        | order by RiskLevel asc, AccountName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_storage_accounts_with_private_endpoints_detailed(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get storage accounts with private endpoints - detailed view"""
        query = """
        Resources
        | where type =~ 'microsoft.network/privateendpoints'
        | mv-expand connection = properties.privateLinkServiceConnections
        | extend targetResourceId = tostring(connection.properties.privateLinkServiceId)
        | where targetResourceId contains 'storageAccounts'
        | extend storageAccountName = tostring(split(targetResourceId, '/')[8])
        | extend connectionStatus = tostring(connection.properties.privateLinkServiceConnectionState.status)
        | extend groupIds = tostring(connection.properties.groupIds)
        | extend subnet = tostring(properties.subnet.id)
        | extend vnet = tostring(split(subnet, '/subnets/')[0])
        | extend vnetName = tostring(split(vnet, '/')[8])
        | extend subnetName = tostring(split(subnet, '/')[10])
        | project 
            AccountName = storageAccountName,
            ResourceGroup = resourceGroup,
            PrivateEndpointName = name,
            Location = location,
            VNet = vnetName,
            Subnet = subnetName,
            ConnectionStatus = connectionStatus,
            ServiceGroup = groupIds
        | order by AccountName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_storage_accounts_empty(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get storage accounts that appear to be empty (no containers or very old)"""
        query = """
        Resources
        | where type =~ 'microsoft.storage/storageaccounts'
        | extend kindVal = tostring(kind)
        | extend createdTime = tostring(properties.creationTime)
        | extend accessTier = tostring(properties.accessTier)
        | extend skuName = tostring(sku.name)
        | project 
            AccountName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            Kind = kindVal,
            SKU = skuName,
            AccessTier = accessTier,
            CreatedDate = createdTime,
            Note = 'Check Azure Monitor metrics for actual usage data',
            Recommendation = 'Review if storage account is needed or can be deleted'
        | order by AccountName asc
        """
        # Note: Actual emptiness requires metrics API - this returns all for review
        return self.query_resources(query, subscriptions)
    
    def get_storage_accounts_unused(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get storage accounts potentially unused - requires metrics validation"""
        query = """
        Resources
        | where type =~ 'microsoft.storage/storageaccounts'
        | extend kindVal = tostring(kind)
        | extend createdTime = tostring(properties.creationTime)
        | extend lastModified = tostring(properties.lastModifiedTime)
        | extend accessTier = tostring(properties.accessTier)
        | extend skuName = tostring(sku.name)
        | project 
            AccountName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            Kind = kindVal,
            SKU = skuName,
            AccessTier = accessTier,
            CreatedDate = createdTime,
            LastModified = lastModified,
            UsagePattern = 'Review Azure Monitor transaction metrics',
            Recommendation = 'Check last 90 days transaction count in Azure Monitor'
        | order by AccountName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_storage_accounts_capacity(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get storage accounts ordered by potential capacity"""
        query = """
        Resources
        | where type =~ 'microsoft.storage/storageaccounts'
        | extend kindVal = tostring(kind)
        | extend accessTier = tostring(properties.accessTier)
        | extend skuName = tostring(sku.name)
        | extend skuTier = tostring(sku.tier)
        | extend isPremium = skuName contains 'Premium'
        | project 
            AccountName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            Kind = kindVal,
            SKU = skuName,
            Tier = skuTier,
            AccessTier = accessTier,
            IsPremium = isPremium,
            CapacityNote = 'Use Azure Monitor Metrics for actual capacity (UsedCapacity metric)',
            CostNote = 'Premium storage has higher cost - verify usage justifies tier'
        | order by IsPremium desc, AccountName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_file_shares(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Azure File Shares inventory"""
        query = """
        Resources
        | where type =~ 'microsoft.storage/storageaccounts/fileservices/shares'
        | extend storageAccount = tostring(split(id, '/')[8])
        | extend shareQuota = toint(properties.shareQuota)
        | extend accessTier = tostring(properties.accessTier)
        | extend enabledProtocols = tostring(properties.enabledProtocols)
        | project 
            FileShareName = name,
            StorageAccount = storageAccount,
            ResourceGroup = resourceGroup,
            QuotaGB = shareQuota,
            AccessTier = accessTier,
            Protocol = case(
                enabledProtocols == 'SMB', 'SMB',
                enabledProtocols == 'NFS', 'NFS',
                'SMB'),
            Note = 'Use Azure Monitor for used capacity metrics'
        | order by StorageAccount asc, FileShareName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_file_shares_with_ad_auth(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get storage accounts with Azure Files AD authentication configured"""
        query = """
        Resources
        | where type =~ 'microsoft.storage/storageaccounts'
        | extend azureFilesIdentityBasedAuth = properties.azureFilesIdentityBasedAuthentication
        | extend directoryServiceOptions = tostring(azureFilesIdentityBasedAuth.directoryServiceOptions)
        | extend activeDirectoryProperties = azureFilesIdentityBasedAuth.activeDirectoryProperties
        | extend domainName = tostring(activeDirectoryProperties.domainName)
        | where directoryServiceOptions != '' and directoryServiceOptions != 'None'
        | project 
            AccountName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            ADJoinStatus = 'Configured',
            DirectoryService = directoryServiceOptions,
            DomainName = domainName,
            AuthType = case(
                directoryServiceOptions == 'AD', 'On-premises AD DS',
                directoryServiceOptions == 'AADDS', 'Azure AD DS',
                directoryServiceOptions == 'AADKERB', 'Azure AD Kerberos',
                'Other'),
            RBACEnabled = 'Check IAM assignments'
        | order by AccountName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_storage_accounts_with_lifecycle_policy(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get storage accounts with lifecycle management policies"""
        query = """
        Resources
        | where type =~ 'microsoft.storage/storageaccounts/managementpolicies'
        | extend storageAccount = tostring(split(id, '/')[8])
        | extend policy = properties.policy
        | extend rules = policy.rules
        | extend ruleCount = array_length(rules)
        | mv-expand rule = rules
        | extend ruleName = tostring(rule.name)
        | extend ruleEnabled = tobool(rule.enabled)
        | extend tierToCool = rule.definition.actions.baseBlob.tierToCool
        | extend tierToArchive = rule.definition.actions.baseBlob.tierToArchive
        | extend deleteBlob = rule.definition.actions.baseBlob.delete
        | summarize 
            RuleCount = count(),
            EnabledRules = countif(ruleEnabled == true),
            Rules = make_list(ruleName)
        by storageAccount, resourceGroup
        | project 
            AccountName = storageAccount,
            ResourceGroup = resourceGroup,
            PolicyRuleCount = RuleCount,
            EnabledRules = EnabledRules,
            RuleNames = Rules,
            Benefit = 'Automated data lifecycle management reduces storage costs'
        | order by AccountName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_storage_cost_optimization(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get storage accounts with cost optimization recommendations"""
        query = """
        Resources
        | where type =~ 'microsoft.storage/storageaccounts'
        | extend kindVal = tostring(kind)
        | extend skuName = tostring(sku.name)
        | extend skuTier = tostring(sku.tier)
        | extend accessTier = tostring(properties.accessTier)
        | extend isPremium = skuName contains 'Premium'
        | extend isHot = accessTier == 'Hot' or accessTier == ''
        | extend hasLifecyclePolicy = false  // Would need separate query
        | extend optimizationType = case(
            isPremium, 'Tier Review',
            isHot and kind == 'StorageV2', 'Consider Cool/Archive Tier',
            kind == 'Storage', 'Upgrade to StorageV2',
            'Review Usage')
        | project 
            AccountName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            CurrentTier = skuTier,
            CurrentSKU = skuName,
            AccessTier = accessTier,
            Kind = kindVal,
            OptimizationType = optimizationType,
            Recommendation = case(
                isPremium, 'Verify Premium usage justifies cost; consider Standard for non-performance-critical data',
                isHot and kind == 'StorageV2', 'Analyze access patterns; move infrequently accessed data to Cool or Archive',
                kind == 'Storage', 'Upgrade to StorageV2 for lifecycle management and better pricing',
                'Review storage metrics for optimization opportunities'),
            EstimatedSavings = case(
                isPremium, 'Up to 60% by moving to Standard',
                isHot, 'Up to 50% for Cool, 90% for Archive tier',
                kind == 'Storage', 'Varies based on usage',
                'Analyze metrics for estimate')
        | order by OptimizationType asc, AccountName asc
        """
        return self.query_resources(query, subscriptions)

    # ============================================
    # AZURE BACKUP - COMPREHENSIVE FUNCTIONS
    # ============================================
    
    def get_vms_with_backup(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Virtual Machines enabled with Azure Backup"""
        query = """
        RecoveryServicesResources
        | where type =~ 'microsoft.recoveryservices/vaults/backupfabrics/protectioncontainers/protecteditems'
        | where properties.backupManagementType == 'AzureIaasVM'
        | extend vmId = tostring(properties.sourceResourceId)
        | extend vmName = tostring(split(vmId, '/')[8])
        | extend vaultName = tostring(split(id, '/')[8])
        | extend vaultResourceGroup = tostring(split(id, '/')[4])
        | extend protectionStatus = tostring(properties.protectionStatus)
        | extend lastBackupStatus = tostring(properties.lastBackupStatus)
        | extend lastBackupTime = tostring(properties.lastBackupTime)
        | extend policyName = tostring(split(properties.policyId, '/')[12])
        | project 
            VMName = vmName,
            VaultName = vaultName,
            VaultResourceGroup = vaultResourceGroup,
            ProtectionStatus = protectionStatus,
            LastBackupStatus = lastBackupStatus,
            LastBackupTime = lastBackupTime,
            BackupPolicy = policyName,
            SourceResourceId = vmId
        | order by VMName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_vms_without_backup(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Virtual Machines NOT enabled with Azure Backup"""
        query = """
        Resources
        | where type =~ 'microsoft.compute/virtualmachines'
        | extend vmId = tolower(id)
        | join kind=leftouter (
            RecoveryServicesResources
            | where type =~ 'microsoft.recoveryservices/vaults/backupfabrics/protectioncontainers/protecteditems'
            | where properties.backupManagementType == 'AzureIaasVM'
            | extend vmId = tolower(tostring(properties.sourceResourceId))
            | project vmId, isProtected = true
        ) on vmId
        | where isnull(isProtected)
        | extend powerState = tostring(properties.extended.instanceView.powerState.displayStatus)
        | extend vmSize = tostring(properties.hardwareProfile.vmSize)
        | extend osType = tostring(properties.storageProfile.osDisk.osType)
        | extend riskLevel = case(
                powerState contains 'running', 'High',
                'Medium')
        | project 
            VMName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            OSType = osType,
            VMSize = vmSize,
            PowerState = powerState,
            BackupStatus = 'Not Protected',
            RiskLevel = riskLevel,
            Recommendation = 'Enable Azure Backup to protect this VM'
        | order by RiskLevel desc, VMName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_file_shares_with_backup(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Azure File Shares enabled for backup"""
        query = """
        RecoveryServicesResources
        | where type =~ 'microsoft.recoveryservices/vaults/backupfabrics/protectioncontainers/protecteditems'
        | where properties.backupManagementType == 'AzureStorage'
        | extend fileShareId = tostring(properties.sourceResourceId)
        | extend fileShareName = tostring(properties.friendlyName)
        | extend vaultName = tostring(split(id, '/')[8])
        | extend protectionStatus = tostring(properties.protectionStatus)
        | extend lastBackupStatus = tostring(properties.lastBackupStatus)
        | extend lastBackupTime = tostring(properties.lastBackupTime)
        | extend policyName = tostring(split(properties.policyId, '/')[12])
        | project 
            FileShareName = fileShareName,
            VaultName = vaultName,
            ProtectionStatus = protectionStatus,
            LastBackupStatus = lastBackupStatus,
            LastBackupTime = lastBackupTime,
            BackupPolicy = policyName,
            SourceResourceId = fileShareId
        | order by FileShareName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_file_shares_without_backup(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Azure File Shares NOT enabled for backup"""
        query = """
        Resources
        | where type =~ 'microsoft.storage/storageaccounts/fileservices/shares'
        | extend shareId = tolower(id)
        | extend storageAccount = tostring(split(id, '/')[8])
        | extend shareName = name
        | join kind=leftouter (
            RecoveryServicesResources
            | where type =~ 'microsoft.recoveryservices/vaults/backupfabrics/protectioncontainers/protecteditems'
            | where properties.backupManagementType == 'AzureStorage'
            | extend shareId = tolower(tostring(properties.sourceResourceId))
            | project shareId, isProtected = true
        ) on shareId
        | where isnull(isProtected)
        | project 
            FileShareName = shareName,
            StorageAccount = storageAccount,
            ResourceGroup = resourceGroup,
            BackupStatus = 'Not Protected',
            Recommendation = 'Enable Azure Backup for this file share'
        | order by StorageAccount asc, FileShareName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_managed_disks_with_backup(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Managed Disks enabled for backup using Backup Vault"""
        query = """
        RecoveryServicesResources
        | where type =~ 'microsoft.dataprotection/backupvaults/backupinstances'
        | where properties.dataSourceInfo.datasourceType == 'Microsoft.Compute/disks'
        | extend diskId = tostring(properties.dataSourceInfo.resourceID)
        | extend diskName = tostring(properties.dataSourceInfo.resourceName)
        | extend vaultName = tostring(split(id, '/')[8])
        | extend protectionStatus = tostring(properties.protectionStatus.status)
        | extend policyName = tostring(split(properties.policyInfo.policyId, '/')[10])
        | project 
            DiskName = diskName,
            BackupVault = vaultName,
            ProtectionStatus = protectionStatus,
            BackupPolicy = policyName,
            SourceResourceId = diskId
        | order by DiskName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_managed_disks_without_backup(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Managed Disks that could benefit from backup (unattached disks)"""
        query = """
        Resources
        | where type =~ 'microsoft.compute/disks'
        | extend managedBy = tostring(properties.managedBy)
        | where isempty(managedBy)
        | extend diskState = tostring(properties.diskState)
        | extend diskSizeGb = toint(properties.diskSizeGB)
        | extend skuName = tostring(sku.name)
        | extend timeCreated = tostring(properties.timeCreated)
        | project 
            DiskName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            DiskSizeGB = diskSizeGb,
            DiskSKU = skuName,
            DiskState = diskState,
            AttachedToVM = 'Unattached',
            CreatedTime = timeCreated,
            Recommendation = 'Consider backup via Backup Vault or delete if unused'
        | order by DiskName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_shared_disks(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Managed Disks configured for shared disk"""
        query = """
        Resources
        | where type =~ 'microsoft.compute/disks'
        | where toint(properties.maxShares) > 1
        | extend diskSizeGb = toint(properties.diskSizeGB)
        | extend skuName = tostring(sku.name)
        | extend maxShares = toint(properties.maxShares)
        | extend diskState = tostring(properties.diskState)
        | project 
            DiskName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            DiskSizeGB = diskSizeGb,
            DiskSKU = skuName,
            MaxShares = maxShares,
            DiskState = diskState,
            Note = 'Shared disk - ensure appropriate backup strategy for clustered workloads'
        | order by DiskName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_storage_blobs_with_backup(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Storage Account Blobs enabled for backup using Backup Vault"""
        query = """
        RecoveryServicesResources
        | where type =~ 'microsoft.dataprotection/backupvaults/backupinstances'
        | where properties.dataSourceInfo.datasourceType == 'Microsoft.Storage/storageAccounts/blobServices'
        | extend storageAccountId = tostring(properties.dataSourceInfo.resourceID)
        | extend storageAccountName = tostring(properties.dataSourceInfo.resourceName)
        | extend vaultName = tostring(split(id, '/')[8])
        | extend protectionStatus = tostring(properties.protectionStatus.status)
        | extend policyName = tostring(split(properties.policyInfo.policyId, '/')[10])
        | project 
            StorageAccountName = storageAccountName,
            BackupVault = vaultName,
            ProtectionStatus = protectionStatus,
            BackupPolicy = policyName,
            SourceResourceId = storageAccountId
        | order by StorageAccountName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_sql_databases_with_backup(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Azure SQL Databases enabled for backup"""
        query = """
        RecoveryServicesResources
        | where type =~ 'microsoft.recoveryservices/vaults/backupfabrics/protectioncontainers/protecteditems'
        | where properties.backupManagementType == 'AzureWorkload' and properties.workloadType == 'SQLDataBase'
        | extend dbName = tostring(properties.friendlyName)
        | extend vaultName = tostring(split(id, '/')[8])
        | extend protectionStatus = tostring(properties.protectionStatus)
        | extend lastBackupStatus = tostring(properties.lastBackupStatus)
        | extend lastBackupTime = tostring(properties.lastBackupTime)
        | extend policyName = tostring(split(properties.policyId, '/')[12])
        | project 
            DatabaseName = dbName,
            VaultName = vaultName,
            ProtectionStatus = protectionStatus,
            LastBackupStatus = lastBackupStatus,
            LastBackupTime = lastBackupTime,
            BackupPolicy = policyName
        | order by DatabaseName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_sql_managed_instance_with_backup(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get SQL Managed Instances enabled for backup"""
        query = """
        RecoveryServicesResources
        | where type =~ 'microsoft.recoveryservices/vaults/backupfabrics/protectioncontainers/protecteditems'
        | where properties.backupManagementType == 'AzureWorkload' and properties.workloadType == 'SAPHanaDatabase' 
            or (properties.backupManagementType == 'AzureWorkload' and tostring(properties.sourceResourceId) contains 'managedInstances')
        | extend instanceName = tostring(properties.friendlyName)
        | extend vaultName = tostring(split(id, '/')[8])
        | extend protectionStatus = tostring(properties.protectionStatus)
        | extend lastBackupStatus = tostring(properties.lastBackupStatus)
        | extend lastBackupTime = tostring(properties.lastBackupTime)
        | project 
            InstanceName = instanceName,
            VaultName = vaultName,
            ProtectionStatus = protectionStatus,
            LastBackupStatus = lastBackupStatus,
            LastBackupTime = lastBackupTime
        | order by InstanceName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_backup_vaults_summary(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get summary of all Backup Vaults and Recovery Services Vaults"""
        query = """
        Resources
        | where type =~ 'microsoft.recoveryservices/vaults' or type =~ 'microsoft.dataprotection/backupvaults'
        | extend vaultType = case(
            type =~ 'microsoft.recoveryservices/vaults', 'Recovery Services Vault',
            type =~ 'microsoft.dataprotection/backupvaults', 'Backup Vault',
            'Unknown')
        | extend skuName = tostring(sku.name)
        | extend softDelete = tostring(properties.securitySettings.softDeleteSettings.softDeleteState)
        | project 
            VaultName = name,
            VaultType = vaultType,
            ResourceGroup = resourceGroup,
            Location = location,
            SKU = skuName,
            SoftDelete = softDelete,
            Tags = tags
        | order by VaultType asc, VaultName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_backup_jobs_failed(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get failed backup jobs from Recovery Services Vaults"""
        query = """
        RecoveryServicesResources
        | where type =~ 'microsoft.recoveryservices/vaults/backupjobs'
        | where properties.status == 'Failed' or properties.status == 'CompletedWithWarnings'
        | extend jobName = name
        | extend vaultName = tostring(split(id, '/')[8])
        | extend entityName = tostring(properties.entityFriendlyName)
        | extend jobStatus = tostring(properties.status)
        | extend startTime = tostring(properties.startTime)
        | extend duration = tostring(properties.duration)
        | extend errorCode = tostring(properties.errorDetails.errorCode)
        | project 
            JobName = jobName,
            VaultName = vaultName,
            EntityName = entityName,
            JobStatus = jobStatus,
            StartTime = startTime,
            Duration = duration,
            ErrorCode = errorCode
        | order by StartTime desc
        | take 100
        """
        return self.query_resources(query, subscriptions)

    # ========== IAM / RBAC ROLE ASSIGNMENT FUNCTIONS ==========
    
    def get_role_assignments_management_group(self, management_group_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get role assignments at Management Group level.
        Uses authorizationresources table for RBAC data.
        """
        query = """
        authorizationresources
        | where type =~ 'microsoft.authorization/roleassignments'
        | where id contains '/providers/Microsoft.Management/managementGroups/'
        | extend roleDefinitionId = tostring(properties.roleDefinitionId)
        | extend principalId = tostring(properties.principalId)
        | extend principalType = tostring(properties.principalType)
        | extend scope = tostring(properties.scope)
        | extend createdOn = tostring(properties.createdOn)
        | extend createdBy = tostring(properties.createdBy)
        | extend managementGroupName = tostring(split(scope, '/')[4])
        | extend roleDefinitionName = case(
            roleDefinitionId contains '8e3af657-a8ff-443c-a75c-2fe8c4bcb635', 'Owner',
            roleDefinitionId contains 'b24988ac-6180-42a0-ab88-20f7382dd24c', 'Contributor',
            roleDefinitionId contains '18d7d88d-d35e-4fb5-a5c3-7773c20a72d9', 'User Access Administrator',
            roleDefinitionId contains 'acdd72a7-3385-48ef-bd42-f606fba81ae7', 'Reader',
            roleDefinitionId contains 'f58310d9-a9f6-439a-9e8d-f62e7b41a168', 'Role Based Access Control Administrator',
            'Custom/Other')
        | extend riskLevel = case(
            roleDefinitionName == 'Owner', 'CRITICAL',
            roleDefinitionName == 'User Access Administrator', 'HIGH',
            roleDefinitionName == 'Contributor', 'MEDIUM',
            'LOW')
        | project 
            AssignmentId = name,
            PrincipalId = principalId,
            PrincipalType = principalType,
            RoleName = roleDefinitionName,
            RoleDefinitionId = roleDefinitionId,
            Scope = scope,
            ManagementGroup = managementGroupName,
            CreatedOn = createdOn,
            CreatedBy = createdBy,
            RiskLevel = riskLevel
        | order by RiskLevel asc, RoleName asc
        """
        return self.query_resources(query)
    
    def get_role_assignments_subscription(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get role assignments at Subscription level.
        Shows permanent (active) role assignments that are always-on.
        """
        query = """
        authorizationresources
        | where type =~ 'microsoft.authorization/roleassignments'
        | extend scope = tostring(properties.scope)
        | where scope matches regex @'^/subscriptions/[^/]+$'
        | extend roleDefinitionId = tostring(properties.roleDefinitionId)
        | extend principalId = tostring(properties.principalId)
        | extend principalType = tostring(properties.principalType)
        | extend createdOn = tostring(properties.createdOn)
        | extend createdBy = tostring(properties.createdBy)
        | extend subscriptionId = tostring(split(scope, '/')[2])
        | extend roleDefinitionName = case(
            roleDefinitionId contains '8e3af657-a8ff-443c-a75c-2fe8c4bcb635', 'Owner',
            roleDefinitionId contains 'b24988ac-6180-42a0-ab88-20f7382dd24c', 'Contributor',
            roleDefinitionId contains '18d7d88d-d35e-4fb5-a5c3-7773c20a72d9', 'User Access Administrator',
            roleDefinitionId contains 'acdd72a7-3385-48ef-bd42-f606fba81ae7', 'Reader',
            roleDefinitionId contains 'f58310d9-a9f6-439a-9e8d-f62e7b41a168', 'RBAC Administrator',
            roleDefinitionId contains 'fb1c8493-542b-48eb-b624-b4c8fea62acd', 'Security Admin',
            roleDefinitionId contains '17d1049b-9a84-46fb-8f53-869881c3d3ab', 'Storage Account Contributor',
            'Custom/Other')
        | extend riskLevel = case(
            roleDefinitionName == 'Owner', 'CRITICAL',
            roleDefinitionName == 'User Access Administrator', 'CRITICAL',
            roleDefinitionName == 'RBAC Administrator', 'HIGH',
            roleDefinitionName == 'Contributor', 'HIGH',
            roleDefinitionName == 'Security Admin', 'MEDIUM',
            'LOW')
        | project 
            AssignmentId = name,
            PrincipalId = principalId,
            PrincipalType = principalType,
            RoleName = roleDefinitionName,
            RoleDefinitionId = roleDefinitionId,
            Scope = scope,
            SubscriptionId = subscriptionId,
            CreatedOn = createdOn,
            CreatedBy = createdBy,
            RiskLevel = riskLevel,
            AssignmentType = 'Active (Permanent)'
        | order by RiskLevel asc, PrincipalType asc, RoleName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_role_assignments_resource_group(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get role assignments at Resource Group level.
        Shows permanent privileged access assignments.
        """
        query = """
        authorizationresources
        | where type =~ 'microsoft.authorization/roleassignments'
        | extend scope = tostring(properties.scope)
        | where scope matches regex @'^/subscriptions/[^/]+/resourceGroups/[^/]+$'
        | extend roleDefinitionId = tostring(properties.roleDefinitionId)
        | extend principalId = tostring(properties.principalId)
        | extend principalType = tostring(properties.principalType)
        | extend createdOn = tostring(properties.createdOn)
        | extend subscriptionId = tostring(split(scope, '/')[2])
        | extend resourceGroup = tostring(split(scope, '/')[4])
        | extend roleDefinitionName = case(
            roleDefinitionId contains '8e3af657-a8ff-443c-a75c-2fe8c4bcb635', 'Owner',
            roleDefinitionId contains 'b24988ac-6180-42a0-ab88-20f7382dd24c', 'Contributor',
            roleDefinitionId contains '18d7d88d-d35e-4fb5-a5c3-7773c20a72d9', 'User Access Administrator',
            roleDefinitionId contains 'acdd72a7-3385-48ef-bd42-f606fba81ae7', 'Reader',
            'Custom/Other')
        | extend riskLevel = case(
            roleDefinitionName == 'Owner', 'CRITICAL',
            roleDefinitionName == 'User Access Administrator', 'HIGH',
            roleDefinitionName == 'Contributor', 'MEDIUM',
            'LOW')
        | project 
            AssignmentId = name,
            PrincipalId = principalId,
            PrincipalType = principalType,
            RoleName = roleDefinitionName,
            ResourceGroup = resourceGroup,
            SubscriptionId = subscriptionId,
            Scope = scope,
            CreatedOn = createdOn,
            RiskLevel = riskLevel,
            AssignmentType = 'Active (Permanent)'
        | order by RiskLevel asc, ResourceGroup asc, RoleName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_role_assignments_service_principals(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get role assignments for Service Principals and Managed Identities.
        Focus on privileged roles (Owner, Contributor).
        """
        query = """
        authorizationresources
        | where type =~ 'microsoft.authorization/roleassignments'
        | extend principalType = tostring(properties.principalType)
        | where principalType == 'ServicePrincipal'
        | extend roleDefinitionId = tostring(properties.roleDefinitionId)
        | extend principalId = tostring(properties.principalId)
        | extend scope = tostring(properties.scope)
        | extend createdOn = tostring(properties.createdOn)
        | extend roleDefinitionName = case(
            roleDefinitionId contains '8e3af657-a8ff-443c-a75c-2fe8c4bcb635', 'Owner',
            roleDefinitionId contains 'b24988ac-6180-42a0-ab88-20f7382dd24c', 'Contributor',
            roleDefinitionId contains '18d7d88d-d35e-4fb5-a5c3-7773c20a72d9', 'User Access Administrator',
            roleDefinitionId contains 'acdd72a7-3385-48ef-bd42-f606fba81ae7', 'Reader',
            'Custom/Other')
        | extend scopeLevel = case(
            scope contains '/providers/Microsoft.Management/managementGroups/', 'ManagementGroup',
            scope matches regex @'^/subscriptions/[^/]+$', 'Subscription',
            scope contains '/resourceGroups/', 'ResourceGroup',
            'Resource')
        | extend riskLevel = case(
            roleDefinitionName == 'Owner', 'CRITICAL',
            roleDefinitionName == 'User Access Administrator', 'HIGH',
            roleDefinitionName == 'Contributor', 'MEDIUM',
            'LOW')
        | project 
            AssignmentId = name,
            PrincipalId = principalId,
            PrincipalType = principalType,
            RoleName = roleDefinitionName,
            ScopeLevel = scopeLevel,
            Scope = scope,
            CreatedOn = createdOn,
            RiskLevel = riskLevel
        | order by RiskLevel asc, ScopeLevel asc, RoleName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_role_assignments_summary(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get comprehensive RBAC role assignment summary across all scopes.
        Provides breakdown by scope, principal type, and role type.
        """
        query = """
        authorizationresources
        | where type =~ 'microsoft.authorization/roleassignments'
        | extend roleDefinitionId = tostring(properties.roleDefinitionId)
        | extend principalId = tostring(properties.principalId)
        | extend principalType = tostring(properties.principalType)
        | extend scope = tostring(properties.scope)
        | extend roleDefinitionName = case(
            roleDefinitionId contains '8e3af657-a8ff-443c-a75c-2fe8c4bcb635', 'Owner',
            roleDefinitionId contains 'b24988ac-6180-42a0-ab88-20f7382dd24c', 'Contributor',
            roleDefinitionId contains '18d7d88d-d35e-4fb5-a5c3-7773c20a72d9', 'User Access Administrator',
            roleDefinitionId contains 'acdd72a7-3385-48ef-bd42-f606fba81ae7', 'Reader',
            roleDefinitionId contains 'f58310d9-a9f6-439a-9e8d-f62e7b41a168', 'RBAC Administrator',
            'Custom/Other')
        | extend scopeLevel = case(
            scope contains '/providers/Microsoft.Management/managementGroups/', 'ManagementGroup',
            scope matches regex @'^/subscriptions/[^/]+$', 'Subscription',
            scope matches regex @'^/subscriptions/[^/]+/resourceGroups/[^/]+$', 'ResourceGroup',
            'Resource')
        | extend riskLevel = case(
            roleDefinitionName == 'Owner', 'CRITICAL',
            roleDefinitionName == 'User Access Administrator', 'CRITICAL',
            roleDefinitionName == 'Contributor' and scopeLevel in ('ManagementGroup', 'Subscription'), 'HIGH',
            roleDefinitionName == 'Contributor', 'MEDIUM',
            'LOW')
        | project 
            AssignmentId = name,
            PrincipalId = principalId,
            PrincipalType = principalType,
            RoleName = roleDefinitionName,
            ScopeLevel = scopeLevel,
            Scope = scope,
            RiskLevel = riskLevel
        | order by RiskLevel asc, ScopeLevel asc, RoleName asc
        """
        return self.query_resources(query, subscriptions)
    
    def get_privileged_role_assignments(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get all privileged role assignments (Owner, Contributor, User Access Administrator).
        Critical security audit function.
        """
        query = """
        authorizationresources
        | where type =~ 'microsoft.authorization/roleassignments'
        | extend roleDefinitionId = tostring(properties.roleDefinitionId)
        | where roleDefinitionId contains '8e3af657-a8ff-443c-a75c-2fe8c4bcb635'  // Owner
            or roleDefinitionId contains 'b24988ac-6180-42a0-ab88-20f7382dd24c'   // Contributor
            or roleDefinitionId contains '18d7d88d-d35e-4fb5-a5c3-7773c20a72d9'   // User Access Administrator
            or roleDefinitionId contains 'f58310d9-a9f6-439a-9e8d-f62e7b41a168'   // RBAC Administrator
        | extend principalId = tostring(properties.principalId)
        | extend principalType = tostring(properties.principalType)
        | extend scope = tostring(properties.scope)
        | extend createdOn = tostring(properties.createdOn)
        | extend createdBy = tostring(properties.createdBy)
        | extend roleDefinitionName = case(
            roleDefinitionId contains '8e3af657-a8ff-443c-a75c-2fe8c4bcb635', 'Owner',
            roleDefinitionId contains 'b24988ac-6180-42a0-ab88-20f7382dd24c', 'Contributor',
            roleDefinitionId contains '18d7d88d-d35e-4fb5-a5c3-7773c20a72d9', 'User Access Administrator',
            roleDefinitionId contains 'f58310d9-a9f6-439a-9e8d-f62e7b41a168', 'RBAC Administrator',
            'Unknown')
        | extend scopeLevel = case(
            scope contains '/providers/Microsoft.Management/managementGroups/', 'ManagementGroup',
            scope matches regex @'^/subscriptions/[^/]+$', 'Subscription',
            scope matches regex @'^/subscriptions/[^/]+/resourceGroups/[^/]+$', 'ResourceGroup',
            'Resource')
        | extend riskLevel = case(
            roleDefinitionName == 'Owner' and scopeLevel == 'ManagementGroup', 'CRITICAL-EXTREME',
            roleDefinitionName == 'Owner' and scopeLevel == 'Subscription', 'CRITICAL',
            roleDefinitionName == 'User Access Administrator', 'CRITICAL',
            roleDefinitionName == 'Contributor' and scopeLevel in ('ManagementGroup', 'Subscription'), 'HIGH',
            'MEDIUM')
        | project 
            AssignmentId = name,
            PrincipalId = principalId,
            PrincipalType = principalType,
            RoleName = roleDefinitionName,
            ScopeLevel = scopeLevel,
            Scope = scope,
            CreatedOn = createdOn,
            CreatedBy = createdBy,
            RiskLevel = riskLevel,
            AssignmentType = 'Active (Permanent)'
        | order by RiskLevel asc, ScopeLevel asc, RoleName asc, PrincipalType asc
        """
        return self.query_resources(query, subscriptions)

