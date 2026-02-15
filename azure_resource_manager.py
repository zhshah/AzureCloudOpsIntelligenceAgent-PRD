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
        self.cost_manager = AzureCostManager()  # Initialize Cost Management client
        self._subscription_cache = {}  # Cache for subscription name lookups
    
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

    async def get_subscriptions_with_hierarchy(self) -> Dict[str, Any]:
        """Get subscriptions along with management group hierarchy"""
        try:
            from azure.mgmt.managementgroups import ManagementGroupsAPI
            from azure.identity import DefaultAzureCredential
            
            subscriptions = []
            management_groups = []
            
            # Get all subscriptions first
            for sub in self.sub_client.subscriptions.list():
                if sub.state == "Enabled":
                    subscriptions.append({
                        "id": sub.subscription_id,
                        "name": sub.display_name,
                        "state": sub.state
                    })
            
            # Try to get management groups hierarchy
            try:
                mg_client = ManagementGroupsAPI(DefaultAzureCredential())
                
                def build_hierarchy(mg_id, depth=0, max_depth=5):
                    """Recursively build management group hierarchy"""
                    if depth > max_depth:
                        return None
                    
                    try:
                        mg = mg_client.management_groups.get(mg_id, expand="children")
                        mg_data = {
                            "id": mg.name,
                            "name": mg.display_name or mg.name,
                            "type": "managementGroup",
                            "children": []
                        }
                        
                        if mg.children:
                            for child in mg.children:
                                if child.type == "/providers/Microsoft.Management/managementGroups":
                                    child_mg = build_hierarchy(child.name, depth + 1)
                                    if child_mg:
                                        mg_data["children"].append(child_mg)
                                elif child.type == "/subscriptions":
                                    mg_data["children"].append({
                                        "id": child.name,
                                        "name": child.display_name or child.name,
                                        "type": "subscription"
                                    })
                        
                        return mg_data
                    except Exception as e:
                        print(f"Error getting management group {mg_id}: {e}")
                        return None
                
                # Get root management groups
                root_mgs = list(mg_client.management_groups.list())
                for root_mg in root_mgs:
                    mg_hierarchy = build_hierarchy(root_mg.name)
                    if mg_hierarchy:
                        management_groups.append(mg_hierarchy)
                
            except ImportError:
                print("Management Groups SDK not installed, using subscriptions only")
            except Exception as mg_error:
                print(f"Could not fetch management groups: {mg_error}")
            
            return {
                "subscriptions": subscriptions,
                "managementGroups": management_groups
            }
        except Exception as e:
            print(f"Error in get_subscriptions_with_hierarchy: {e}")
            return {
                "subscriptions": [],
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
    
    def get_resources_for_diagram(self, resource_group: str = None, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get resources with enriched properties for architecture diagram generation.
        
        Includes VM size, disk size, IP addresses, SKU, and availability set info
        to enable richer diagram labels.
        """
        rg_filter = f"| where resourceGroup =~ '{resource_group}'" if resource_group else ""
        query = f"""
        Resources
        {rg_filter}
        | extend
            vmSize = tostring(properties.hardwareProfile.vmSize),
            diskSizeGB = toint(properties.diskSizeGB),
            osType = tostring(properties.osType),
            privateIP = tostring(properties.ipConfigurations[0].properties.privateIPAddress),
            publicIPAddr = tostring(properties.ipAddress),
            skuName = tostring(sku.name),
            skuTier = tostring(sku.tier),
            availabilitySet = tostring(split(properties.availabilitySet.id, '/')[-1]),
            provisioningState = tostring(properties.provisioningState)
        | project
            name,
            type,
            resourceGroup,
            location,
            subscriptionId,
            vmSize,
            diskSizeGB,
            osType,
            privateIP,
            publicIPAddr,
            skuName,
            skuTier,
            availabilitySet,
            provisioningState
        | order by type asc, name asc
        """
        result = self.query_resources(query, subscriptions)
        
        # Add subscription names to results
        if result and 'data' in result and isinstance(result['data'], list):
            sub_names = self._get_subscription_names()
            for resource in result['data']:
                sub_id = resource.get('subscriptionId', '')
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

    # ============================================================
    # RBAC / IAM ROLE ASSIGNMENT FUNCTIONS
    # ============================================================

    def get_role_assignments_at_subscription(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all active role assignments at subscription level using Azure Resource Graph authorizationresources"""
        query = """
        authorizationresources
        | where type =~ 'microsoft.authorization/roleassignments'
        | extend roleDefinitionId = tostring(properties.roleDefinitionId)
        | extend principalId = tostring(properties.principalId)
        | extend principalType = tostring(properties.principalType)
        | extend scope = tostring(properties.scope)
        | extend createdOn = tostring(properties.createdOn)
        | extend createdBy = tostring(properties.createdBy)
        | extend updatedOn = tostring(properties.updatedOn)
        | where scope matches regex "^/subscriptions/[^/]+$"
        | project
            RoleAssignmentId = id,
            RoleDefinitionId = roleDefinitionId,
            PrincipalId = principalId,
            PrincipalType = principalType,
            Scope = scope,
            CreatedOn = createdOn,
            CreatedBy = createdBy,
            UpdatedOn = updatedOn
        | order by PrincipalType asc, CreatedOn desc
        """
        return self.query_resources(query, subscriptions)

    def get_role_assignments_at_management_group(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all active role assignments at management group level"""
        query = """
        authorizationresources
        | where type =~ 'microsoft.authorization/roleassignments'
        | extend roleDefinitionId = tostring(properties.roleDefinitionId)
        | extend principalId = tostring(properties.principalId)
        | extend principalType = tostring(properties.principalType)
        | extend scope = tostring(properties.scope)
        | extend createdOn = tostring(properties.createdOn)
        | extend createdBy = tostring(properties.createdBy)
        | where scope matches regex "^/providers/Microsoft.Management/managementGroups/"
        | project
            RoleAssignmentId = id,
            RoleDefinitionId = roleDefinitionId,
            PrincipalId = principalId,
            PrincipalType = principalType,
            Scope = scope,
            CreatedOn = createdOn,
            CreatedBy = createdBy
        | order by PrincipalType asc, CreatedOn desc
        """
        return self.query_resources(query, subscriptions)

    def get_role_assignments_at_resource_group(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all active role assignments at resource group level"""
        query = """
        authorizationresources
        | where type =~ 'microsoft.authorization/roleassignments'
        | extend roleDefinitionId = tostring(properties.roleDefinitionId)
        | extend principalId = tostring(properties.principalId)
        | extend principalType = tostring(properties.principalType)
        | extend scope = tostring(properties.scope)
        | extend createdOn = tostring(properties.createdOn)
        | extend createdBy = tostring(properties.createdBy)
        | where scope matches regex "^/subscriptions/[^/]+/resourceGroups/[^/]+$"
        | project
            RoleAssignmentId = id,
            RoleDefinitionId = roleDefinitionId,
            PrincipalId = principalId,
            PrincipalType = principalType,
            Scope = scope,
            CreatedOn = createdOn,
            CreatedBy = createdBy
        | order by PrincipalType asc, CreatedOn desc
        """
        return self.query_resources(query, subscriptions)

    def get_role_definitions(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all role definitions (built-in and custom) to map role names"""
        query = """
        authorizationresources
        | where type =~ 'microsoft.authorization/roledefinitions'
        | extend roleName = tostring(properties.roleName)
        | extend roleType = tostring(properties.type)
        | extend description = tostring(properties.description)
        | project
            RoleDefinitionId = id,
            RoleName = roleName,
            RoleType = roleType,
            Description = description
        | order by RoleName asc
        """
        return self.query_resources(query, subscriptions)

    def get_role_assignments_privileged(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get privileged role assignments (Owner, Contributor, User Access Administrator) across all scopes"""
        query = """
        authorizationresources
        | where type =~ 'microsoft.authorization/roleassignments'
        | extend roleDefinitionId = tostring(properties.roleDefinitionId)
        | extend principalId = tostring(properties.principalId)
        | extend principalType = tostring(properties.principalType)
        | extend scope = tostring(properties.scope)
        | extend createdOn = tostring(properties.createdOn)
        | extend createdBy = tostring(properties.createdBy)
        | join kind=leftouter (
            authorizationresources
            | where type =~ 'microsoft.authorization/roledefinitions'
            | extend roleName = tostring(properties.roleName)
            | extend roleDefId = id
            | project roleDefId, roleName
        ) on $left.roleDefinitionId == $right.roleDefId
        | where roleName in ('Owner', 'Contributor', 'User Access Administrator')
        | project
            PrincipalId = principalId,
            PrincipalType = principalType,
            RoleName = roleName,
            Scope = scope,
            CreatedOn = createdOn,
            CreatedBy = createdBy
        | order by RoleName asc, PrincipalType asc
        """
        return self.query_resources(query, subscriptions)

    def get_rbac_summary(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get comprehensive RBAC summary with counts by scope, role type, and principal type"""
        query = """
        authorizationresources
        | where type =~ 'microsoft.authorization/roleassignments'
        | extend principalType = tostring(properties.principalType)
        | extend scope = tostring(properties.scope)
        | extend scopeLevel = case(
            scope matches regex "^/providers/Microsoft.Management/managementGroups/", "Management Group",
            scope matches regex "^/subscriptions/[^/]+$", "Subscription",
            scope matches regex "^/subscriptions/[^/]+/resourceGroups/[^/]+$", "Resource Group",
            "Resource"
          )
        | summarize Count = count() by scopeLevel, principalType
        | order by scopeLevel asc, Count desc
        """
        return self.query_resources(query, subscriptions)

    # ============================================================
    # MANAGEMENT GROUP & HIERARCHY FUNCTIONS
    # ============================================================

    def get_management_group_hierarchy(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get complete management group hierarchy structure using Management Groups API"""
        try:
            from azure.mgmt.managementgroups import ManagementGroupsAPI
            from azure.identity import DefaultAzureCredential
            
            credential = DefaultAzureCredential()
            mg_client = ManagementGroupsAPI(credential)
            
            hierarchy = []
            
            # Get all management groups
            mg_list = list(mg_client.management_groups.list())
            
            def build_mg_tree(mg_id, depth=0, max_depth=5):
                if depth >= max_depth:
                    return None
                try:
                    mg_details = mg_client.management_groups.get(
                        mg_id, expand="children", recurse=True
                    )
                    result = {
                        "name": mg_details.display_name or mg_details.name,
                        "id": mg_details.name,
                        "type": "managementGroup",
                        "children": []
                    }
                    if mg_details.children:
                        for child in mg_details.children:
                            if child.type and 'managementGroups' in child.type:
                                child_tree = build_mg_tree(child.name, depth + 1)
                                if child_tree:
                                    result["children"].append(child_tree)
                            elif child.type and 'subscriptions' in child.type:
                                result["children"].append({
                                    "name": child.display_name or child.name,
                                    "id": child.name,
                                    "type": "subscription"
                                })
                    return result
                except Exception as e:
                    return {"name": mg_id, "id": mg_id, "type": "managementGroup", "children": [], "error": str(e)}
            
            # Find root management group(s) and build tree from there
            root_groups = [mg for mg in mg_list if not hasattr(mg, 'parent') or mg.parent is None or 
                          (hasattr(mg.parent, 'id') and mg.parent.id is None)]
            
            if not root_groups and mg_list:
                # If we can't find root, try building from each top-level group
                root_groups = mg_list[:3]  # Limit to prevent over-fetching
            
            for mg in root_groups:
                tree = build_mg_tree(mg.name)
                if tree:
                    hierarchy.append(tree)
            
            return {
                "count": len(mg_list),
                "total_management_groups": len(mg_list),
                "hierarchy": hierarchy,
                "management_groups": [{"name": mg.display_name or mg.name, "id": mg.name} for mg in mg_list]
            }
        except Exception as e:
            return {"error": f"Failed to retrieve management group hierarchy: {str(e)}", "count": 0, "hierarchy": []}

    # ============================================================
    # SECURITY & DEFENDER FOR CLOUD FUNCTIONS
    # ============================================================

    def get_security_recommendations(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Microsoft Defender for Cloud security recommendations using Azure Resource Graph"""
        query = """
        securityresources
        | where type =~ 'microsoft.security/assessments'
        | extend status = tostring(properties.status.code)
        | extend displayName = tostring(properties.displayName)
        | extend severity = tostring(properties.metadata.severity)
        | extend category = tostring(properties.metadata.categories[0])
        | extend resourceId = tostring(properties.resourceDetails.Id)
        | extend resourceType = tostring(split(resourceId, '/')[6])
        | extend description = tostring(properties.metadata.description)
        | extend remediationDescription = tostring(properties.metadata.remediationDescription)
        | where status == 'Unhealthy'
        | project
            RecommendationName = displayName,
            Severity = severity,
            Category = category,
            AffectedResource = resourceId,
            ResourceType = resourceType,
            Description = description,
            Remediation = remediationDescription,
            Status = status
        | order by Severity asc, Category asc
        | take 200
        """
        return self.query_resources(query, subscriptions)

    def get_security_score_details(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get security score breakdown by security control using Azure Resource Graph"""
        query = """
        securityresources
        | where type =~ 'microsoft.security/securescores/securescorecontrols'
        | extend controlName = tostring(properties.displayName)
        | extend currentScore = todouble(properties.score.current)
        | extend maxScore = todouble(properties.score.max)
        | extend percentage = iff(maxScore > 0, round(currentScore / maxScore * 100, 1), 0.0)
        | extend healthyResources = toint(properties.healthyResourceCount)
        | extend unhealthyResources = toint(properties.unhealthyResourceCount)
        | extend notApplicable = toint(properties.notApplicableResourceCount)
        | project
            ControlName = controlName,
            CurrentScore = currentScore,
            MaxScore = maxScore,
            Percentage = percentage,
            HealthyResources = healthyResources,
            UnhealthyResources = unhealthyResources,
            NotApplicable = notApplicable
        | order by Percentage asc
        """
        return self.query_resources(query, subscriptions)

    def get_security_alerts(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get active security alerts from Microsoft Defender for Cloud"""
        query = """
        securityresources
        | where type =~ 'microsoft.security/locations/alerts'
        | extend alertName = tostring(properties.alertDisplayName)
        | extend severity = tostring(properties.severity)
        | extend status = tostring(properties.status)
        | extend description = tostring(properties.description)
        | extend startTime = tostring(properties.startTimeUtc)
        | extend affectedResource = tostring(properties.compromisedEntity)
        | extend alertType = tostring(properties.alertType)
        | where status != 'Dismissed' and status != 'Resolved'
        | project
            AlertName = alertName,
            Severity = severity,
            Status = status,
            Description = description,
            StartTime = startTime,
            AffectedResource = affectedResource,
            AlertType = alertType
        | order by Severity asc, StartTime desc
        | take 100
        """
        return self.query_resources(query, subscriptions)

    def get_regulatory_compliance(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get regulatory compliance assessment status"""
        query = """
        securityresources
        | where type =~ 'microsoft.security/regulatorycompliancestandards'
        | extend standardName = tostring(properties.displayName)
        | extend state = tostring(properties.state)
        | extend passedControls = toint(properties.passedControls)
        | extend failedControls = toint(properties.failedControls)
        | extend skippedControls = toint(properties.skippedControls)
        | extend unsupportedControls = toint(properties.unsupportedControls)
        | project
            StandardName = standardName,
            State = state,
            PassedControls = passedControls,
            FailedControls = failedControls,
            SkippedControls = skippedControls,
            UnsupportedControls = unsupportedControls
        | order by StandardName asc
        """
        return self.query_resources(query, subscriptions)

    # ============================================================
    # PRIVATE DNS ZONE FUNCTIONS
    # ============================================================

    def get_private_dns_zones(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Private DNS Zones with details"""
        query = """
        resources
        | where type =~ 'microsoft.network/privatednszones'
        | extend recordCount = toint(properties.numberOfRecordSets)
        | extend vnetLinkCount = toint(properties.numberOfVirtualNetworkLinks)
        | extend autoRegistration = toint(properties.numberOfVirtualNetworkLinksWithRegistration)
        | extend maxRecordSets = toint(properties.maxNumberOfRecordSets)
        | project
            ZoneName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            RecordCount = recordCount,
            VNetLinks = vnetLinkCount,
            AutoRegistrationLinks = autoRegistration,
            MaxRecordSets = maxRecordSets,
            SubscriptionId = subscriptionId,
            Tags = tags
        | order by ZoneName asc
        """
        return self.query_resources(query, subscriptions)

    def get_private_dns_vnet_links(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get VNet links for Private DNS Zones"""
        query = """
        resources
        | where type =~ 'microsoft.network/privatednszones/virtualnetworklinks'
        | extend zoneName = tostring(split(id, '/')[8])
        | extend linkName = name
        | extend registrationEnabled = tostring(properties.registrationEnabled)
        | extend vnetId = tostring(properties.virtualNetwork.id)
        | extend provisioningState = tostring(properties.provisioningState)
        | project
            ZoneName = zoneName,
            LinkName = linkName,
            RegistrationEnabled = registrationEnabled,
            VNetId = vnetId,
            ProvisioningState = provisioningState,
            ResourceGroup = resourceGroup
        | order by ZoneName asc
        """
        return self.query_resources(query, subscriptions)

    def get_private_endpoints(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Private Endpoints with details"""
        query = """
        resources
        | where type =~ 'microsoft.network/privateendpoints'
        | extend targetServiceId = tostring(properties.privateLinkServiceConnections[0].properties.privateLinkServiceId)
        | extend targetServiceType = tostring(split(targetServiceId, '/')[6])
        | extend targetServiceName = tostring(split(targetServiceId, '/')[8])
        | extend connectionStatus = tostring(properties.privateLinkServiceConnections[0].properties.privateLinkServiceConnectionState.status)
        | extend subnetId = tostring(properties.subnet.id)
        | extend vnetName = tostring(split(subnetId, '/')[8])
        | extend subnetName = tostring(split(subnetId, '/')[10])
        | mv-expand ipConfig = properties.customDnsConfigs
        | extend privateIp = tostring(ipConfig.ipAddresses[0])
        | extend fqdn = tostring(ipConfig.fqdn)
        | project
            EndpointName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            TargetServiceType = targetServiceType,
            TargetServiceName = targetServiceName,
            ConnectionStatus = connectionStatus,
            VNetName = vnetName,
            SubnetName = subnetName,
            PrivateIP = privateIp,
            FQDN = fqdn,
            SubscriptionId = subscriptionId
        | order by TargetServiceType asc, EndpointName asc
        """
        return self.query_resources(query, subscriptions)

    # ============================================================
    # NETWORK SECURITY GROUPS DETAILED
    # ============================================================

    def get_nsgs_with_rules(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all NSGs with their security rules for analysis"""
        query = """
        resources
        | where type =~ 'microsoft.network/networksecuritygroups'
        | mv-expand rules = properties.securityRules
        | extend ruleName = tostring(rules.name)
        | extend direction = tostring(rules.properties.direction)
        | extend access = tostring(rules.properties.access)
        | extend priority = toint(rules.properties.priority)
        | extend sourceAddress = tostring(rules.properties.sourceAddressPrefix)
        | extend destinationPort = tostring(rules.properties.destinationPortRange)
        | extend protocol = tostring(rules.properties.protocol)
        | extend subnetCount = array_length(properties.subnets)
        | extend nicCount = array_length(properties.networkInterfaces)
        | project
            NSGName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            RuleName = ruleName,
            Direction = direction,
            Access = access,
            Priority = priority,
            SourceAddress = sourceAddress,
            DestinationPort = destinationPort,
            Protocol = protocol,
            SubnetAssociations = subnetCount,
            NICAssociations = nicCount
        | order by NSGName asc, Priority asc
        """
        return self.query_resources(query, subscriptions)

    def get_nsgs_risky_rules(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get NSGs with risky rules (Any source, exposed sensitive ports)"""
        query = """
        resources
        | where type =~ 'microsoft.network/networksecuritygroups'
        | mv-expand rules = properties.securityRules
        | extend ruleName = tostring(rules.name)
        | extend direction = tostring(rules.properties.direction)
        | extend access = tostring(rules.properties.access)
        | extend priority = toint(rules.properties.priority)
        | extend sourceAddress = tostring(rules.properties.sourceAddressPrefix)
        | extend destinationPort = tostring(rules.properties.destinationPortRange)
        | extend protocol = tostring(rules.properties.protocol)
        | where access == 'Allow' and direction == 'Inbound'
        | where sourceAddress in ('*', '0.0.0.0/0', 'Internet', 'Any')
            or destinationPort in ('3389', '22', '1433', '445', '23', '5985', '5986')
            or destinationPort == '*'
        | project
            NSGName = name,
            ResourceGroup = resourceGroup,
            RuleName = ruleName,
            Priority = priority,
            SourceAddress = sourceAddress,
            DestinationPort = destinationPort,
            Protocol = protocol,
            RiskLevel = case(
                destinationPort == '*' and sourceAddress in ('*', '0.0.0.0/0', 'Internet', 'Any'), 'CRITICAL',
                sourceAddress in ('*', '0.0.0.0/0', 'Internet', 'Any') and destinationPort in ('3389', '22'), 'HIGH',
                sourceAddress in ('*', '0.0.0.0/0', 'Internet', 'Any'), 'MEDIUM',
                'LOW'
            )
        | order by RiskLevel asc, Priority asc
        """
        return self.query_resources(query, subscriptions)

    # ============================================================
    # LOAD BALANCERS
    # ============================================================

    def get_load_balancers(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Load Balancers with details"""
        query = """
        resources
        | where type =~ 'microsoft.network/loadbalancers'
        | extend sku = tostring(properties.sku.name)
        | extend frontendCount = array_length(properties.frontendIPConfigurations)
        | extend backendCount = array_length(properties.backendAddressPools)
        | extend probeCount = array_length(properties.probes)
        | extend ruleCount = array_length(properties.loadBalancingRules)
        | extend lbType = iff(
            array_length(properties.frontendIPConfigurations) > 0 and 
            isnotempty(properties.frontendIPConfigurations[0].properties.publicIPAddress),
            'Public', 'Internal')
        | project
            LBName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            SKU = sku,
            Type = lbType,
            FrontendIPs = frontendCount,
            BackendPools = backendCount,
            Probes = probeCount,
            Rules = ruleCount,
            SubscriptionId = subscriptionId,
            Tags = tags
        | order by LBName asc
        """
        return self.query_resources(query, subscriptions)

    # ============================================================
    # VPN & EXPRESSROUTE GATEWAYS
    # ============================================================

    def get_vpn_gateways(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all VPN Gateways"""
        query = """
        resources
        | where type =~ 'microsoft.network/virtualnetworkgateways'
        | extend gatewayType = tostring(properties.gatewayType)
        | extend vpnType = tostring(properties.vpnType)
        | extend sku = tostring(properties.sku.name)
        | extend activeActive = tostring(properties.activeActive)
        | extend bgpEnabled = tostring(properties.enableBgp)
        | extend provisioningState = tostring(properties.provisioningState)
        | project
            GatewayName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            GatewayType = gatewayType,
            VPNType = vpnType,
            SKU = sku,
            ActiveActive = activeActive,
            BGPEnabled = bgpEnabled,
            ProvisioningState = provisioningState,
            SubscriptionId = subscriptionId
        | order by GatewayName asc
        """
        return self.query_resources(query, subscriptions)

    def get_expressroute_circuits(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all ExpressRoute circuits"""
        query = """
        resources
        | where type =~ 'microsoft.network/expressroutecircuits'
        | extend serviceProvider = tostring(properties.serviceProviderProperties.serviceProviderName)
        | extend peeringLocation = tostring(properties.serviceProviderProperties.peeringLocation)
        | extend bandwidth = tostring(properties.serviceProviderProperties.bandwidthInMbps)
        | extend skuTier = tostring(properties.sku.tier)
        | extend skuFamily = tostring(properties.sku.family)
        | extend circuitState = tostring(properties.circuitProvisioningState)
        | extend providerState = tostring(properties.serviceProviderProvisioningState)
        | project
            CircuitName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            ServiceProvider = serviceProvider,
            PeeringLocation = peeringLocation,
            Bandwidth = bandwidth,
            SKUTier = skuTier,
            SKUFamily = skuFamily,
            CircuitState = circuitState,
            ProviderState = providerState,
            SubscriptionId = subscriptionId
        | order by CircuitName asc
        """
        return self.query_resources(query, subscriptions)

    # ============================================================
    # WAF POLICIES & APPLICATION GATEWAYS
    # ============================================================

    def get_waf_policies(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Web Application Firewall policies"""
        query = """
        resources
        | where type =~ 'microsoft.network/applicationgatewaywebapplicationfirewallpolicies'
            or type =~ 'microsoft.network/frontdoorwebapplicationfirewallpolicies'
        | extend policyMode = tostring(properties.policySettings.mode)
        | extend managedRuleCount = array_length(properties.managedRules.managedRuleSets)
        | extend customRuleCount = array_length(properties.customRules)
        | project
            PolicyName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            Type = type,
            Mode = policyMode,
            ManagedRuleSets = managedRuleCount,
            CustomRules = customRuleCount,
            SubscriptionId = subscriptionId
        | order by PolicyName asc
        """
        return self.query_resources(query, subscriptions)

    def get_application_gateways(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Application Gateways with details"""
        query = """
        resources
        | where type =~ 'microsoft.network/applicationgateways'
        | extend sku = tostring(properties.sku.name)
        | extend tier = tostring(properties.sku.tier)
        | extend capacity = toint(properties.sku.capacity)
        | extend wafEnabled = isnotempty(properties.webApplicationFirewallConfiguration)
        | extend frontendCount = array_length(properties.frontendIPConfigurations)
        | extend backendPoolCount = array_length(properties.backendAddressPools)
        | extend listenerCount = array_length(properties.httpListeners)
        | extend probeCount = array_length(properties.probes)
        | extend operationalState = tostring(properties.operationalState)
        | project
            GatewayName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            SKU = sku,
            Tier = tier,
            Capacity = capacity,
            WAFEnabled = wafEnabled,
            FrontendIPs = frontendCount,
            BackendPools = backendPoolCount,
            Listeners = listenerCount,
            Probes = probeCount,
            OperationalState = operationalState,
            SubscriptionId = subscriptionId
        | order by GatewayName asc
        """
        return self.query_resources(query, subscriptions)

    # ============================================================
    # AZURE FIREWALL
    # ============================================================

    def get_azure_firewalls(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Azure Firewalls"""
        query = """
        resources
        | where type =~ 'microsoft.network/azurefirewalls'
        | extend sku = tostring(properties.sku.name)
        | extend tier = tostring(properties.sku.tier)
        | extend threatIntelMode = tostring(properties.threatIntelMode)
        | extend provisioningState = tostring(properties.provisioningState)
        | extend firewallPolicyId = tostring(properties.firewallPolicy.id)
        | extend firewallPolicyName = tostring(split(firewallPolicyId, '/')[8])
        | extend publicIpCount = array_length(properties.ipConfigurations)
        | project
            FirewallName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            SKU = sku,
            Tier = tier,
            ThreatIntelMode = threatIntelMode,
            FirewallPolicy = firewallPolicyName,
            PublicIPs = publicIpCount,
            ProvisioningState = provisioningState,
            SubscriptionId = subscriptionId
        | order by FirewallName asc
        """
        return self.query_resources(query, subscriptions)

    # ============================================================
    # VIRTUAL WAN
    # ============================================================

    def get_virtual_wans(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Virtual WANs and Hubs"""
        query = """
        resources
        | where type =~ 'microsoft.network/virtualwans'
            or type =~ 'microsoft.network/virtualhubs'
        | extend wanType = iff(type =~ 'microsoft.network/virtualwans', 'Virtual WAN', 'Virtual Hub')
        | extend sku = tostring(properties.sku)
        | extend provisioningState = tostring(properties.provisioningState)
        | extend addressPrefix = tostring(properties.addressPrefix)
        | project
            Name = name,
            Type = wanType,
            ResourceGroup = resourceGroup,
            Location = location,
            SKU = sku,
            AddressPrefix = addressPrefix,
            ProvisioningState = provisioningState,
            SubscriptionId = subscriptionId
        | order by Type asc, Name asc
        """
        return self.query_resources(query, subscriptions)

    # ============================================================
    # FRONT DOOR & TRAFFIC MANAGER
    # ============================================================

    def get_front_doors(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Azure Front Door profiles"""
        query = """
        resources
        | where type =~ 'microsoft.cdn/profiles' or type =~ 'microsoft.network/frontdoors'
        | extend sku = tostring(properties.sku.name)
        | extend provisioningState = tostring(properties.provisioningState)
        | project
            FrontDoorName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            Type = type,
            SKU = sku,
            ProvisioningState = provisioningState,
            SubscriptionId = subscriptionId
        | order by FrontDoorName asc
        """
        return self.query_resources(query, subscriptions)

    def get_traffic_manager_profiles(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get all Traffic Manager profiles"""
        query = """
        resources
        | where type =~ 'microsoft.network/trafficmanagerprofiles'
        | extend routingMethod = tostring(properties.trafficRoutingMethod)
        | extend dnsName = tostring(properties.dnsConfig.relativeName)
        | extend ttl = toint(properties.dnsConfig.ttl)
        | extend monitorProtocol = tostring(properties.monitorConfig.protocol)
        | extend monitorPort = toint(properties.monitorConfig.port)
        | extend endpointCount = array_length(properties.endpoints)
        | extend profileStatus = tostring(properties.profileStatus)
        | project
            ProfileName = name,
            ResourceGroup = resourceGroup,
            RoutingMethod = routingMethod,
            DNSName = dnsName,
            TTL = ttl,
            MonitorProtocol = monitorProtocol,
            MonitorPort = monitorPort,
            EndpointCount = endpointCount,
            ProfileStatus = profileStatus,
            SubscriptionId = subscriptionId
        | order by ProfileName asc
        """
        return self.query_resources(query, subscriptions)

    # ============================================================
    # NETWORK WATCHER & DDOS
    # ============================================================

    def get_network_watchers(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Network Watcher status by region"""
        query = """
        resources
        | where type =~ 'microsoft.network/networkwatchers'
        | extend provisioningState = tostring(properties.provisioningState)
        | project
            Name = name,
            ResourceGroup = resourceGroup,
            Location = location,
            ProvisioningState = provisioningState,
            SubscriptionId = subscriptionId
        | order by Location asc
        """
        return self.query_resources(query, subscriptions)

    def get_ddos_protection_plans(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get DDoS Protection Plans"""
        query = """
        resources
        | where type =~ 'microsoft.network/ddosprotectionplans'
        | extend vnetCount = array_length(properties.virtualNetworks)
        | extend provisioningState = tostring(properties.provisioningState)
        | project
            PlanName = name,
            ResourceGroup = resourceGroup,
            Location = location,
            ProtectedVNets = vnetCount,
            ProvisioningState = provisioningState,
            SubscriptionId = subscriptionId
        | order by PlanName asc
        """
        return self.query_resources(query, subscriptions)

    # ==========================================
    # AZURE INVENTORY FUNCTIONS
    # Based on: https://github.com/scautomation/Azure-Inventory-Workbook
    # ==========================================

    def get_inventory_overview(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get overview of all Azure resources - total counts, counts by type, by location, subscriptions and resource groups."""
        query = """
        Resources
        | summarize TotalResources=count() by type
        | order by TotalResources desc
        """
        type_counts = self.query_resources(query, subscriptions)

        location_query = """
        Resources
        | summarize Count=count() by location
        | order by Count desc
        """
        location_counts = self.query_resources(location_query, subscriptions)

        rg_query = """
        resourcecontainers
        | where type =~ 'microsoft.resources/subscriptions/resourcegroups'
        | summarize ResourceGroupCount=count() by subscriptionId
        """
        rg_counts = self.query_resources(rg_query, subscriptions)

        return {
            "inventory_type": "overview",
            "resource_counts_by_type": type_counts,
            "resource_counts_by_location": location_counts,
            "resource_groups_by_subscription": rg_counts
        }

    def get_inventory_compute_vms(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get comprehensive VM inventory - status, sizes, OS, creation date, SQL extensions, availability sets."""
        query = """
        Resources
        | where type == "microsoft.compute/virtualmachines"
        | extend vmID = tolower(id)
        | extend osDiskId = tolower(tostring(properties.storageProfile.osDisk.managedDisk.id))
        | extend provisioningState = tostring(properties.extended.instanceView.powerState.displayStatus)
        | extend vmSize = tostring(properties.hardwareProfile.vmSize)
        | join kind=leftouter(
            resources
            | where type =~ 'microsoft.compute/disks'
            | where properties !has 'Unattached'
            | where properties has 'osType'
            | project timeCreated = tostring(properties.timeCreated), OS = tostring(properties.osType), osSku = tostring(sku.name), osDiskSizeGB = toint(properties.diskSizeGB), osDiskId=tolower(tostring(id))
        ) on osDiskId
        | join kind=leftouter(
            resources
            | where type =~ 'microsoft.compute/availabilitysets'
            | extend VirtualMachines = array_length(properties.virtualMachines)
            | mv-expand VirtualMachine=properties.virtualMachines
            | extend FaultDomainCount = properties.platformFaultDomainCount
            | extend UpdateDomainCount = properties.platformUpdateDomainCount
            | extend vmID = tolower(VirtualMachine.id)
            | project AvailabilitySetID = id, vmID, FaultDomainCount, UpdateDomainCount
        ) on vmID
        | join kind=leftouter(
            resources
            | where type =~ 'microsoft.sqlvirtualmachine/sqlvirtualmachines'
            | extend SQLLicense = properties.sqlServerLicenseType
            | extend SQLImage = properties.sqlImageOffer
            | extend SQLSku = properties.sqlImageSku
            | extend SQLManagement = properties.sqlManagement
            | extend vmID = tostring(tolower(properties.virtualMachineResourceId))
            | project SQLId=id, SQLLicense, SQLImage, SQLSku, SQLManagement, vmID
        ) on vmID
        | project-away vmID1, vmID2, osDiskId1
        | project vmID, vmSize, provisioningState, OS, resourceGroup, location, subscriptionId, SQLLicense, SQLImage, SQLSku, SQLManagement, FaultDomainCount, UpdateDomainCount, AvailabilitySetID, timeCreated
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_compute_vmss(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get VM Scale Sets inventory - sizes, capacity, OS, upgrade mode."""
        query = """
        resources
        | where type has 'microsoft.compute/virtualmachinescalesets'
        | extend Size = sku.name
        | extend Capacity = sku.capacity
        | extend UpgradeMode = properties.upgradePolicy.mode
        | extend OSType = properties.virtualMachineProfile.storageProfile.osDisk.osType
        | extend OS = properties.virtualMachineProfile.storageProfile.imageReference.offer
        | extend OSVersion = properties.virtualMachineProfile.storageProfile.imageReference.sku
        | extend OverProvision = properties.overprovision
        | extend ZoneBalance = properties.zoneBalance
        | project VMSS = id, location, resourceGroup, subscriptionId, Size, Capacity, OSType, UpgradeMode, OverProvision
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_compute_vm_networking(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get VM networking inventory - VMs with NICs, private IPs, public IPs."""
        query = """
        Resources
        | where type =~ 'microsoft.compute/virtualmachines'
        | extend nics=array_length(properties.networkProfile.networkInterfaces)
        | mv-expand nic=properties.networkProfile.networkInterfaces
        | where nics == 1 or nic.properties.primary =~ 'true' or isempty(nic)
        | project vmId = id, vmName = name, vmSize=tostring(properties.hardwareProfile.vmSize), nicId = tostring(nic.id)
        | join kind=leftouter (
            Resources
            | where type =~ 'microsoft.network/networkinterfaces'
            | extend ipConfigsCount=array_length(properties.ipConfigurations)
            | mv-expand ipconfig=properties.ipConfigurations
            | where ipConfigsCount == 1 or ipconfig.properties.primary =~ 'true'
            | project nicId = id, privateIP= tostring(ipconfig.properties.privateIPAddress), publicIpId = tostring(ipconfig.properties.publicIPAddress.id), subscriptionId
        ) on nicId
        | project-away nicId1
        | summarize by vmId, vmSize, nicId, privateIP, publicIpId, subscriptionId
        | join kind=leftouter (
            Resources
            | where type =~ 'microsoft.network/publicipaddresses'
            | project publicIpId = id, publicIpAddress = tostring(properties.ipAddress)
        ) on publicIpId
        | project-away publicIpId1
        | sort by publicIpAddress desc
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_compute_vm_disks(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get VM disk/storage inventory - OS disks and data disks per VM."""
        query = """
        Resources
        | where type == "microsoft.compute/virtualmachines"
        | extend osDiskId= tolower(tostring(properties.storageProfile.osDisk.managedDisk.id))
        | join kind=leftouter(
            resources
            | where type =~ 'microsoft.compute/disks'
            | where properties !has 'Unattached'
            | where properties has 'osType'
            | project timeCreated = tostring(properties.timeCreated), OS = tostring(properties.osType), osSku = tostring(sku.name), osDiskSizeGB = toint(properties.diskSizeGB), osDiskId=tolower(tostring(id))
        ) on osDiskId
        | join kind=leftouter(
            Resources
            | where type =~ 'microsoft.compute/disks'
            | where properties !has "osType"
            | where properties !has 'Unattached'
            | project sku = tostring(sku.name), diskSizeGB = toint(properties.diskSizeGB), id = managedBy
            | summarize DataDisksGB=sum(diskSizeGB), DataDiskCount=count(sku) by id, sku
        ) on id
        | project vmId=id, OS, location, resourceGroup, timeCreated, subscriptionId, osDiskId, osSku, osDiskSizeGB, DataDisksGB, DataDiskCount
        | sort by DataDiskCount desc
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_compute_arc(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get hybrid/ARC machines inventory - on-premises and multi-cloud servers connected via Azure ARC."""
        query = """
        resources
        | where type == "microsoft.hybridcompute/machines"
        | extend MachineId=id,
            NetworkProfile = properties.networkProfile,
            SerialNumber = tostring(properties.detectedProperties.serialNumber),
            OS = tostring(properties.osSku),
            Status = tostring(properties.status),
            FQDN = tostring(properties.dnsFqdn),
            LastSeen = todatetime(properties.lastStatusChange),
            ServerVersion = properties.osVersion
        | extend ServerVersion = case(
            ServerVersion has '10.0.20348', 'Server 2022',
            ServerVersion has '10.0.17763', 'Server 2019',
            ServerVersion has '10.0.14393', 'Server 2016',
            ServerVersion has '6.3.9600', 'Server 2012 R2',
            tostring(ServerVersion))
        | mv-expand nic = NetworkProfile.networkInterfaces
        | mv-expand IP = nic.ipAddresses
        | extend IP = tostring(IP.address)
        | summarize IPs = make_set(IP), arg_max(LastSeen, OS, FQDN, Status, SerialNumber) by MachineId
        | project MachineId, OS, FQDN, Status, SerialNumber, LastSeen, IPs
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_paas_automation(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get automation resources inventory - Automation Accounts, Logic Apps, Custom APIs, Runbooks."""
        query = """
        resources
        | where type has 'microsoft.automation'
            or type has 'microsoft.logic'
            or type has 'microsoft.web/customapis'
        | extend type = case(
            type =~ 'microsoft.automation/automationaccounts', 'Automation Accounts',
            type =~ 'microsoft.web/connections', 'LogicApp Connectors',
            type =~ 'microsoft.web/customapis','LogicApp API Connectors',
            type =~ 'microsoft.logic/workflows','LogicApps',
            type =~ 'microsoft.logic/integrationaccounts', 'Integration Accounts',
            type =~ 'microsoft.automation/automationaccounts/runbooks', 'Automation Runbooks',
            type =~ 'microsoft.automation/automationaccounts/configurations', 'Automation Configurations',
            strcat("Not Translated: ", type))
        | where type !has "Not Translated"
        | extend RunbookType = tostring(properties.runbookType)
        | extend State = case(
            type =~ 'Automation Runbooks', tostring(properties.state),
            type =~ 'LogicApps', tostring(properties.state),
            type =~ 'Automation Accounts', tostring(properties.state),
            type =~ 'Automation Configurations', tostring(properties.state),
            ' ')
        | project Resource=id, type, resourceGroup, subscriptionId, RunbookType, State, location
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_paas_apps(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get application resources inventory - App Services, Functions, API Management, Front Door, App Gateways."""
        query = """
        resources
        | where type has 'microsoft.web'
            or type =~ 'microsoft.apimanagement/service'
            or type =~ 'microsoft.network/frontdoors'
            or type =~ 'microsoft.network/applicationgateways'
            or type =~ 'microsoft.appconfiguration/configurationstores'
        | extend type = case(
            type == 'microsoft.web/serverfarms', strcat("App Service Plans - ", properties.kind),
            kind == 'functionapp', "Azure Functions",
            kind == "api", "API Apps",
            type == 'microsoft.web/sites', "App Services",
            type =~ 'microsoft.network/applicationgateways', 'App Gateways',
            type =~ 'microsoft.network/frontdoors', 'Front Door',
            type =~ 'microsoft.apimanagement/service', 'API Management',
            type =~ 'microsoft.web/certificates', 'App Certificates',
            type =~ 'microsoft.appconfiguration/configurationstores', 'App Config Stores',
            type =~ 'microsoft.web/connections', 'API Connections',
            strcat("Not Translated: ", type))
        | where type !has "Not Translated"
        | extend Sku = case(
            type =~ 'App Gateways', tostring(properties.sku.name),
            type =~ 'Azure Functions', tostring(properties.sku),
            type =~ 'API Management', tostring(sku.name),
            type contains 'App Service Plans', tostring(sku.name),
            type =~ 'App Services', tostring(properties.sku),
            type =~ 'App Config Stores', tostring(sku.name),
            ' ')
        | extend State = case(
            type =~ 'App Config Stores', tostring(properties.provisioningState),
            type contains 'App Service Plans', tostring(properties.status),
            type =~ 'Azure Functions', tostring(properties.enabled),
            type =~ 'App Services', tostring(properties.state),
            type =~ 'API Management', tostring(properties.provisioningState),
            type =~ 'App Gateways', tostring(properties.provisioningState),
            type =~ 'Front Door', tostring(properties.provisioningState),
            ' ')
        | project Resource=id, type, subscriptionId, resourceGroup, Sku, State, location
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_paas_containers(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get container resources inventory - AKS, ACR, ACI with details."""
        query = """
        resources
        | where type =~ 'microsoft.containerservice/managedclusters'
            or type =~ 'microsoft.containerregistry/registries'
            or type =~ 'microsoft.containerinstance/containergroups'
        | extend type = case(
            type =~ 'microsoft.containerservice/managedclusters', 'AKS',
            type =~ 'microsoft.containerregistry/registries', 'Container Registry',
            type =~ 'microsoft.containerinstance/containergroups', 'Container Instances',
            strcat("Not Translated: ", type))
        | extend Tier = sku.tier
        | extend sku = sku.name
        | extend State = case(
            type =~ 'Container Registry', tostring(properties.provisioningState),
            type =~ 'Container Instances', tostring(properties.instanceView.state),
            tostring(properties.powerState.code))
        | extend Version = properties.kubernetesVersion
        | extend AgentProfiles = properties.agentPoolProfiles
        | mvexpand AgentProfiles
        | extend NodeCount = AgentProfiles.["count"]
        | project id, type, location, resourceGroup, subscriptionId, sku, Tier, State, Version, NodeCount
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_paas_data(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get data platform inventory - SQL, CosmosDB, MySQL, PostgreSQL, Synapse, ADX, Data Factory, Purview."""
        query = """
        resources
        | where type has 'microsoft.documentdb'
            or type has 'microsoft.sql'
            or type has 'microsoft.dbformysql'
            or type has 'microsoft.purview'
            or type has 'microsoft.datafactory'
            or type has 'microsoft.analysisservices'
            or type has 'microsoft.datamigration'
            or type has 'microsoft.synapse'
            or type has 'microsoft.kusto'
            or type has 'microsoft.dbforpostgresql'
            or type has 'microsoft.digitaltwins'
        | extend type = case(
            type =~ 'microsoft.documentdb/databaseaccounts', 'CosmosDB',
            type =~ 'microsoft.sql/servers/databases', 'SQL DBs',
            type =~ 'microsoft.dbformysql/servers', 'MySQL',
            type =~ 'microsoft.sql/servers', 'SQL Servers',
            type =~ 'microsoft.purview/accounts', 'Purview Accounts',
            type =~ 'microsoft.synapse/workspaces/sqlpools', 'Synapse SQL Pools',
            type =~ 'microsoft.kusto/clusters', 'ADX Clusters',
            type =~ 'microsoft.datafactory/factories', 'Data Factories',
            type =~ 'microsoft.synapse/workspaces', 'Synapse Workspaces',
            type =~ 'microsoft.analysisservices/servers', 'Analysis Services',
            type =~ 'microsoft.datamigration/services', 'DB Migration Service',
            type =~ 'microsoft.sql/managedinstances/databases', 'Managed Instance DBs',
            type =~ 'microsoft.sql/managedinstances', 'Managed Instance',
            type =~ 'microsoft.datamigration/services/projects', 'Data Migration Projects',
            type =~ 'microsoft.sql/virtualclusters', 'SQL Virtual Clusters',
            type =~ 'microsoft.dbforpostgresql/servers', 'PostgreSQL DBs',
            type =~ 'microsoft.digitaltwins/digitaltwinsinstances', 'Digital Twins',
            strcat("Not Translated: ", type))
        | where type !has "Not Translated"
        | extend Sku = case(
            type =~ 'CosmosDB', tostring(properties.databaseAccountOfferType),
            type =~ 'SQL DBs', tostring(sku.name),
            type =~ 'MySQL', tostring(sku.name),
            type =~ 'ADX Clusters', tostring(sku.name),
            type =~ 'Purview Accounts', tostring(sku.name),
            type =~ 'PostgreSQL DBs', strcat(tostring(sku.tier), ', ', tostring(sku.family)),
            ' ')
        | extend Status = case(
            type =~ 'CosmosDB', tostring(properties.provisioningState),
            type =~ 'SQL DBs', tostring(properties.status),
            type =~ 'MySQL', tostring(properties.userVisibleState),
            type =~ 'Managed Instance DBs', tostring(properties.status),
            ' ')
        | extend Endpoint = case(
            type =~ 'MySQL', tostring(properties.fullyQualifiedDomainName),
            type =~ 'SQL Servers', tostring(properties.fullyQualifiedDomainName),
            type =~ 'CosmosDB', tostring(properties.documentEndpoint),
            type =~ 'ADX Clusters', tostring(properties.uri),
            type =~ 'Synapse Workspaces', tostring(properties.connectivityEndpoints),
            ' ')
        | extend Tier = sku.tier
        | project Resource=id, resourceGroup, subscriptionId, type, Sku, Tier, Status, Endpoint, location
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_paas_events(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get event/messaging resources inventory - Service Bus, Event Hub, Event Grid, Relay."""
        query = """
        resources
        | where type has 'microsoft.servicebus'
            or type has 'microsoft.eventhub'
            or type has 'microsoft.eventgrid'
            or type has 'microsoft.relay'
        | extend type = case(
            type == 'microsoft.eventgrid/systemtopics', "EventGrid System Topics",
            type =~ "microsoft.eventgrid/topics", "EventGrid Topics",
            type =~ 'microsoft.eventhub/namespaces', "EventHub Namespaces",
            type =~ 'microsoft.servicebus/namespaces', 'ServiceBus Namespaces',
            type =~ 'microsoft.relay/namespaces', 'Relays',
            strcat("Not Translated: ", type))
        | where type !has "Not Translated"
        | extend Sku = case(
            type =~ 'Relays', tostring(sku.name),
            type =~ 'EventGrid Topics', tostring(sku.name),
            type =~ 'EventHub Namespaces', tostring(sku.name),
            type =~ 'ServiceBus Namespaces', tostring(sku.name),
            ' ')
        | extend Status = case(
            type =~ 'Relays', tostring(properties.provisioningState),
            type =~ 'EventGrid System Topics', tostring(properties.provisioningState),
            type =~ 'EventGrid Topics', tostring(properties.publicNetworkAccess),
            type =~ 'EventHub Namespaces', tostring(properties.status),
            type =~ 'ServiceBus Namespaces', tostring(properties.status),
            ' ')
        | extend Endpoint = case(
            type =~ 'Relays', tostring(properties.serviceBusEndpoint),
            type =~ 'EventGrid Topics', tostring(properties.endpoint),
            type =~ 'EventHub Namespaces', tostring(properties.serviceBusEndpoint),
            type =~ 'ServiceBus Namespaces', tostring(properties.serviceBusEndpoint),
            ' ')
        | project Resource=id, type, subscriptionId, resourceGroup, Sku, Status, Endpoint, location
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_paas_iot(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get IoT resources inventory - IoT Hubs, IoT Central Apps, IoT Security Solutions."""
        query = """
        resources
        | where type =~ 'microsoft.devices/iothubs'
            or type =~ 'microsoft.iotcentral/iotapps'
            or type =~ 'microsoft.security/iotsecuritysolutions'
        | extend type = case(
            type =~ 'microsoft.devices/iothubs', 'IoT Hubs',
            type =~ 'microsoft.iotcentral/iotapps', 'IoT Apps',
            type =~ 'microsoft.security/iotsecuritysolutions', 'IoT Security',
            strcat("Not Translated: ", type))
        | extend Tier = sku.tier
        | extend sku = sku.name
        | extend State = tostring(properties.state)
        | extend HostName = tostring(properties.hostName)
        | extend EventHubEndPoint = tostring(properties.eventHubEndpoints.events.endpoint)
        | project id, type, location, resourceGroup, subscriptionId, sku, Tier, State, HostName, EventHubEndPoint
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_paas_mlai(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get ML/AI resources inventory - Machine Learning Workspaces, Cognitive Services, OpenAI."""
        query = """
        resources
        | where type =~ 'Microsoft.MachineLearningServices/workspaces'
            or type =~ 'microsoft.cognitiveservices/accounts'
        | extend type = case(
            type =~ 'Microsoft.MachineLearningServices/workspaces', 'ML Workspaces',
            type =~ 'microsoft.cognitiveservices/accounts', 'Cognitive Services',
            strcat("Not Translated: ", type))
        | where type !has "Not Translated"
        | extend Tier = sku.tier
        | extend sku = sku.name
        | extend Endpoint = case(
            type =~ 'ML Workspaces', tostring(properties.discoveryUrl),
            type =~ 'Cognitive Services', tostring(properties.endpoint),
            ' ')
        | extend Storage = tostring(properties.storageAccount)
        | extend AppInsights = tostring(properties.applicationInsights)
        | project id, type, location, resourceGroup, subscriptionId, sku, Tier, Endpoint, Storage, AppInsights
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_paas_storage(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get storage & backup inventory - Storage Accounts, Key Vaults, Recovery Services, Azure File Sync."""
        query = """
        resources
        | where type =~ 'microsoft.storagesync/storagesyncservices'
            or type =~ 'microsoft.recoveryservices/vaults'
            or type =~ 'microsoft.storage/storageaccounts'
            or type =~ 'microsoft.keyvault/vaults'
        | extend type = case(
            type =~ 'microsoft.storagesync/storagesyncservices', 'Azure File Sync',
            type =~ 'microsoft.recoveryservices/vaults', 'Azure Backup',
            type =~ 'microsoft.storage/storageaccounts', 'Storage Accounts',
            type =~ 'microsoft.keyvault/vaults', 'Key Vaults',
            strcat("Not Translated: ", type))
        | extend Sku = case(
            type !has 'Key Vaults', tostring(sku.name),
            type =~ 'Key Vaults', tostring(properties.sku.name),
            ' ')
        | project Resource=id, type, kind, subscriptionId, resourceGroup, Sku, location
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_paas_wvd(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Windows Virtual Desktop / Azure Virtual Desktop inventory - Host Pools, Workspaces, App Groups."""
        query = """
        resources
        | where type has 'microsoft.desktopvirtualization'
        | extend type = case(
            type =~ 'microsoft.desktopvirtualization/applicationgroups', 'AVD App Groups',
            type =~ 'microsoft.desktopvirtualization/hostpools', 'AVD Host Pools',
            type =~ 'microsoft.desktopvirtualization/workspaces', 'AVD Workspaces',
            strcat("Not Translated: ", type))
        | where type !has "Not Translated"
        | project id, type, resourceGroup, subscriptionId, kind, location
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_networking(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get networking resources overview - all network resource types with counts."""
        query = """
        Resources
        | where type has "microsoft.network"
            or type has 'microsoft.cdn'
        | summarize Count=count() by type
        | order by Count desc
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_networking_nsgs(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get NSG inventory including unassociated NSGs. Shows NSGs with their association status."""
        query = """
        Resources
        | where type =~ 'microsoft.network/networksecuritygroups'
        | extend HasNIC = isnotnull(properties.networkInterfaces)
        | extend HasSubnet = isnotnull(properties.subnets)
        | extend IsUnassociated = iif(isnull(properties.networkInterfaces) and isnull(properties.subnets), true, false)
        | project Resource=id, resourceGroup, subscriptionId, location, HasNIC, HasSubnet, IsUnassociated
        | order by IsUnassociated desc
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_networking_nsg_rules(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get NSG security rules inventory - all rules across all NSGs with access, direction, ports."""
        query = """
        Resources
        | where type =~ 'microsoft.network/networksecuritygroups'
        | project id, nsgRules = parse_json(parse_json(properties).securityRules), networksecurityGroupName = name, subscriptionId, resourceGroup, location
        | mvexpand nsgRule = nsgRules
        | project id, location,
            access=nsgRule.properties.access,
            protocol=nsgRule.properties.protocol,
            direction=nsgRule.properties.direction,
            priority=nsgRule.properties.priority,
            sourceAddressPrefix = nsgRule.properties.sourceAddressPrefix,
            destinationAddressPrefix = nsgRule.properties.destinationAddressPrefix,
            networksecurityGroupName,
            networksecurityRuleName = tostring(nsgRule.name),
            subscriptionId, resourceGroup,
            destinationPortRange = nsgRule.properties.destinationPortRange,
            sourcePortRange = nsgRule.properties.sourcePortRange
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_networking_ip(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get IP address inventory per subnet - shows used/available IPs across VNets and subnets."""
        query = """
        resources
        | where type =~ 'Microsoft.Network/virtualNetworks'
        | extend addressPrefixes=array_length(properties.addressSpace.addressPrefixes)
        | extend vNetAddressSpace=properties.addressSpace.addressPrefixes
        | mv-expand subnet=properties.subnets
        | extend virtualNetwork = name
        | extend subnetPrefix = subnet.properties.addressPrefix
        | extend subnetName = tostring(subnet.name)
        | extend prefixLength = toint(split(subnetPrefix, "/")[1])
        | extend numberOfIpAddresses = case(
            prefixLength == 29, 3,
            prefixLength == 28, 11,
            prefixLength == 27, 27,
            prefixLength == 26, 59,
            prefixLength == 25, 123,
            prefixLength == 24, 251,
            prefixLength == 23, 507,
            prefixLength == 22, 1019,
            prefixLength == 21, 2043,
            prefixLength == 20, 4091,
            prefixLength == 19, 8187,
            prefixLength == 18, 16379,
            prefixLength == 17, 32763,
            prefixLength == 16, 65531,
            0)
        | join kind=leftouter (
            resources
            | where type =~ 'microsoft.network/networkinterfaces'
            | project id, ipConfigurations = properties.ipConfigurations, subscriptionId
            | mvexpand ipConfigurations
            | project id, subnetId = tostring(ipConfigurations.properties.subnet.id), subscriptionId
            | parse kind=regex subnetId with '/virtualNetworks/' virtualNetwork '/subnets/' subnet
            | extend resourceGroup = tostring(split(subnetId,"/",4)[0])
            | extend subnetName = subnet
            | summarize usedIPAddresses = count() by subnetName, virtualNetwork, subscriptionId
        ) on subnetName, virtualNetwork, subscriptionId
        | extend usedIPAddresses = iff(isnull(usedIPAddresses),0,usedIPAddresses)
        | project subscriptionId, resourceGroup, virtualNetwork, SubnetName = subnetName, numberOfIpAddresses, usedIPAddresses, AvailableIPAddresses = (toint(numberOfIpAddresses) - usedIPAddresses)
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_monitoring_alerts(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get active fired alerts from Azure Monitor."""
        query = """
        AlertsManagementResources
        | extend AlertStatus = tostring(properties.essentials.monitorCondition)
        | extend AlertState = tostring(properties.essentials.alertState)
        | extend AlertTime = tostring(properties.essentials.startDateTime)
        | extend AlertSuppressed = tostring(properties.essentials.actionStatus.isSuppressed)
        | extend Severity = tostring(properties.essentials.severity)
        | where AlertStatus == 'Fired'
        | project id, name, subscriptionId, resourceGroup, AlertStatus, AlertState, AlertTime, AlertSuppressed, Severity
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_monitoring_resources(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get monitoring/alerting resources - Workbooks, Alert Rules, Action Groups, Dashboards."""
        query = """
        resources
        | where type has 'microsoft.insights/'
            or type has 'microsoft.alertsmanagement/smartdetectoralertrules'
            or type has 'microsoft.portal/dashboards'
        | where type != 'microsoft.insights/components'
        | extend type = case(
            type == 'microsoft.insights/workbooks', "Workbooks",
            type == 'microsoft.insights/activitylogalerts', "Activity Log Alerts",
            type == 'microsoft.insights/scheduledqueryrules', "Log Search Alerts",
            type == 'microsoft.insights/actiongroups', "Action Groups",
            type == 'microsoft.insights/metricalerts', "Metric Alerts",
            type =~ 'microsoft.alertsmanagement/smartdetectoralertrules','Smart Detection Rules',
            type =~ 'microsoft.insights/webtests', 'URL Web Tests',
            type =~ 'microsoft.portal/dashboards', 'Portal Dashboards',
            type =~ 'microsoft.insights/datacollectionrules', 'Data Collection Rules',
            type =~ 'microsoft.insights/autoscalesettings', 'Auto Scale Settings',
            type =~ 'microsoft.insights/datacollectionendpoints', 'Data Collection Endpoints',
            strcat("Not Translated: ", type))
        | where type !has "Not Translated"
        | extend Enabled = case(
            type =~ 'Smart Detection Rules', tostring(properties.state),
            tostring(properties.enabled))
        | project name, type, subscriptionId, location, resourceGroup, Enabled
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_monitoring_appinsights(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Application Insights inventory - components with retention and ingestion mode."""
        query = """
        Resources
        | where type =~ 'microsoft.insights/components'
        | extend RetentionInDays = tostring(properties.RetentionInDays)
        | extend IngestionMode = tostring(properties.IngestionMode)
        | project Resource=id, location, resourceGroup, subscriptionId, IngestionMode, RetentionInDays
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_monitoring_log_analytics(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Log Analytics workspace inventory - workspaces with SKU and retention settings."""
        query = """
        Resources
        | where type =~ 'microsoft.operationalinsights/workspaces'
        | extend Sku = tostring(properties.sku.name)
        | extend RetentionInDays = tostring(properties.retentionInDays)
        | project Workspace=id, resourceGroup, location, subscriptionId, Sku, RetentionInDays
        """
        return self.query_resources(query, subscriptions)

    def get_inventory_security_scores(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get Azure Security Center secure scores and controls by subscription."""
        score_query = """
        securityresources
        | where type == "microsoft.security/securescores"
        | extend subscriptionSecureScore = round(100 * bin((todouble(properties.score.current))/ todouble(properties.score.max), 0.001))
        | where subscriptionSecureScore > 0
        | project subscriptionSecureScore, subscriptionId
        | order by subscriptionSecureScore asc
        """
        scores = self.query_resources(score_query, subscriptions)

        controls_query = """
        SecurityResources
        | where type == 'microsoft.security/securescores/securescorecontrols'
        | extend SecureControl = tostring(properties.displayName), unhealthy = toint(properties.unhealthyResourceCount), currentscore = tostring(properties.score.current), maxscore = tostring(properties.score.max), subscriptionId
        | project SecureControl, unhealthy, currentscore, maxscore, subscriptionId
        """
        controls = self.query_resources(controls_query, subscriptions)

        return {
            "inventory_type": "security_scores",
            "secure_scores": scores,
            "secure_controls": controls
        }

    def get_inventory_governance_policy(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get governance policy inventory - policy assignments, compliance status, initiatives deployed."""
        query = """
        policyresources
        | where type =~ 'microsoft.policyinsights/policystates'
        | extend AssignmentName = tostring(properties.policyAssignmentName),
            Initiative = tostring(properties.policySetDefinitionId),
            PolicyDefintion = tostring(properties.policyDefinitionId),
            Compliance = tostring(properties.complianceState),
            Scope = tostring(properties.policyAssignmentScope),
            PolicyAction = tostring(properties.policyDefinitionAction),
            ResourceType = tostring(properties.resourceType)
        | summarize Assignments = count(AssignmentName),
            InitiativesDeployed = dcountif(Initiative, isnotnull(Initiative)),
            PoliciesDeployed = dcountif(PolicyDefintion, isempty(Initiative)),
            CompliantResources = countif(Compliance == 'Compliant'),
            NonCompliantResources = countif(Compliance != 'Compliant') by subscriptionId
        | order by Assignments desc
        """
        return self.query_resources(query, subscriptions)

    def get_all_inventory_summary(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get a comprehensive inventory summary across all Azure resource categories."""
        summary = {
            "inventory_type": "full_summary",
            "categories": {},
            "total_resources": 0
        }

        checks = [
            ("Overview", self.get_inventory_overview),
            ("Compute - VMs", self.get_inventory_compute_vms),
            ("Compute - VMSS", self.get_inventory_compute_vmss),
            ("Compute - ARC Machines", self.get_inventory_compute_arc),
            ("PaaS - Automation", self.get_inventory_paas_automation),
            ("PaaS - Applications", self.get_inventory_paas_apps),
            ("PaaS - Containers", self.get_inventory_paas_containers),
            ("PaaS - Data Platform", self.get_inventory_paas_data),
            ("PaaS - Events/Messaging", self.get_inventory_paas_events),
            ("PaaS - IoT", self.get_inventory_paas_iot),
            ("PaaS - ML/AI", self.get_inventory_paas_mlai),
            ("PaaS - Storage & Backup", self.get_inventory_paas_storage),
            ("PaaS - Virtual Desktop", self.get_inventory_paas_wvd),
            ("Networking", self.get_inventory_networking),
            ("Networking - NSGs", self.get_inventory_networking_nsgs),
            ("Monitoring - Alerts", self.get_inventory_monitoring_alerts),
            ("Monitoring - Resources", self.get_inventory_monitoring_resources),
            ("Monitoring - App Insights", self.get_inventory_monitoring_appinsights),
            ("Monitoring - Log Analytics", self.get_inventory_monitoring_log_analytics),
            ("Security Scores", self.get_inventory_security_scores),
            ("Governance - Policy", self.get_inventory_governance_policy),
        ]

        for name, func in checks:
            try:
                result = func(subscriptions)
                count = result.get("count", 0) or result.get("total_records", 0) or 0
                summary["categories"][name] = {
                    "count": count,
                    "label": f"{name}: {count} resources"
                }
                summary["total_resources"] += count
            except Exception as e:
                summary["categories"][name] = {"count": 0, "error": str(e)}

        return summary

    # ==========================================
    # CLOUD OPERATIONS HEALTH ASSESSMENT
    # Based on: https://github.com/Azure/cloud-rolesandops
    # Management Score + Environment + Operational Tasks
    # ==========================================

    def get_advisor_health_score(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Azure Advisor Management Score — percentage of resources WITHOUT active advisor recommendations."""
        query = """
        resources
        | summarize resourcetotal=count()
        | project key=1, resourcetotal
        | join (
            advisorresources
            | where type == 'microsoft.advisor/recommendations'
            | distinct tostring(properties.impactedValue)
            | summarize advisoraffectedresourcetotal=count()
            | project key=1, advisoraffectedresourcetotal
        ) on key
        | project
            AdvisorManagementScore = iif(resourcetotal > 0, round(toreal(resourcetotal - advisoraffectedresourcetotal) / toreal(resourcetotal) * 100, 1), 0.0),
            TotalResources = resourcetotal,
            ResourcesWithRecommendations = advisoraffectedresourcetotal,
            HealthyResources = resourcetotal - advisoraffectedresourcetotal
        """
        score_result = self.query_resources(query, subscriptions)
        # Fetch resource-level detail: top impacted resources with recommendation info
        detail_query = """
        advisorresources
        | where type == 'microsoft.advisor/recommendations'
        | extend Category = tostring(properties.category)
        | extend Impact = tostring(properties.impact)
        | extend Problem = tostring(properties.shortDescription.problem)
        | extend Solution = tostring(properties.shortDescription.solution)
        | extend ResourceName = tostring(properties.impactedValue)
        | extend ResourceType = tostring(properties.impactedField)
        | project ResourceName, ResourceType, Category, Impact, Problem, Solution, ResourceGroup=resourceGroup, Location=location, SubscriptionId=subscriptionId
        | order by Impact asc, Category asc
        | take 30
        """
        detail_result = self.query_resources(detail_query, subscriptions)
        # Merge: attach resource_details to score result
        if isinstance(score_result, dict) and "error" not in score_result:
            score_result["resource_details"] = detail_result.get("data", []) if isinstance(detail_result, dict) else []
        return score_result

    def get_advisor_recommendations_breakdown(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Azure Advisor recommendations breakdown by category and impact."""
        query = """
        advisorresources
        | where type == 'microsoft.advisor/recommendations'
        | extend Category = tostring(properties.category)
        | extend Category = replace('HighAvailability', 'Reliability', Category)
        | extend Description = tostring(properties.shortDescription.problem)
        | extend ImpactedField = tostring(properties.impactedField)
        | extend ImpactedValue = tostring(properties.impactedValue)
        | extend Impact = tostring(properties.impact)
        | extend LastUpdated = tostring(properties.lastUpdated)
        | project Impact, ImpactedField, ImpactedValue, Description, resourceGroup, subscriptionId, Category, LastUpdated
        | summarize Count = count() by Category, Impact
        | order by Category asc, Impact desc
        """
        return self.query_resources(query, subscriptions)

    def get_backup_protection_score(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Azure Backup Management Score — percentage of VMs protected by backup."""
        query = """
        resources
        | where type in~ ('microsoft.compute/virtualmachines','microsoft.classiccompute/virtualmachines')
        | extend resourceId=tolower(id)
        | join kind = leftouter (
            recoveryservicesresources
            | where type == 'microsoft.recoveryservices/vaults/backupfabrics/protectioncontainers/protecteditems'
            | extend protectedResourceId = tolower(tostring(properties.sourceResourceId))
            | project protectedResourceId
        ) on $left.resourceId == $right.protectedResourceId
        | summarize
            VMTotal = count(),
            Protected = countif(isnotempty(protectedResourceId)),
            Unprotected = countif(isempty(protectedResourceId))
        | project
            BackupManagementScore = iif(VMTotal > 0, round(toreal(Protected) / toreal(VMTotal) * 100, 1), 0.0),
            VMTotal, Protected, Unprotected, key=1
        """
        score_result = self.query_resources(query, subscriptions)
        # Fetch resource-level detail: unprotected VMs
        detail_query = """
        resources
        | where type in~ ('microsoft.compute/virtualmachines','microsoft.classiccompute/virtualmachines')
        | extend resourceId=tolower(id)
        | join kind = leftouter (
            recoveryservicesresources
            | where type == 'microsoft.recoveryservices/vaults/backupfabrics/protectioncontainers/protecteditems'
            | extend protectedResourceId = tolower(tostring(properties.sourceResourceId))
            | project protectedResourceId
        ) on $left.resourceId == $right.protectedResourceId
        | extend BackupStatus = iif(isnotempty(protectedResourceId), 'Protected', 'Unprotected')
        | where BackupStatus == 'Unprotected'
        | project VMName=name, ResourceGroup=resourceGroup, Location=location, BackupStatus, SubscriptionId=subscriptionId
        | order by ResourceGroup asc
        | take 50
        """
        detail_result = self.query_resources(detail_query, subscriptions)
        if isinstance(score_result, dict) and "error" not in score_result:
            score_result["resource_details"] = detail_result.get("data", []) if isinstance(detail_result, dict) else []
        return score_result

    def get_monitor_alerts_score(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Azure Monitor Management Score — alert response effectiveness based on fired, acknowledged, and closed alerts."""
        query = """
        resources
        | summarize resourcetotal=count()
        | project key=1, resourcetotal
        | join kind=leftouter (
            alertsmanagementresources
            | where type == 'microsoft.alertsmanagement/alerts'
            | extend alertState = tostring(properties.essentials.alertState)
            | extend monitorCondition = tostring(properties.essentials.monitorCondition)
            | summarize
                TotalAlerts = count(),
                New = countif(alertState == 'New'),
                Acknowledged = countif(alertState == 'Acknowledged'),
                Closed = countif(alertState == 'Closed'),
                Fired = countif(monitorCondition == 'Fired'),
                Resolved = countif(monitorCondition == 'Resolved')
            | extend pctClosed = iif(TotalAlerts > 0, round(toreal(Closed) / toreal(TotalAlerts) * 100, 1), 0.0)
            | extend pctAck = iif(TotalAlerts > 0, round(toreal(Acknowledged) / toreal(TotalAlerts) * 100, 1), 0.0)
            | project key=1, TotalAlerts, New, Acknowledged, Closed, Fired, Resolved, pctClosed, pctAck
        ) on key
        | extend TotalAlerts = coalesce(TotalAlerts, 0)
        | extend Fired = coalesce(Fired, 0)
        | extend pctClosed = coalesce(pctClosed, 0.0)
        | extend pctAck = coalesce(pctAck, 0.0)
        | extend Flag1 = iif(Fired > 0 and pctClosed < 20.0, 33.3, 0.0)
        | extend Flag2 = iif(Fired > 0 and pctAck < 50.0, 33.3, 0.0)
        | extend Flag3 = iif(TotalAlerts > resourcetotal, 33.3, 0.0)
        | project
            MonitorManagementScore = round(100.0 - Flag1 - Flag2 - Flag3, 1),
            TotalResources = resourcetotal,
            TotalAlerts, New = coalesce(New, 0), Acknowledged = coalesce(Acknowledged, 0),
            Closed = coalesce(Closed, 0), Fired, Resolved = coalesce(Resolved, 0),
            ClosedPct = pctClosed, AcknowledgedPct = pctAck
        """
        score_result = self.query_resources(query, subscriptions)
        # Fetch resource-level detail: active unresolved alerts
        detail_query = """
        alertsmanagementresources
        | where type == 'microsoft.alertsmanagement/alerts'
        | extend alertState = tostring(properties.essentials.alertState)
        | where alertState != 'Closed'
        | extend severity = tostring(properties.essentials.severity)
        | extend monitorCondition = tostring(properties.essentials.monitorCondition)
        | extend targetResource = tostring(properties.essentials.targetResourceName)
        | extend targetResourceType = tostring(properties.essentials.targetResourceType)
        | extend targetResourceGroup = tostring(properties.essentials.targetResourceGroup)
        | extend signalType = tostring(properties.essentials.signalType)
        | extend startDateTime = tostring(properties.essentials.startDateTime)
        | extend alertName = name
        | project AlertName=alertName, Severity=severity, State=alertState, Condition=monitorCondition, TargetResource=targetResource, ResourceType=targetResourceType, TargetResourceGroup=targetResourceGroup, SignalType=signalType, StartTime=startDateTime, ResourceGroup=resourceGroup, Location=location, SubscriptionId=subscriptionId
        | order by Severity asc
        | take 30
        """
        detail_result = self.query_resources(detail_query, subscriptions)
        if isinstance(score_result, dict) and "error" not in score_result:
            score_result["resource_details"] = detail_result.get("data", []) if isinstance(detail_result, dict) else []
        return score_result

    def get_security_posture_score(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Defender for Cloud Management Score — percentage of healthy security assessments."""
        query = """
        securityresources
        | where type == "microsoft.security/assessments"
        | extend status = properties.status.code
        | project tostring(status)
        | summarize
            TotalRecommendations = countif(status <> ""),
            HealthyRecommendations = countif(status == "Healthy"),
            UnhealthyRecommendations = countif(status == "Unhealthy"),
            NotApplicableRecommendations = countif(status == "NotApplicable")
        | project
            DefenderManagementScore = iif(TotalRecommendations - NotApplicableRecommendations > 0,
                round(toreal(HealthyRecommendations) / toreal(TotalRecommendations - NotApplicableRecommendations) * 100, 1), 0.0),
            TotalRecommendations, HealthyRecommendations, UnhealthyRecommendations, NotApplicableRecommendations,
            TotalMinNA = TotalRecommendations - NotApplicableRecommendations
        """
        score_result = self.query_resources(query, subscriptions)
        # Fetch resource-level detail: top unhealthy security assessments with parsed resource context
        detail_query = """
        securityresources
        | where type == "microsoft.security/assessments"
        | extend status = tostring(properties.status.code)
        | where status == "Unhealthy"
        | extend displayName = tostring(properties.displayName)
        | extend severity = tostring(properties.metadata.severity)
        | extend category = tostring(properties.metadata.categories[0])
        | extend description = tostring(properties.metadata.description)
        | extend remediation = tostring(properties.metadata.remediationDescription)
        | extend resourceSource = tostring(properties.resourceDetails.Id)
        | extend parsedParts = split(resourceSource, '/')
        | extend ResourceName = iif(array_length(parsedParts) > 0, tostring(parsedParts[array_length(parsedParts)-1]), 'Unknown')
        | extend ResourceGroup = iif(array_length(parsedParts) >= 5, tostring(parsedParts[4]), resourceGroup)
        | project Finding=displayName, Severity=severity, Category=category, ResourceName, ResourceGroup, Description=description, Remediation=remediation, AffectedResourceId=resourceSource, Location=location, SubscriptionId=subscriptionId
        | order by Severity asc
        | take 30
        """
        detail_result = self.query_resources(detail_query, subscriptions)
        if isinstance(score_result, dict) and "error" not in score_result:
            score_result["resource_details"] = detail_result.get("data", []) if isinstance(detail_result, dict) else []
        return score_result

    def get_update_compliance_score(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Update Management Score — based on system update assessment (assessment ID 4ab6e3c5-74dd-8b35-9ab9-f61b30875b27)."""
        query = """
        securityresources
        | where type == "microsoft.security/assessments"
        | where name == "4ab6e3c5-74dd-8b35-9ab9-f61b30875b27"
        | extend state = tostring(properties.status.code)
        | extend cause = trim(" ", tostring(properties.status.cause))
        | summarize
            Total = count(),
            Healthy = countif(tostring(state) == "Healthy"),
            Unhealthy = countif(tostring(state) == "Unhealthy"),
            NotApplicable = countif(tostring(state) == "NotApplicable"),
            NotApplicableOffByPolicy = countif(cause == "OffByPolicy"),
            NotApplicableVmNotReportingHB = countif(cause == "VmNotReportingHB")
        | extend Applicable = Total - NotApplicable
        | project
            UpdateManagementScore = iif(Applicable > 0, round(toreal(Healthy) / toreal(Applicable) * 100, 1), 0.0),
            Total, Healthy, Unhealthy, NotApplicable,
            OffByPolicy = NotApplicableOffByPolicy,
            NotReportingHeartbeat = NotApplicableVmNotReportingHB, key=1
        """
        score_result = self.query_resources(query, subscriptions)
        # Fetch resource-level detail: VMs needing updates with parsed resource context
        detail_query = """
        securityresources
        | where type == "microsoft.security/assessments"
        | where name == "4ab6e3c5-74dd-8b35-9ab9-f61b30875b27"
        | extend state = tostring(properties.status.code)
        | where state == "Unhealthy"
        | extend resourceId = tostring(properties.resourceDetails.Id)
        | extend cause = tostring(properties.status.cause)
        | extend description = tostring(properties.status.description)
        | extend parsedParts = split(resourceId, '/')
        | extend ResourceName = iif(array_length(parsedParts) > 0, tostring(parsedParts[array_length(parsedParts)-1]), 'Unknown')
        | extend ResourceGroup = iif(array_length(parsedParts) >= 5, tostring(parsedParts[4]), resourceGroup)
        | extend ResourceType = iif(array_length(parsedParts) >= 8, strcat(tostring(parsedParts[6]), '/', tostring(parsedParts[7])), '')
        | project ResourceName, ResourceGroup, ResourceType, State=state, Cause=cause, Description=description, Location=location, SubscriptionId=subscriptionId, FullResourceId=resourceId
        | take 30
        """
        detail_result = self.query_resources(detail_query, subscriptions)
        if isinstance(score_result, dict) and "error" not in score_result:
            score_result["resource_details"] = detail_result.get("data", []) if isinstance(detail_result, dict) else []
        return score_result

    def get_policy_compliance_score(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Azure Policy Management Score — percentage of compliant policy resources."""
        query = """
        policyresources
        | where type == "microsoft.policyinsights/policystates"
        | where properties.complianceState <> ""
        | extend complianceState = tostring(properties.complianceState)
        | summarize
            TotalResources = count(),
            Compliant = countif(complianceState == "Compliant"),
            Noncompliant = countif(complianceState == "NonCompliant"),
            Exempt = countif(complianceState == "Exempt")
        | project
            PolicyManagementScore = iif(TotalResources - Exempt > 0,
                toint(round(toreal(Compliant) / toreal(TotalResources - Exempt) * 100, 0)), 0),
            Compliant, Noncompliant, Exempt, key=1
        """
        score_result = self.query_resources(query, subscriptions)
        # Fetch resource-level detail: top noncompliant resources with parsed resource context
        detail_query = """
        policyresources
        | where type == "microsoft.policyinsights/policystates"
        | extend complianceState = tostring(properties.complianceState)
        | where complianceState == "NonCompliant"
        | extend policyName = tostring(properties.policyDefinitionName)
        | extend policyAssignment = tostring(properties.policyAssignmentName)
        | extend resourceId = tostring(properties.resourceId)
        | extend resourceType = tostring(properties.resourceType)
        | extend resourceLocation = tostring(properties.resourceLocation)
        | extend parsedParts = split(resourceId, '/')
        | extend ResourceName = iif(array_length(parsedParts) > 0, tostring(parsedParts[array_length(parsedParts)-1]), 'Unknown')
        | extend ResourceGroup = iif(array_length(parsedParts) >= 5, tostring(parsedParts[4]), '')
        | project PolicyAssignment=policyAssignment, PolicyDefinition=policyName, ResourceName, ResourceGroup, ResourceType=resourceType, Location=resourceLocation, SubscriptionId=subscriptionId, FullResourceId=resourceId
        | take 30
        """
        detail_result = self.query_resources(detail_query, subscriptions)
        if isinstance(score_result, dict) and "error" not in score_result:
            score_result["resource_details"] = detail_result.get("data", []) if isinstance(detail_result, dict) else []
        return score_result

    def get_overall_ops_health_score(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Overall Cloud Operations Health — runs all 6 management pillar assessments and computes a combined score with resource-level insights."""
        score_components = []

        assessments = [
            ("Azure Advisor", self.get_advisor_health_score),
            ("Azure Backup", self.get_backup_protection_score),
            ("Azure Monitor", self.get_monitor_alerts_score),
            ("Defender for Cloud", self.get_security_posture_score),
            ("Update Management", self.get_update_compliance_score),
            ("Azure Policy", self.get_policy_compliance_score),
        ]

        for name, method in assessments:
            try:
                result = method(subscriptions=subscriptions)
                data = result.get("data", [])
                resource_details = result.get("resource_details", [])
                if data and len(data) > 0:
                    row = data[0]
                    score_key = [k for k in row.keys() if "Score" in k or "score" in k]
                    if score_key:
                        score_val = row[score_key[0]]
                        score_components.append({
                            "pillar": name,
                            "score": score_val,
                            "details": row,
                            "resource_details": resource_details[:15],
                            "affected_resource_count": len(resource_details)
                        })
                    else:
                        score_components.append({"pillar": name, "score": "N/A", "details": row, "resource_details": resource_details[:15], "affected_resource_count": len(resource_details)})
                else:
                    score_components.append({"pillar": name, "score": "N/A", "details": "No data returned", "resource_details": [], "affected_resource_count": 0})
            except Exception as e:
                score_components.append({"pillar": name, "score": "Error", "details": str(e), "resource_details": [], "affected_resource_count": 0})

        # Calculate overall score as average of numeric scores
        numeric_scores = [s["score"] for s in score_components if isinstance(s["score"], (int, float))]
        overall_score = round(sum(numeric_scores) / len(numeric_scores), 1) if numeric_scores else 0

        # Determine health grade
        if overall_score >= 90:
            grade = "A — Excellent"
        elif overall_score >= 75:
            grade = "B — Good"
        elif overall_score >= 60:
            grade = "C — Needs Improvement"
        elif overall_score >= 40:
            grade = "D — At Risk"
        else:
            grade = "F — Critical"

        # Build priority actions from lowest-scoring pillars
        sorted_pillars = sorted(
            [s for s in score_components if isinstance(s["score"], (int, float))],
            key=lambda x: x["score"]
        )
        priority_actions = []
        for p in sorted_pillars[:3]:
            if p["score"] < 50:
                priority_actions.append(f"CRITICAL: {p['pillar']} is at {p['score']}% — immediate action required")
            elif p["score"] < 75:
                priority_actions.append(f"WARNING: {p['pillar']} is at {p['score']}% — improvement recommended")

        return {
            "query_name": "Overall Cloud Operations Health Score",
            "overall_management_score": overall_score,
            "health_grade": grade,
            "pillars_assessed": len(score_components),
            "pillars_with_data": len(numeric_scores),
            "pillar_scores": score_components,
            "priority_actions": priority_actions,
            "scoring_methodology": "Average of 6 management pillars: Advisor, Backup, Monitor, Defender, Update, Policy (based on Azure Cloud Roles & Ops framework)",
            "source": "https://github.com/Azure/cloud-rolesandops"
        }

    def get_environment_overview(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Environment Overview — comprehensive snapshot of monitoring, security, and operational resources."""
        query = """
        resources
        | where type in (
            'microsoft.operationalinsights/workspaces',
            'microsoft.insights/components',
            'microsoft.insights/actiongroups',
            'microsoft.insights/activitylogalerts',
            'microsoft.insights/metricalerts',
            'microsoft.insights/scheduledqueryrules',
            'microsoft.automation/automationaccounts',
            'microsoft.logic/workflows',
            'microsoft.keyvault/vaults',
            'microsoft.recoveryservices/vaults',
            'microsoft.security/automations',
            'microsoft.network/networkwatchers',
            'microsoft.network/networksecuritygroups',
            'microsoft.network/azurefirewalls',
            'microsoft.web/serverfarms',
            'microsoft.compute/virtualmachines',
            'microsoft.sql/servers',
            'microsoft.storage/storageaccounts'
        )
        | extend resourceType = case(
            type =~ 'microsoft.operationalinsights/workspaces', 'Log Analytics Workspaces',
            type =~ 'microsoft.insights/components', 'Application Insights',
            type =~ 'microsoft.insights/actiongroups', 'Action Groups',
            type =~ 'microsoft.insights/activitylogalerts', 'Activity Log Alerts',
            type =~ 'microsoft.insights/metricalerts', 'Metric Alerts',
            type =~ 'microsoft.insights/scheduledqueryrules', 'Log Alert Rules',
            type =~ 'microsoft.automation/automationaccounts', 'Automation Accounts',
            type =~ 'microsoft.logic/workflows', 'Logic Apps',
            type =~ 'microsoft.keyvault/vaults', 'Key Vaults',
            type =~ 'microsoft.recoveryservices/vaults', 'Recovery Services Vaults',
            type =~ 'microsoft.security/automations', 'Security Automations',
            type =~ 'microsoft.network/networkwatchers', 'Network Watchers',
            type =~ 'microsoft.network/networksecuritygroups', 'NSGs',
            type =~ 'microsoft.network/azurefirewalls', 'Azure Firewalls',
            type =~ 'microsoft.web/serverfarms', 'App Service Plans',
            type =~ 'microsoft.compute/virtualmachines', 'Virtual Machines',
            type =~ 'microsoft.sql/servers', 'SQL Servers',
            type =~ 'microsoft.storage/storageaccounts', 'Storage Accounts',
            type
        )
        | summarize Count = count() by resourceType
        | order by Count desc
        """
        return self.query_resources(query, subscriptions)

    def get_resource_tagging_health(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Tag governance health — percentage of resources with required tags (environment, owner, costcenter)."""
        query = """
        resources
        | extend hasEnvironmentTag = isnotempty(tags['environment']) or isnotempty(tags['Environment']) or isnotempty(tags['env'])
        | extend hasOwnerTag = isnotempty(tags['owner']) or isnotempty(tags['Owner']) or isnotempty(tags['createdBy'])
        | extend hasCostCenterTag = isnotempty(tags['costcenter']) or isnotempty(tags['CostCenter']) or isnotempty(tags['cost-center'])
        | summarize
            TotalResources = count(),
            WithEnvironmentTag = countif(hasEnvironmentTag),
            WithOwnerTag = countif(hasOwnerTag),
            WithCostCenterTag = countif(hasCostCenterTag),
            WithAllTags = countif(hasEnvironmentTag and hasOwnerTag and hasCostCenterTag)
        | project
            TaggingScore = iif(TotalResources > 0, round(toreal(WithAllTags) / toreal(TotalResources) * 100, 1), 0.0),
            TotalResources,
            EnvironmentTagPct = iif(TotalResources > 0, round(toreal(WithEnvironmentTag) / toreal(TotalResources) * 100, 1), 0.0),
            OwnerTagPct = iif(TotalResources > 0, round(toreal(WithOwnerTag) / toreal(TotalResources) * 100, 1), 0.0),
            CostCenterTagPct = iif(TotalResources > 0, round(toreal(WithCostCenterTag) / toreal(TotalResources) * 100, 1), 0.0),
            FullyTagged = WithAllTags, MissingTags = TotalResources - WithAllTags
        """
        return self.query_resources(query, subscriptions)

    def get_network_security_health(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Network security posture — NSGs, Firewalls, WAFs, and private links."""
        query = """
        resources
        | where type in~ (
            'microsoft.network/networksecuritygroups',
            'microsoft.network/azurefirewalls',
            'microsoft.network/applicationgateways',
            'microsoft.network/frontdoors',
            'microsoft.network/privateendpoints',
            'microsoft.network/privatednszones'
        )
        | extend resourceType = case(
            type =~ 'microsoft.network/networksecuritygroups', 'NSGs',
            type =~ 'microsoft.network/azurefirewalls', 'Azure Firewalls',
            type =~ 'microsoft.network/applicationgateways', 'App Gateways (WAF)',
            type =~ 'microsoft.network/frontdoors', 'Front Doors',
            type =~ 'microsoft.network/privateendpoints', 'Private Endpoints',
            type =~ 'microsoft.network/privatednszones', 'Private DNS Zones',
            type
        )
        | summarize Count = count() by resourceType
        | order by Count desc
        """
        return self.query_resources(query, subscriptions)

    def get_disaster_recovery_readiness(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Disaster recovery readiness — backup vaults, replicated items, ASR status."""
        query = """
        recoveryservicesresources
        | extend itemType = case(
            type =~ 'microsoft.recoveryservices/vaults/backupfabrics/protectioncontainers/protecteditems', 'Backup Protected Items',
            type =~ 'microsoft.recoveryservices/vaults/replicationfabrics/replicationprotectioncontainers/replicationprotecteditems', 'ASR Replicated Items',
            type
        )
        | summarize Count = count() by itemType
        | union (
            resources
            | where type =~ 'microsoft.recoveryservices/vaults'
            | summarize Count = count()
            | extend itemType = 'Recovery Services Vaults'
        )
        | order by Count desc
        """
        return self.query_resources(query, subscriptions)

    # ==========================================
    # ORPHANED RESOURCES FUNCTIONS
    # Based on: https://github.com/dolevshor/azure-orphan-resources
    # ==========================================

    def get_orphaned_app_service_plans(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned App Service Plans - plans without any hosted apps. These cost money even when empty."""
        query = """
        resources
        | where type =~ "microsoft.web/serverfarms"
        | where properties.numberOfSites == 0
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            Sku = tostring(sku.name), Tier = tostring(sku.tier),
            Capacity = toint(sku.capacity), Kind = kind,
            NumberOfSites = toint(properties.numberOfSites),
            Status = tostring(properties.status),
            Tags = tags, OrphanReason = 'No hosted apps - plan is empty'
        | order by Tier desc, subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_availability_sets(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned Availability Sets - sets not associated to any VM/VMSS. Excludes ASR sets."""
        query = """
        Resources
        | where type =~ 'Microsoft.Compute/availabilitySets'
        | where properties.virtualMachines == "[]"
        | where not(name endswith "-asr")
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location, Sku = tostring(sku.name),
            FaultDomains = toint(properties.platformFaultDomainCount),
            UpdateDomains = toint(properties.platformUpdateDomainCount),
            VirtualMachineCount = 0, Tags = tags,
            OrphanReason = 'No VMs associated - availability set is empty'
        | order by subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_managed_disks(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned Managed Disks - disks in Unattached state. These cost money. Excludes ASR/AKS disks."""
        query = """
        Resources
        | where type has "microsoft.compute/disks"
        | extend diskState = tostring(properties.diskState)
        | where (managedBy == "" and diskState != 'ActiveSAS') or (diskState == 'Unattached' and diskState != 'ActiveSAS')
        | where not(name endswith "-ASRReplica" or name startswith "ms-asr-" or name startswith "asrseeddisk-")
        | where (tags !contains "kubernetes.io-created-for-pvc") and tags !contains "ASR-ReplicaDisk"
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            DiskType = tostring(sku.name), DiskTier = tostring(sku.tier),
            DiskSizeGB = tolong(properties.diskSizeGB), DiskState = diskState,
            OsType = tostring(properties.osType),
            TimeCreated = tostring(properties.timeCreated),
            Tags = tags, OrphanReason = 'Unattached disk - not connected to any VM'
        | order by DiskSizeGB desc, subscriptionId, ResourceGroup
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_sql_elastic_pools(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned SQL Elastic Pools - pools without any databases. These cost money when empty."""
        query = """
        resources
        | where type =~ 'microsoft.sql/servers/elasticpools'
        | project elasticPoolId = tolower(id), Resource = id, resourceGroup, location, subscriptionId, tags, properties
        | join kind=leftouter (
            resources
            | where type =~ 'Microsoft.Sql/servers/databases'
            | project id, properties
            | extend elasticPoolId = tolower(properties.elasticPoolId)
        ) on elasticPoolId
        | summarize databaseCount = countif(id != '') by Resource, resourceGroup, location, subscriptionId, tostring(tags)
        | where databaseCount == 0
        | project 
            subscriptionId, ResourceId = Resource, ResourceGroup = resourceGroup,
            Location = location, DatabaseCount = databaseCount, Tags = tags,
            OrphanReason = 'No databases in pool'
        | order by subscriptionId, ResourceGroup
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_public_ips(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned Public IPs - IPs not attached to any resource. Static IPs cost money when unattached."""
        query = """
        Resources
        | where type == "microsoft.network/publicipaddresses"
        | where properties.ipConfiguration == "" and properties.natGateway == "" and properties.publicIPPrefix == ""
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            SkuName = tostring(sku.name), SkuTier = tostring(sku.tier),
            AllocationMethod = tostring(properties.publicIPAllocationMethod),
            IpAddress = tostring(properties.ipAddress),
            Tags = tags, OrphanReason = 'Not attached to any resource'
        | order by SkuName desc, subscriptionId, ResourceGroup
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_nics(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned Network Interfaces - NICs not attached to any resource."""
        query = """
        Resources
        | where type has "microsoft.network/networkinterfaces"
        | where isnull(properties.privateEndpoint)
        | where isnull(properties.privateLinkService)
        | where properties.hostedWorkloads == "[]"
        | where properties !has 'virtualmachine'
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            PrivateIP = tostring(properties.ipConfigurations[0].properties.privateIPAddress),
            SubnetId = tostring(properties.ipConfigurations[0].properties.subnet.id),
            Tags = tags, OrphanReason = 'Not attached to any VM or service'
        | order by subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_nsgs(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned NSGs - not attached to any NIC or subnet."""
        query = """
        Resources
        | where type == "microsoft.network/networksecuritygroups"
        | where isnull(properties.networkInterfaces) and isnull(properties.subnets)
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            InboundRuleCount = toint(array_length(properties.securityRules)),
            ProvisioningState = tostring(properties.provisioningState),
            Tags = tags, OrphanReason = 'Not attached to any NIC or subnet'
        | order by subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_route_tables(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned Route Tables - not attached to any subnet."""
        query = """
        resources
        | where type == "microsoft.network/routetables"
        | where isnull(properties.subnets)
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            RouteCount = toint(array_length(properties.routes)),
            DisableBgpRoutePropagation = tobool(properties.disableBgpRoutePropagation),
            Tags = tags, OrphanReason = 'Not attached to any subnet'
        | order by subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_load_balancers(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned Load Balancers - without backend pools or NAT rules. These cost money when idle."""
        query = """
        resources
        | where type == "microsoft.network/loadbalancers"
        | where properties.backendAddressPools == "[]" and properties.inboundNatRules == "[]"
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            SkuName = tostring(sku.name), SkuTier = tostring(sku.tier),
            FrontendIPCount = toint(array_length(properties.frontendIPConfigurations)),
            BackendPoolCount = 0, Tags = tags,
            OrphanReason = 'No backend pools or NAT rules configured'
        | order by SkuName desc, subscriptionId, ResourceGroup
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_front_door_waf_policies(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned Front Door WAF Policies - without security links."""
        query = """
        resources
        | where type == "microsoft.network/frontdoorwebapplicationfirewallpolicies"
        | where properties.securityPolicyLinks == "[]"
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            SkuName = tostring(sku.name),
            PolicyMode = tostring(properties.policySettings.mode),
            Tags = tags, OrphanReason = 'No security policy links - WAF not attached'
        | order by subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_traffic_manager_profiles(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned Traffic Manager Profiles - without endpoints."""
        query = """
        resources
        | where type == "microsoft.network/trafficmanagerprofiles"
        | where properties.endpoints == "[]"
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            RoutingMethod = tostring(properties.trafficRoutingMethod),
            DnsFqdn = tostring(properties.dnsConfig.fqdn),
            ProfileStatus = tostring(properties.profileStatus),
            Tags = tags, OrphanReason = 'No endpoints configured'
        | order by subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_application_gateways(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned Application Gateways - without backend targets. These are expensive when idle."""
        query = """
        resources
        | where type =~ 'microsoft.network/applicationgateways'
        | extend backendPoolsCount = array_length(properties.backendAddressPools)
        | extend SKUName = tostring(properties.sku.name)
        | extend SKUTier = tostring(properties.sku.tier)
        | extend SKUCapacity = toint(properties.sku.capacity)
        | extend AppGwId = tostring(id)
        | project AppGwId, resourceGroup, location, subscriptionId, tags, name, type, SKUName, SKUTier, SKUCapacity
        | join kind=leftouter (
            resources
            | where type =~ 'microsoft.network/applicationgateways'
            | mvexpand backendPools = properties.backendAddressPools
            | extend backendIPCount = array_length(backendPools.properties.backendIPConfigurations)
            | extend backendAddressesCount = array_length(backendPools.properties.backendAddresses)
            | extend AppGwId = tostring(id)
            | summarize backendIPCount = sum(backendIPCount), backendAddressesCount = sum(backendAddressesCount) by AppGwId
        ) on AppGwId
        | project-away AppGwId1
        | where (backendIPCount == 0 or isempty(backendIPCount)) and (backendAddressesCount == 0 or isempty(backendAddressesCount))
        | project 
            subscriptionId, ResourceId = AppGwId, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            SKUName, SKUTier, SKUCapacity,
            Tags = tags, OrphanReason = 'No backend targets - empty backend pools'
        | order by SKUTier desc, subscriptionId, ResourceGroup
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_virtual_networks(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned Virtual Networks - VNets without any subnets."""
        query = """
        resources
        | where type == "microsoft.network/virtualnetworks"
        | where properties.subnets == "[]"
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            AddressSpace = tostring(properties.addressSpace.addressPrefixes),
            SubnetCount = 0, Tags = tags,
            OrphanReason = 'No subnets configured - virtual network is empty'
        | order by subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_subnets(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned Subnets - without connected devices or delegation."""
        query = """
        resources
        | where type =~ "microsoft.network/virtualnetworks"
        | extend subnet = properties.subnets
        | mv-expand subnet
        | extend ipConfigurations = subnet.properties.ipConfigurations
        | extend delegations = subnet.properties.delegations
        | extend appGatewayConfigs = subnet.properties.applicationGatewayIPConfigurations
        | where isnull(ipConfigurations) and delegations == "[]" and isnull(appGatewayConfigs)
        | project 
            subscriptionId, ResourceId = tostring(subnet.id),
            ResourceName = tostring(subnet.name),
            ResourceType = 'microsoft.network/virtualnetworks/subnets',
            VNetName = name, ResourceGroup = resourceGroup, Location = location,
            AddressPrefix = tostring(subnet.properties.addressPrefix),
            Tags = tags, OrphanReason = 'No connected devices or delegations'
        | order by subscriptionId, VNetName, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_nat_gateways(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned NAT Gateways - not attached to any subnet. These cost money when idle."""
        query = """
        resources
        | where type == "microsoft.network/natgateways"
        | where isnull(properties.subnets)
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            SkuName = tostring(sku.name),
            IdleTimeoutMinutes = toint(properties.idleTimeoutInMinutes),
            Tags = tags, OrphanReason = 'Not attached to any subnet'
        | order by subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_ip_groups(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned IP Groups - not attached to any Azure Firewall."""
        query = """
        resources
        | where type == "microsoft.network/ipgroups"
        | where properties.firewalls == "[]" and properties.firewallPolicies == "[]"
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            IpAddressCount = toint(array_length(properties.ipAddresses)),
            Tags = tags, OrphanReason = 'Not attached to any Azure Firewall'
        | order by subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_private_dns_zones(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned Private DNS Zones - without Virtual Network Links. These cost money."""
        query = """
        resources
        | where type == "microsoft.network/privatednszones"
        | where properties.numberOfVirtualNetworkLinks == 0
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            NumberOfRecordSets = toint(properties.numberOfRecordSets),
            NumberOfVNetLinks = toint(properties.numberOfVirtualNetworkLinks),
            Tags = tags, OrphanReason = 'No Virtual Network links'
        | order by subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_private_endpoints(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned Private Endpoints - in Disconnected state. These cost money."""
        query = """
        resources
        | where type =~ "microsoft.network/privateendpoints"
        | extend connection = iff(array_length(properties.manualPrivateLinkServiceConnections) > 0, properties.manualPrivateLinkServiceConnections[0], properties.privateLinkServiceConnections[0])
        | extend stateEnum = tostring(connection.properties.privateLinkServiceConnectionState.status)
        | where stateEnum == "Disconnected"
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            ConnectionState = stateEnum,
            TargetService = tostring(split(tostring(connection.properties.privateLinkServiceId), "/")[8]),
            Tags = tags, OrphanReason = 'Disconnected from target service'
        | order by subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_vnet_gateways(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned VNet Gateways - without P2S config or connections. These are expensive when idle."""
        query = """
        resources
        | where type =~ "microsoft.network/virtualnetworkgateways"
        | extend SKU = tostring(properties.sku.name)
        | extend Tier = tostring(properties.sku.tier)
        | extend GatewayType = tostring(properties.gatewayType)
        | extend Resource = id
        | join kind=leftouter (
            resources
            | where type =~ "microsoft.network/connections"
            | mv-expand Resource = pack_array(properties.virtualNetworkGateway1.id, properties.virtualNetworkGateway2.id) to typeof(string)
            | project Resource, connectionId = id
        ) on Resource
        | where isempty(properties.vpnClientConfiguration) and isempty(connectionId)
        | project 
            subscriptionId, ResourceId = Resource, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            GatewayType, SKU, Tier,
            Tags = tags, OrphanReason = 'No P2S config or connections - gateway is idle'
        | order by GatewayType, SKU desc, subscriptionId, ResourceGroup
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_ddos_plans(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned DDoS Protection Plans - without protected VNets. Very expensive (~$2,944/month)."""
        query = """
        resources
        | where type == "microsoft.network/ddosprotectionplans"
        | where isnull(properties.virtualNetworks)
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            ProtectedVNetCount = 0, Tags = tags,
            OrphanReason = 'No VNets protected - DDoS plan is idle',
            EstimatedMonthlyCost = '$2,944/month'
        | order by subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_resource_groups(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get empty Resource Groups - RGs without any resources."""
        query = """
        ResourceContainers
        | where type == "microsoft.resources/subscriptions/resourcegroups"
        | extend rgAndSub = strcat(resourceGroup, "--", subscriptionId)
        | join kind=leftouter (
            Resources
            | extend rgAndSub = strcat(resourceGroup, "--", subscriptionId)
            | summarize resourceCount = count() by rgAndSub
        ) on rgAndSub
        | where isnull(resourceCount)
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            ResourceCount = 0, Tags = tags,
            OrphanReason = 'No resources in group - resource group is empty'
        | order by subscriptionId, ResourceGroup
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_api_connections(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get orphaned API Connections - not used by any Logic App."""
        query = """
        resources
        | where type =~ 'Microsoft.Web/connections'
        | project subscriptionId, Resource = id, apiName = name, resourceGroup, tags, location, type, properties
        | join kind=leftouter (
            resources
            | where type == 'microsoft.logic/workflows'
            | extend var_json = properties["parameters"]["$connections"]["value"]
            | mvexpand var_connection = var_json
            | where notnull(var_connection)
            | extend connectionId = extract("connectionId\\\\":\\\\"(.*?)\\\\"", 1, tostring(var_connection))
            | project connectionId, workflowName = name
        ) on $left.Resource == $right.connectionId
        | where connectionId == ""
        | project 
            subscriptionId, ResourceId = Resource, ResourceName = apiName, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            ApiDisplayName = tostring(properties.displayName),
            Tags = tags, OrphanReason = 'Not used by any Logic App'
        | order by subscriptionId, ResourceGroup, ResourceName
        """
        return self.query_resources(query, subscriptions)

    def get_orphaned_certificates(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get expired App Service Certificates."""
        query = """
        resources
        | where type == 'microsoft.web/certificates'
        | extend expiresOn = todatetime(properties.expirationDate)
        | where expiresOn <= now()
        | project 
            subscriptionId, ResourceId = id, ResourceName = name, ResourceType = type,
            ResourceGroup = resourceGroup, Location = location,
            ExpirationDate = expiresOn,
            SubjectName = tostring(properties.subjectName),
            Issuer = tostring(properties.issuer),
            Thumbprint = tostring(properties.thumbprint),
            Tags = tags, OrphanReason = 'Certificate has expired'
        | order by ExpirationDate asc, subscriptionId, ResourceGroup
        """
        return self.query_resources(query, subscriptions)

    def get_all_orphaned_resources_summary(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get a summary count of all orphaned resource types with cost impact indicators."""
        sub_names = self._get_subscription_names()
        summary = {"success": True, "categories": {}, "total_orphaned": 0, "cost_impact_resources": 0}
        
        cost_impact = {"App Service Plans", "Managed Disks", "SQL Elastic Pools", "Public IPs",
                       "Load Balancers", "Application Gateways", "NAT Gateways", "Private DNS Zones",
                       "Private Endpoints", "VNet Gateways", "DDoS Protection Plans"}
        
        checks = [
            ("App Service Plans", self.get_orphaned_app_service_plans),
            ("Availability Sets", self.get_orphaned_availability_sets),
            ("Managed Disks", self.get_orphaned_managed_disks),
            ("SQL Elastic Pools", self.get_orphaned_sql_elastic_pools),
            ("Public IPs", self.get_orphaned_public_ips),
            ("Network Interfaces", self.get_orphaned_nics),
            ("Network Security Groups", self.get_orphaned_nsgs),
            ("Route Tables", self.get_orphaned_route_tables),
            ("Load Balancers", self.get_orphaned_load_balancers),
            ("Application Gateways", self.get_orphaned_application_gateways),
            ("NAT Gateways", self.get_orphaned_nat_gateways),
            ("Private DNS Zones", self.get_orphaned_private_dns_zones),
            ("Private Endpoints", self.get_orphaned_private_endpoints),
            ("VNet Gateways", self.get_orphaned_vnet_gateways),
            ("DDoS Protection Plans", self.get_orphaned_ddos_plans),
            ("Resource Groups", self.get_orphaned_resource_groups),
            ("Front Door WAF", self.get_orphaned_front_door_waf_policies),
            ("Traffic Manager", self.get_orphaned_traffic_manager_profiles),
            ("Virtual Networks", self.get_orphaned_virtual_networks),
            ("Subnets", self.get_orphaned_subnets),
            ("IP Groups", self.get_orphaned_ip_groups),
            ("API Connections", self.get_orphaned_api_connections),
            ("Certificates", self.get_orphaned_certificates),
        ]
        
        for name, func in checks:
            try:
                result = func(subscriptions)
                count = result.get("count", 0) or result.get("total_records", 0) or 0
                has_cost = name in cost_impact
                summary["categories"][name] = {
                    "count": count,
                    "cost_impact": has_cost,
                    "label": f"{'💰 ' if has_cost else ''}{name}: {count} orphaned"
                }
                summary["total_orphaned"] += count
                if has_cost and count > 0:
                    summary["cost_impact_resources"] += count
            except Exception as e:
                summary["categories"][name] = {"count": 0, "error": str(e)}
        
        return summary
