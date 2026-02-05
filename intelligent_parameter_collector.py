"""
Intelligent Parameter Collector
Conversationally collects ALL required parameters before allowing deployment
NO SUBMISSIONS until ALL data is gathered
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from azure_schema_provider import AzureSchemaProvider

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of Azure operations"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MODIFY = "modify"  # For operations like resize, scale, etc.
    ADD = "add"  # For adding child resources (slots, endpoints, etc.)


class ParameterCollector:
    """
    Intelligently collects parameters for ANY Azure operation
    Uses Azure schemas to know what's required
    Conversationally asks for missing information
    """
    
    def __init__(self, subscription_id: str):
        self.subscription_id = subscription_id
        self.schema_provider = AzureSchemaProvider(subscription_id)
    
    def analyze_request(self, user_message: str, conversation_history: List[Dict] = None) -> Dict:
        """
        Analyze user request to determine:
        1. What operation they want (create/update/delete/modify)
        2. What resource type
        3. What parameters they've provided
        4. What parameters are missing
        
        Returns:
            {
                "operation_type": OperationType,
                "resource_type": str,  # e.g., "Microsoft.Storage/storageAccounts"
                "resource_name": str or None,
                "provided_params": dict,
                "missing_params": list,
                "ready_to_submit": bool,
                "next_question": str or None
            }
        """
        try:
            # Parse the user intent
            intent = self._parse_intent(user_message, conversation_history)
            
            if not intent["resource_type"]:
                return {
                    "operation_type": None,
                    "resource_type": None,
                    "resource_name": None,
                    "provided_params": {},
                    "missing_params": [],
                    "ready_to_submit": False,
                    "next_question": "I couldn't identify what Azure resource you want to work with. Could you be more specific?"
                }
            
            # Get schema for the resource type
            schema = self.schema_provider.get_resource_schema(intent["resource_type"])
            
            if not schema:
                logger.warning(f"Schema not available for {intent['resource_type']}")
                # Still try to proceed with basic validation
                return self._handle_no_schema(intent, user_message)
            
            # Identify required parameters
            required_params = self._get_required_parameters(
                schema, 
                intent["operation_type"]
            )
            
            # Check what we have vs what we need
            provided = intent["provided_params"]
            missing = self._identify_missing_params(required_params, provided)
            
            # Generate next question if parameters are missing
            next_question = None
            if missing:
                next_question = self._generate_next_question(
                    missing, 
                    intent["operation_type"],
                    intent["resource_type"]
                )
            
            return {
                "operation_type": intent["operation_type"],
                "resource_type": intent["resource_type"],
                "resource_name": intent.get("resource_name"),
                "target_resource": intent.get("target_resource"),  # For update operations
                "provided_params": provided,
                "missing_params": missing,
                "required_params": required_params,
                "ready_to_submit": len(missing) == 0,
                "next_question": next_question,
                "schema": schema
            }
            
        except Exception as e:
            logger.error(f"Error analyzing request: {str(e)}")
            return {
                "operation_type": None,
                "resource_type": None,
                "resource_name": None,
                "provided_params": {},
                "missing_params": [],
                "ready_to_submit": False,
                "next_question": f"I encountered an error: {str(e)}. Could you rephrase your request?"
            }
    
    def _parse_intent(self, user_message: str, conversation_history: List[Dict] = None) -> Dict:
        """
        Parse user message to extract:
        - Operation type (create/update/delete/modify)
        - Resource type
        - Parameters provided
        """
        msg_lower = user_message.lower()
        
        # Detect operation type
        operation_type = None
        if any(word in msg_lower for word in ["create", "deploy", "provision", "add new"]):
            operation_type = OperationType.CREATE
        elif any(word in msg_lower for word in ["update", "modify", "change", "edit", "set"]):
            operation_type = OperationType.UPDATE
        elif any(word in msg_lower for word in ["delete", "remove", "destroy"]):
            operation_type = OperationType.DELETE
        elif any(word in msg_lower for word in ["resize", "scale", "increase", "decrease"]):
            operation_type = OperationType.MODIFY
        elif any(word in msg_lower for word in ["add", "attach", "enable"]):
            operation_type = OperationType.ADD
        else:
            operation_type = OperationType.CREATE  # Default assumption
        
        # Detect resource type
        resource_type_map = {
            "storage account": "Microsoft.Storage/storageAccounts",
            "storage": "Microsoft.Storage/storageAccounts",
            "vm": "Microsoft.Compute/virtualMachines",
            "virtual machine": "Microsoft.Compute/virtualMachines",
            "app service": "Microsoft.Web/sites",
            "web app": "Microsoft.Web/sites",
            "function app": "Microsoft.Web/sites",
            "sql server": "Microsoft.Sql/servers",
            "sql database": "Microsoft.Sql/servers/databases",
            "resource group": "Microsoft.Resources/resourceGroups",
            "vnet": "Microsoft.Network/virtualNetworks",
            "virtual network": "Microsoft.Network/virtualNetworks",
            "subnet": "Microsoft.Network/virtualNetworks/subnets",
            "nic": "Microsoft.Network/networkInterfaces",
            "network interface": "Microsoft.Network/networkInterfaces",
            "public ip": "Microsoft.Network/publicIPAddresses",
            "nsg": "Microsoft.Network/networkSecurityGroups",
            "network security group": "Microsoft.Network/networkSecurityGroups",
            "private endpoint": "Microsoft.Network/privateEndpoints",
            "slot": "Microsoft.Web/sites/slots",
            "staging slot": "Microsoft.Web/sites/slots",
            "deployment slot": "Microsoft.Web/sites/slots",
            "disk": "Microsoft.Compute/disks",
            "managed disk": "Microsoft.Compute/disks"
        }
        
        resource_type = None
        for keyword, res_type in resource_type_map.items():
            if keyword in msg_lower:
                resource_type = res_type
                break
        
        # Extract parameters from the message
        provided_params = {}
        
        # Extract name
        if "named" in msg_lower or "name" in msg_lower or "called" in msg_lower:
            # Try to extract name
            import re
            name_patterns = [
                r'named\s+([a-zA-Z0-9_-]+)',
                r'name\s+([a-zA-Z0-9_-]+)',
                r'called\s+([a-zA-Z0-9_-]+)',
                r'create\s+([a-zA-Z0-9_-]+)',
            ]
            for pattern in name_patterns:
                match = re.search(pattern, msg_lower)
                if match:
                    provided_params["name"] = match.group(1)
                    break
        
        # Extract resource group
        if "resource group" in msg_lower or "in" in msg_lower:
            import re
            rg_patterns = [
                r'resource group\s+([a-zA-Z0-9_-]+)',
                r'in\s+([a-zA-Z0-9_-]+)',
                r'rg\s+([a-zA-Z0-9_-]+)',
            ]
            for pattern in rg_patterns:
                match = re.search(pattern, msg_lower)
                if match:
                    possible_rg = match.group(1)
                    # Filter out common words that aren't resource groups
                    if possible_rg not in ["the", "a", "an", "this", "that", "with", "for"]:
                        provided_params["resource_group"] = possible_rg
                        break
        
        # Extract location/region
        azure_regions = [
            "eastus", "eastus2", "westus", "westus2", "westus3",
            "centralus", "northcentralus", "southcentralus", "westcentralus",
            "canadacentral", "canadaeast",
            "brazilsouth",
            "northeurope", "westeurope",
            "uksouth", "ukwest",
            "francecentral", "francesouth",
            "germanywestcentral",
            "switzerlandnorth", "switzerlandwest",
            "norwayeast", "norwaywest",
            "swedencentral",
            "eastasia", "southeastasia",
            "japaneast", "japanwest",
            "koreacentral", "koreasouth",
            "australiaeast", "australiasoutheast", "australiacentral",
            "southindia", "centralindia", "westindia",
            "uaenorth", "uaecentral"
        ]
        
        for region in azure_regions:
            if region in msg_lower.replace(" ", ""):
                provided_params["location"] = region
                break
        
        # Common region name mappings
        region_aliases = {
            "east us": "eastus",
            "west us": "westus",
            "west europe": "westeurope",
            "north europe": "northeurope",
            "uk south": "uksouth"
        }
        
        for alias, region in region_aliases.items():
            if alias in msg_lower:
                provided_params["location"] = region
                break
        
        # Extract size (for VMs, disks, etc.)
        if "size" in msg_lower:
            import re
            size_match = re.search(r'size\s+([A-Za-z0-9_]+)', msg_lower)
            if size_match:
                provided_params["size"] = size_match.group(1)
        
        # Extract SKU (for storage, etc.)
        sku_keywords = ["standard", "premium", "lrs", "grs", "zrs"]
        for keyword in sku_keywords:
            if keyword in msg_lower:
                if "sku" not in provided_params:
                    provided_params["sku"] = keyword
        
        # For UPDATE operations, try to identify target resource
        target_resource = None
        if operation_type in [OperationType.UPDATE, OperationType.MODIFY, OperationType.ADD]:
            # Try to identify existing resource name
            for_patterns = [
                r'for\s+([a-zA-Z0-9_-]+)',
                r'on\s+([a-zA-Z0-9_-]+)',
                r'to\s+([a-zA-Z0-9_-]+)',
            ]
            import re
            for pattern in for_patterns:
                match = re.search(pattern, msg_lower)
                if match:
                    target_resource = match.group(1)
                    break
        
        # For tags
        if "tag" in msg_lower:
            import re
            tag_match = re.search(r'tag\s+([a-zA-Z0-9_-]+)\s*[:=]\s*([a-zA-Z0-9_-]+)', msg_lower)
            if tag_match:
                if "tags" not in provided_params:
                    provided_params["tags"] = {}
                provided_params["tags"][tag_match.group(1)] = tag_match.group(2)
        
        return {
            "operation_type": operation_type,
            "resource_type": resource_type,
            "resource_name": provided_params.get("name"),
            "target_resource": target_resource,
            "provided_params": provided_params
        }
    
    def _get_required_parameters(self, schema: Dict, operation_type: OperationType) -> List[Dict]:
        """
        Get required parameters based on operation type and resource schema
        """
        required = []
        
        # Always need resource name for most operations
        if operation_type != OperationType.DELETE:
            required.append({
                "name": "name",
                "type": "string",
                "description": "Resource name",
                "mandatory": True
            })
        
        # For CREATE operations
        if operation_type == OperationType.CREATE:
            # Location is almost always required for CREATE
            required.append({
                "name": "location",
                "type": "string",
                "description": "Azure region",
                "mandatory": True
            })
            
            # Resource group (except for resource groups themselves)
            if schema.get("resourceType") != "Microsoft.Resources/resourceGroups":
                required.append({
                    "name": "resource_group",
                    "type": "string",
                    "description": "Resource group name",
                    "mandatory": True
                })
            
            # Add resource-specific required properties
            properties = schema.get("properties", {})
            for prop_name, prop_info in properties.items():
                if prop_info.get("required", False):
                    required.append({
                        "name": prop_name,
                        "type": prop_info.get("type", "string"),
                        "description": prop_info.get("description", f"{prop_name} property"),
                        "mandatory": True,
                        "enum": prop_info.get("enum"),
                        "default": prop_info.get("default")
                    })
        
        # For UPDATE/MODIFY operations
        elif operation_type in [OperationType.UPDATE, OperationType.MODIFY]:
            required.append({
                "name": "target_resource",
                "type": "string",
                "description": "Existing resource to modify",
                "mandatory": True
            })
            required.append({
                "name": "resource_group",
                "type": "string",
                "description": "Resource group of the resource",
                "mandatory": True
            })
        
        # For ADD operations (like adding slots, endpoints)
        elif operation_type == OperationType.ADD:
            required.append({
                "name": "parent_resource",
                "type": "string",
                "description": "Parent resource name",
                "mandatory": True
            })
            required.append({
                "name": "resource_group",
                "type": "string",
                "description": "Resource group",
                "mandatory": True
            })
        
        # For DELETE operations
        elif operation_type == OperationType.DELETE:
            required.append({
                "name": "target_resource",
                "type": "string",
                "description": "Resource to delete",
                "mandatory": True
            })
            required.append({
                "name": "resource_group",
                "type": "string",
                "description": "Resource group",
                "mandatory": True
            })
        
        return required
    
    def _identify_missing_params(self, required_params: List[Dict], provided_params: Dict) -> List[Dict]:
        """
        Identify which required parameters are missing
        """
        missing = []
        
        for req_param in required_params:
            param_name = req_param["name"]
            
            # Check if parameter is provided
            if param_name not in provided_params or not provided_params[param_name]:
                # Check for aliases
                aliases = {
                    "resource_group": ["rg", "resourcegroup"],
                    "location": ["region", "loc"],
                    "target_resource": ["resource", "resource_name"]
                }
                
                found = False
                if param_name in aliases:
                    for alias in aliases[param_name]:
                        if alias in provided_params and provided_params[alias]:
                            # Copy aliased value to main parameter
                            provided_params[param_name] = provided_params[alias]
                            found = True
                            break
                
                if not found and req_param.get("mandatory", True):
                    missing.append(req_param)
        
        return missing
    
    def _generate_next_question(self, missing_params: List[Dict], operation_type: OperationType, resource_type: str) -> str:
        """
        Generate conversational question for the next missing parameter
        """
        if not missing_params:
            return None
        
        # Ask for the first missing parameter
        param = missing_params[0]
        param_name = param["name"]
        description = param["description"]
        
        # Friendly question templates
        questions = {
            "name": f"What would you like to name this {self._friendly_resource_name(resource_type)}?",
            "location": "Which Azure region would you like to use? (e.g., eastus, westeurope, southeastasia)",
            "resource_group": "Which resource group should this be deployed to?",
            "target_resource": f"Which {self._friendly_resource_name(resource_type)} would you like to modify?",
            "parent_resource": "What's the name of the parent resource?",
            "sku": "Which SKU/tier would you like? (e.g., Standard_LRS, Premium_LRS for storage)",
            "size": "What size/VM size would you like? (e.g., Standard_B2s, Standard_D2s_v3)",
        }
        
        question = questions.get(param_name, f"Please provide the {param_name} ({description})")
        
        # Add enum options if available
        if param.get("enum"):
            options = param["enum"][:5]  # Show first 5 options
            question += f"\n\nOptions: {', '.join(options)}"
        
        # Add default if available
        if param.get("default"):
            question += f"\n(Default: {param['default']})"
        
        return question
    
    def _friendly_resource_name(self, resource_type: str) -> str:
        """Convert resource type to friendly name"""
        mappings = {
            "Microsoft.Storage/storageAccounts": "storage account",
            "Microsoft.Compute/virtualMachines": "virtual machine",
            "Microsoft.Web/sites": "web app",
            "Microsoft.Sql/servers": "SQL server",
            "Microsoft.Network/virtualNetworks": "virtual network",
            "Microsoft.Network/privateEndpoints": "private endpoint",
            "Microsoft.Web/sites/slots": "deployment slot"
        }
        return mappings.get(resource_type, resource_type.split('/')[-1])
    
    def _handle_no_schema(self, intent: Dict, user_message: str) -> Dict:
        """
        Handle cases where schema is not available
        Use basic heuristics
        """
        # Basic required params for common operations
        basic_required = []
        
        if intent["operation_type"] == OperationType.CREATE:
            basic_required = ["name", "resource_group", "location"]
        elif intent["operation_type"] in [OperationType.UPDATE, OperationType.MODIFY]:
            basic_required = ["target_resource", "resource_group"]
        
        provided = intent["provided_params"]
        missing = [{"name": param, "description": param, "mandatory": True} 
                   for param in basic_required if param not in provided]
        
        next_question = None
        if missing:
            next_question = self._generate_next_question(
                missing,
                intent["operation_type"],
                intent["resource_type"]
            )
        
        return {
            "operation_type": intent["operation_type"],
            "resource_type": intent["resource_type"],
            "resource_name": intent.get("resource_name"),
            "target_resource": intent.get("target_resource"),
            "provided_params": provided,
            "missing_params": missing,
            "required_params": [{"name": p, "mandatory": True} for p in basic_required],
            "ready_to_submit": len(missing) == 0,
            "next_question": next_question,
            "schema": None
        }
