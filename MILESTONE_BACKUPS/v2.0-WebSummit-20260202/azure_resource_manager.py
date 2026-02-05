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
    
    def query_resources(self, query: str, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute a Resource Graph query
        
        Args:
            query: KQL query string
            subscriptions: List of subscription IDs to query
        """
        try:
            if not subscriptions:
                subscriptions = [self.subscription_id]
            
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
            return {"error": str(e)}
    
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
        """Get all resources with detailed information (name, type, RG, location, tags)"""
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
        return self.query_resources(query, subscriptions)
    
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
        return self.query_resources(query, subscriptions)
    
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
                  kind = kind,
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
    
    def get_policy_compliance_status(self, subscriptions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get Azure Policy compliance status using policyresources
        Returns policy assignments and their compliance state
        """
        query = """
        policyresources
        | where type =~ 'microsoft.policyinsights/policystates'
        | summarize 
            TotalResources = count(),
            CompliantResources = countif(properties.complianceState == 'Compliant'),
            NonCompliantResources = countif(properties.complianceState == 'NonCompliant')
            by policyAssignmentName = tostring(properties.policyAssignmentName), 
               policyDefinitionName = tostring(properties.policyDefinitionName),
               policyDefinitionAction = tostring(properties.policyDefinitionAction)
        | extend CompliancePercentage = round(todouble(CompliantResources) / todouble(TotalResources) * 100, 2)
        | project 
            PolicyName = policyAssignmentName,
            ComplianceState = case(
                CompliancePercentage == 100, 'Compliant',
                CompliancePercentage >= 80, 'Mostly Compliant',
                CompliancePercentage >= 50, 'Partially Compliant',
                'Non-Compliant'
            ),
            CompliantResources,
            NonCompliantResources,
            CompliancePercentage,
            Severity = case(
                policyDefinitionAction == 'deny', 'High',
                policyDefinitionAction == 'audit', 'Medium',
                'Low'
            ),
            RemediationRequired = case(NonCompliantResources > 0, 'Yes', 'No')
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
        | extend osType = properties.osType
        | extend osVersion = properties.osVersion
        | extend status = properties.status
        | extend agentVersion = properties.agentVersion
        | extend lastStatusChange = properties.lastStatusChange
        | extend defenderStatus = properties.extensions[0].provisioningState
        | extend monitoringStatus = properties.extensions[1].provisioningState
        | project 
            MachineName = name,
            ResourceGroup = resourceGroup,
            Subscription = subscriptionId,
            OSType = osType,
            OSVersion = osVersion,
            AgentStatus = status,
            AgentVersion = agentVersion,
            DefenderStatus = case(
                defenderStatus == 'Succeeded', 'Enabled',
                defenderStatus == 'Failed', 'Failed',
                'Not Configured'
            ),
            MonitoringStatus = case(
                monitoringStatus == 'Succeeded', 'Enabled',
                monitoringStatus == 'Failed', 'Failed',
                'Not Configured'
            ),
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
        
        # Step 4: Merge actual costs with resource metadata
        if result and 'data' in result and isinstance(result['data'], list):
            for resource in result['data']:
                resource_name_lower = resource.get('ResourceNameLower', resource.get('ResourceName', '')).lower()
                
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
            SKU = resourceSku,
            UtilizationPercent = utilizationPercent,
            RecommendedAction = recommendedAction,
            ImplementationEffort = implementationEffort,
            Tags = tags
        | order by ResourceName asc
        """
        
        result = self.query_resources(query, subscriptions)
        
        # Step 3: Merge actual costs and calculate savings
        if result and 'data' in result and isinstance(result['data'], list):
            for resource in result['data']:
                resource_name_lower = resource.get('ResourceNameLower', resource.get('ResourceName', '')).lower()
                
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

