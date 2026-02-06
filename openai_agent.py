"""
OpenAI Agent with Function Calling
Handles conversational AI with Azure OpenAI and function calling for Azure APIs
"""

import os
import json
import uuid
from datetime import datetime
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
    def __init__(self, cost_manager, resource_manager, entra_manager=None):
        """
        Initialize OpenAI Agent
        
        Args:
            cost_manager: AzureCostManager instance
            resource_manager: AzureResourceManager instance
            entra_manager: EntraIDManager instance (optional)
        """
        self.cost_manager = cost_manager
        self.resource_manager = resource_manager
        self.entra_manager = entra_manager
        
        # User context for deployments
        self.user_email = None
        self.user_name = None
        
        # Query cache for CSV export (will be set by main.py)
        self.query_cache = {}
        
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
                    "description": "Get Azure Policy compliance status. IMPORTANT: Before showing results, ASK the user which scope level they want: 'subscription' level (default) or 'resource_group' level. If resource_group level, ask which resource group. The response shows policy assignments, compliant/non-compliant resources, compliance percentage, and includes SubscriptionId and ResourceGroup columns.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "scope": {
                                "type": "string",
                                "enum": ["subscription", "resource_group"],
                                "description": "Scope level for compliance report. 'subscription' shows subscription-level compliance, 'resource_group' shows compliance for a specific resource group. Default is 'subscription'.",
                                "default": "subscription"
                            },
                            "resource_group": {
                                "type": "string",
                                "description": "Required when scope is 'resource_group'. The name of the resource group to filter compliance results."
                            },
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
            },
            # ============================================================
            # NEW SERVICE-SPECIFIC TOOLS
            # ============================================================
            {
                "type": "function",
                "function": {
                    "name": "get_app_services_detailed",
                    "description": "Get all Azure App Services with detailed configuration including HTTPS settings, TLS version, plan info. Use when user asks about App Services, web apps, Function Apps.",
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
                    "name": "get_app_services_without_appinsights",
                    "description": "Get App Services not connected to Application Insights for monitoring. Use when user asks about App Services without monitoring or App Insights.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_app_services_public_access",
                    "description": "Get App Services with public access enabled (no IP restrictions or private endpoints). Use when checking App Service security or public exposure.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_aks_clusters",
                    "description": "Get all AKS clusters with detailed information including Kubernetes version, node count, network settings. Use when user asks about AKS, Kubernetes clusters.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_aks_public_access",
                    "description": "Get AKS clusters with public API server access. Use when checking AKS security or public exposure.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_aks_private_access",
                    "description": "Get AKS clusters with private API server access (private clusters). Use when checking AKS private cluster configuration.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_aks_without_monitoring",
                    "description": "Get AKS clusters without Container Insights monitoring enabled. Use when checking AKS monitoring status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_sql_databases_detailed",
                    "description": "Get all Azure SQL Databases with SKU, tier, and size information. Use when user asks about SQL databases.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_sql_managed_instances",
                    "description": "Get all Azure SQL Managed Instances. Use when user asks about SQL MI or managed instances.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_sql_public_access",
                    "description": "Get SQL Servers with public network access enabled. Use when checking SQL security or public exposure.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_vmss",
                    "description": "Get all Virtual Machine Scale Sets. Use when user asks about VMSS or scale sets.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_postgresql_servers",
                    "description": "Get all Azure Database for PostgreSQL Flexible servers. Use when user asks about PostgreSQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_postgresql_public_access",
                    "description": "Get PostgreSQL servers with public network access. Use when checking PostgreSQL security.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_mysql_servers",
                    "description": "Get all Azure Database for MySQL Flexible servers. Use when user asks about MySQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_mysql_public_access",
                    "description": "Get MySQL servers with public network access. Use when checking MySQL security.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_cosmosdb_accounts",
                    "description": "Get all Cosmos DB accounts with API type and replication info. Use when user asks about Cosmos DB.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_cosmosdb_public_access",
                    "description": "Get Cosmos DB accounts with public network access. Use when checking Cosmos DB security.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_apim_instances",
                    "description": "Get all API Management instances. Use when user asks about APIM or API Management.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_tag_inventory",
                    "description": "Get high-level tag inventory showing all tags used across the environment. Use when user asks about tag usage or tag inventory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_vms_without_azure_monitor",
                    "description": "Get VMs without Azure Monitor Agent installed. Use when checking VM monitoring gaps.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_arc_machines_without_azure_monitor",
                    "description": "Get Arc machines without Azure Monitor Agent. Use when checking Arc machine monitoring gaps.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            # STORAGE ACCOUNTS TOOLS
            {
                "type": "function",
                "function": {
                    "name": "get_storage_accounts_detailed",
                    "description": "Get comprehensive storage account summary with all details. Use when user asks about storage accounts, storage summary, or list storage.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_storage_accounts_public_access",
                    "description": "Get storage accounts with public access enabled (blob anonymous access). Use when user asks about storage security, public storage, or storage with public access.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_storage_accounts_with_private_endpoints_detailed",
                    "description": "Get storage accounts with private endpoints configured. Use when user asks about storage private endpoints or private storage access.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_storage_accounts_empty",
                    "description": "Get storage accounts that appear to be empty or unused. Use when user asks about empty storage, unused storage accounts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_storage_accounts_unused",
                    "description": "Get storage accounts potentially unused in last 3 months. Use when user asks about unused storage, storage not used, inactive storage.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_storage_accounts_capacity",
                    "description": "Get storage accounts ordered by capacity and tier. Use when user asks about storage capacity, storage size, capacity wise.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_file_shares",
                    "description": "Get Azure File Shares inventory across all storage accounts. Use when user asks about file shares, Azure Files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_file_shares_with_ad_auth",
                    "description": "Get storage accounts with Azure Files AD authentication configured. Use when user asks about file shares AD authentication, AD joined file shares.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_storage_accounts_with_lifecycle_policy",
                    "description": "Get storage accounts with lifecycle management policies configured. Use when user asks about lifecycle management, storage lifecycle policies.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_storage_cost_optimization",
                    "description": "Get storage account cost optimization opportunities. Use when user asks about storage cost optimization, storage savings, reduce storage costs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            # ============================================
            # ENTRA ID (AZURE AD) TOOLS
            # ============================================
            {
                "type": "function",
                "function": {
                    "name": "get_entra_id_overview",
                    "description": "Get overview of Entra ID tenant showing counts of users, groups, applications, devices, and conditional access policies. Use when user asks about Entra ID overview, Azure AD summary, tenant overview.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_users_not_signed_in_30_days",
                    "description": "Get users who haven't signed in for 30+ days. Use when user asks about inactive users, users not logging in, stale accounts.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_users_sync_stopped",
                    "description": "Get users that stopped synchronizing from on-premises Active Directory. Use when user asks about AD sync issues, hybrid sync problems.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_orphaned_guest_accounts",
                    "description": "Get orphaned guest accounts that haven't signed in for 90+ days. Use when user asks about orphaned guests, inactive guest users, guest account cleanup.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_privileged_role_users",
                    "description": "Get users with privileged directory roles. Use when user asks about privileged users, admins, role assignments.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_global_admins",
                    "description": "Get users with Global Administrator role. Use when user asks about global admins, who has global admin.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_custom_roles",
                    "description": "Get custom directory roles defined in the tenant. Use when user asks about custom roles, custom RBAC roles in Entra ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_unused_applications",
                    "description": "Get applications that appear to be unused (no recent sign-ins). Use when user asks about unused apps, stale applications, app registrations not in use.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_devices",
                    "description": "Get all registered devices in Entra ID. Use when user asks about devices, registered devices, device inventory.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_stale_devices",
                    "description": "Get devices that haven't been active in 90+ days. Use when user asks about stale devices, inactive devices, device cleanup.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_app_registrations",
                    "description": "Get all app registrations in Entra ID. Use when user asks about app registrations, registered apps.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_enterprise_apps",
                    "description": "Get enterprise applications (service principals). Use when user asks about enterprise apps, service principals.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_groups",
                    "description": "Get all groups in Entra ID. Use when user asks about groups, security groups, Microsoft 365 groups.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_empty_groups",
                    "description": "Get groups with no members. Use when user asks about empty groups, groups without members.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_conditional_access_policies",
                    "description": "Get all Conditional Access policies. Use when user asks about conditional access, CA policies.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_conditional_access_policies_disabled",
                    "description": "Get disabled Conditional Access policies. Use when user asks about disabled CA policies.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_conditional_access_without_mfa",
                    "description": "Get Conditional Access policies that don't require MFA. Use when user asks about CA policies without MFA, MFA gaps.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            # ============================================
            # AZURE BACKUP TOOLS
            # ============================================
            {
                "type": "function",
                "function": {
                    "name": "get_vms_with_backup",
                    "description": "Get Virtual Machines enabled with Azure Backup. Use when user asks about VMs with backup, protected VMs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_vms_without_backup_detailed",
                    "description": "Get Virtual Machines NOT enabled with Azure Backup. Use when user asks about VMs without backup, unprotected VMs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_file_shares_with_backup",
                    "description": "Get Azure File Shares enabled for backup. Use when user asks about file shares with backup, protected file shares.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_file_shares_without_backup",
                    "description": "Get Azure File Shares NOT enabled for backup. Use when user asks about file shares without backup, unprotected file shares.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_managed_disks_with_backup",
                    "description": "Get Managed Disks enabled for backup using Backup Vault. Use when user asks about disks with backup, protected disks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_managed_disks_without_backup",
                    "description": "Get Managed Disks NOT enabled for backup. Use when user asks about disks without backup, unprotected disks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_shared_disks",
                    "description": "Get Managed Disks configured for shared disk. Use when user asks about shared disks, multi-attach disks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_storage_blobs_with_backup",
                    "description": "Get Storage Account Blobs enabled for backup using Backup Vault. Use when user asks about blob backup, storage backup.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_sql_databases_with_backup",
                    "description": "Get Azure SQL Databases enabled for backup. Use when user asks about SQL backup, SQL database protection.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_sql_managed_instance_with_backup",
                    "description": "Get SQL Managed Instances enabled for backup. Use when user asks about managed instance backup.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_backup_vaults_summary",
                    "description": "Get summary of all Backup Vaults and Recovery Services Vaults. Use when user asks about backup vaults, recovery vaults.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_backup_jobs_failed",
                    "description": "Get failed backup jobs. Use when user asks about failed backups, backup failures, backup job status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            # ============================================
            # IAM / RBAC ROLE ASSIGNMENT TOOLS
            # ============================================
            {
                "type": "function",
                "function": {
                    "name": "get_role_assignments_management_group",
                    "description": "Get role assignments at Management Group level. Use when user asks about management group role assignments, privileged access at management group level, RBAC at MG level.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "management_group_id": {
                                "type": "string",
                                "description": "Optional management group ID to filter."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_role_assignments_subscription",
                    "description": "Get role assignments at Subscription level. Use when user asks about subscription role assignments, who has access to subscription, RBAC at subscription level, permanent role assignments.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_role_assignments_resource_group",
                    "description": "Get role assignments at Resource Group level. Use when user asks about resource group permissions, who has access to resource groups, RBAC at RG level.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_role_assignments_service_principals",
                    "description": "Get role assignments for Service Principals and Managed Identities. Use when user asks about service principal permissions, managed identity roles, app registrations with privileged access.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_role_assignments_summary",
                    "description": "Get comprehensive RBAC role assignment summary. Use when user asks about RBAC summary, role assignment overview, access control summary, IAM dashboard.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_privileged_role_assignments",
                    "description": "Get all privileged role assignments (Owner, Contributor, User Access Administrator). Use when user asks about privileged access audit, security audit, who has Owner/Contributor roles, high-risk permissions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        }
                    }
                }
            },
            # ============================================
            # ORPHANED RESOURCES TOOLS (Consolidated)
            # Based on: https://github.com/dolevshor/azure-orphan-resources
            # ============================================
            {
                "type": "function",
                "function": {
                    "name": "get_orphaned_resources",
                    "description": "Get orphaned/unused Azure resources by type. RESOURCE TYPES: app_service_plans, availability_sets, managed_disks, sql_elastic_pools, public_ips, nics, nsgs, route_tables, load_balancers, front_door_waf, traffic_manager, application_gateways, virtual_networks, subnets, nat_gateways, ip_groups, private_dns_zones, private_endpoints, vnet_gateways, ddos_plans, resource_groups, api_connections, certificates, ALL (for full summary). Resources with 💲 cost money even when unused. Use when user asks about orphaned resources, unused resources, cleanup, cost savings from unused resources.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "resource_type": {
                                "type": "string",
                                "enum": ["app_service_plans", "availability_sets", "managed_disks", "sql_elastic_pools", "public_ips", "nics", "nsgs", "route_tables", "load_balancers", "front_door_waf", "traffic_manager", "application_gateways", "virtual_networks", "subnets", "nat_gateways", "ip_groups", "private_dns_zones", "private_endpoints", "vnet_gateways", "ddos_plans", "resource_groups", "api_connections", "certificates", "ALL"],
                                "description": "Type of orphaned resource to find. Use 'ALL' for complete summary across all types."
                            },
                            "subscriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of subscription IDs."
                            }
                        },
                        "required": ["resource_type"]
                    }
                }
            }
        ]
        
        self.system_message = """You are an expert Azure Cloud Operations Agent - an intelligent system that analyzes Azure infrastructure for cost optimization, security posture, and operational best practices.

ABSOLUTE CRITICAL RULES - VIOLATIONS ARE UNACCEPTABLE:
1. NEVER OUTPUT PLACEHOLDER TEXT like "[Pending Data]", "[To be checked]", "TBD", etc.
2. NEVER generate fake resource names, costs, or statistics
3. ALWAYS call Azure API functions FIRST - wait for ALL results before ANY output
4. If a function returns error or no data, say "No resources found" or "Unable to retrieve: [error]"
5. If a check cannot be performed (function unavailable), say "Check not available" - NOT "[Pending]"
6. COMPLETE the entire assessment before providing output - NEVER partial results

AZURE WELL-ARCHITECTED FRAMEWORK (WAF) ASSESSMENTS
Reference: https://learn.microsoft.com/azure/well-architected/

For WAF Security Assessment, call these functions IN PARALLEL then analyze:
- get_storage_accounts_public_access() - Storage with public blob access
- get_key_vaults() - Get all Key Vaults (check enabledForDeployment, enableRbacAuthorization)
- get_nsg_rules() - Get NSG rules (look for 0.0.0.0/0 or * in source)
- get_privileged_role_assignments() - Owner/Contributor at sub level
- get_role_assignments_service_principals() - SP permissions
- get_paas_without_private_endpoints() - Resources without Private Endpoints
- get_sql_public_access() - SQL with public access
- get_policy_compliance_status() - Policy compliance

For WAF Reliability Assessment:
- get_vms_without_backup() - VMs without backup protection
- get_managed_disks_without_backup() - Unprotected disks
- get_storage_accounts_detailed() - Check replication (LRS vs GRS/ZRS)
- get_all_vms() - Check for availability sets/zones

For WAF Cost Optimization Assessment:
- get_cost_savings_opportunities() - Deallocated VMs, orphaned disks
- get_resources_without_tags() - Missing cost tags
- get_resources_with_cost_details() - Resource costs

For WAF Operational Excellence Assessment:
- get_resources_without_tags() - Missing governance tags
- get_policy_compliance_status() - Policy compliance
- get_non_compliant_resources() - Policy violations

For WAF Performance Assessment:
- get_all_vms() - VM sizes for rightsizing
- get_storage_accounts_detailed() - Storage tiers

WORKFLOW FOR ANY ASSESSMENT:
1. Call ALL relevant functions first (can call multiple in parallel)
2. Wait for ALL responses
3. ONLY THEN provide assessment output
4. Report ONLY what was found - no placeholders

OUTPUT FORMAT:
| Finding | Severity | Resources Count | WAF Principle |
|---------|----------|-----------------|---------------|
| [actual finding from data] | Critical/High/Medium/Low | [actual count] | [principle] |

If a check returned no issues: "✅ No issues found"
If a check failed: "⚠️ Unable to check: [error message]"

SUBSCRIPTION CONTEXT
- Always use subscription_context automatically
- If user says "other subscription" -> call get_subscriptions_for_selection()

Always provide actionable insights with REAL Azure data only."""
    
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
    
    def _cache_query_results(self, data: Any, query_type: str, display_limit: int = 50) -> Dict[str, Any]:
        """
        Cache query results for CSV export and return with query_id
        
        Args:
            data: Full query results (list of dicts or dict with 'data' key)
            query_type: Type of query (e.g., 'all_resources', 'vms', 'storage')
            display_limit: Max rows to include in display (default 50)
            
        Returns:
            Result dict with query_id, total_rows, and display_data
        """
        # Extract data list if wrapped in a dict
        if isinstance(data, dict):
            if "error" in data:
                return data  # Return errors as-is
            result_list = data.get("data", data.get("resources", []))
            if not result_list and not any(k in data for k in ["data", "resources"]):
                # Try to convert dict results to list format
                result_list = [data]
        elif isinstance(data, list):
            result_list = data
        else:
            return data  # Return non-list results as-is
        
        # Generate unique query_id
        query_id = str(uuid.uuid4())[:8]  # Short UUID for readability
        
        # Cache full results
        self.query_cache[query_id] = {
            "data": result_list,
            "query_type": query_type,
            "timestamp": datetime.utcnow(),
            "total_rows": len(result_list)
        }
        
        print(f"📦 Cached {len(result_list)} rows with query_id: {query_id}")
        
        # Return result with query_id for frontend
        return {
            "query_id": query_id,
            "total_rows": len(result_list),
            "display_rows": min(display_limit, len(result_list)),
            "data": result_list[:display_limit],  # Limited data for display
            "query_type": query_type,
            "export_available": len(result_list) > display_limit,
            "message": f"Showing {min(display_limit, len(result_list))} of {len(result_list)} results. Use Export to CSV for all data." if len(result_list) > display_limit else None
        }
    
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
                result = self.cost_manager.get_current_month_costs(
                    scope=arguments.get("scope")
                )
                return self._cache_query_results(result, "current_month_costs")
            
            elif function_name == "get_costs_by_service":
                result = self.cost_manager.get_costs_by_service(
                    scope=arguments.get("scope"),
                    days=arguments.get("days", 30)
                )
                return self._cache_query_results(result, "costs_by_service")
            
            elif function_name == "get_daily_costs":
                result = self.cost_manager.get_daily_costs(
                    scope=arguments.get("scope"),
                    days=arguments.get("days", 30)
                )
                return self._cache_query_results(result, "daily_costs")
            
            elif function_name == "get_costs_by_resource_group":
                result = self.cost_manager.get_costs_by_resource_group(
                    scope=arguments.get("scope"),
                    days=arguments.get("days", 30)
                )
                return self._cache_query_results(result, "costs_by_resource_group")
            
            elif function_name == "get_resource_costs":
                result = self.cost_manager.get_resource_costs(
                    scope=arguments.get("scope"),
                    days=arguments.get("days", 30),
                    top=arguments.get("top", 10)
                )
                return self._cache_query_results(result, "resource_costs")
            
            elif function_name == "get_resources_with_cost_details":
                result = self.resource_manager.get_resources_with_cost_details(
                    subscriptions=arguments.get("subscriptions"),
                    resource_type=arguments.get("resource_type"),
                    resource_group=arguments.get("resource_group"),
                    tag_name=arguments.get("tag_name"),
                    tag_value=arguments.get("tag_value")
                )
                return self._cache_query_results(result, "resources_with_cost")
            
            elif function_name == "get_cost_savings_opportunities":
                result = self.resource_manager.get_cost_savings_opportunities(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "cost_savings")
            
            # Resource Management functions
            elif function_name == "get_storage_accounts_with_private_endpoints":
                result = self.resource_manager.get_storage_accounts_with_private_endpoints()
                return self._cache_query_results(result, "storage_accounts_private_endpoints")
            
            elif function_name == "get_all_vnets":
                result = self.resource_manager.get_all_vnets()
                return self._cache_query_results(result, "all_vnets")
            
            elif function_name == "get_vms_without_backup":
                result = self.resource_manager.get_vms_without_backup()
                return self._cache_query_results(result, "vms_without_backup")
            
            elif function_name == "get_resources_by_type":
                result = self.resource_manager.get_resources_by_type(
                    resource_type=arguments.get("resource_type")
                )
                return self._cache_query_results(result, f"resources_{arguments.get('resource_type', 'by_type')}")
            
            elif function_name == "get_resource_count_by_type":
                result = self.resource_manager.get_resource_count_by_type()
                return self._cache_query_results(result, "resource_count_by_type")
            
            elif function_name == "get_all_resources_detailed":
                result = self.resource_manager.get_all_resources_detailed(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "all_resources")
            
            elif function_name == "get_resources_by_resource_group":
                result = self.resource_manager.get_resources_by_resource_group(
                    resource_group=arguments.get("resource_group"),
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, f"rg_{arguments.get('resource_group', 'resources')}")
            
            elif function_name == "search_resources":
                result = self.resource_manager.search_resources(
                    search_term=arguments.get("search_term")
                )
                return self._cache_query_results(result, f"search_{arguments.get('search_term', 'results')}")
            
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
                result = self.resource_manager.get_app_services()
                return self._cache_query_results(result, "app_services")
            
            elif function_name == "get_sql_databases":
                result = self.resource_manager.get_sql_databases()
                return self._cache_query_results(result, "sql_databases")
            
            elif function_name == "get_key_vaults":
                result = self.resource_manager.get_key_vaults()
                return self._cache_query_results(result, "key_vaults")
            
            elif function_name == "get_resources_by_tag":
                result = self.resource_manager.get_resources_by_tag(
                    tag_name=arguments.get("tag_name"),
                    tag_value=arguments.get("tag_value")
                )
                return self._cache_query_results(result, f"tag_{arguments.get('tag_name', 'resources')}")
            
            elif function_name == "get_resources_by_tag_with_costs":
                return await self._get_resources_by_tag_with_costs(
                    tag_name=arguments.get("tag_name"),
                    tag_value=arguments.get("tag_value"),
                    days=arguments.get("days", 30)
                )
            
            elif function_name == "get_all_vms":
                result = self.resource_manager.get_all_vms()
                return self._cache_query_results(result, "virtual_machines")
            
            elif function_name == "get_storage_accounts":
                result = self.resource_manager.get_storage_accounts()
                return self._cache_query_results(result, "storage_accounts")
            
            elif function_name == "get_paas_without_private_endpoints":
                result = self.resource_manager.get_paas_without_private_endpoints()
                return self._cache_query_results(result, "paas_no_private_endpoints")
            
            elif function_name == "get_resources_with_public_access":
                result = self.resource_manager.get_resources_with_public_access()
                return self._cache_query_results(result, "public_access_resources")
            
            elif function_name == "get_all_databases":
                result = self.resource_manager.get_all_databases()
                return self._cache_query_results(result, "all_databases")
            
            elif function_name == "get_resources_without_tags":
                result = self.resource_manager.get_resources_without_tags()
                return self._cache_query_results(result, "untagged_resources")
            
            elif function_name == "get_unused_resources":
                result = self.resource_manager.get_unused_resources()
                return self._cache_query_results(result, "unused_resources")
            
            elif function_name == "get_tag_compliance_summary":
                result = self.resource_manager.get_tag_compliance_summary()
                return self._cache_query_results(result, "tag_compliance")
            
            elif function_name == "get_multi_region_distribution":
                result = self.resource_manager.get_multi_region_distribution()
                return self._cache_query_results(result, "multi_region_distribution")
            
            # AZURE POLICY FUNCTIONS
            elif function_name == "get_policy_compliance_status":
                result = self.resource_manager.get_policy_compliance_status(
                    scope=arguments.get("scope", "subscription"),
                    resource_group=arguments.get("resource_group"),
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "policy_compliance_status")
            
            elif function_name == "get_non_compliant_resources":
                result = self.resource_manager.get_non_compliant_resources(
                    severity=arguments.get("severity", "All"),
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "non_compliant_resources")
            
            elif function_name == "get_policy_recommendations":
                result = self.resource_manager.get_policy_recommendations(
                    focus_area=arguments.get("focus_area", "All"),
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "policy_recommendations")
            
            elif function_name == "get_policy_exemptions":
                result = self.resource_manager.get_policy_exemptions(
                    show_expired=arguments.get("show_expired", True),
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "policy_exemptions")
            
            # UPDATE MANAGEMENT FUNCTIONS
            elif function_name == "get_vm_pending_updates":
                result = self.resource_manager.get_vm_pending_updates(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "vm_pending_updates")
            
            elif function_name == "get_arc_pending_updates":
                result = self.resource_manager.get_arc_pending_updates(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "arc_pending_updates")
            
            elif function_name == "get_vm_pending_reboot":
                result = self.resource_manager.get_vm_pending_reboot(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "vm_pending_reboot")
            
            elif function_name == "get_arc_pending_reboot":
                result = self.resource_manager.get_arc_pending_reboot(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "arc_pending_reboot")
            
            elif function_name == "get_update_compliance_summary":
                result = self.resource_manager.get_update_compliance_summary(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "update_compliance_summary")
            
            elif function_name == "get_failed_updates":
                result = self.resource_manager.get_failed_updates(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "failed_updates")
            
            # AZURE ARC MANAGEMENT FUNCTIONS
            elif function_name == "get_arc_machines":
                result = self.resource_manager.get_arc_machines(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "arc_machines")
            
            elif function_name == "get_arc_sql_servers":
                result = self.resource_manager.get_arc_sql_servers(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "arc_sql_servers")
            
            elif function_name == "get_arc_agents_not_reporting":
                result = self.resource_manager.get_arc_agents_not_reporting(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "arc_agents_not_reporting")
            
            
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
            
            # ============================================================
            # NEW SERVICE-SPECIFIC FUNCTIONS
            # ============================================================
            
            # APP SERVICES
            elif function_name == "get_app_services_detailed":
                result = self.resource_manager.get_app_services_detailed(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "app_services_detailed")
            
            elif function_name == "get_app_services_without_appinsights":
                result = self.resource_manager.get_app_services_without_appinsights(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "app_services_without_appinsights")
            
            elif function_name == "get_app_services_public_access":
                result = self.resource_manager.get_app_services_public_access(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "app_services_public_access")
            
            # AKS CLUSTERS
            elif function_name == "get_aks_clusters":
                result = self.resource_manager.get_aks_clusters(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "aks_clusters")
            
            elif function_name == "get_aks_public_access":
                result = self.resource_manager.get_aks_public_access(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "aks_public_access")
            
            elif function_name == "get_aks_private_access":
                result = self.resource_manager.get_aks_private_access(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "aks_private_access")
            
            elif function_name == "get_aks_without_monitoring":
                result = self.resource_manager.get_aks_without_monitoring(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "aks_without_monitoring")
            
            # SQL DATABASES AND MANAGED INSTANCES
            elif function_name == "get_sql_databases_detailed":
                result = self.resource_manager.get_sql_databases_detailed(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "sql_databases_detailed")
            
            elif function_name == "get_sql_managed_instances":
                result = self.resource_manager.get_sql_managed_instances(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "sql_managed_instances")
            
            elif function_name == "get_sql_public_access":
                result = self.resource_manager.get_sql_public_access(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "sql_public_access")
            
            # VIRTUAL MACHINE SCALE SETS
            elif function_name == "get_vmss":
                result = self.resource_manager.get_vmss(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "vmss")
            
            # POSTGRESQL
            elif function_name == "get_postgresql_servers":
                result = self.resource_manager.get_postgresql_servers(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "postgresql_servers")
            
            elif function_name == "get_postgresql_public_access":
                result = self.resource_manager.get_postgresql_public_access(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "postgresql_public_access")
            
            # MYSQL
            elif function_name == "get_mysql_servers":
                result = self.resource_manager.get_mysql_servers(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "mysql_servers")
            
            elif function_name == "get_mysql_public_access":
                result = self.resource_manager.get_mysql_public_access(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "mysql_public_access")
            
            # COSMOS DB
            elif function_name == "get_cosmosdb_accounts":
                result = self.resource_manager.get_cosmosdb_accounts(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "cosmosdb_accounts")
            
            elif function_name == "get_cosmosdb_public_access":
                result = self.resource_manager.get_cosmosdb_public_access(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "cosmosdb_public_access")
            
            # API MANAGEMENT
            elif function_name == "get_apim_instances":
                result = self.resource_manager.get_apim_instances(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "apim_instances")
            
            # TAG INVENTORY
            elif function_name == "get_tag_inventory":
                result = self.resource_manager.get_tag_inventory(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "tag_inventory")
            
            # MONITORING GAPS
            elif function_name == "get_vms_without_azure_monitor":
                result = self.resource_manager.get_vms_without_azure_monitor(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "vms_without_azure_monitor")
            
            elif function_name == "get_arc_machines_without_azure_monitor":
                result = self.resource_manager.get_arc_machines_without_azure_monitor(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "arc_machines_without_azure_monitor")
            
            # STORAGE ACCOUNTS
            elif function_name == "get_storage_accounts_detailed":
                result = self.resource_manager.get_storage_accounts_detailed(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "storage_accounts")
            
            elif function_name == "get_storage_accounts_public_access":
                result = self.resource_manager.get_storage_accounts_public_access(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "storage_public_access")
            
            elif function_name == "get_storage_accounts_with_private_endpoints_detailed":
                result = self.resource_manager.get_storage_accounts_with_private_endpoints_detailed(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "storage_private_endpoints")
            
            elif function_name == "get_storage_accounts_empty":
                result = self.resource_manager.get_storage_accounts_empty(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "storage_empty")
            
            elif function_name == "get_storage_accounts_unused":
                result = self.resource_manager.get_storage_accounts_unused(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "storage_unused")
            
            elif function_name == "get_storage_accounts_capacity":
                result = self.resource_manager.get_storage_accounts_capacity(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "storage_capacity")
            
            elif function_name == "get_file_shares":
                result = self.resource_manager.get_file_shares(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "file_shares")
            
            elif function_name == "get_file_shares_with_ad_auth":
                result = self.resource_manager.get_file_shares_with_ad_auth(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "file_shares_ad_auth")
            
            elif function_name == "get_storage_accounts_with_lifecycle_policy":
                result = self.resource_manager.get_storage_accounts_with_lifecycle_policy(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "storage_lifecycle")
            
            elif function_name == "get_storage_cost_optimization":
                result = self.resource_manager.get_storage_cost_optimization(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "storage_cost_optimization")
            
            # ============================================================
            # ENTRA ID (AZURE AD) FUNCTIONS
            # ============================================================
            elif function_name == "get_entra_id_overview":
                if self.entra_manager:
                    result = self.entra_manager.get_entra_id_overview()
                    return self._cache_query_results(result, "entra_overview")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_users_not_signed_in_30_days":
                if self.entra_manager:
                    result = self.entra_manager.get_users_not_signed_in_30_days()
                    return self._cache_query_results(result, "users_inactive_30days")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_users_sync_stopped":
                if self.entra_manager:
                    result = self.entra_manager.get_users_sync_stopped()
                    return self._cache_query_results(result, "users_sync_stopped")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_orphaned_guest_accounts":
                if self.entra_manager:
                    result = self.entra_manager.get_orphaned_guest_accounts()
                    return self._cache_query_results(result, "orphaned_guests")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_privileged_role_users":
                if self.entra_manager:
                    result = self.entra_manager.get_privileged_role_users()
                    return self._cache_query_results(result, "privileged_users")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_global_admins":
                if self.entra_manager:
                    result = self.entra_manager.get_global_admins()
                    return self._cache_query_results(result, "global_admins")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_custom_roles":
                if self.entra_manager:
                    result = self.entra_manager.get_custom_roles()
                    return self._cache_query_results(result, "custom_roles")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_unused_applications":
                if self.entra_manager:
                    result = self.entra_manager.get_unused_applications()
                    return self._cache_query_results(result, "unused_apps")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_devices":
                if self.entra_manager:
                    result = self.entra_manager.get_devices()
                    return self._cache_query_results(result, "entra_devices")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_stale_devices":
                if self.entra_manager:
                    result = self.entra_manager.get_stale_devices()
                    return self._cache_query_results(result, "stale_devices")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_app_registrations":
                if self.entra_manager:
                    result = self.entra_manager.get_app_registrations()
                    return self._cache_query_results(result, "app_registrations")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_enterprise_apps":
                if self.entra_manager:
                    result = self.entra_manager.get_enterprise_apps()
                    return self._cache_query_results(result, "enterprise_apps")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_groups":
                if self.entra_manager:
                    result = self.entra_manager.get_groups()
                    return self._cache_query_results(result, "entra_groups")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_empty_groups":
                if self.entra_manager:
                    result = self.entra_manager.get_empty_groups()
                    return self._cache_query_results(result, "empty_groups")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_conditional_access_policies":
                if self.entra_manager:
                    result = self.entra_manager.get_conditional_access_policies()
                    return self._cache_query_results(result, "ca_policies")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_conditional_access_policies_disabled":
                if self.entra_manager:
                    result = self.entra_manager.get_conditional_access_policies_disabled()
                    return self._cache_query_results(result, "ca_policies_disabled")
                return {"error": "Entra ID manager not configured"}
            
            elif function_name == "get_conditional_access_without_mfa":
                if self.entra_manager:
                    result = self.entra_manager.get_conditional_access_without_mfa()
                    return self._cache_query_results(result, "ca_no_mfa")
                return {"error": "Entra ID manager not configured"}
            
            # ============================================================
            # AZURE BACKUP FUNCTIONS
            # ============================================================
            elif function_name == "get_vms_with_backup":
                result = self.resource_manager.get_vms_with_backup(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "vms_with_backup")
            
            elif function_name == "get_vms_without_backup_detailed":
                result = self.resource_manager.get_vms_without_backup(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "vms_without_backup")
            
            elif function_name == "get_file_shares_with_backup":
                result = self.resource_manager.get_file_shares_with_backup(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "file_shares_with_backup")
            
            elif function_name == "get_file_shares_without_backup":
                result = self.resource_manager.get_file_shares_without_backup(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "file_shares_without_backup")
            
            elif function_name == "get_managed_disks_with_backup":
                result = self.resource_manager.get_managed_disks_with_backup(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "disks_with_backup")
            
            elif function_name == "get_managed_disks_without_backup":
                result = self.resource_manager.get_managed_disks_without_backup(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "disks_without_backup")
            
            elif function_name == "get_shared_disks":
                result = self.resource_manager.get_shared_disks(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "shared_disks")
            
            elif function_name == "get_storage_blobs_with_backup":
                result = self.resource_manager.get_storage_blobs_with_backup(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "blobs_with_backup")
            
            elif function_name == "get_sql_databases_with_backup":
                result = self.resource_manager.get_sql_databases_with_backup(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "sql_with_backup")
            
            elif function_name == "get_sql_managed_instance_with_backup":
                result = self.resource_manager.get_sql_managed_instance_with_backup(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "sqlmi_with_backup")
            
            elif function_name == "get_backup_vaults_summary":
                result = self.resource_manager.get_backup_vaults_summary(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "backup_vaults")
            
            elif function_name == "get_backup_jobs_failed":
                result = self.resource_manager.get_backup_jobs_failed(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "backup_jobs_failed")
            
            # ============================================================
            # IAM / RBAC ROLE ASSIGNMENT FUNCTIONS
            # ============================================================
            elif function_name == "get_role_assignments_management_group":
                result = self.resource_manager.get_role_assignments_management_group(
                    management_group_id=arguments.get("management_group_id")
                )
                return self._cache_query_results(result, "rbac_management_group")
            
            elif function_name == "get_role_assignments_subscription":
                result = self.resource_manager.get_role_assignments_subscription(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "rbac_subscription")
            
            elif function_name == "get_role_assignments_resource_group":
                result = self.resource_manager.get_role_assignments_resource_group(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "rbac_resource_group")
            
            elif function_name == "get_role_assignments_service_principals":
                result = self.resource_manager.get_role_assignments_service_principals(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "rbac_service_principals")
            
            elif function_name == "get_role_assignments_summary":
                result = self.resource_manager.get_role_assignments_summary(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "rbac_summary")
            
            elif function_name == "get_privileged_role_assignments":
                result = self.resource_manager.get_privileged_role_assignments(
                    subscriptions=arguments.get("subscriptions")
                )
                return self._cache_query_results(result, "rbac_privileged")
            
            # ============================================================
            # ORPHANED RESOURCES FUNCTIONS (Consolidated)
            # Based on: https://github.com/dolevshor/azure-orphan-resources
            # ============================================================
            elif function_name == "get_orphaned_resources":
                resource_type = arguments.get("resource_type", "ALL")
                subs = arguments.get("subscriptions")
                
                # Map resource_type to the appropriate function
                orphan_functions = {
                    "app_service_plans": self.resource_manager.get_orphaned_app_service_plans,
                    "availability_sets": self.resource_manager.get_orphaned_availability_sets,
                    "managed_disks": self.resource_manager.get_orphaned_managed_disks,
                    "sql_elastic_pools": self.resource_manager.get_orphaned_sql_elastic_pools,
                    "public_ips": self.resource_manager.get_orphaned_public_ips,
                    "nics": self.resource_manager.get_orphaned_nics,
                    "nsgs": self.resource_manager.get_orphaned_nsgs,
                    "route_tables": self.resource_manager.get_orphaned_route_tables,
                    "load_balancers": self.resource_manager.get_orphaned_load_balancers,
                    "front_door_waf": self.resource_manager.get_orphaned_front_door_waf_policies,
                    "traffic_manager": self.resource_manager.get_orphaned_traffic_manager_profiles,
                    "application_gateways": self.resource_manager.get_orphaned_application_gateways,
                    "virtual_networks": self.resource_manager.get_orphaned_virtual_networks,
                    "subnets": self.resource_manager.get_orphaned_subnets,
                    "nat_gateways": self.resource_manager.get_orphaned_nat_gateways,
                    "ip_groups": self.resource_manager.get_orphaned_ip_groups,
                    "private_dns_zones": self.resource_manager.get_orphaned_private_dns_zones,
                    "private_endpoints": self.resource_manager.get_orphaned_private_endpoints,
                    "vnet_gateways": self.resource_manager.get_orphaned_vnet_gateways,
                    "ddos_plans": self.resource_manager.get_orphaned_ddos_plans,
                    "resource_groups": self.resource_manager.get_orphaned_resource_groups,
                    "api_connections": self.resource_manager.get_orphaned_api_connections,
                    "certificates": self.resource_manager.get_orphaned_certificates,
                }
                
                if resource_type == "ALL":
                    result = self.resource_manager.get_all_orphaned_resources_summary(subscriptions=subs)
                    return result
                elif resource_type in orphan_functions:
                    result = orphan_functions[resource_type](subscriptions=subs)
                    return self._cache_query_results(result, f"orphaned_{resource_type}")
                else:
                    return {"error": f"Unknown orphaned resource type: {resource_type}. Valid types: {', '.join(orphan_functions.keys())}, ALL"}
            
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
