"""
Azure Resource Creator
Handles creation of Azure resources with proper validation and confirmation
"""

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.sql import SqlManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from typing import Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class ResourceCreator:
    """Creates Azure resources with validation and confirmations"""
    
    def __init__(self, subscription_id: str = None):
        """Initialize resource creator"""
        self.credential = DefaultAzureCredential()
        self.subscription_id = subscription_id or os.getenv("AZURE_SUBSCRIPTION_ID")
        
        # Initialize management clients
        self.compute_client = ComputeManagementClient(self.credential, self.subscription_id)
        self.sql_client = SqlManagementClient(self.credential, self.subscription_id)
        self.storage_client = StorageManagementClient(self.credential, self.subscription_id)
        self.web_client = WebSiteManagementClient(self.credential, self.subscription_id)
        self.network_client = NetworkManagementClient(self.credential, self.subscription_id)
        self.resource_client = ResourceManagementClient(self.credential, self.subscription_id)
    
    async def create_virtual_machine(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a virtual machine
        
        Required params:
        - name: VM name
        - resource_group: Resource group name
        - location: Azure region
        - size: VM size (e.g., Standard_D2s_v3)
        - os_type: Windows or Linux
        - admin_username: Admin username
        - admin_password: Admin password (for Windows) or ssh_key (for Linux)
        """
        try:
            name = params["name"]
            resource_group = params["resource_group"]
            location = params.get("location", "eastus")
            vm_size = params.get("size", "Standard_D2s_v3")
            os_type = params.get("os_type", "Linux").lower()
            
            # Ensure resource group exists
            await self._ensure_resource_group(resource_group, location)
            
            # Create network components first
            vnet_name = f"{name}-vnet"
            subnet_name = f"{name}-subnet"
            nic_name = f"{name}-nic"
            ip_name = f"{name}-ip"
            
            # Create VNet
            logger.info(f"Creating VNet: {vnet_name}")
            vnet_params = {
                "location": location,
                "address_space": {
                    "address_prefixes": ["10.0.0.0/16"]
                }
            }
            vnet_poller = self.network_client.virtual_networks.begin_create_or_update(
                resource_group,
                vnet_name,
                vnet_params
            )
            vnet = vnet_poller.result()
            
            # Create Subnet
            logger.info(f"Creating Subnet: {subnet_name}")
            subnet_params = {
                "address_prefix": "10.0.0.0/24"
            }
            subnet_poller = self.network_client.subnets.begin_create_or_update(
                resource_group,
                vnet_name,
                subnet_name,
                subnet_params
            )
            subnet = subnet_poller.result()
            
            # Create Public IP
            logger.info(f"Creating Public IP: {ip_name}")
            ip_params = {
                "location": location,
                "public_ip_allocation_method": "Dynamic"
            }
            ip_poller = self.network_client.public_ip_addresses.begin_create_or_update(
                resource_group,
                ip_name,
                ip_params
            )
            public_ip = ip_poller.result()
            
            # Create NIC
            logger.info(f"Creating NIC: {nic_name}")
            nic_params = {
                "location": location,
                "ip_configurations": [{
                    "name": f"{name}-ipconfig",
                    "subnet": {"id": subnet.id},
                    "public_ip_address": {"id": public_ip.id}
                }]
            }
            nic_poller = self.network_client.network_interfaces.begin_create_or_update(
                resource_group,
                nic_name,
                nic_params
            )
            nic = nic_poller.result()
            
            # Create VM
            logger.info(f"Creating VM: {name}")
            
            # OS Profile
            if os_type == "linux":
                os_profile = {
                    "computer_name": name,
                    "admin_username": params.get("admin_username", "azureuser"),
                    "admin_password": params.get("admin_password", "TempPassword123!")  # Should be provided
                }
                
                image_reference = {
                    "publisher": "Canonical",
                    "offer": "0001-com-ubuntu-server-jammy",
                    "sku": "22_04-lts-gen2",
                    "version": "latest"
                }
            else:  # Windows
                os_profile = {
                    "computer_name": name,
                    "admin_username": params.get("admin_username", "azureuser"),
                    "admin_password": params.get("admin_password", "TempPassword123!")
                }
                
                image_reference = {
                    "publisher": "MicrosoftWindowsServer",
                    "offer": "WindowsServer",
                    "sku": "2022-Datacenter",
                    "version": "latest"
                }
            
            vm_params = {
                "location": location,
                "hardware_profile": {
                    "vm_size": vm_size
                },
                "storage_profile": {
                    "image_reference": image_reference,
                    "os_disk": {
                        "create_option": "FromImage",
                        "managed_disk": {
                            "storage_account_type": params.get("disk_type", "Standard_LRS")
                        }
                    }
                },
                "os_profile": os_profile,
                "network_profile": {
                    "network_interfaces": [{
                        "id": nic.id
                    }]
                }
            }
            
            vm_poller = self.compute_client.virtual_machines.begin_create_or_update(
                resource_group,
                name,
                vm_params
            )
            
            vm = vm_poller.result()
            
            return {
                "status": "success",
                "resource_id": vm.id,
                "name": name,
                "location": location,
                "size": vm_size,
                "os_type": os_type,
                "message": f"✅ Virtual Machine '{name}' created successfully!"
            }
            
        except Exception as e:
            logger.error(f"Error creating VM: {e}")
            return {
                "status": "error",
                "message": f"❌ Failed to create VM: {str(e)}"
            }
    
    async def create_sql_database(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create Azure SQL Database
        
        Required params:
        - name: Database name
        - server_name: SQL Server name
        - resource_group: Resource group
        - location: Azure region
        - tier: Service tier (Basic, Standard, Premium)
        """
        try:
            db_name = params["name"]
            server_name = params["server_name"]
            resource_group = params["resource_group"]
            location = params.get("location", "eastus")
            
            # Ensure resource group exists
            await self._ensure_resource_group(resource_group, location)
            
            # Check if server exists, create if not
            try:
                server = self.sql_client.servers.get(resource_group, server_name)
                logger.info(f"Using existing SQL Server: {server_name}")
            except:
                logger.info(f"Creating SQL Server: {server_name}")
                server_params = {
                    "location": location,
                    "administrator_login": params.get("admin_username", "sqladmin"),
                    "administrator_login_password": params.get("admin_password", "TempPassword123!"),
                    "version": "12.0"
                }
                server_poller = self.sql_client.servers.begin_create_or_update(
                    resource_group,
                    server_name,
                    server_params
                )
                server = server_poller.result()
            
            # Create database
            logger.info(f"Creating SQL Database: {db_name}")
            db_params = {
                "location": location,
                "sku": {
                    "name": params.get("tier", "Basic"),
                    "tier": params.get("tier", "Basic")
                }
            }
            
            db_poller = self.sql_client.databases.begin_create_or_update(
                resource_group,
                server_name,
                db_name,
                db_params
            )
            database = db_poller.result()
            
            return {
                "status": "success",
                "resource_id": database.id,
                "name": db_name,
                "server": server_name,
                "location": location,
                "message": f"✅ SQL Database '{db_name}' created successfully on server '{server_name}'!"
            }
            
        except Exception as e:
            logger.error(f"Error creating SQL Database: {e}")
            return {
                "status": "error",
                "message": f"❌ Failed to create SQL Database: {str(e)}"
            }
    
    async def create_storage_account(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create Azure Storage Account
        
        Required params:
        - name: Storage account name (must be globally unique, lowercase, no special chars)
        - resource_group: Resource group
        - location: Azure region
        - sku: SKU name (Standard_LRS, Standard_GRS, etc.)
        """
        try:
            name = params["name"].lower().replace("-", "").replace("_", "")[:24]  # Storage account name requirements
            resource_group = params["resource_group"]
            location = params.get("location", "eastus")
            sku = params.get("sku", "Standard_LRS")
            
            # Ensure resource group exists
            await self._ensure_resource_group(resource_group, location)
            
            logger.info(f"Creating Storage Account: {name}")
            storage_params = {
                "sku": {"name": sku},
                "kind": params.get("kind", "StorageV2"),
                "location": location,
                "encryption": {
                    "services": {
                        "file": {"enabled": True},
                        "blob": {"enabled": True}
                    },
                    "key_source": "Microsoft.Storage"
                },
                "enable_https_traffic_only": True
            }
            
            storage_poller = self.storage_client.storage_accounts.begin_create(
                resource_group,
                name,
                storage_params
            )
            storage_account = storage_poller.result()
            
            return {
                "status": "success",
                "resource_id": storage_account.id,
                "name": name,
                "location": location,
                "sku": sku,
                "message": f"✅ Storage Account '{name}' created successfully!"
            }
            
        except Exception as e:
            logger.error(f"Error creating Storage Account: {e}")
            return {
                "status": "error",
                "message": f"❌ Failed to create Storage Account: {str(e)}"
            }
    
    async def _ensure_resource_group(self, resource_group_name: str, location: str):
        """Ensure resource group exists, create if it doesn't"""
        try:
            self.resource_client.resource_groups.get(resource_group_name)
            logger.info(f"Resource group {resource_group_name} exists")
        except:
            logger.info(f"Creating resource group: {resource_group_name}")
            self.resource_client.resource_groups.create_or_update(
                resource_group_name,
                {"location": location}
            )
    
    def validate_resource_name(self, name: str, resource_type: str) -> Dict[str, Any]:
        """Validate resource name meets Azure naming requirements"""
        errors = []
        
        if resource_type == "storage_account":
            if len(name) < 3 or len(name) > 24:
                errors.append("Storage account name must be between 3 and 24 characters")
            if not name.islower() or not name.isalnum():
                errors.append("Storage account name must be lowercase alphanumeric only")
        
        elif resource_type in ["virtual_machine", "sql_database"]:
            if len(name) < 1 or len(name) > 64:
                errors.append(f"{resource_type} name must be between 1 and 64 characters")
            if not name[0].isalpha():
                errors.append(f"{resource_type} name must start with a letter")
        
        if errors:
            return {"valid": False, "errors": errors}
        
        return {"valid": True, "errors": []}


# Singleton instance
_resource_creator = None

def get_resource_creator(subscription_id: str = None) -> ResourceCreator:
    """Get singleton resource creator"""
    global _resource_creator
    if _resource_creator is None:
        _resource_creator = ResourceCreator(subscription_id)
    return _resource_creator
