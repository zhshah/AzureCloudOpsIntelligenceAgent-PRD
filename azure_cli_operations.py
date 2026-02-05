"""
Azure CLI-Based Operations
Direct Azure CLI command execution - NO ARM template generation
This approach is more reliable and handles ALL resource types automatically
"""

import os
import json
import asyncio
import subprocess
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AzureCLIOperations:
    """
    Execute Azure operations using Azure CLI directly
    No ARM templates - just pure CLI commands
    """
    
    def __init__(self, subscription_id: str):
        self.subscription_id = subscription_id
        
    async def create_resource(
        self,
        resource_type: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create ANY Azure resource using appropriate CLI command
        
        Args:
            resource_type: Azure resource type (e.g., "disk", "vm", "storage")
            params: Resource parameters from user
            
        Returns:
            Dict with command, preview, and estimated cost
        """
        try:
            # Generate the appropriate Azure CLI command
            cli_command = self._generate_cli_command(resource_type, params)
            
            if not cli_command:
                return {
                    "status": "error",
                    "message": f"Resource type '{resource_type}' not yet supported"
                }
            
            # Generate human-readable explanation
            explanation = self._generate_explanation(resource_type, params)
            
            # Estimate cost
            estimated_cost = self._estimate_cost(resource_type, params)
            
            return {
                "status": "success",
                "command": cli_command,
                "explanation": explanation,
                "resource_type": resource_type,
                "resource_name": params.get("name"),
                "resource_group": params.get("resource_group"),
                "location": params.get("location", "westeurope"),
                "estimated_cost": estimated_cost,
                "preview": f"Will execute: {cli_command[:100]}..."
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating CLI command: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to generate command: {str(e)}"
            }
    
    def _generate_cli_command(self, resource_type: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Generate Azure CLI command for the resource type
        
        Returns the EXACT command that will be executed
        """
        resource_type_lower = resource_type.lower()
        
        # DISK
        if "disk" in resource_type_lower:
            return self._cmd_disk(params)
        
        # STORAGE ACCOUNT
        elif "storage" in resource_type_lower:
            return self._cmd_storage(params)
        
        # VIRTUAL MACHINE
        elif "vm" in resource_type_lower or "virtual machine" in resource_type_lower or "virtualmachine" in resource_type_lower or "machine" in resource_type_lower:
            return self._cmd_vm(params)
        
        # AVAILABILITY SET
        elif "availability" in resource_type_lower:
            return self._cmd_availability_set(params)
        
        # VIRTUAL NETWORK
        elif "vnet" in resource_type_lower or "network" in resource_type_lower:
            return self._cmd_vnet(params)
        
        # RESOURCE GROUP
        elif "resourcegroup" in resource_type_lower or resource_type_lower == "resource group":
            return self._cmd_resource_group(params)
        
        # SQL DATABASE
        elif "sql" in resource_type_lower:
            return self._cmd_sql(params)
        
        # Add more resource types as needed
        else:
            return None
    
    def _cmd_disk(self, params: Dict[str, Any]) -> str:
        """Generate Azure CLI command for managed disk"""
        name = params.get("name")
        rg = params.get("resource_group")
        location = params.get("location", "westeurope")
        size_gb = params.get("size_gb", params.get("disk_size_gb", 128))
        sku = params.get("sku", "Premium_LRS")
        
        # Build command
        cmd = f"az disk create --name {name} --resource-group {rg} --location {location} --size-gb {size_gb} --sku {sku}"
        
        # Add tags if provided
        if params.get("tags"):
            tags = params["tags"]
            if isinstance(tags, dict):
                tag_str = " ".join([f"{k}={v}" for k, v in tags.items()])
                cmd += f" --tags {tag_str}"
        
        # Add subscription
        cmd += f" --subscription {self.subscription_id}"
        
        # Output as JSON for parsing
        cmd += " --output json"
        
        return cmd
    
    def _cmd_storage(self, params: Dict[str, Any]) -> str:
        """Generate Azure CLI command for storage account"""
        name = params.get("name", "").lower().replace("-", "").replace("_", "")[:24]
        rg = params.get("resource_group")
        location = params.get("location", "westeurope")
        sku = params.get("sku", "Standard_LRS")
        kind = params.get("kind", "StorageV2")
        
        # Check if keys should be disabled
        disable_keys = params.get("disable_shared_key", False) or "disable" in params.get("requirements", "").lower()
        
        cmd = f"az storage account create --name {name} --resource-group {rg} --location {location} --sku {sku} --kind {kind}"
        
        # Disable shared key access if requested
        if disable_keys:
            cmd += " --allow-shared-key-access false"
        
        # Public access
        if params.get("allow_blob_public_access", True):
            cmd += " --allow-blob-public-access true"
        else:
            cmd += " --allow-blob-public-access false"
        
        # Tags
        if params.get("tags"):
            tags = params["tags"]
            if isinstance(tags, dict):
                tag_str = " ".join([f"{k}={v}" for k, v in tags.items()])
                cmd += f" --tags {tag_str}"
        
        cmd += f" --subscription {self.subscription_id} --output json"
        
        return cmd
    
    def _cmd_vm(self, params: Dict[str, Any]) -> str:
        """Generate Azure CLI command for virtual machine"""
        name = params.get("name")
        rg = params.get("resource_group")
        location = params.get("location", "westeurope")
        size = params.get("size", params.get("vm_size", "Standard_B2s"))
        os_type = params.get("os_type", "linux").lower()
        
        # Set image based on OS type
        if os_type == "linux":
            image = params.get("image", "Ubuntu2204")  # Ubuntu 22.04 LTS
        else:
            image = params.get("image", "Win2022Datacenter")
        
        cmd = f"az vm create --name {name} --resource-group {rg} --location {location} --size {size} --image {image}"
        
        # Admin credentials (required)
        admin_user = params.get("admin_username", "azureuser")
        cmd += f" --admin-username {admin_user}"
        
        # Generate SSH keys for Linux
        if os_type == "linux":
            cmd += " --generate-ssh-keys"
        
        # Tags
        if params.get("tags"):
            tags = params["tags"]
            if isinstance(tags, dict):
                tag_str = " ".join([f"{k}={v}" for k, v in tags.items()])
                cmd += f" --tags {tag_str}"
        
        cmd += f" --subscription {self.subscription_id} --output json"
        
        return cmd
    
    def _cmd_availability_set(self, params: Dict[str, Any]) -> str:
        """Generate Azure CLI command for availability set"""
        name = params.get("name")
        rg = params.get("resource_group")
        location = params.get("location", "westeurope")
        
        cmd = f"az vm availability-set create --name {name} --resource-group {rg} --location {location}"
        
        # Fault/Update domains
        if params.get("platform_fault_domain_count"):
            cmd += f" --platform-fault-domain-count {params['platform_fault_domain_count']}"
        
        if params.get("platform_update_domain_count"):
            cmd += f" --platform-update-domain-count {params['platform_update_domain_count']}"
        
        # Tags
        if params.get("tags"):
            tags = params["tags"]
            if isinstance(tags, dict):
                tag_str = " ".join([f"{k}={v}" for k, v in tags.items()])
                cmd += f" --tags {tag_str}"
        
        cmd += f" --subscription {self.subscription_id} --output json"
        
        return cmd
    
    def _cmd_vnet(self, params: Dict[str, Any]) -> str:
        """Generate Azure CLI command for virtual network"""
        name = params.get("name")
        rg = params.get("resource_group")
        location = params.get("location", "westeurope")
        address_prefix = params.get("address_prefix", "10.0.0.0/16")
        
        cmd = f"az network vnet create --name {name} --resource-group {rg} --location {location} --address-prefix {address_prefix}"
        
        # Subnet
        if params.get("subnet_name"):
            cmd += f" --subnet-name {params['subnet_name']}"
            if params.get("subnet_prefix"):
                cmd += f" --subnet-prefix {params['subnet_prefix']}"
        
        # Tags
        if params.get("tags"):
            tags = params["tags"]
            if isinstance(tags, dict):
                tag_str = " ".join([f"{k}={v}" for k, v in tags.items()])
                cmd += f" --tags {tag_str}"
        
        cmd += f" --subscription {self.subscription_id} --output json"
        
        return cmd
    
    def _cmd_resource_group(self, params: Dict[str, Any]) -> str:
        """Generate Azure CLI command for resource group"""
        name = params.get("name")
        location = params.get("location", "westeurope")
        
        cmd = f"az group create --name {name} --location {location}"
        
        # Tags
        if params.get("tags"):
            tags = params["tags"]
            if isinstance(tags, dict):
                tag_str = " ".join([f"{k}={v}" for k, v in tags.items()])
                cmd += f" --tags {tag_str}"
        
        cmd += f" --subscription {self.subscription_id} --output json"
        
        return cmd
    
    def _cmd_sql(self, params: Dict[str, Any]) -> str:
        """Generate Azure CLI command for SQL database"""
        name = params.get("name")
        rg = params.get("resource_group")
        server = params.get("server_name")
        location = params.get("location", "westeurope")
        
        # Need to create server first if not exists
        cmd = f"az sql db create --name {name} --resource-group {rg} --server {server}"
        
        # Service objective (tier)
        if params.get("service_objective"):
            cmd += f" --service-objective {params['service_objective']}"
        
        # Tags
        if params.get("tags"):
            tags = params["tags"]
            if isinstance(tags, dict):
                tag_str = " ".join([f"{k}={v}" for k, v in tags.items()])
                cmd += f" --tags {tag_str}"
        
        cmd += f" --subscription {self.subscription_id} --output json"
        
        return cmd
    
    def _generate_explanation(self, resource_type: str, params: Dict[str, Any]) -> str:
        """Generate human-readable explanation of what will be created"""
        name = params.get("name")
        rg = params.get("resource_group")
        location = params.get("location", "westeurope")
        
        explanations = {
            "disk": f"Create a managed disk '{name}' in {rg} ({location})",
            "storage": f"Create storage account '{name}' in {rg} ({location})",
            "vm": f"Create virtual machine '{name}' in {rg} ({location})",
            "availability": f"Create availability set '{name}' in {rg} ({location})",
            "vnet": f"Create virtual network '{name}' in {rg} ({location})",
            "resource group": f"Create resource group '{name}' in {location}",
            "sql": f"Create SQL database '{name}' in {rg} ({location})"
        }
        
        for key, explanation in explanations.items():
            if key in resource_type.lower():
                return explanation
        
        return f"Create {resource_type} '{name}' in {rg} ({location})"
    
    def _estimate_cost(self, resource_type: str, params: Dict[str, Any]) -> str:
        """Simple cost estimation"""
        resource_type_lower = resource_type.lower()
        
        if "disk" in resource_type_lower:
            size_gb = params.get("size_gb", params.get("disk_size_gb", 128))
            sku = params.get("sku", "Premium_LRS")
            if "premium" in sku.lower():
                return f"~${size_gb * 0.15:.2f}/month"
            else:
                return f"~${size_gb * 0.05:.2f}/month"
        
        elif "storage" in resource_type_lower:
            return "$10-50/month (depends on usage)"
        
        elif "vm" in resource_type_lower:
            size = params.get("size", params.get("vm_size", "Standard_B2s"))
            if "B1" in size:
                return "$10-20/month"
            elif "B2" in size:
                return "$30-60/month"
            else:
                return "$50-200/month"
        
        elif "availability" in resource_type_lower:
            return "$0/month (no charge for availability sets)"
        
        elif "vnet" in resource_type_lower:
            return "$0-10/month (minimal charge)"
        
        elif "resourcegroup" in resource_type_lower:
            return "$0/month (free)"
        
        else:
            return "Cost varies by usage"
    
    async def execute_command(self, command: str) -> Dict[str, Any]:
        """
        Execute Azure CLI command
        
        Args:
            command: Azure CLI command to execute
            
        Returns:
            Dict with result or error
        """
        try:
            logger.info(f"🚀 Executing: {command}")
            
            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Parse JSON output
                result = json.loads(stdout.decode('utf-8'))
                logger.info(f"✅ Command executed successfully")
                return {
                    "status": "success",
                    "result": result
                }
            else:
                error_msg = stderr.decode('utf-8')
                logger.error(f"❌ Command failed: {error_msg}")
                return {
                    "status": "error",
                    "message": error_msg
                }
                
        except Exception as e:
            logger.error(f"❌ Execution error: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
