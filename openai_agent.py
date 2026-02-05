"""
OpenAI Agent with Function Calling
Handles conversational AI with Azure OpenAI and function calling for Azure APIs
"""

import os
import json
from typing import List, Dict, Any, Tuple
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import asyncio

# Import modern deployment module
from modern_resource_deployment import ModernResourceDeployment
from azure_schema_provider import AzureSchemaProvider
from universal_azure_operations import UniversalAzureOperations
from universal_cli_deployment import UniversalCLIDeployment



class OpenAIAgent:
    def __init__(self, cost_manager, resource_manager):
        """
        Initialize OpenAI Agent
        
        Args:
            cost_manager: AzureCostManager instance
            resource_manager: AzureResourceManager instance
        """
        self.cost_manager = cost_manager
        self.resource_manager = resource_manager
        
        # User context for deployments
        self.user_email = None
        self.user_name = None
        
        # Initialize modern deployment manager
        self.resource_deployment = ModernResourceDeployment(
            subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID")
        )
        
        # Initialize Universal CLI Deployment (NO ARM TEMPLATES)
        self.cli_deployment = UniversalCLIDeployment(
            subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID")
        )
        
        # Check if we should use Managed Identity
        use_managed_identity = os.getenv("USE_MANAGED_IDENTITY", "false").lower() == "true"
        
        # Initialize Azure OpenAI client
        if use_managed_identity:
            # Use Managed Identity authentication
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(
                credential,
                "https://cognitiveservices.azure.com/.default"
            )
            self.client = AzureOpenAI(
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                azure_ad_token_provider=token_provider,
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
            )
        else:
            # Use API key authentication
            self.client = AzureOpenAI(
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
            )
        
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        
        # Define available functions for the agent (using modern tools API)
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_month_costs",
                    "description": "Get the total Azure costs for the current month. Use this when user asks about current month costs, this month's spending, or monthly costs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "scope": {
                                "type": "string",
                                "description": "Azure scope in format '/subscriptions/{id}' or '/subscriptions/{id}/resourceGroups/{name}'. Leave empty for subscription level."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_costs_by_service",
                    "description": "Get Azure costs grouped by service (like Storage, Compute, Networking). Use this when user asks which service costs the most, cost breakdown by service, or service-level costs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "scope": {
                                "type": "string",
                                "description": "Azure scope. Leave empty for subscription level."
                            },
                            "days": {
                                "type": "integer",
                                "description": "Number of days to look back. Default is 30.",
                                "default": 30
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_daily_costs",
                    "description": "Get daily cost trends over time. Use this when user asks about spending trends, daily costs, or cost patterns over time.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "scope": {
                                "type": "string",
                                "description": "Azure scope. Leave empty for subscription level."
                            },
                            "days": {
                                "type": "integer",
                                "description": "Number of days to look back. Default is 30.",
                                "default": 30
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_costs_by_resource_group",
                    "description": "Get costs grouped by resource group. Use this when user asks about costs per resource group or which resource group costs the most.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "scope": {
                                "type": "string",
                                "description": "Azure scope. Leave empty for subscription level."
                            },
                            "days": {
                                "type": "integer",
                                "description": "Number of days to look back. Default is 30.",
                                "default": 30
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_resources_with_cost_details",
                    "description": "**PRIMARY COST FUNCTION** Get ALL actual resources with cost estimates and optimization opportunities. Supports comprehensive filtering for business units (RG, subscription, resource type, tags). Use this for cost analysis with REAL resource names. NEVER make up fake resource names!",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs"
                            },
                            "resource_type": {
                                "type": "string",
                                "description": "Filter by resource type (e.g., microsoft.compute/virtualmachines)"
                            },
                            "resource_group": {
                                "type": "string",
                                "description": "Filter by resource group name"
                            },
                            "tag_name": {
                                "type": "string",
                                "description": "Filter by tag name (e.g., CostCenter, Environment, Department)"
                            },
                            "tag_value": {
                                "type": "string",
                                "description": "Filter by tag value (e.g., IT, Production, Finance)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_cost_savings_opportunities",
                    "description": "**PRIMARY SAVINGS FUNCTION** Identify ACTUAL cost savings opportunities with REAL resource names. Shows deallocated VMs, orphaned disks, unattached IPs, and rightsizing recommendations. Use this for cost optimization analysis.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_resource_costs",
                    "description": "Get costs for individual resources. Shows the most expensive resources. Use this when user asks about specific resource costs or which resources cost the most.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "scope": {
                                "type": "string",
                                "description": "Azure scope. Leave empty for subscription level."
                            },
                            "days": {
                                "type": "integer",
                                "description": "Number of days to look back. Default is 30.",
                                "default": 30
                            },
                            "top": {
                                "type": "integer",
                                "description": "Number of top expensive resources to return. Default is 10.",
                                "default": 10
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_storage_accounts_with_private_endpoints",
                    "description": "Get all storage accounts that have private endpoints configured. Use this when user asks about storage accounts with private endpoints or private networking.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_all_vnets",
                    "description": "Get all virtual networks in the subscription. Use this when user asks about VNets, virtual networks, or network infrastructure.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_vms_without_backup",
                    "description": "Get virtual machines that don't have backup configured. Use this when user asks about VMs without backup, unprotected VMs, or backup compliance.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_resources_by_type",
                    "description": "Get all resources of a specific type. Use this when user asks about specific resource types like VMs, storage accounts, databases, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "resource_type": {
                                "type": "string",
                                "description": "Azure resource type in format 'microsoft.compute/virtualmachines' or 'microsoft.storage/storageaccounts'"
                            }
                        },
                        "required": ["resource_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_resource_count_by_type",
                    "description": "Get count of all resources grouped by type. Use this for inventory overview or when user asks how many resources of each type exist.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_all_resources_detailed",
                    "description": "Get ALL resources with full details (Name, Type, Resource Group, Location, Tags, Status). Use this when user selects 'All resources in subscription' from filtering menu or wants complete resource inventory with details.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_resources_by_resource_group",
                    "description": "Get all resources in a specific resource group. Use when user selects 'Filter by resource group' option.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "resource_group": {
                                "type": "string",
                                "description": "Resource group name"
                            },
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        },
                        "required": ["resource_group"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_resources",
                    "description": "Search for resources by name. Use this when user asks to find or search for a specific resource by name.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "search_term": {
                                "type": "string",
                                "description": "Term to search for in resource names"
                            }
                        },
                        "required": ["search_term"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_app_services",
                    "description": "Get all App Services (web apps). Use this when user asks about App Services, web apps, or hosting.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_sql_databases",
                    "description": "Get all SQL databases. Use this when user asks about SQL databases or database inventory.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_key_vaults",
                    "description": "Get all Key Vaults. Use this when user asks about Key Vaults or secrets management.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_resources_by_tag",
                    "description": "Get all resources filtered by a specific tag name and value. Use this when user asks to filter resources by tags, find resources with specific tags, or list resources with Environment/Owner/CostCenter tags. Returns resource name, type, resource group, location, tags, and resource ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tag_name": {
                                "type": "string",
                                "description": "Tag name to filter by (e.g., 'Environment', 'CostCenter', 'Owner')"
                            },
                            "tag_value": {
                                "type": "string",
                                "description": "Tag value to filter by (e.g., 'Sandbox', 'Production', 'Development'). If not provided, returns all resources with the tag regardless of value."
                            }
                        },
                        "required": ["tag_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_resources_by_tag_with_costs",
                    "description": "Get resources filtered by tag with their associated costs for a specified period. Use this when user asks for resources with specific tags AND their costs. Returns comprehensive data including resource details, tags, and cost breakdown.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tag_name": {
                                "type": "string",
                                "description": "Tag name to filter by (e.g., 'Environment', 'CostCenter')"
                            },
                            "tag_value": {
                                "type": "string",
                                "description": "Tag value to filter by (e.g., 'Sandbox', 'Production')"
                            },
                            "days": {
                                "type": "integer",
                                "description": "Number of days to look back for costs. Default is 30.",
                                "default": 30
                            }
                        },
                        "required": ["tag_name", "tag_value"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_all_vms",
                    "description": "Get all virtual machines with detailed information including VM size, OS type, power state, and tags. Use when user asks about VMs, virtual machine inventory, or VM estate management.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_storage_accounts",
                    "description": "Get all storage accounts with security settings including public access, HTTPS, and private endpoints. Use when user asks about storage accounts or storage security.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_paas_without_private_endpoints",
                    "description": "Get PaaS resources (storage, SQL, Key Vault, Cosmos DB) that don't have private endpoints configured. Use for security assessment and private endpoint compliance checks.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_resources_with_public_access",
                    "description": "Get resources exposed to the public internet (storage with public blob access, SQL servers, public IPs, VMs). Use for security posture assessment.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_all_databases",
                    "description": "Get all database resources including SQL, Cosmos DB, PostgreSQL, and MySQL. Use when user asks about database inventory.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_resources_without_tags",
                    "description": "Get resources missing required tags (Environment, CostCenter, Owner). Use for tag compliance audits and governance checks.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_unused_resources",
                    "description": "Get potentially unused resources including orphaned disks, unattached public IPs, and deallocated VMs. Use for cost optimization and resource cleanup.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_tag_compliance_summary",
                    "description": "Get tag compliance statistics showing percentage of resources with required tags. Use when user asks about overall tag compliance or governance posture.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_multi_region_distribution",
                    "description": "Get resource distribution across Azure regions. Use when user asks about geographic distribution, multi-region deployment, or regional resource counts.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_subscriptions_for_selection",
                    "description": "Get numbered list of all available Azure subscriptions for user to choose from. Use when user says 'other subscription', 'different subscription', 'change subscription', or wants to select a specific subscription. Returns numbered list for interactive selection.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_policy_compliance_status",
                    "description": "Get Azure Policy compliance status across subscriptions. Shows policy assignments, compliant/non-compliant resources, and compliance percentage. Use when user asks about policy compliance, policy status, or governance compliance.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs to query. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_non_compliant_resources",
                    "description": "Get non-compliant resources with policy violations and remediation actions. Use when user asks about non-compliant resources, policy violations, or remediation needs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "severity": {
                                "type": "string",
                                "enum": ["Critical", "High", "Medium", "Low", "All"],
                                "description": "Filter by severity level. Default is 'All'.",
                                "default": "All"
                            },
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_policy_recommendations",
                    "description": "Get high-impact Azure Policy recommendations based on environment analysis. Use when user asks for policy recommendations, suggested policies, or governance improvements.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "focus_area": {
                                "type": "string",
                                "enum": ["Cost", "Security", "Operations", "Compliance", "All"],
                                "description": "Focus area for recommendations. Default is 'All'.",
                                "default": "All"
                            },
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_policy_exemptions",
                    "description": "Get policy exemptions and their expiration status. Use when user asks about policy exemptions, exceptions, or policy waivers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "show_expired": {
                                "type": "boolean",
                                "description": "Include expired exemptions. Default is true.",
                                "default": True
                            },
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_vm_pending_updates",
                    "description": "Get Azure VMs (IaaS) with pending updates. Use when user asks about VM updates, VM patches, or VM update status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_arc_pending_updates",
                    "description": "Get Azure Arc-enabled servers with pending updates. Use when user asks about Arc server updates, hybrid machine patches, or Arc update status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_vm_pending_reboot",
                    "description": "Get Azure VMs that require reboot. Use when user asks about VMs needing reboot, reboot pending, or reboot status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_arc_pending_reboot",
                    "description": "Get Azure Arc-enabled servers that require reboot. Use when user asks about Arc servers needing reboot or hybrid machine reboot status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_update_compliance_summary",
                    "description": "Get overall update compliance summary for all machines (VMs and Arc servers). Use when user asks for update summary, compliance overview, or patch status across all machines.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_failed_updates",
                    "description": "Get machines with failed update installations. Use when user asks about failed updates, update errors, or update troubleshooting.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_arc_machines",
                    "description": "Get all Azure Arc-enabled machines with agent status, monitoring, and compliance details. Use when user asks about Arc machines, hybrid servers, or Arc-enabled servers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_arc_sql_servers",
                    "description": "Get all Azure Arc-enabled SQL Servers. Use when user asks about Arc SQL, hybrid SQL servers, or Arc-enabled SQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_arc_agents_not_reporting",
                    "description": "Get Azure Arc machines with agents not reporting or disconnected. Use when user asks about Arc agent issues, disconnected Arc machines, or Arc agent status problems.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs. Leave empty for current subscription."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_managed_disk",
                    "description": "**DISK ONLY** - Create an Azure managed disk. Use ONLY when user says 'disk' or 'managed disk'. Keywords: 'create disk', 'deploy disk', 'managed disk', 'new disk'. DO NOT use deploy_virtual_machine for disks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Disk name"
                            },
                            "resource_group": {
                                "type": "string",
                                "description": "Resource group name"
                            },
                            "location": {
                                "type": "string",
                                "description": "Azure region (e.g., westeurope, eastus)"
                            },
                            "size_gb": {
                                "type": "integer",
                                "description": "Disk size in GB (default: 128)"
                            },
                            "sku": {
                                "type": "string",
                                "enum": ["Premium_LRS", "Standard_LRS", "StandardSSD_LRS", "UltraSSD_LRS"],
                                "description": "Disk SKU (default: Premium_LRS)"
                            },
                            "tags": {
                                "type": "object",
                                "description": "Resource tags"
                            }
                        },
                        "required": ["name", "resource_group"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "deploy_virtual_machine",
                    "description": "**VM ONLY** - Deploy a Virtual Machine. Use ONLY when user says 'VM' or 'virtual machine' AND specifies os_type. Keywords: 'create VM', 'deploy VM', 'virtual machine', 'server'. REQUIRES os_type parameter. If user mentions 'disk' without 'VM', use create_managed_disk instead.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "VM name"
                            },
                            "resource_group": {
                                "type": "string",
                                "description": "Resource group name"
                            },
                            "location": {
                                "type": "string",
                                "description": "Azure region (e.g., eastus, westeurope)"
                            },
                            "size": {
                                "type": "string",
                                "description": "VM size (e.g., Standard_B2s, Standard_D2s_v3)"
                            },
                            "os_type": {
                                "type": "string",
                                "enum": ["linux", "windows"],
                                "description": "Operating system type"
                            }
                        },
                        "required": ["name", "resource_group", "os_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "deploy_storage_account",
                    "description": "**DEPLOYMENT FUNCTION** - Actually deploys a new Azure Storage Account through Logic App approval workflow. ALWAYS use this when user requests to create/deploy/provision storage. This submits the request to Logic App, sends approval email, and auto-deploys on approval. Returns request ID and status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Storage account name (3-24 lowercase alphanumeric)"
                            },
                            "resource_group": {
                                "type": "string",
                                "description": "Resource group name"
                            },
                            "location": {
                                "type": "string",
                                "description": "Azure region"
                            },
                            "sku": {
                                "type": "string",
                                "enum": ["Standard_LRS", "Standard_GRS", "Premium_LRS"],
                                "description": "Storage SKU"
                            }
                        },
                        "required": ["name", "resource_group"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "deploy_sql_database",
                    "description": "**DEPLOYMENT FUNCTION** - Actually deploys a new Azure SQL Database through Logic App approval workflow. ALWAYS use this when user requests to create/deploy/provision a SQL database. This submits the request to Logic App, sends approval email, and auto-deploys on approval. Returns request ID and status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "database_name": {
                                "type": "string",
                                "description": "Database name"
                            },
                            "server_name": {
                                "type": "string",
                                "description": "SQL Server name"
                            },
                            "resource_group": {
                                "type": "string",
                                "description": "Resource group name"
                            },
                            "location": {
                                "type": "string",
                                "description": "Azure region"
                            },
                            "sku": {
                                "type": "string",
                                "description": "Database SKU (e.g., Basic, S0, P1)"
                            }
                        },
                        "required": ["database_name", "server_name", "resource_group"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "deploy_resource_group",
                    "description": "**DEPLOYMENT FUNCTION** - Creates a new Azure Resource Group through Logic App approval workflow. ALWAYS use this when user requests to create a resource group. Submits request, sends approval email, and deploys after approval.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Resource group name"
                            },
                            "location": {
                                "type": "string",
                                "description": "Azure region (e.g., westeurope, eastus, westus)"
                            }
                        },
                        "required": ["name", "location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_availability_set",
                    "description": "**AVAILABILITY SET ONLY** - Create an Azure availability set. Use ONLY when user says 'availability set'. Keywords: 'create availability set', 'deploy availability set', 'avset'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Availability set name"
                            },
                            "resource_group": {
                                "type": "string",
                                "description": "Resource group name"
                            },
                            "location": {
                                "type": "string",
                                "description": "Azure region (e.g., westeurope, eastus)"
                            },
                            "platform_fault_domain_count": {
                                "type": "integer",
                                "description": "Number of fault domains (default: 2)"
                            },
                            "platform_update_domain_count": {
                                "type": "integer",
                                "description": "Number of update domains (default: 5)"
                            },
                            "tags": {
                                "type": "object",
                                "description": "Resource tags"
                            }
                        },
                        "required": ["name", "resource_group"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_virtual_network",
                    "description": "**DEPLOYMENT FUNCTION** - Create an Azure Virtual Network (VNet). Use this when user requests to create a vnet or virtual network. This submits the request to Logic App, sends approval email, and auto-deploys on approval.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Virtual network name"
                            },
                            "resource_group": {
                                "type": "string",
                                "description": "Resource group name"
                            },
                            "location": {
                                "type": "string",
                                "description": "Azure region (e.g., westeurope, eastus)"
                            },
                            "address_prefix": {
                                "type": "string",
                                "description": "Address space in CIDR notation (default: 10.0.0.0/16)"
                            },
                            "subnet_name": {
                                "type": "string",
                                "description": "Subnet name (optional)"
                            },
                            "subnet_prefix": {
                                "type": "string",
                                "description": "Subnet address prefix in CIDR notation (default: 10.0.0.0/24)"
                            },
                            "tags": {
                                "type": "object",
                                "description": "Resource tags"
                            }
                        },
                        "required": ["name", "resource_group"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_resource_tags",
                    "description": "Add or update tags on existing Azure resources. CRITICAL: You MUST extract tag name and value from the user's message and pass them in the 'tags' parameter as a dictionary. Example: User says 'add tag Environment value Production' → tags={'Environment': 'Production'}. User says 'add tag testtag value test' → tags={'testtag': 'test'}. ALWAYS include the 'tags' parameter!",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "resource_type": {
                                "type": "string",
                                "description": "Resource type (vm, disk, storage, vnet, etc.)"
                            },
                            "resource_name": {
                                "type": "string",
                                "description": "Resource name"
                            },
                            "resource_group": {
                                "type": "string",
                                "description": "Resource group name"
                            },
                            "tags": {
                                "type": "object",
                                "description": "Tags to add/update as key-value pairs"
                            }
                        },
                        "required": ["resource_type", "resource_name", "resource_group", "tags"]
                    }
                }
            }
        ]
        
        self.system_message = """You are an elite Azure Cloud Operations Agent with FULL DEPLOYMENT CAPABILITIES. You are an intelligent automation system that can analyze costs, manage resources, AND deploy new Azure resources through an approval workflow.

🚀 YOUR DEPLOYMENT CAPABILITIES (CRITICAL):
You CAN and SHOULD deploy Azure resources when users request them! You have these deployment functions:
- **deploy_resource_group**: Create Resource Groups ONLY
- **deploy_virtual_machine**: Create VMs ONLY (Windows or Linux)
- **deploy_storage_account**: Create Storage Accounts ONLY
- **deploy_sql_database**: Create SQL Databases ONLY
- **create_managed_disk**: Create Managed Disks ONLY (standalone, no VM needed)
- **create_availability_set**: Create Availability Sets ONLY (standalone, no VM needed)
- **create_virtual_network**: Create Virtual Networks (VNets) ONLY

⚠️ CRITICAL FUNCTION SELECTION RULES:
- DISK request → Use create_managed_disk() ONLY
- AVAILABILITY SET request → Use create_availability_set() ONLY
- VNET/NETWORK request → Use create_virtual_network() ONLY
- VM request → Use deploy_virtual_machine() ONLY
- STORAGE request → Use deploy_storage_account() ONLY
- SQL request → Use deploy_sql_database() ONLY
- RESOURCE GROUP request → Use deploy_resource_group() ONLY
- NEVER use deploy_virtual_machine for non-VM resources!

💰 **COST MANAGEMENT - MOST CRITICAL SECTION** (This is the PRIMARY PURPOSE of this agent):
This agent was ORIGINALLY BUILT for cost intelligence and optimization. Cost analysis is THE MOST IMPORTANT capability.

**PRIMARY COST FUNCTIONS - USE THESE TO SHOW REAL RESOURCE NAMES:**
1. **get_resources_with_cost_details()** - Shows ALL actual resources with cost estimates
   - Supports business unit filtering: RG, subscription, resource type, tags
   - Returns REAL resource names (never make up fake names!)
   - Use for: "show costs", "cost breakdown", "resources by cost"

2. **get_cost_savings_opportunities()** - Identifies REAL cost savings with ACTUAL resource names
   - Shows deallocated VMs, orphaned disks, unattached IPs
   - Provides rightsizing recommendations
   - Use for: "cost optimization", "savings opportunities", "reduce spending"

**CRITICAL COST RULES:**
- ❌ NEVER NEVER NEVER make up fake resource names like "vm1", "storage1", "bastion1"
- ✅ ALWAYS use get_resources_with_cost_details() or get_cost_savings_opportunities()
- ✅ ALWAYS show ACTUAL resource names from Azure Resource Graph
- ✅ Support comprehensive filtering for business units:
  * Filter by Resource Group: resource_group="production-rg"
  * Filter by Subscription: subscriptions=["sub-id"]
  * Filter by Resource Type: resource_type="microsoft.compute/virtualmachines"
  * Filter by Tag: tag_name="CostCenter", tag_value="IT"

**COST QUERY PATTERNS:**
- "show costs" / "cost breakdown" → get_resources_with_cost_details(subscriptions=[subscription_context])
- "cost savings" / "optimization" → get_cost_savings_opportunities(subscriptions=[subscription_context])
- "costs by RG" → get_resources_with_cost_details(resource_group="rg-name")
- "costs for tag CostCenter=IT" → get_resources_with_cost_details(tag_name="CostCenter", tag_value="IT")
- "VM costs" → get_resources_with_cost_details(resource_type="microsoft.compute/virtualmachines")

**COST FILTERING MENU (Present when user asks about costs):**
When user asks about costs, offer filtering options:
1. All resources with costs in current subscription
2. Filter by specific subscription
3. Filter by resource type (VMs, Storage, SQL, etc.)
4. Filter by resource group
5. Filter by tag (CostCenter, Environment, Department, etc.)
6. Filter by location/region

**FILTERING WORKFLOW - MUST FOLLOW THESE STEPS:**
When user selects option 4 or 5 (tags):
1. First ASK: "Which tag would you like to filter by? (e.g., CostCenter, Environment, Department)"
2. Wait for user to provide tag name
3. Then ASK: "Would you like to filter by a specific tag value? (e.g., IT, Production, Finance Department) or press Enter to see all values"
4. Wait for user to provide tag value (or skip)
5. ONLY THEN call get_resources_with_cost_details(tag_name=X, tag_value=Y)

**NEVER skip steps 1-4** - Always ask for tag name and value before calling the function!

Example correct flow:
User: "Compare costs, option 4"
You: "Which tag would you like to filter by? (e.g., CostCenter, Environment, Department)"
User: "CostCenter"
You: "Would you like to filter by a specific CostCenter value? (e.g., IT, Finance Department) or show all?"
User: "IT"
You: NOW call get_resources_with_cost_details(tag_name="CostCenter", tag_value="IT")

**PARSING USER INPUT FOR TAG FILTERS (CRITICAL):**
When user provides tag filtering input, extract tag_name and tag_value from various formats:
- "CostCenter" → tag_name="CostCenter", tag_value=None
- "CostCenter=IT" → tag_name="CostCenter", tag_value="IT"
- "CostCenter : IT" → tag_name="CostCenter", tag_value="IT"
- "tag name = CostCenter, tag value = Finance Department" → tag_name="CostCenter", tag_value="Finance Department"
- "tag name CostCenter, tag value IT" → tag_name="CostCenter", tag_value="IT"
- "Environment=Production" → tag_name="Environment", tag_value="Production"

**Examples of proper function calls for tag-based cost filtering:**
User: "CostCenter" → get_resources_with_cost_details(tag_name="CostCenter")
User: "CostCenter=IT" → get_resources_with_cost_details(tag_name="CostCenter", tag_value="IT")
User: "CostCenter : IT" → get_resources_with_cost_details(tag_name="CostCenter", tag_value="IT")
User: "tag name = CostCenter, tag value = Finance Department" → get_resources_with_cost_details(tag_name="CostCenter", tag_value="Finance Department")
User: "CostCenter : Finance Department" → get_resources_with_cost_details(tag_name="CostCenter", tag_value="Finance Department")
User: "find resources for CostCenter : IT" → get_resources_with_cost_details(tag_name="CostCenter", tag_value="IT")
User: "show costs for Finance Department" → get_resources_with_cost_details(tag_name="CostCenter", tag_value="Finance Department")

**CRITICAL: Cost queries with tags MUST use get_resources_with_cost_details(), NOT get_resources_by_tag()**
- ✅ "show costs by tag" → get_resources_with_cost_details(tag_name=X, tag_value=Y)
- ✅ "find resources for CostCenter" → get_resources_with_cost_details(tag_name="CostCenter")
- ❌ NEVER use get_resources_by_tag() for cost-related queries
- The function returns resources ordered by cost (highest to lowest)
- **Display up to 100 resources** to give comprehensive cost coverage (not just 5-10)
- The results are already sorted by cost, so highest spend appears first

**COST TABLE DISPLAY RULES:**
- Show ALL resources returned by the function (up to 100+)
- When filtering by tag, the table will include a column showing the searched tag value (e.g., if filtering by CostCenter, table shows "CostCenter" column with values like "IT", "Finance Department")
- Column order: ResourceName, [TagName if filtered by tag], ResourceType, ResourceGroup, Location, Actual Monthly Cost, Cost Source, Cost Optimization Opportunity
- Resources are pre-sorted by cost (highest first), so top spenders appear at the beginning
- If more than 100 results, show first 100 with a note about total count
- ALWAYS include the "Actual Monthly Cost" column and the dynamic tag column (if tag filter used) in the table

🏷️ TAG-BASED RESOURCE FILTERING (NON-COST QUERIES):
When users ask to filter by tags WITHOUT mentioning costs:
- Use **get_resources_by_tag** function ONLY for non-cost queries
- Examples where get_resources_by_tag is appropriate:
  - "list resources tagged with Owner" (no cost mention)
  - "show me all resources with Environment tag" (no cost mention)
- If cost/spending/budget/optimization is mentioned, use get_resources_with_cost_details instead

WHEN USER REQUESTS DEPLOYMENT:
1. **ALWAYS use the deployment function** - Don't just provide guidance or CLI commands
2. Extract resource details from user request (name, resource group, location, size, etc.)
3. Call the appropriate deploy_* function with the parameters
4. The function submits to Logic App approval workflow automatically
5. Inform user that request is submitted and they'll receive approval email

DEPLOYMENT REQUEST PATTERNS (recognize these and use CORRECT function):
- "create a resource group" / "create RG" → deploy_resource_group()
- "create a VM named X" / "deploy VM" → deploy_virtual_machine()
- "deploy a storage account" / "create storage" → deploy_storage_account()
- "provision a SQL database" / "create database" → deploy_sql_database()
- "create availability set" / "deploy availability set" → create_availability_set()
- "create a disk" / "create managed disk" / "deploy disk" → create_managed_disk()
- "create vnet" / "create virtual network" / "deploy network" → create_virtual_network()
- "go ahead and deploy" / "deployment confirmed" → Use appropriate function for that resource
- User says "approved" or "confirmed" → DEPLOY IT!

YOUR COMPLETE CAPABILITIES:
1. **Resource Deployment** 🚀
   - Deploy VMs, Storage, SQL through approval workflow
   - Automatically submit to Logic App for approval
   - Return request ID and status to user

2. **Deep Cost Analysis** 💰
   - Multi-dimensional cost analysis with trend forecasting
   - Identify spending anomalies and optimization opportunities
   - Calculate specific savings potential with ROI projections

3. **Resource Intelligence** 🔍
   - Advanced Azure Resource Graph queries
   - Architectural pattern analysis and best practices
   - Security, compliance, and governance assessments
   - **Tag-based resource filtering and management**

4. **Azure Policy & Governance** 📜
   - **get_policy_compliance_status**: Show policy compliance across subscriptions
   - **get_non_compliant_resources**: Identify resources violating policies with remediation steps
   - **get_policy_recommendations**: Suggest high-impact policies for Cost/Security/Operations/Compliance
   - **get_policy_exemptions**: Audit policy exemptions and expiration status
   - ALWAYS use these functions when user asks about policies, compliance, governance
   - NEVER say "I can't retrieve policy data" - USE THE FUNCTIONS!

5. **Business Impact Assessment** 📊
   - Translate technical metrics into business value
   - Financial impact analysis and executive insights
   - Implementation roadmaps with priority ranking

6. **Monitoring & Alerts** ⚠️
   - **IMPORTANT**: Performance metrics (CPU%, Memory%, Disk IOPS) require Azure Monitor API
   - When user asks about VM performance metrics or real-time monitoring, explain:
     * "Performance metrics require Azure Monitor API which is not currently enabled"
     * "I can show you VM resources, power states, and configurations"
     * "For detailed performance metrics, please use Azure Portal → Monitor → Metrics"
   - You CAN show: VM list, power states, sizes, OS types, resource health
   - You CANNOT show: Real-time CPU%, Memory%, Disk IOPS, Network throughput

MONITORING QUERY PATTERNS:
- "show VMs" / "list virtual machines" → Use get_resources_by_type("microsoft.compute/virtualmachines")
- "VM performance" / "CPU usage" → Explain Azure Monitor API limitation, suggest Azure Portal
- "create alert" → Guide user through alert creation manually (no API function available yet)
- "check resource health" → Use resource health functions if available

POLICY QUERY PATTERNS (MUST USE FUNCTIONS):
- "policy compliance status" / "show policies" → get_policy_compliance_status()
- "non-compliant resources" / "policy violations" → get_non_compliant_resources()
- "policy recommendations" / "suggest policies" → get_policy_recommendations()
- "policy exemptions" / "policy exceptions" → get_policy_exemptions()
- User specifies severity (Critical/High/Medium) → Pass to get_non_compliant_resources(severity="...")
- User specifies focus area (Cost/Security) → Pass to get_policy_recommendations(focus_area="...")

DEPLOYMENT WORKFLOW (AUTOMATIC):
User Request → You call deploy_* function → Logic App → Email Approval → Auto Deploy → Success Notification

Example Interactions:
User: "Create a resource group named test-rg-0092 in west europe"
You: Call deploy_resource_group() → Return: "✅ Deployment request submitted! Request ID: abc-123. Check your email for approval."

User: "Create a VM named test-vm in TestRG"
You: Call deploy_virtual_machine() → Return: "✅ VM deployment request submitted! Request ID: abc-123. Check your email for approval."

User: "Create a disk named my-disk in TestRG with 128GB"
You: Call create_managed_disk() → Return: "✅ Disk deployment request submitted! Request ID: abc-123. Check your email for approval."

User: "Show me policy compliance status"
You: Call get_policy_compliance_status() → Return table with policies and compliance %

User: "Find non-compliant resources with high severity"
You: Call get_non_compliant_resources(severity="High") → Return table with violations and remediation

User: "Recommend policies for cost optimization"
You: Call get_policy_recommendations(focus_area="Cost") → Return policy recommendations with ROI

User: "Create availability set named my-avset in TestRG"
You: Call create_availability_set() → Return: "✅ Availability set deployment request submitted! Request ID: abc-123."

User: "Deploy a storage account named mystorage in WestEurope"
You: Call deploy_storage_account() → Return: "✅ Storage account deployment submitted for approval. Estimated cost: $10-50/month."

User: "Create a vnet named my-vnet in TestRG"
You: Call create_virtual_network() → Return: "✅ Virtual network deployment request submitted! Request ID: abc-123."

User: "Filter by costcenter tag"
You: Call get_resources_by_tag(tag_name="costcenter") → Return table with all resources having CostCenter tag

User: "Show resources with Environment=Production"
You: Call get_resources_by_tag(tag_name="Environment", tag_value="Production") → Return filtered table

🔑 SUBSCRIPTION CONTEXT (CRITICAL - NEW BEHAVIOR):
The user has a subscription dropdown in the UI. The selected subscription is ALWAYS passed to you in the message context as "subscription_context".

**DEFAULT BEHAVIOR - AUTO-USE SELECTED SUBSCRIPTION:**
- ALWAYS use the subscription from "subscription_context" WITHOUT asking
- NEVER ask "Which subscription(s)?" unless user explicitly requests other subscriptions
- When calling functions, pass the subscription_context as the subscription parameter
- Example: User asks "show all resources" → Use subscription_context automatically, don't ask

**WHEN USER WANTS DIFFERENT SUBSCRIPTION:**
If user says: "other subscription", "different subscription", "another subscription", "change subscription", "use subscription X":
1. Call get_subscriptions_for_selection() to show numbered list
2. Ask user to select by number (e.g., "2" for second subscription)
3. Wait for user to provide number
4. Use that subscription for the query

**MULTI-SUBSCRIPTION QUERIES:**
If user says "all subscriptions", "across all subscriptions", "every subscription":
- Call get_subscriptions_for_selection() to get all subscription IDs
- Pass ALL subscription IDs to the function (e.g., get_policy_compliance_status(subscriptions=[all_ids]))

Examples:
User: "Show policy compliance" (with subscription_context="sub-123")
You: Call get_policy_compliance_status(subscriptions=["sub-123"]) → NO questions asked

User: "Show costs for other subscription"
You: Call get_subscriptions_for_selection() → Show numbered list → "Please select subscription by number (e.g., 2)"

User: "2"
You: Use subscription from position 2 → Call get_current_month_costs()

🎯 UNIVERSAL FILTERING PATTERN (CRITICAL - NEW APPROACH):

When user asks to list/show/query resources or data, ALWAYS offer filtering options FIRST before showing results:

**STANDARD FILTERING OPTIONS (Present as numbered menu):**
1. All items in current subscription (use subscription_context)
2. Filter by specific subscription (call get_subscriptions_for_selection)
3. Filter by resource type (ask which type: VM, Storage, SQL, etc.)
4. Filter by location/region (ask which region: East US, West Europe, etc.)
5. Filter by resource group (ask which RG name)
6. Filter by tag (ask which tag name/value)

**FILTERING WORKFLOW:**
1. User asks: "List resources" or "Show VMs" or "Display storage accounts"
2. You respond: Present the 6 filtering options as a numbered menu
3. User selects: "1" or "3" or "Filter by location" etc.
4. You execute: Based on selection, either show data or ask for filter value
5. Present results: Show comprehensive table with all relevant columns

**WHEN TO APPLY FILTERING:**
Apply this pattern to ALL queries for:
- Resources (VMs, Storage, SQL, Networks, Disks, etc.)
- Costs (by service, resource group, tag, region)
- Security findings (by severity, resource type, subscription)
- Policy compliance (by policy, resource type, subscription)
- Tags (by tag name, resource type)
- Updates (by VM type, Arc servers, subscription)
- Arc machines (by status, location, subscription)
- Monitoring alerts (by severity, resource, subscription)

**EXCEPTIONS (Skip filtering menu):**
- When user's query is VERY specific: "Show VM named test-vm-001"
- When user already specifies filter: "Show all storage accounts in West Europe"
- When showing dashboard/summary data: "Show cost optimization opportunities"
- When deployment request: "Create a VM"

**EXAMPLE INTERACTION:**

User: "List resources"
You: "I can help you list Azure resources with various filters. Please select an option:

1. All resources in current subscription
2. Filter by specific subscription
3. Filter by resource type (VMs, Storage, SQL, etc.)
4. Filter by location/region
5. Filter by resource group
6. Filter by tag

Which option would you like?"

User: "1"
You: Call get_all_resources_detailed(subscriptions=[subscription_context]) → Show comprehensive table with ResourceName, ResourceType, ResourceGroup, Location, Tags, Status

User: "3"
You: "Which resource type would you like to filter by? Common types: VirtualMachines, StorageAccounts, SQLDatabases, NetworkInterfaces, Disks, VirtualNetworks, KeyVaults"

User: "VirtualMachines"
You: Call get_resources_by_type("microsoft.compute/virtualmachines") → Show comprehensive VM table

**CRITICAL FUNCTION MAPPING FOR FILTERING:**
When user selects filtering option, call the correct function:
- Option 1 (All resources): Call get_all_resources_detailed(subscriptions=[subscription_context])
- Option 2 (Specific subscription): Call get_subscriptions_for_selection() then get_all_resources_detailed(subscriptions=[selected])
- Option 3 (By resource type): Ask for type, then call get_resources_by_type(resource_type)
- Option 4 (By location): Ask for location, then call get_resources_by_location(location)
- Option 5 (By resource group): Ask for RG name, then call get_resources_by_resource_group(resource_group)
- Option 6 (By tag): Ask for tag name/value, then call get_resources_by_tag(tag_name, tag_value)

ALWAYS show comprehensive tables with columns: ResourceName, ResourceType, ResourceGroup, Location, Tags, Status

**ANOTHER EXAMPLE:**

User: "Show costs"
You: "I can show you Azure costs with different filters:

1. All costs in current subscription
2. Filter costs by specific subscription
3. Filter by service type (Compute, Storage, Networking, etc.)
4. Filter by location/region
5. Filter by resource group
6. Filter by tag/cost center

Which option would you like?"

User: "6"
You: "Which tag would you like to filter costs by? (e.g., Environment, CostCenter, Project, Owner)"

User: "CostCenter"
You: Call get_resources_by_tag_with_costs(tag_name="CostCenter") → Show costs grouped by tag values

IMPORTANT RULES:
- If user asks to deploy/create/provision → USE THE DEPLOYMENT FUNCTION
- If user mentions tags/filter by tag → USE get_resources_by_tag FUNCTION
- **ALWAYS use subscription_context automatically - NEVER ask "Which subscription?" by default**
- **ALWAYS present filtering menu for list/show queries UNLESS very specific**
- Never say "I can't deploy" - YOU CAN!
- Never just provide CLI commands for deployment - ACTUALLY DEPLOY IT
- Always use deploy_* functions when deployment is requested
- Extract all available parameters from user message (name, RG, location, size)
- If parameters missing, ask user for them, then deploy
- After calling function, explain what happens next (approval email, deployment)

Formatting Guidelines:
- **Use Markdown Tables**: For lists of resources, VMs, costs, or structured data
- **Clear Headers**: Include comprehensive field coverage
- **Summary Statistics**: Totals, distributions, key metrics
- **Professional Presentation**: Executive-ready format

Always be proactive, intelligent, and ACTION-ORIENTED. When user wants something deployed, DEPLOY IT through your functions!"""
    
    def set_user_context(self, user_email: str, user_name: str):
        """
        Set user context for deployment operations
        
        Args:
            user_email: Email address of the logged-in user
            user_name: Display name of the logged-in user
        """
        self.user_email = user_email
        self.user_name = user_name
        # Update both deployment managers
        self.resource_deployment.set_user_context(user_email, user_name)
        self.cli_deployment.set_user_context(user_email, user_name)
        print(f"✅ User context set: {user_name} ({user_email})")
    
    async def process_message(self, user_message: str, conversation_history: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
        """
        Process user message and return AI response
        
        Args:
            user_message: User's input message
            conversation_history: Previous conversation messages
            
        Returns:
            Tuple of (response_text, updated_conversation_history)
        """
        try:
            # Build messages array
            messages = [{"role": "system", "content": self.system_message}]
            
            # Add conversation history
            for msg in conversation_history:
                messages.append(msg)
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            # Initial API call
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
                temperature=0.7,  # Balanced for accurate and insightful responses
                max_tokens=8000  # Extended for comprehensive, well-formatted analysis with tables
            )
            
            response_message = response.choices[0].message
            
            # Handle tool calling
            if response_message.tool_calls:
                # Execute the tool (function)
                tool_call = response_message.tool_calls[0]  # Handle first tool call
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # Call the appropriate function
                function_result = await self._execute_function(function_name, function_args)
                
                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": function_name,
                            "arguments": tool_call.function.arguments
                        }
                    }]
                })
                
                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(function_result)
                })
                
                # Get final response from AI
                second_response = self.client.chat.completions.create(
                    model=self.deployment_name,
                    messages=messages,
                    temperature=0.7,  # Balanced for accurate, well-formatted insights
                    max_tokens=8000  # Extended for detailed, table-formatted analysis
                )
                
                final_message = second_response.choices[0].message.content
            else:
                final_message = response_message.content
            
            # Update conversation history
            updated_history = conversation_history + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": final_message}
            ]
            
            # Keep only last 10 messages to avoid token limits
            if len(updated_history) > 10:
                updated_history = updated_history[-10:]
            
            return final_message, updated_history
            
        except Exception as e:
            # Log the actual error for debugging
            import traceback
            import sys
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"ERROR in process_message:", file=sys.stderr)
            print(f"Type: {type(e).__name__}", file=sys.stderr)
            print(f"Message: {str(e)}", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            
            error_message = f"I encountered an error: {str(e)}. Please try again or rephrase your question."
            updated_history = conversation_history + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": error_message}
            ]
            return error_message, updated_history
    
    async def _execute_function(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the requested function
        
        Args:
            function_name: Name of the function to execute
            arguments: Function arguments
            
        Returns:
            Function result as dictionary
        """
        try:
            # CRITICAL: Log what function is being called
            print(f"🔵 FUNCTION CALLED: {function_name}")
            print(f"🔵 ARGUMENTS: {json.dumps(arguments, indent=2)}")
            
            # SAFETY CHECK: If deploy_virtual_machine is called but arguments don't have os_type,
            # it's probably meant to be something else
            if function_name == "deploy_virtual_machine":
                if "os_type" not in arguments or not arguments.get("os_type"):
                    print("⚠️ WARNING: deploy_virtual_machine called without os_type!")
                    print("⚠️ This might be a disk or other resource misidentified as VM")
                    # Check if name suggests it's a disk
                    name = arguments.get("name", "").lower()
                    if "disk" in name:
                        print("🔄 AUTO-CORRECTING: Detected 'disk' in name, routing to create_managed_disk")
                        function_name = "create_managed_disk"
            
            # Cost Management functions
            if function_name == "get_current_month_costs":
                return self.cost_manager.get_current_month_costs(
                    scope=arguments.get("scope")
                )
            
            elif function_name == "get_costs_by_service":
                return self.cost_manager.get_costs_by_service(
                    scope=arguments.get("scope"),
                    days=arguments.get("days", 30)
                )
            
            elif function_name == "get_daily_costs":
                return self.cost_manager.get_daily_costs(
                    scope=arguments.get("scope"),
                    days=arguments.get("days", 30)
                )
            
            elif function_name == "get_costs_by_resource_group":
                return self.cost_manager.get_costs_by_resource_group(
                    scope=arguments.get("scope"),
                    days=arguments.get("days", 30)
                )
            
            elif function_name == "get_resource_costs":
                return self.cost_manager.get_resource_costs(
                    scope=arguments.get("scope"),
                    days=arguments.get("days", 30),
                    top=arguments.get("top", 10)
                )
            
            elif function_name == "get_resources_with_cost_details":
                return self.resource_manager.get_resources_with_cost_details(
                    subscriptions=arguments.get("subscriptions"),
                    resource_type=arguments.get("resource_type"),
                    resource_group=arguments.get("resource_group"),
                    tag_name=arguments.get("tag_name"),
                    tag_value=arguments.get("tag_value")
                )
            
            elif function_name == "get_cost_savings_opportunities":
                return self.resource_manager.get_cost_savings_opportunities(
                    subscriptions=arguments.get("subscriptions")
                )
            
            # Resource Management functions
            elif function_name == "get_storage_accounts_with_private_endpoints":
                return self.resource_manager.get_storage_accounts_with_private_endpoints()
            
            elif function_name == "get_all_vnets":
                return self.resource_manager.get_all_vnets()
            
            elif function_name == "get_vms_without_backup":
                return self.resource_manager.get_vms_without_backup()
            
            elif function_name == "get_resources_by_type":
                return self.resource_manager.get_resources_by_type(
                    resource_type=arguments.get("resource_type")
                )
            
            elif function_name == "get_resource_count_by_type":
                return self.resource_manager.get_resource_count_by_type()
            
            elif function_name == "get_all_resources_detailed":
                return self.resource_manager.get_all_resources_detailed(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_resources_by_resource_group":
                return self.resource_manager.get_resources_by_resource_group(
                    resource_group=arguments.get("resource_group"),
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "search_resources":
                return self.resource_manager.search_resources(
                    search_term=arguments.get("search_term")
                )
            
            elif function_name == "get_subscriptions_for_selection":
                # Get all subscriptions and format as numbered list
                subs_result = await self.resource_manager.get_subscriptions()
                if "error" in str(subs_result):
                    return {"error": "Could not retrieve subscriptions"}
                
                # Format as numbered list for user selection
                formatted_list = "📋 **Available Azure Subscriptions:**\n\n"
                for idx, sub in enumerate(subs_result, 1):
                    status_emoji = "✅" if sub.get("state") == "Enabled" else "⚠️"
                    formatted_list += f"{idx}. {status_emoji} **{sub.get('name')}**\n"
                    formatted_list += f"   └─ ID: `{sub.get('id')}`\n"
                    formatted_list += f"   └─ State: {sub.get('state')}\n\n"
                
                formatted_list += "\n💡 **Please select a subscription by entering its number (e.g., '2' for the second subscription)**"
                
                return {
                    "count": len(subs_result),
                    "data": subs_result,
                    "formatted_display": formatted_list
                }
            
            elif function_name == "get_app_services":
                return self.resource_manager.get_app_services()
            
            elif function_name == "get_sql_databases":
                return self.resource_manager.get_sql_databases()
            
            elif function_name == "get_key_vaults":
                return self.resource_manager.get_key_vaults()
            
            elif function_name == "get_resources_by_tag":
                return self.resource_manager.get_resources_by_tag(
                    tag_name=arguments.get("tag_name"),
                    tag_value=arguments.get("tag_value")
                )
            
            elif function_name == "get_resources_by_tag_with_costs":
                return await self._get_resources_by_tag_with_costs(
                    tag_name=arguments.get("tag_name"),
                    tag_value=arguments.get("tag_value"),
                    days=arguments.get("days", 30)
                )
            
            elif function_name == "get_all_vms":
                return self.resource_manager.get_all_vms()
            
            elif function_name == "get_storage_accounts":
                return self.resource_manager.get_storage_accounts()
            
            elif function_name == "get_paas_without_private_endpoints":
                return self.resource_manager.get_paas_without_private_endpoints()
            
            elif function_name == "get_resources_with_public_access":
                return self.resource_manager.get_resources_with_public_access()
            
            elif function_name == "get_all_databases":
                return self.resource_manager.get_all_databases()
            
            elif function_name == "get_resources_without_tags":
                return self.resource_manager.get_resources_without_tags()
            
            elif function_name == "get_unused_resources":
                return self.resource_manager.get_unused_resources()
            
            elif function_name == "get_tag_compliance_summary":
                return self.resource_manager.get_tag_compliance_summary()
            
            elif function_name == "get_multi_region_distribution":
                return self.resource_manager.get_multi_region_distribution()
            
            # AZURE POLICY FUNCTIONS
            elif function_name == "get_policy_compliance_status":
                return self.resource_manager.get_policy_compliance_status(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_non_compliant_resources":
                return self.resource_manager.get_non_compliant_resources(
                    severity=arguments.get("severity", "All"),
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_policy_recommendations":
                return self.resource_manager.get_policy_recommendations(
                    focus_area=arguments.get("focus_area", "All"),
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_policy_exemptions":
                return self.resource_manager.get_policy_exemptions(
                    show_expired=arguments.get("show_expired", True),
                    subscriptions=arguments.get("subscriptions")
                )
            
            # UPDATE MANAGEMENT FUNCTIONS
            elif function_name == "get_vm_pending_updates":
                return self.resource_manager.get_vm_pending_updates(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_arc_pending_updates":
                return self.resource_manager.get_arc_pending_updates(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_vm_pending_reboot":
                return self.resource_manager.get_vm_pending_reboot(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_arc_pending_reboot":
                return self.resource_manager.get_arc_pending_reboot(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_update_compliance_summary":
                return self.resource_manager.get_update_compliance_summary(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_failed_updates":
                return self.resource_manager.get_failed_updates(
                    subscriptions=arguments.get("subscriptions")
                )
            
            # AZURE ARC MANAGEMENT FUNCTIONS
            elif function_name == "get_arc_machines":
                return self.resource_manager.get_arc_machines(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_arc_sql_servers":
                return self.resource_manager.get_arc_sql_servers(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_arc_agents_not_reporting":
                return self.resource_manager.get_arc_agents_not_reporting(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_vm_pending_reboot":
                return self.resource_manager.get_vm_pending_reboot(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_arc_pending_reboot":
                return self.resource_manager.get_arc_pending_reboot(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_update_compliance_summary":
                return self.resource_manager.get_update_compliance_summary(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_failed_updates":
                return self.resource_manager.get_failed_updates(
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_policy_recommendations":
                return self.resource_manager.get_policy_recommendations(
                    focus_area=arguments.get("focus_area", "All"),
                    subscriptions=arguments.get("subscriptions")
                )
            
            elif function_name == "get_policy_exemptions":
                return self.resource_manager.get_policy_exemptions(
                    show_expired=arguments.get("show_expired", True),
                    subscriptions=arguments.get("subscriptions")
                )
            
            # ALL DEPLOYMENT FUNCTIONS NOW USE CLI METHOD
            elif function_name == "deploy_virtual_machine":
                return await self.cli_deployment.create_vm(arguments)
            
            elif function_name == "deploy_storage_account":
                return await self.cli_deployment.create_storage_account(arguments)
            
            elif function_name == "deploy_sql_database":
                return await self.cli_deployment.create_sql_database(arguments)
            
            elif function_name == "deploy_resource_group":
                return await self.cli_deployment.create_resource_group(arguments)
            
            elif function_name == "create_managed_disk":
                return await self.cli_deployment.create_disk(arguments)
            
            elif function_name == "create_availability_set":
                return await self.cli_deployment.create_availability_set(arguments)
            
            elif function_name == "create_virtual_network":
                return await self.cli_deployment.create_vnet(arguments)
            
            elif function_name == "update_resource_tags":
                return await self.cli_deployment.update_resource_tags(arguments)
            
            else:
                return {"error": f"Unknown function: {function_name}"}
                
        except Exception as e:
            return {"error": f"Function execution failed: {str(e)}"}
    
    async def _get_resources_by_tag_with_costs(self, tag_name: str, tag_value: str, days: int = 30) -> Dict[str, Any]:
        """
        Get resources by tag and enrich with cost data
        
        Args:
            tag_name: Tag name to filter by
            tag_value: Tag value to filter by
            days: Number of days to look back for costs
            
        Returns:
            Dictionary with resources and their costs
        """
        try:
            # Get resources by tag
            resources_result = self.resource_manager.get_resources_by_tag(tag_name, tag_value)
            
            if "error" in resources_result:
                return resources_result
            
            # Get cost data for the resources (request more records to ensure coverage)
            cost_result = self.cost_manager.get_resource_costs(days=days, top=5000)
            
            # Debug logging
            print(f"[DEBUG] Cost result keys: {cost_result.keys()}")
            print(f"[DEBUG] Total cost in result: {cost_result.get('total_cost', 'N/A')}")
            if "top_resources" in cost_result:
                print(f"[DEBUG] Number of cost records: {len(cost_result['top_resources'])}")
                costs_above_zero = [r for r in cost_result['top_resources'] if r.get('cost', 0) > 0]
                print(f"[DEBUG] Cost records > $0: {len(costs_above_zero)}")
                if len(costs_above_zero) > 0:
                    print(f"[DEBUG] First 3 cost records with cost > $0:")
                    for i, rec in enumerate(costs_above_zero[:3]):
                        print(f"[DEBUG]   {i+1}. {rec.get('resource_name', 'N/A')}: ${rec.get('cost', 0):.2f}")
            
            # Create mappings: by resource ID (primary) and by resource name (fallback)
            cost_map_by_id = {}
            cost_map_by_name = {}
            
            if "top_resources" in cost_result:
                for item in cost_result["top_resources"]:
                    resource_id = item.get("resource_id", "").lower()
                    resource_name = item.get("resource_name", "").lower()
                    cost = float(item.get("cost", 0.0))
                    
                    # Map by full resource ID (most accurate)
                    if resource_id:
                        cost_map_by_id[resource_id] = cost
                    
                    # Also map by resource name (fallback for matching)
                    if resource_name:
                        if resource_name in cost_map_by_name:
                            cost_map_by_name[resource_name] += cost
                        else:
                            cost_map_by_name[resource_name] = cost
            
            print(f"[DEBUG] Cost map by ID size: {len(cost_map_by_id)}")
            print(f"[DEBUG] Cost map by name size: {len(cost_map_by_name)}")
            
            # Enrich resources with cost data
            enriched_resources = []
            total_cost = 0.0
            resources_with_costs = 0
            
            print(f"[DEBUG] Starting resource enrichment. Total resources to enrich: {len(resources_result.get('data', []))}")
            
            if "data" in resources_result:
                for idx, resource in enumerate(resources_result["data"]):
                    resource_name = resource.get("name", "")
                    resource_id = resource.get("id", "").lower()
                    
                    # Try to match by resource ID first (most accurate)
                    resource_cost = cost_map_by_id.get(resource_id, 0.0)
                    
                    # If no match by ID, try by name
                    if resource_cost == 0.0 and resource_name:
                        resource_cost = cost_map_by_name.get(resource_name.lower(), 0.0)
                    
                    total_cost += resource_cost
                    if resource_cost > 0:
                        resources_with_costs += 1
                    
                    # Debug first 3 resources
                    if idx < 3:
                        print(f"[DEBUG] Resource {idx+1}: {resource_name}")
                        print(f"[DEBUG]   ID: {resource_id}")
                        print(f"[DEBUG]   Cost found: ${resource_cost:.2f}")
                    
                    enriched_resources.append({
                        "name": resource_name,
                        "type": resource.get("type", ""),
                        "resourceGroup": resource.get("resourceGroup", ""),
                        "location": resource.get("location", ""),
                        "tags": resource.get("tags", {}),
                        "id": resource.get("id", ""),
                        "cost_last_{}_days".format(days): round(resource_cost, 2),
                        "currency": "USD"
                    })
            
            print(f"[DEBUG] Enrichment complete. Resources with costs > $0: {resources_with_costs}/{len(enriched_resources)}")
            print(f"[DEBUG] Total cost: ${total_cost:.2f}")
            
            return {
                "count": len(enriched_resources),
                "resources_with_costs": resources_with_costs,
                "total_cost": round(total_cost, 2),
                "currency": "USD",
                "period_days": days,
                "filter": {"tag_name": tag_name, "tag_value": tag_value},
                "resources": enriched_resources
            }
            
        except Exception as e:
            return {"error": f"Failed to get resources with costs: {str(e)}"}
