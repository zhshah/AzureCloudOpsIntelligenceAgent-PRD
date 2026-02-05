"""
Modern Resource Deployment with Logic App Integration
Handles resource creation through Azure Logic Apps approval workflow
"""
import os
import logging
from typing import Dict, Any, Optional
from logic_app_client import LogicAppClient
from intelligent_template_generator import IntelligentTemplateGenerator

logger = logging.getLogger(__name__)


class ModernResourceDeployment:
    """
    Modern resource deployment manager that integrates with Logic App approval workflow.
    All resource creation requests go through the approval process.
    """
    
    def __init__(self, subscription_id: str = None, user_email: str = None, user_name: str = None):
        """
        Initialize modern deployment manager
        
        Args:
            subscription_id: Azure subscription ID
            user_email: Email of the logged-in user
            user_name: Name of the logged-in user
        """
        self.subscription_id = subscription_id or os.getenv("AZURE_SUBSCRIPTION_ID")
        self.logic_app_client = LogicAppClient()
        self.template_generator = IntelligentTemplateGenerator(self.subscription_id)
        
        # User context (can be updated later)
        self.user_email = user_email or os.getenv("USER_EMAIL", "admin@example.com")
        self.user_name = user_name or os.getenv("USER_NAME", "Azure Admin")
        
        logger.info(f"ModernResourceDeployment initialized with subscription: {self.subscription_id}")
        logger.info(f"Logic App approval workflow enabled: {self.logic_app_client.is_enabled()}")
    
    def set_user_context(self, user_email: str, user_name: str):
        """
        Set user context for deployment operations
        
        Args:
            user_email: Email address of the logged-in user
            user_name: Display name of the logged-in user
        """
        self.user_email = user_email
        self.user_name = user_name
        logger.info(f"User context updated: {user_name} ({user_email})")
    
    async def create_virtual_machine(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a virtual machine through Logic App approval workflow
        
        Required params:
        - name: VM name
        - resource_group: Resource group name
        - os_type: linux or windows
        
        Optional params:
        - location: Azure region (default: westeurope)
        - size: VM size (default: Standard_B2s)
        """
        try:
            # Extract and validate parameters
            name = params.get("name")
            resource_group = params.get("resource_group")
            os_type = params.get("os_type", "linux").lower()
            location = params.get("location", "westeurope")
            size = params.get("size", "Standard_B2s")
            
            if not name or not resource_group:
                return {
                    "status": "error",
                    "message": "Missing required parameters: name and resource_group are required"
                }
            
            # Build VM configuration for ARM template
            vm_properties = {
                "location": location,
                "vmSize": size,
                "osType": os_type
            }
            
            # Generate ARM template for VM deployment
            arm_template = self.logic_app_client.generate_arm_template(
                resource_type="Microsoft.Compute/virtualMachines",
                resource_name=name,
                properties=vm_properties
            )
            
            # Calculate estimated cost (rough estimate)
            estimated_cost = self._estimate_vm_cost(size)
            
            # Submit for approval through Logic App (using instance user context)
            approval_result = await self.logic_app_client.submit_for_approval(
                resource_type="Virtual Machine",
                resource_name=name,
                deployment_template=arm_template,
                resource_group=resource_group,
                user_email=self.user_email,
                user_name=self.user_name,
                estimated_cost=estimated_cost,
                justification=f"Creating {os_type} VM '{name}' with size {size} in {location}"
            )
            
            return approval_result
            
        except Exception as e:
            logger.error(f"Error creating VM: {e}")
            return {
                "status": "error",
                "message": f"Failed to submit VM creation request: {str(e)}"
            }
    
    async def create_storage_account(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a storage account using INTELLIGENT template generation
        NO HARD-CODING - uses Azure schemas + AI to generate complete templates
        
        Required params:
        - name: Storage account name (3-24 lowercase alphanumeric)
        - resource_group: Resource group name
        
        Optional params:
        - location: Azure region (default: westeurope)
        - requirements: User's additional requirements
        """
        try:
            # Extract and validate parameters
            name = params.get("name", "").lower().replace("-", "").replace("_", "")[:24]
            resource_group = params.get("resource_group")
            location = params.get("location", "westeurope")
            user_requirements = params.get("requirements", params.get("justification", "Standard storage account"))
            
            if not name or not resource_group:
                return {
                    "status": "error",
                    "message": "Missing required parameters: name and resource_group are required"
                }
            
            if len(name) < 3:
                return {
                    "status": "error",
                    "message": "Storage account name must be at least 3 characters"
                }
            
            logger.info(f"🚀 Creating storage account '{name}' with INTELLIGENT template generation")
            
            # Use AI + Azure schemas to generate COMPLETE template
            arm_template, error = self.template_generator.generate_with_retry(
                resource_type="Microsoft.Storage/storageAccounts",
                resource_name=name,
                location=location,
                resource_group=resource_group,
                user_requirements=user_requirements,
                max_retries=2
            )
            
            if not arm_template:
                logger.error(f"❌ Failed to generate template: {error}")
                return {
                    "status": "error",
                    "message": f"Failed to generate ARM template: {error}"
                }
            
            logger.info("✅ Intelligent ARM template generated and validated")
            
            # Estimate cost (simple estimation based on SKU if available)
            sku_name = "Standard_LRS"  # default
            if arm_template.get("resources") and len(arm_template["resources"]) > 0:
                resource_sku = arm_template["resources"][0].get("sku", {}).get("name")
                if resource_sku:
                    sku_name = resource_sku
            
            estimated_cost = self._estimate_storage_cost(sku_name)
            
            # Submit for approval through Logic App
            approval_result = await self.logic_app_client.submit_for_approval(
                resource_type="Storage Account",
                resource_name=name,
                deployment_template=arm_template,
                resource_group=resource_group,
                user_email=self.user_email,
                user_name=self.user_name,
                estimated_cost=estimated_cost,
                justification=f"Creating storage account '{name}' in {location}. {user_requirements}"
            )
            
            return approval_result
            
        except Exception as e:
            logger.error(f"❌ Error in create_storage_account: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to create storage account: {str(e)}"
            }
    async def create_sql_database(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an Azure SQL Database through Logic App approval workflow
        
        Required params:
        - database_name: Database name
        - server_name: SQL Server name
        - resource_group: Resource group name
        
        Optional params:
        - location: Azure region (default: westeurope)
        - sku: Database SKU (default: Basic)
        """
        try:
            # Extract and validate parameters
            database_name = params.get("database_name")
            server_name = params.get("server_name")
            resource_group = params.get("resource_group")
            location = params.get("location", "westeurope")
            sku = params.get("sku", "Basic")
            
            if not database_name or not server_name or not resource_group:
                return {
                    "status": "error",
                    "message": "Missing required parameters: database_name, server_name, and resource_group are required"
                }
            
            # Build SQL database configuration
            db_properties = {
                "location": location,
                "sku": {
                    "name": sku,
                    "tier": sku
                }
            }
            
            # Generate ARM template
            arm_template = self.logic_app_client.generate_arm_template(
                resource_type="Microsoft.Sql/servers/databases",
                resource_name=f"{server_name}/{database_name}",
                properties=db_properties
            )
            
            # Estimate cost
            estimated_cost = self._estimate_sql_cost(sku)
            
            # Submit for approval through Logic App (using instance user context)
            approval_result = await self.logic_app_client.submit_for_approval(
                resource_type="SQL Database",
                resource_name=database_name,
                deployment_template=arm_template,
                resource_group=resource_group,
                user_email=self.user_email,
                user_name=self.user_name,
                estimated_cost=estimated_cost,
                justification=f"Creating SQL database '{database_name}' on server '{server_name}' with SKU {sku}"
            )
            
            return approval_result
            
        except Exception as e:
            logger.error(f"Error creating SQL database: {e}")
            return {
                "status": "error",
                "message": f"Failed to submit SQL database creation request: {str(e)}"
            }
    
    async def create_resource_group(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an Azure Resource Group through Logic App approval workflow
        
        Required params:
        - name: Resource group name
        - location: Azure region (e.g., westeurope, eastus)
        """
        try:
            name = params.get("name")
            location = params.get("location", "westeurope")
            
            if not name:
                return {
                    "status": "error",
                    "message": "Missing required parameter: name is required"
                }
            
            # Build ARM template for resource group
            # Note: Resource groups use subscription-level deployment
            arm_template = {
                "$schema": "https://schema.management.azure.com/schemas/2018-05-01/subscriptionDeploymentTemplate.json#",
                "contentVersion": "1.0.0.0",
                "resources": [
                    {
                        "type": "Microsoft.Resources/resourceGroups",
                        "apiVersion": "2021-04-01",
                        "name": name,
                        "location": location,
                        "properties": {}
                    }
                ]
            }
            
            # Submit for approval through Logic App (using instance user context)
            # Use the same resource group name as target (even though it doesn't exist yet)
            # The deployment will be at subscription level
            approval_result = await self.logic_app_client.submit_for_approval(
                resource_type="Resource Group",
                resource_name=name,
                deployment_template=arm_template,
                resource_group=name,  # This is the RG being created
                user_email=self.user_email,
                user_name=self.user_name,
                estimated_cost="Free (no cost for resource groups)",
                justification=f"Creating resource group '{name}' in {location}",
                location=location
            )
            
            return approval_result
            
        except Exception as e:
            logger.error(f"Error creating resource group: {e}")
            return {
                "status": "error",
                "message": f"Failed to submit resource group creation request: {str(e)}"
            }
    
    def _estimate_vm_cost(self, size: str) -> str:
        """Estimate monthly cost for VM size"""
        cost_map = {
            "Standard_B1s": "$7.59/month",
            "Standard_B2s": "$30.37/month",
            "Standard_B2ms": "$60.74/month",
            "Standard_D2s_v3": "$70.08/month",
            "Standard_D4s_v3": "$140.16/month",
            "Standard_D8s_v3": "$280.32/month"
        }
        return cost_map.get(size, "~$50-100/month")
    
    def _estimate_storage_cost(self, sku: str) -> str:
        """Estimate monthly cost for storage account"""
        cost_map = {
            "Standard_LRS": "$0.02/GB + transactions",
            "Standard_GRS": "$0.04/GB + transactions",
            "Premium_LRS": "$0.15/GB + transactions"
        }
        return cost_map.get(sku, "~$10-50/month for typical usage")
    
    def _estimate_sql_cost(self, sku: str) -> str:
        """Estimate monthly cost for SQL database"""
        cost_map = {
            "Basic": "$4.99/month",
            "S0": "$15/month",
            "S1": "$30/month",
            "S2": "$75/month",
            "P1": "$465/month"
        }
        return cost_map.get(sku, "~$15-100/month")


# Global instance
_modern_deployment: Optional[ModernResourceDeployment] = None


def get_modern_deployment(subscription_id: str = None) -> ModernResourceDeployment:
    """Get or create global ModernResourceDeployment instance"""
    global _modern_deployment
    if _modern_deployment is None:
        _modern_deployment = ModernResourceDeployment(subscription_id)
    return _modern_deployment
