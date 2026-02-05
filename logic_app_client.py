"""
Logic App Integration for Approval Workflow
Handles resource creation approval through Azure Logic Apps
"""
import os
import uuid
import json
import httpx
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class LogicAppClient:
    """Client for interacting with Azure Logic App approval workflow"""
    
    def __init__(self):
        # Try base64-encoded URL first, then plain URL
        base64_url = os.getenv("LOGIC_APP_WEBHOOK_URL_BASE64")
        if base64_url:
            import base64
            try:
                self.webhook_url = base64.b64decode(base64_url).decode('utf-8')
                logger.info("Using base64-decoded webhook URL")
            except Exception as e:
                logger.error(f"Failed to decode base64 webhook URL: {e}")
                self.webhook_url = os.getenv("LOGIC_APP_WEBHOOK_URL")
        else:
            self.webhook_url = os.getenv("LOGIC_APP_WEBHOOK_URL")
        
        self.enabled = os.getenv("ENABLE_APPROVAL_WORKFLOW", "false").lower() == "true"

        if self.enabled and not self.webhook_url:
            logger.warning("Approval workflow enabled but LOGIC_APP_WEBHOOK_URL not set")
            self.enabled = False
    async def submit_for_approval(
        self,
        resource_type: str,
        resource_name: str,
        deployment_template: Dict[str, Any],
        resource_group: str,
        user_email: str,
        user_name: str,
        estimated_cost: str = "Not calculated",
        justification: str = "User requested via AI Agent",
        location: str = "westeurope"
    ) -> Dict[str, Any]:
        """
        Submit a resource creation request for approval
        
        Args:
            resource_type: Type of resource (VM, Storage, etc.)
            resource_name: Name of the resource
            deployment_template: ARM template for deployment
            user_email: Email of requesting user
            user_name: Name of requesting user
            estimated_cost: Estimated monthly cost
            justification: Business justification
            
        Returns:
            Dict with requestId and status
        """
        if not self.enabled:
            # If approval workflow disabled, return immediate approval
            return {
                "requestId": str(uuid.uuid4()),
                "status": "auto_approved",
                "message": "Approval workflow is disabled. Request auto-approved."
            }
        
        request_id = str(uuid.uuid4())

        # Write to Cosmos DB first
        try:
            from azure.cosmos import CosmosClient
            cosmos_endpoint = os.getenv('COSMOS_ENDPOINT')
            cosmos_key = os.getenv('COSMOS_KEY')
            
            if cosmos_endpoint and cosmos_key:
                client = CosmosClient(cosmos_endpoint, cosmos_key)
                database = client.get_database_client('cloudops-deployments-db')
                container = database.get_container_client('deployment-requests')
                
                document = {
                    'id': request_id,
                    'requestId': request_id,
                    'resourceType': resource_type,
                    'resourceName': resource_name,
                    'details': deployment_template,
                    'resourceGroup': resource_group,
                    'userEmail': user_email,
                    'userName': user_name,
                    'estimatedCost': estimated_cost,
                    'justification': justification,
                    'status': 'pending',
                    'createdAt': datetime.utcnow().isoformat() + 'Z'
                }
                
                container.create_item(document)
                logger.info(f'✅ Saved approval request to Cosmos DB: {request_id}')
        except Exception as cosmos_error:
            logger.error(f'Failed to save to Cosmos DB: {cosmos_error}')
            # Continue anyway - Logic App may succeed

        
        # Format template as readable JSON string for email display
        formatted_template = json.dumps(deployment_template, indent=2)
        
        # Generate CLI command for display
        cli_command = self._generate_cli_command(resource_type, resource_name, resource_group, location, deployment_template)
        
        # Create professional email body with all details
        email_body = f"""Hi {user_name},

Your Azure resource deployment request is ready for approval:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 DEPLOYMENT DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 Resource Type: {resource_type}
📦 Resource Name: {resource_name}
🗂️ Resource Group: {resource_group}
📍 Location: {location}
💰 Estimated Cost: {estimated_cost}
📝 Justification: {justification}
🆔 Request ID: {request_id}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💻 DEPLOYMENT COMMAND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{cli_command}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 ARM TEMPLATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{formatted_template}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Please click Approve or Reject below to proceed.
"""
        
        payload = {
            "requestId": request_id,
            "resourceType": resource_type,
            "resourceName": resource_name,
            "details": deployment_template,  # Original for deployment
            "emailBody": email_body,  # Clean formatted body for email
            "resourceGroup": resource_group,
            "userEmail": user_email,
            "userName": user_name,
            "estimatedCost": estimated_cost,
            "justification": justification,
            "location": location,
            "cliCommand": cli_command,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Log the complete payload for debugging
        logger.info("📤 SUBMITTING TO LOGIC APP:")
        logger.info("=" * 100)
        logger.info(f"Request ID: {request_id}")
        logger.info(f"Resource Type: {resource_type}")
        logger.info(f"Resource Name: {resource_name}")
        logger.info(f"Resource Group: {resource_group}")
        logger.info(f"User Email: {user_email}")
        logger.info("ARM Template being sent:")
        logger.info(json.dumps(deployment_template, indent=2))
        logger.info("=" * 100)
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                response.raise_for_status()
                
                logger.info(f"Approval request submitted: {request_id}")
                
                return {
                    "requestId": request_id,
                    "status": "pending_approval",
                    "message": f"Deployment request sent for approval. Check your email ({user_email}) for approval link.",
                    "estimatedCost": estimated_cost
                }
                
        except httpx.HTTPError as e:
            logger.error(f"Failed to submit approval request: {e}")
            return {
                "requestId": request_id,
                "status": "error",
                "message": f"Failed to submit approval request: {str(e)}"
            }
    
    def is_enabled(self) -> bool:
        """Check if approval workflow is enabled"""
        return self.enabled
    
    def generate_arm_template(
        self,
        resource_type: str,
        resource_name: str,
        properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate ARM template for resource deployment
        
        Args:
            resource_type: Azure resource type (e.g., "Microsoft.Compute/virtualMachines")
            resource_name: Name of the resource
            properties: Resource-specific properties
            
        Returns:
            ARM template dict
        """
        location = properties.get("location", "westeurope")

        # Build resource-specific properties and remove metadata fields that should not be in ARM
        resource_properties = self._build_resource_properties(resource_type, properties)

        template = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "resources": [
                {
                    "type": resource_type,
                    "apiVersion": self._get_api_version(resource_type),
                    "name": resource_name,
                    "location": location,
                    "properties": resource_properties
                }
            ]
        }
        
        return template

    def _build_resource_properties(self, resource_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Build resource-specific properties for ARM templates."""

        # Remove fields that should not be passed into the ARM properties bag
        clean_props = {
            k: v
            for k, v in properties.items()
            if k
            not in [
                "location",
                "resourceGroup",
                "resource_group",
                "vnet",
                "vnetName",
                "vnet_resource_group",
                "vnetResourceGroup",
                "subnet",
                "subnetName",
            ]
        }

        if resource_type == "Microsoft.Network/networkInterfaces":
            return self._build_nic_properties(properties)

        return clean_props

    def _build_nic_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Construct ipConfigurations for NIC deployments."""

        vnet = properties.get("vnet") or properties.get("vnetName")
        subnet = properties.get("subnet") or properties.get("subnetName")
        vnet_rg = (
            properties.get("vnetResourceGroup")
            or properties.get("vnet_resource_group")
            or properties.get("resourceGroup")
            or properties.get("resource_group")
        )

        if not vnet or not subnet or not vnet_rg:
            logger.warning(
                "NIC request missing vnet/subnet info: vnet=%s subnet=%s vnet_rg=%s",
                vnet,
                subnet,
                vnet_rg,
            )
            return {
                "ipConfigurations": [
                    {
                        "name": "ipconfig1",
                        "properties": {
                            "privateIPAllocationMethod": "Dynamic"
                        },
                    }
                ]
            }

        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        if not subscription_id:
            raise ValueError("AZURE_SUBSCRIPTION_ID environment variable is required")
        subnet_id = (
            f"/subscriptions/{subscription_id}/resourceGroups/{vnet_rg}"
            f"/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/{subnet}"
        )

        return {
            "ipConfigurations": [
                {
                    "name": "ipconfig1",
                    "properties": {
                        "subnet": {"id": subnet_id},
                        "privateIPAllocationMethod": "Dynamic",
                    },
                }
            ]
        }
    
    def _generate_cli_command(
        self,
        resource_type: str,
        resource_name: str,
        resource_group: str,
        location: str,
        deployment_template: Dict[str, Any]
    ) -> str:
        """Generate Azure CLI command for the deployment"""
        
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID", "")
        
        # Extract SKU if available
        resources = deployment_template.get("resources", [])
        if resources:
            props = resources[0].get("properties", {})
            sku = resources[0].get("sku", {})
            kind = resources[0].get("kind", "")
        else:
            props = {}
            sku = {}
            kind = ""
        
        # Generate command based on resource type
        if "Storage" in resource_type or resource_type == "Storage Account":
            sku_name = sku.get("name", "Standard_LRS")
            kind_value = kind or "StorageV2"
            allow_blob = props.get("allowBlobPublicAccess", True)
            allow_blob_str = "true" if allow_blob else "false"
            
            return f"az storage account create --name {resource_name} --resource-group {resource_group} --location {location} --sku {sku_name} --kind {kind_value} --allow-blob-public-access {allow_blob_str} --subscription {subscription_id} --output json"
        
        elif "VirtualMachine" in resource_type or resource_type == "Virtual Machine":
            vm_size = props.get("hardwareProfile", {}).get("vmSize", "Standard_B2s")
            image = props.get("storageProfile", {}).get("imageReference", {})
            image_str = f"{image.get('publisher', 'Canonical')}:{image.get('offer', 'UbuntuServer')}:{image.get('sku', '18.04-LTS')}:{image.get('version', 'latest')}"
            
            return f"az vm create --name {resource_name} --resource-group {resource_group} --location {location} --size {vm_size} --image {image_str} --subscription {subscription_id} --output json"
        
        elif "virtualNetworks" in resource_type or resource_type == "Virtual Network":
            address_prefix = props.get("addressSpace", {}).get("addressPrefixes", ["10.0.0.0/16"])[0]
            
            return f"az network vnet create --name {resource_name} --resource-group {resource_group} --location {location} --address-prefix {address_prefix} --subscription {subscription_id} --output json"
        
        elif "Database" in resource_type or "Sql" in resource_type:
            return f"az sql db create --name {resource_name} --resource-group {resource_group} --server <server-name> --subscription {subscription_id} --output json"
        
        elif "Disk" in resource_type or resource_type == "Managed Disk":
            sku_name = sku.get("name", "Standard_LRS")
            size_gb = props.get("diskSizeGB", 128)
            
            return f"az disk create --name {resource_name} --resource-group {resource_group} --location {location} --sku {sku_name} --size-gb {size_gb} --subscription {subscription_id} --output json"
        
        else:
            # Generic deployment command
            return f"az deployment group create --resource-group {resource_group} --template-file <template.json> --parameters resourceName={resource_name} location={location} --subscription {subscription_id} --output json"
    
    def _get_api_version(self, resource_type: str) -> str:
        """Get appropriate API version for resource type"""
        api_versions = {
            "Microsoft.Compute/virtualMachines": "2023-03-01",
            "Microsoft.Storage/storageAccounts": "2023-01-01",
            "Microsoft.Network/virtualNetworks": "2023-04-01",
            "Microsoft.Network/networkInterfaces": "2023-04-01",
            "Microsoft.Network/publicIPAddresses": "2023-04-01",
            "Microsoft.ContainerInstance/containerGroups": "2023-05-01"
        }
        
        return api_versions.get(resource_type, "2023-01-01")



