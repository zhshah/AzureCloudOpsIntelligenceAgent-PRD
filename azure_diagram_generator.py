"""
Azure Architecture Diagram Generator
Generates professional Azure architecture diagrams using the 'diagrams' library.
Inspired by: https://github.com/cmb211087/azure-diagrams-skill
             https://github.com/jonathan-vella/azure-agentic-infraops

Supports:
- Architecture diagrams from natural language descriptions
- Diagrams from live Azure subscription/resource group resources
- Pre-built patterns (hub-spoke, microservices, serverless, etc.)
- High-resolution PNG export for chat display + download
"""

import ast
import base64
import os
import re
import subprocess
import sys
import tempfile
import json
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

ALLOWED_IMPORTS = {
    "diagrams", "diagrams.azure", "diagrams.azure.aimachinelearning",
    "diagrams.azure.analytics", "diagrams.azure.azurestack", "diagrams.azure.blockchain",
    "diagrams.azure.compute", "diagrams.azure.containers", "diagrams.azure.database",
    "diagrams.azure.databases", "diagrams.azure.devops", "diagrams.azure.general",
    "diagrams.azure.identity", "diagrams.azure.integration", "diagrams.azure.intune",
    "diagrams.azure.iot", "diagrams.azure.managementgovernance", "diagrams.azure.migration",
    "diagrams.azure.mixedreality", "diagrams.azure.ml", "diagrams.azure.monitor",
    "diagrams.azure.network", "diagrams.azure.networking", "diagrams.azure.security",
    "diagrams.azure.storage", "diagrams.azure.web",
    "diagrams.onprem", "diagrams.onprem.client", "diagrams.onprem.compute",
    "diagrams.onprem.database", "diagrams.onprem.network",
    "diagrams.generic", "diagrams.generic.blank", "diagrams.generic.compute",
    "diagrams.generic.database", "diagrams.generic.storage",
    "diagrams.programming", "diagrams.programming.flowchart",
    "diagrams.saas", "diagrams.saas.chat", "diagrams.saas.erp", "diagrams.saas.cdn",
    "diagrams.custom",
    "graphviz",
    "datetime", "collections", "pathlib",
}

BLOCKED_BUILTINS = {
    "exec", "eval", "compile", "open", "__import__",
    "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr", "hasattr",
    "breakpoint", "input", "help",
}

BLOCKED_ATTRIBUTES = {
    "__class__", "__bases__", "__subclasses__", "__globals__",
    "__code__", "__builtins__", "__import__", "__loader__",
    "__spec__", "__dict__", "__mro__", "__init_subclass__",
}

BLOCKED_IMPORTS_SET = {
    "os", "sys", "subprocess", "socket", "urllib", "requests",
    "http", "pickle", "shelve", "ctypes", "importlib",
    "shutil", "glob", "fnmatch", "io", "builtins",
    "code", "codeop", "marshal", "types",
}

EXECUTION_TIMEOUT = 60


# ============================================================================
# CODE VALIDATION
# ============================================================================

class CodeValidationError(Exception):
    pass


class CodeValidator(ast.NodeVisitor):
    def __init__(self):
        self.errors = []

    def visit_Import(self, node):
        for alias in node.names:
            if not self._is_allowed_import(alias.name):
                self.errors.append(f"Blocked import: '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module and not self._is_allowed_import(node.module):
            self.errors.append(f"Blocked import: '{node.module}'")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_BUILTINS:
                self.errors.append(f"Blocked builtin: '{node.func.id}()'")
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in BLOCKED_BUILTINS:
                self.errors.append(f"Blocked builtin: '{node.func.attr}()'")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr in BLOCKED_ATTRIBUTES:
            self.errors.append(f"Blocked attribute: '{node.attr}'")
        self.generic_visit(node)

    def _is_allowed_import(self, module_name):
        base = module_name.split('.')[0]
        if base in BLOCKED_IMPORTS_SET:
            return False
        if module_name in ALLOWED_IMPORTS:
            return True
        for allowed in ALLOWED_IMPORTS:
            if module_name.startswith(allowed + "."):
                return True
        return False

    def validate(self, code):
        self.errors = []
        try:
            tree = ast.parse(code)
            self.visit(tree)
        except SyntaxError as e:
            self.errors.append(f"Syntax error: {e}")
        return self.errors


def validate_code(code: str) -> Tuple[bool, List[str]]:
    validator = CodeValidator()
    errors = validator.validate(code)
    return len(errors) == 0, errors


def sanitize_name(name: str) -> str:
    sanitized = re.sub(r'[^a-zA-Z0-9\s\-_.,!?()\'"]', '', name)
    return sanitized[:200]


# ============================================================================
# RESOURCE TYPE TO DIAGRAM NODE MAPPING
# ============================================================================

RESOURCE_TYPE_MAP = {
    # Compute
    "microsoft.compute/virtualmachines": ("diagrams.azure.compute", "VM"),
    "microsoft.compute/virtualmachinescalesets": ("diagrams.azure.compute", "VMSS"),
    "microsoft.compute/disks": ("diagrams.azure.compute", "Disks"),
    "microsoft.compute/snapshots": ("diagrams.azure.compute", "Disks"),
    "microsoft.compute/availabilitysets": ("diagrams.azure.compute", "AvailabilitySets"),
    "microsoft.hybridcompute/machines": ("diagrams.azure.compute", "VM"),
    "microsoft.containerservice/managedclusters": ("diagrams.azure.compute", "AKS"),
    "microsoft.containerregistry/registries": ("diagrams.azure.compute", "ACR"),
    "microsoft.web/sites": ("diagrams.azure.compute", "AppServices"),
    "microsoft.web/serverfarms": ("diagrams.azure.compute", "AppServices"),
    "microsoft.web/staticsites": ("diagrams.azure.web", "StaticApps"),
    "microsoft.app/containerapps": ("diagrams.azure.compute", "ContainerApps"),
    # Database
    "microsoft.sql/servers": ("diagrams.azure.database", "SQL"),
    "microsoft.sql/servers/databases": ("diagrams.azure.database", "SQLDatabases"),
    "microsoft.sql/managedinstances": ("diagrams.azure.database", "SQL"),
    "microsoft.documentdb/databaseaccounts": ("diagrams.azure.database", "CosmosDb"),
    "microsoft.dbforpostgresql/flexibleservers": ("diagrams.azure.database", "DatabaseForPostgresqlServers"),
    "microsoft.dbformysql/flexibleservers": ("diagrams.azure.database", "DatabaseForMysqlServers"),
    "microsoft.cache/redis": ("diagrams.azure.database", "CacheForRedis"),
    # Networking
    "microsoft.network/virtualnetworks": ("diagrams.azure.network", "VirtualNetworks"),
    "microsoft.network/networkinterfaces": ("diagrams.azure.network", "VirtualNetworks"),
    "microsoft.network/privateendpoints": ("diagrams.azure.network", "VirtualNetworks"),
    "microsoft.network/routetables": ("diagrams.azure.network", "RouteTables"),
    "microsoft.network/loadbalancers": ("diagrams.azure.network", "LoadBalancers"),
    "microsoft.network/applicationgateways": ("diagrams.azure.network", "ApplicationGateway"),
    "microsoft.network/azurefirewalls": ("diagrams.azure.network", "Firewall"),
    "microsoft.network/networksecuritygroups": ("diagrams.azure.network", "ApplicationSecurityGroups"),
    "microsoft.network/publicipaddresses": ("diagrams.azure.network", "PublicIpAddresses"),
    "microsoft.network/frontdoors": ("diagrams.azure.network", "FrontDoors"),
    "microsoft.network/expressroutecircuits": ("diagrams.azure.network", "ExpressrouteCircuits"),
    "microsoft.network/virtualnetworkgateways": ("diagrams.azure.network", "VirtualNetworkGateways"),
    "microsoft.network/bastionhosts": ("diagrams.azure.networking", "Bastions"),
    "microsoft.network/natgateways": ("diagrams.azure.networking", "Nat"),
    "microsoft.network/privatednszones": ("diagrams.azure.network", "DNSPrivateZones"),
    "microsoft.network/dnszones": ("diagrams.azure.network", "DNSZones"),
    "microsoft.network/trafficmanagerprofiles": ("diagrams.azure.network", "TrafficManagerProfiles"),
    "microsoft.cdn/profiles": ("diagrams.azure.network", "CDNProfiles"),
    # Storage
    "microsoft.storage/storageaccounts": ("diagrams.azure.storage", "StorageAccounts"),
    "microsoft.datalakestore/accounts": ("diagrams.azure.storage", "DataLakeStorage"),
    "microsoft.netapp/netappaccounts": ("diagrams.azure.storage", "AzureNetappFiles"),
    # Integration
    "microsoft.logic/workflows": ("diagrams.azure.integration", "LogicApps"),
    "microsoft.servicebus/namespaces": ("diagrams.azure.integration", "ServiceBus"),
    "microsoft.eventgrid/topics": ("diagrams.azure.integration", "EventGridTopics"),
    "microsoft.apimanagement/service": ("diagrams.azure.integration", "APIManagement"),
    "microsoft.datafactory/factories": ("diagrams.azure.integration", "DataFactories"),
    "microsoft.relay/namespaces": ("diagrams.azure.integration", "Relays"),
    "microsoft.appconfiguration/configurationstores": ("diagrams.azure.integration", "AppConfiguration"),
    # Security & Identity
    "microsoft.keyvault/vaults": ("diagrams.azure.security", "KeyVaults"),
    "microsoft.operationalinsights/workspaces": ("diagrams.azure.monitor", "LogAnalyticsWorkspaces"),
    # IoT
    "microsoft.devices/iothubs": ("diagrams.azure.iot", "IotHub"),
    # AI/ML
    "microsoft.machinelearningservices/workspaces": ("diagrams.azure.ml", "MachineLearningServiceWorkspaces"),
    "microsoft.cognitiveservices/accounts": ("diagrams.azure.ml", "CognitiveServices"),
    # Analytics
    "microsoft.synapse/workspaces": ("diagrams.azure.analytics", "SynapseAnalytics"),
    "microsoft.databricks/workspaces": ("diagrams.azure.analytics", "Databricks"),
    "microsoft.eventhub/namespaces": ("diagrams.azure.analytics", "EventHubs"),
    "microsoft.streamanalytics/streamingjobs": ("diagrams.azure.analytics", "StreamAnalyticsJobs"),
    # DevOps
    "microsoft.devtestlab/labs": ("diagrams.azure.devops", "DevtestLabs"),
    # Monitor
    "microsoft.insights/components": ("diagrams.azure.monitor", "ApplicationInsights"),
    "microsoft.insights/actiongroups": ("diagrams.azure.monitor", "Monitor"),
    # Recovery
    "microsoft.recoveryservices/vaults": ("diagrams.azure.storage", "StorageAccounts"),
    # Management
    "microsoft.automation/automationaccounts": ("diagrams.azure.managementgovernance", "AutomationAccounts"),
}

# Fallback icon by category
CATEGORY_FALLBACK = {
    "compute": ("diagrams.azure.compute", "VM"),
    "network": ("diagrams.azure.network", "VirtualNetworks"),
    "storage": ("diagrams.azure.storage", "StorageAccounts"),
    "database": ("diagrams.azure.database", "SQL"),
    "web": ("diagrams.azure.web", "AppServices"),
    "security": ("diagrams.azure.security", "KeyVaults"),
    "integration": ("diagrams.azure.integration", "LogicApps"),
    "iot": ("diagrams.azure.iot", "IotHub"),
    "analytics": ("diagrams.azure.analytics", "Databricks"),
    "ml": ("diagrams.azure.ml", "CognitiveServices"),
    "monitor": ("diagrams.azure.monitor", "Monitor"),
    "identity": ("diagrams.azure.identity", "ActiveDirectory"),
    "devops": ("diagrams.azure.devops", "AzureDevops"),
}


# ============================================================================
# COMPREHENSIVE DIAGRAM - RESOURCE CATEGORIZATION & RELATIONSHIPS
# ============================================================================

TYPE_TO_CATEGORY = {
    # Compute
    "microsoft.compute/virtualmachines": "Compute",
    "microsoft.compute/virtualmachinescalesets": "Compute",
    "microsoft.compute/availabilitysets": "Compute",
    "microsoft.compute/disks": "Compute",
    "microsoft.compute/snapshots": "Compute",
    "microsoft.hybridcompute/machines": "Compute",
    "microsoft.hybridcompute/machines/extensions": "Compute",
    "microsoft.web/sites": "Compute",
    "microsoft.web/serverfarms": "Compute",
    "microsoft.web/staticsites": "Compute",
    "microsoft.app/containerapps": "Compute",
    "microsoft.app/managedenvironments": "Compute",
    "microsoft.containerservice/managedclusters": "Compute",
    "microsoft.containerregistry/registries": "Compute",
    # Networking
    "microsoft.network/virtualnetworks": "Networking",
    "microsoft.network/networkinterfaces": "Networking",
    "microsoft.network/networksecuritygroups": "Networking",
    "microsoft.network/publicipaddresses": "Networking",
    "microsoft.network/privateendpoints": "Networking",
    "microsoft.network/loadbalancers": "Networking",
    "microsoft.network/applicationgateways": "Networking",
    "microsoft.network/azurefirewalls": "Networking",
    "microsoft.network/frontdoors": "Networking",
    "microsoft.network/routetables": "Networking",
    "microsoft.network/dnszones": "Networking",
    "microsoft.network/privatednszones": "Networking",
    "microsoft.network/bastionhosts": "Networking",
    "microsoft.network/natgateways": "Networking",
    "microsoft.network/trafficmanagerprofiles": "Networking",
    "microsoft.network/expressroutecircuits": "Networking",
    "microsoft.network/vpngateways": "Networking",
    "microsoft.network/virtualnetworkgateways": "Networking",
    "microsoft.cdn/profiles": "Networking",
    # Data & Storage
    "microsoft.sql/servers": "Data",
    "microsoft.sql/servers/databases": "Data",
    "microsoft.sql/managedinstances": "Data",
    "microsoft.documentdb/databaseaccounts": "Data",
    "microsoft.dbforpostgresql/flexibleservers": "Data",
    "microsoft.dbformysql/flexibleservers": "Data",
    "microsoft.cache/redis": "Data",
    "microsoft.storage/storageaccounts": "Data",
    # Security & Identity
    "microsoft.keyvault/vaults": "Security",
    "microsoft.managedidentity/userassignedidentities": "Security",
    # Monitoring
    "microsoft.insights/components": "Monitoring",
    "microsoft.operationalinsights/workspaces": "Monitoring",
    "microsoft.insights/actiongroups": "Monitoring",
    "microsoft.alertsmanagement/smartdetectoralertrules": "Monitoring",
    # Integration
    "microsoft.apimanagement/service": "Integration",
    "microsoft.logic/workflows": "Integration",
    "microsoft.servicebus/namespaces": "Integration",
    "microsoft.eventgrid/topics": "Integration",
    "microsoft.eventgrid/systemtopics": "Integration",
    "microsoft.eventhub/namespaces": "Integration",
    "microsoft.web/connections": "Integration",
    # AI and Machine Learning
    "microsoft.cognitiveservices/accounts": "AI",
    "microsoft.machinelearningservices/workspaces": "AI",
    # Management
    "microsoft.recoveryservices/vaults": "Management",
    "microsoft.automation/automationaccounts": "Management",
    "microsoft.portal/dashboards": "Management",
}

CATEGORY_DISPLAY = {
    "Networking":  {"bgcolor": "#E3F2FD", "label": "Networking"},
    "Compute":     {"bgcolor": "#E8F5E9", "label": "Compute and Apps"},
    "Data":        {"bgcolor": "#FFF8E1", "label": "Data and Storage"},
    "Security":    {"bgcolor": "#FCE4EC", "label": "Security and Identity"},
    "Monitoring":  {"bgcolor": "#F3E5F5", "label": "Monitoring"},
    "Integration": {"bgcolor": "#E0F7FA", "label": "Integration"},
    "AI":          {"bgcolor": "#EDE7F6", "label": "AI and Machine Learning"},
    "Management":  {"bgcolor": "#ECEFF1", "label": "Management"},
    "Other":       {"bgcolor": "#F5F5F5", "label": "Other Resources"},
}

# Relationship rules: (type_a_contains, type_b_contains, label, color, style)
# When both types exist in the same resource group, draw an edge
COMPREHENSIVE_EDGE_RULES = [
    # VM dependencies
    ("virtualmachines", "networkinterfaces", "", "#1565C0", "solid"),
    ("virtualmachines", "disks", "", "#78909C", "solid"),
    ("virtualmachines", "availabilitysets", "HA", "#2E7D32", "dashed"),
    ("virtualmachinescalesets", "loadbalancers", "", "#1565C0", "solid"),
    # NIC connectivity
    ("networkinterfaces", "publicipaddresses", "", "#1565C0", "solid"),
    ("networkinterfaces", "networksecuritygroups", "secured by", "#C62828", "dashed"),
    # App hosting
    ("web/sites", "serverfarms", "hosted on", "#2E7D32", "solid"),
    ("app/containerapps", "app/managedenvironments", "runs in", "#2E7D32", "solid"),
    # Private endpoints (connect to many service types)
    ("privateendpoints", "sql", "private link", "#C62828", "dashed"),
    ("privateendpoints", "storage", "private link", "#C62828", "dashed"),
    ("privateendpoints", "keyvault", "private link", "#C62828", "dashed"),
    ("privateendpoints", "documentdb", "private link", "#C62828", "dashed"),
    ("privateendpoints", "web/sites", "private link", "#C62828", "dashed"),
    ("privateendpoints", "apimanagement", "private link", "#C62828", "dashed"),
    ("privateendpoints", "containerregistry", "private link", "#C62828", "dashed"),
    ("privateendpoints", "cache/redis", "private link", "#C62828", "dashed"),
    # Monitoring
    ("insights/components", "web/sites", "monitors", "#6A1B9A", "dotted"),
    ("insights/components", "containerservice", "monitors", "#6A1B9A", "dotted"),
    ("insights/components", "apimanagement", "monitors", "#6A1B9A", "dotted"),
    ("insights/components", "app/containerapps", "monitors", "#6A1B9A", "dotted"),
    ("operationalinsights", "insights/components", "logs to", "#6A1B9A", "dotted"),
    # Security
    ("keyvault", "web/sites", "secrets/certs", "#C62828", "dashed"),
    ("keyvault", "apimanagement", "certs", "#C62828", "dashed"),
    ("keyvault", "containerservice", "secrets", "#C62828", "dashed"),
    ("keyvault", "virtualmachines", "secrets", "#C62828", "dashed"),
    # Load balancing / routing
    ("loadbalancers", "virtualmachines", "routes to", "#1565C0", "solid"),
    ("applicationgateways", "web/sites", "routes to", "#1565C0", "solid"),
    ("applicationgateways", "containerservice", "routes to", "#1565C0", "solid"),
    ("frontdoors", "web/sites", "routes to", "#1565C0", "solid"),
    ("azurefirewalls", "virtualnetworks", "protects", "#C62828", "dashed"),
    # APIM backends
    ("apimanagement", "web/sites", "backend API", "#00695C", "solid"),
    ("apimanagement", "containerservice", "backend API", "#00695C", "solid"),
    ("apimanagement", "logic/workflows", "backend API", "#00695C", "solid"),
    ("apimanagement", "app/containerapps", "backend API", "#00695C", "solid"),
    # Container orchestration
    ("containerservice", "containerregistry", "pulls images", "#2E7D32", "solid"),
    # Backup
    ("recoveryservices", "virtualmachines", "backup", "#37474F", "dashed"),
    ("recoveryservices", "sql", "backup", "#37474F", "dashed"),
    # Database parent-child
    ("sql/servers", "sql/servers/databases", "", "#F57F17", "solid"),
    # Messaging / events
    ("logic/workflows", "servicebus", "messaging", "#00695C", "dashed"),
    ("web/sites", "servicebus", "messaging", "#00695C", "dashed"),
    ("eventgrid", "web/sites", "events", "#00695C", "dashed"),
    ("eventgrid", "logic/workflows", "events", "#00695C", "dashed"),
    ("eventhub", "web/sites", "streams", "#00695C", "dashed"),
    # NIC to VNet
    ("networkinterfaces", "virtualnetworks", "connected to", "#1565C0", "dashed"),
    # AI / Cognitive Services
    ("cognitiveservices", "virtualnetworks", "connected to", "#1565C0", "dashed"),
    ("cognitiveservices", "privateendpoints", "private link", "#C62828", "dashed"),
    ("apimanagement", "cognitiveservices", "backend AI", "#6A1B9A", "solid"),
    ("web/sites", "cognitiveservices", "calls AI", "#6A1B9A", "dashed"),
    ("insights/components", "cognitiveservices", "monitors", "#6A1B9A", "dotted"),
    ("machinelearningservices", "storage", "uses", "#2E7D32", "dashed"),
    ("machinelearningservices", "keyvault", "secrets", "#C62828", "dashed"),
    ("machinelearningservices", "containerregistry", "images", "#2E7D32", "dashed"),
    # Bastion
    ("bastionhosts", "virtualnetworks", "secure access", "#C62828", "dashed"),
    # VPN / ExpressRoute
    ("virtualnetworkgateways", "virtualnetworks", "", "#1565C0", "solid"),
    ("expressroutecircuits", "virtualnetworkgateways", "hybrid", "#6A1B9A", "solid"),
]

MAX_COMPREHENSIVE_NODES = 50


def _get_resource_category(resource_type: str) -> str:
    """Determine the logical category for a resource type."""
    rt = resource_type.lower()
    if rt in TYPE_TO_CATEGORY:
        return TYPE_TO_CATEGORY[rt]
    # Partial matching fallback
    for pattern, category in [
        ("compute", "Compute"), ("web/", "Compute"), ("containerservice", "Compute"),
        ("containerregistry", "Compute"), ("app/", "Compute"),
        ("network", "Networking"), ("cdn", "Networking"), ("frontdoor", "Networking"),
        ("sql", "Data"), ("documentdb", "Data"), ("cosmos", "Data"),
        ("cache", "Data"), ("storage", "Data"), ("dbfor", "Data"),
        ("keyvault", "Security"), ("identity", "Security"), ("authorization", "Security"),
        ("insights", "Monitoring"), ("operationalinsights", "Monitoring"), ("monitor", "Monitoring"),
        ("apimanagement", "Integration"), ("logic", "Integration"),
        ("servicebus", "Integration"), ("eventgrid", "Integration"), ("eventhub", "Integration"),
        ("recoveryservices", "Management"), ("automation", "Management"),
        ("cognitiveservices", "AI"), ("machinelearningservices", "AI"),
    ]:
        if pattern in rt:
            return category
    return "Other"


def _detect_edges(resources: List[Dict[str, Any]], primary_names: set) -> List[tuple]:
    """
    Detect relationships between resources based on:
    1. Type-pair rules (COMPREHENSIVE_EDGE_RULES)
    2. Name correlation - if resource B's name contains resource A's name,
       and their types have a known relationship, draw an edge.
       This adds confidence that the edge is between THESE specific resources.
    Prioritizes edges involving primary (user-selected) resources.
    """
    resource_list = [(r["name"], r["type"].lower()) for r in resources]
    edges = []
    seen_pairs = set()

    for i, (name_a, type_a) in enumerate(resource_list):
        for j, (name_b, type_b) in enumerate(resource_list):
            if i >= j:
                continue
            pair_key = (min(name_a, name_b), max(name_a, name_b))
            if pair_key in seen_pairs:
                continue

            # Check if names are correlated (one contains the other)
            name_correlated = (
                name_a.lower() in name_b.lower() or
                name_b.lower() in name_a.lower()
            )

            for src_pat, tgt_pat, label, color, style in COMPREHENSIVE_EDGE_RULES:
                matched = False
                if src_pat in type_a and tgt_pat in type_b:
                    edges.append((name_a, name_b, label, color, style))
                    matched = True
                elif src_pat in type_b and tgt_pat in type_a:
                    edges.append((name_b, name_a, label, color, style))
                    matched = True
                if matched:
                    seen_pairs.add(pair_key)
                    break

            # If no type-rule matched but names are correlated and types are
            # plausibly related (same provider or known parent-child), add a
            # generic dependency edge
            if pair_key not in seen_pairs and name_correlated:
                # Only for name-correlated pairs where one is primary
                if name_a.lower() in primary_names or name_b.lower() in primary_names:
                    edges.append((name_a, name_b, "", "#78909C", "dashed"))
                    seen_pairs.add(pair_key)

    # Prioritize edges involving primary resources, limit total
    primary_edges = [e for e in edges if e[0].lower() in primary_names or e[1].lower() in primary_names]
    other_edges = [e for e in edges if e not in primary_edges]
    return (primary_edges + other_edges)[:25]


# Resource types that are known child/dependent resources of VMs
VM_CHILD_TYPE_PATTERNS = [
    "microsoft.compute/disks",
    "microsoft.compute/snapshots",
    "microsoft.compute/availabilitysets",
    "microsoft.network/networkinterfaces",
    "microsoft.network/publicipaddresses",
    "microsoft.network/networksecuritygroups",
    "microsoft.hybridcompute/machines/extensions",
]

# Singleton infrastructure types - only included if exactly 1 exists in the RG
# (high confidence it's THE shared resource for everything in the RG)
SINGLETON_INFRA_TYPES = {
    "microsoft.network/virtualnetworks",
    "microsoft.keyvault/vaults",
    "microsoft.operationalinsights/workspaces",
    "microsoft.recoveryservices/vaults",
    "microsoft.network/bastionhosts",
    "microsoft.network/azurefirewalls",
    "microsoft.network/applicationgateways",
    "microsoft.network/natgateways",
}


def _find_related_resources(
    primary_resources: List[Dict[str, Any]],
    all_rg_resources: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Smart dependency discovery: from all resources in the same RG(s),
    find only those actually related to the primary resources.

    Uses three phases:
    Phase 1 - Direct name correlation:
        Resources whose name contains the primary resource name.
        Catches NIC, Disk, PIP, NSG, extensions named after the VM.
        e.g., VM "arc-linux-vm-01" → "arc-linux-vm-01-nic", "arc-linux-vm-01_OsDisk_1_xxx"

    Phase 2 - Transitive name correlation:
        From Phase 1 results, find more resources that name-correlate with THOSE.
        Catches deeper dependency chains.
        e.g., NIC "arc-linux-vm-01-nic" → potential IP/NSG named after the NIC.

    Phase 3 - Singleton shared infrastructure:
        If there's exactly ONE VNet, ONE Key Vault, etc. in the RG, include it.
        High confidence it's THE shared resource. Skips if there are multiples
        (can't determine which one is relevant without ARM properties).
    """
    related = []
    primary_names_lower = {r["name"].lower() for r in primary_resources}
    already_included = set(primary_names_lower)

    # Phase 1: Direct name correlation
    # Primary name must be at least 3 chars to avoid false matches
    phase1_found = []
    for primary in primary_resources:
        pname = primary["name"].lower()
        if len(pname) < 3:
            continue
        for r in all_rg_resources:
            rname = r["name"].lower()
            if rname in already_included:
                continue
            if pname in rname:
                phase1_found.append(r)
                already_included.add(rname)

    related.extend(phase1_found)

    # Phase 2: Transitive name correlation from Phase 1 results
    # Only use found resources with names >= 5 chars to avoid noisy matches
    phase2_found = []
    for found_r in phase1_found:
        fname = found_r["name"].lower()
        if len(fname) < 5:
            continue
        for r in all_rg_resources:
            rname = r["name"].lower()
            if rname in already_included:
                continue
            if fname in rname:
                phase2_found.append(r)
                already_included.add(rname)

    related.extend(phase2_found)

    # Phase 3: Singleton shared infrastructure
    # Count each singleton type in the RG. Only include if exactly 1 of that type.
    type_groups = {}  # type -> list of resources
    for r in all_rg_resources:
        rname = r["name"].lower()
        if rname in already_included:
            continue
        rtype = r.get("type", "").lower()
        if rtype in SINGLETON_INFRA_TYPES:
            type_groups.setdefault(rtype, []).append(r)

    for rtype, group in type_groups.items():
        if len(group) == 1:
            r = group[0]
            related.append(r)
            already_included.add(r["name"].lower())

    return related


# ============================================================================
# PATTERN TEMPLATES
# ============================================================================

DIAGRAM_PATTERNS = {
    "web-3tier": {
        "name": "Web Application (3-Tier)",
        "description": "App Gateway + App Service + SQL Database + Redis + Key Vault",
        "template": '''
from diagrams import Diagram, Cluster, Edge
from diagrams.azure.network import ApplicationGateway, CDNProfiles
from diagrams.azure.compute import AppServices
from diagrams.azure.database import SQLDatabases, CacheForRedis
from diagrams.azure.storage import BlobStorage
from diagrams.azure.security import KeyVaults

graph_attr = {{"bgcolor": "white", "pad": "0.8", "nodesep": "0.9", "ranksep": "0.9", "splines": "spline", "fontname": "Arial Bold", "fontsize": "16", "dpi": "200"}}
node_attr = {{"fontname": "Arial Bold", "fontsize": "11", "labelloc": "t"}}

with Diagram("{name}", show=False, filename="{output}", direction="TB", outformat="png", graph_attr=graph_attr, node_attr=node_attr):
    cdn = CDNProfiles("CDN")
    with Cluster("Frontend"):
        gateway = ApplicationGateway("App Gateway")
        web = AppServices("Web App")
    with Cluster("Backend"):
        api = AppServices("API")
        cache = CacheForRedis("Redis")
    with Cluster("Data"):
        db = SQLDatabases("SQL Database")
        storage = BlobStorage("Static Assets")
    kv = KeyVaults("Key Vault")
    cdn >> gateway >> web >> api
    api >> [cache, db]
    api >> kv
    web >> storage
'''
    },
    "microservices": {
        "name": "Microservices with AKS",
        "description": "AKS + Cosmos DB + Redis + Service Bus + App Insights",
        "template": '''
from diagrams import Diagram, Cluster, Edge
from diagrams.azure.compute import AKS, ACR
from diagrams.azure.network import ApplicationGateway
from diagrams.azure.database import CosmosDb, CacheForRedis
from diagrams.azure.integration import ServiceBus
from diagrams.azure.security import KeyVaults
from diagrams.azure.monitor import ApplicationInsights

graph_attr = {{"bgcolor": "white", "pad": "0.8", "nodesep": "0.9", "ranksep": "0.9", "splines": "spline", "fontname": "Arial Bold", "fontsize": "16", "dpi": "200"}}
node_attr = {{"fontname": "Arial Bold", "fontsize": "11", "labelloc": "t"}}

with Diagram("{name}", show=False, filename="{output}", direction="LR", outformat="png", graph_attr=graph_attr, node_attr=node_attr):
    with Cluster("Ingress"):
        gateway = ApplicationGateway("App Gateway")
    with Cluster("AKS Cluster"):
        acr = ACR("Container Registry")
        aks = AKS("AKS")
    with Cluster("Data Services"):
        cosmos = CosmosDb("Cosmos DB")
        redis = CacheForRedis("Redis")
    with Cluster("Messaging"):
        bus = ServiceBus("Service Bus")
    insights = ApplicationInsights("App Insights")
    kv = KeyVaults("Key Vault")
    gateway >> aks
    acr >> aks
    aks >> [cosmos, redis, bus]
    aks >> kv
    aks >> insights
'''
    },
    "serverless": {
        "name": "Serverless / Event-Driven",
        "description": "Functions + Event Grid + Service Bus + Cosmos DB",
        "template": '''
from diagrams import Diagram, Cluster, Edge
from diagrams.azure.compute import FunctionApps
from diagrams.azure.integration import EventGridTopics, ServiceBus, LogicApps
from diagrams.azure.storage import BlobStorage, QueuesStorage
from diagrams.azure.database import CosmosDb

graph_attr = {{"bgcolor": "white", "pad": "0.8", "nodesep": "0.9", "ranksep": "0.9", "splines": "spline", "fontname": "Arial Bold", "fontsize": "16", "dpi": "200"}}
node_attr = {{"fontname": "Arial Bold", "fontsize": "11", "labelloc": "t"}}

with Diagram("{name}", show=False, filename="{output}", direction="LR", outformat="png", graph_attr=graph_attr, node_attr=node_attr):
    with Cluster("Event Sources"):
        blob = BlobStorage("Blob Trigger")
        queue = QueuesStorage("Queue Trigger")
        eventgrid = EventGridTopics("Event Grid")
    with Cluster("Processing"):
        func1 = FunctionApps("Processor 1")
        func2 = FunctionApps("Processor 2")
        logic = LogicApps("Orchestrator")
    with Cluster("Output"):
        bus = ServiceBus("Service Bus")
        cosmos = CosmosDb("Cosmos DB")
    blob >> func1 >> cosmos
    queue >> func2 >> bus
    eventgrid >> logic >> [func1, func2]
'''
    },
    "hub-spoke": {
        "name": "Hub-Spoke Network Topology",
        "description": "Hub VNet with Firewall + Bastion + VPN + Spoke VNets",
        "template": '''
from diagrams import Diagram, Cluster, Edge
from diagrams.azure.network import VirtualNetworks, Firewall, VirtualNetworkGateways
from diagrams.azure.networking import Bastions
from diagrams.azure.compute import VM
from diagrams.azure.database import SQLDatabases

graph_attr = {{"bgcolor": "white", "pad": "0.8", "nodesep": "0.9", "ranksep": "0.9", "splines": "spline", "fontname": "Arial Bold", "fontsize": "16", "dpi": "200"}}
node_attr = {{"fontname": "Arial Bold", "fontsize": "11", "labelloc": "t"}}

with Diagram("{name}", show=False, filename="{output}", direction="TB", outformat="png", graph_attr=graph_attr, node_attr=node_attr):
    with Cluster("Hub VNet"):
        firewall = Firewall("Azure Firewall")
        bastion = Bastions("Bastion")
        vpn = VirtualNetworkGateways("VPN Gateway")
    with Cluster("Spoke 1 - Web Tier"):
        web_vm = VM("Web Server")
    with Cluster("Spoke 2 - Data Tier"):
        db = SQLDatabases("SQL Database")
    with Cluster("Spoke 3 - App Tier"):
        app_vm = VM("App Server")
    onprem = VirtualNetworkGateways("On-Premises")
    onprem >> Edge(label="VPN") >> vpn >> firewall
    web_vm >> Edge(label="Peering") >> firewall
    app_vm >> Edge(label="Peering") >> firewall
    db >> Edge(label="Peering") >> firewall
    bastion >> [web_vm, app_vm, db]
'''
    },
    "data-platform": {
        "name": "Data Platform / Analytics",
        "description": "Data Factory + Data Lake + Databricks + Synapse",
        "template": '''
from diagrams import Diagram, Cluster, Edge
from diagrams.azure.analytics import DataFactories, Databricks, SynapseAnalytics, EventHubs
from diagrams.azure.storage import DataLakeStorage, BlobStorage
from diagrams.azure.database import SQLDatabases
from diagrams.azure.ml import MachineLearningServiceWorkspaces

graph_attr = {{"bgcolor": "white", "pad": "0.8", "nodesep": "0.9", "ranksep": "0.9", "splines": "spline", "fontname": "Arial Bold", "fontsize": "16", "dpi": "200"}}
node_attr = {{"fontname": "Arial Bold", "fontsize": "11", "labelloc": "t"}}

with Diagram("{name}", show=False, filename="{output}", direction="LR", outformat="png", graph_attr=graph_attr, node_attr=node_attr):
    with Cluster("Sources"):
        blob = BlobStorage("Raw Data")
        events = EventHubs("Streaming")
        sql = SQLDatabases("Operational DB")
    with Cluster("Ingestion"):
        adf = DataFactories("Data Factory")
    with Cluster("Storage"):
        lake = DataLakeStorage("Data Lake")
    with Cluster("Processing"):
        databricks = Databricks("Databricks")
        synapse = SynapseAnalytics("Synapse")
    ml = MachineLearningServiceWorkspaces("ML Workspace")
    [blob, events, sql] >> adf >> lake
    lake >> databricks >> synapse
    databricks >> ml
'''
    },
    "multi-region": {
        "name": "Multi-Region High Availability",
        "description": "Front Door + Multi-region App Services + Cosmos DB geo-replication",
        "template": '''
from diagrams import Diagram, Cluster, Edge
from diagrams.azure.network import FrontDoors
from diagrams.azure.compute import AppServices
from diagrams.azure.database import CosmosDb, SQLDatabases
from diagrams.azure.storage import BlobStorage

graph_attr = {{"bgcolor": "white", "pad": "0.8", "nodesep": "0.9", "ranksep": "0.9", "splines": "spline", "fontname": "Arial Bold", "fontsize": "16", "dpi": "200"}}
node_attr = {{"fontname": "Arial Bold", "fontsize": "11", "labelloc": "t"}}

with Diagram("{name}", show=False, filename="{output}", direction="TB", outformat="png", graph_attr=graph_attr, node_attr=node_attr):
    frontdoor = FrontDoors("Front Door")
    with Cluster("Region 1 - Primary"):
        app1 = AppServices("App Service")
        sql1 = SQLDatabases("SQL (Primary)")
    with Cluster("Region 2 - Secondary"):
        app2 = AppServices("App Service")
        sql2 = SQLDatabases("SQL (Secondary)")
    cosmos = CosmosDb("Cosmos DB\\n(Multi-Region)")
    blob = BlobStorage("Blob (GRS)")
    frontdoor >> [app1, app2]
    app1 >> [sql1, cosmos]
    app2 >> [sql2, cosmos]
    sql1 >> Edge(label="Geo-Replication", style="dashed") >> sql2
    [app1, app2] >> blob
'''
    },
    "zero-trust": {
        "name": "Zero Trust Security Architecture",
        "description": "Entra ID + Conditional Access + Firewall + Sentinel + Defender",
        "template": '''
from diagrams import Diagram, Cluster, Edge
from diagrams.azure.identity import ActiveDirectory, ConditionalAccess, ManagedIdentities
from diagrams.azure.network import Firewall, ApplicationGateway
from diagrams.azure.security import KeyVaults, Sentinel, Defender
from diagrams.azure.compute import AppServices
from diagrams.azure.database import SQLDatabases

graph_attr = {{"bgcolor": "white", "pad": "0.8", "nodesep": "0.9", "ranksep": "0.9", "splines": "spline", "fontname": "Arial Bold", "fontsize": "16", "dpi": "200"}}
node_attr = {{"fontname": "Arial Bold", "fontsize": "11", "labelloc": "t"}}

with Diagram("{name}", show=False, filename="{output}", direction="TB", outformat="png", graph_attr=graph_attr, node_attr=node_attr):
    with Cluster("Identity"):
        aad = ActiveDirectory("Entra ID")
        ca = ConditionalAccess("Conditional Access")
    with Cluster("Network Security"):
        waf = ApplicationGateway("WAF")
        firewall = Firewall("Firewall")
    with Cluster("Application"):
        app = AppServices("App Service")
        mi = ManagedIdentities("Managed Identity")
    with Cluster("Data"):
        sql = SQLDatabases("SQL")
    kv = KeyVaults("Key Vault")
    with Cluster("Security Operations"):
        sentinel = Sentinel("Sentinel")
        defender = Defender("Defender")
    aad >> ca >> waf >> app
    app >> mi >> [kv, sql]
    firewall >> [app, sql]
    [app, sql] >> sentinel
    defender >> [app, sql]
'''
    },
    "iot-solution": {
        "name": "IoT Solution Architecture",
        "description": "IoT Hub + Stream Analytics + Functions + Cosmos DB",
        "template": '''
from diagrams import Diagram, Cluster, Edge
from diagrams.azure.iot import IotHub, IotEdge
from diagrams.azure.analytics import StreamAnalyticsJobs, EventHubs
from diagrams.azure.compute import FunctionApps
from diagrams.azure.database import CosmosDb
from diagrams.azure.storage import DataLakeStorage
from diagrams.azure.ml import MachineLearningServiceWorkspaces

graph_attr = {{"bgcolor": "white", "pad": "0.8", "nodesep": "0.9", "ranksep": "0.9", "splines": "spline", "fontname": "Arial Bold", "fontsize": "16", "dpi": "200"}}
node_attr = {{"fontname": "Arial Bold", "fontsize": "11", "labelloc": "t"}}

with Diagram("{name}", show=False, filename="{output}", direction="LR", outformat="png", graph_attr=graph_attr, node_attr=node_attr):
    with Cluster("Edge"):
        edge = IotEdge("IoT Edge")
    with Cluster("Ingestion"):
        iot = IotHub("IoT Hub")
        eh = EventHubs("Event Hubs")
    with Cluster("Processing"):
        asa = StreamAnalyticsJobs("Stream Analytics")
        func = FunctionApps("Alerting")
    with Cluster("Storage"):
        cosmos = CosmosDb("Hot Store")
        lake = DataLakeStorage("Cold Store")
    ml = MachineLearningServiceWorkspaces("ML Workspace")
    edge >> iot >> asa
    asa >> [cosmos, lake, func]
    eh >> asa
    lake >> ml
'''
    },
    "devops-cicd": {
        "name": "DevOps CI/CD Pipeline",
        "description": "Azure Repos + Pipelines + ACR + AKS + App Insights",
        "template": '''
from diagrams import Diagram, Cluster, Edge
from diagrams.azure.devops import Repos, Pipelines, Artifacts
from diagrams.azure.compute import AKS, ACR
from diagrams.azure.security import KeyVaults
from diagrams.azure.monitor import ApplicationInsights

graph_attr = {{"bgcolor": "white", "pad": "0.8", "nodesep": "0.9", "ranksep": "0.9", "splines": "spline", "fontname": "Arial Bold", "fontsize": "16", "dpi": "200"}}
node_attr = {{"fontname": "Arial Bold", "fontsize": "11", "labelloc": "t"}}

with Diagram("{name}", show=False, filename="{output}", direction="LR", outformat="png", graph_attr=graph_attr, node_attr=node_attr):
    with Cluster("Source Control"):
        repos = Repos("Azure Repos")
    with Cluster("Build"):
        build = Pipelines("Build Pipeline")
        artifacts = Artifacts("Artifacts")
    with Cluster("Release"):
        release = Pipelines("Release Pipeline")
    with Cluster("Environments"):
        acr = ACR("Container Registry")
        aks_dev = AKS("Dev")
        aks_prod = AKS("Prod")
    kv = KeyVaults("Key Vault")
    insights = ApplicationInsights("App Insights")
    repos >> build >> artifacts >> release
    release >> acr >> [aks_dev, aks_prod]
    release >> kv
    [aks_dev, aks_prod] >> insights
'''
    },
    "ai-ml": {
        "name": "AI/ML Solution Architecture",
        "description": "ML Workspace + Cognitive Services + AKS + Cosmos DB + APIM",
        "template": '''
from diagrams import Diagram, Cluster, Edge
from diagrams.azure.ml import MachineLearningServiceWorkspaces, CognitiveServices
from diagrams.azure.compute import FunctionApps, AKS
from diagrams.azure.storage import BlobStorage
from diagrams.azure.database import CosmosDb
from diagrams.azure.integration import APIManagement

graph_attr = {{"bgcolor": "white", "pad": "0.8", "nodesep": "0.9", "ranksep": "0.9", "splines": "spline", "fontname": "Arial Bold", "fontsize": "16", "dpi": "200"}}
node_attr = {{"fontname": "Arial Bold", "fontsize": "11", "labelloc": "t"}}

with Diagram("{name}", show=False, filename="{output}", direction="LR", outformat="png", graph_attr=graph_attr, node_attr=node_attr):
    with Cluster("Data"):
        blob = BlobStorage("Training Data")
        cosmos = CosmosDb("Feature Store")
    with Cluster("ML Platform"):
        mlws = MachineLearningServiceWorkspaces("ML Workspace")
        cognitive = CognitiveServices("Cognitive Services")
    with Cluster("Serving"):
        aks = AKS("Model Serving")
        func = FunctionApps("Inference API")
    apim = APIManagement("API Management")
    blob >> mlws >> aks
    cosmos >> mlws
    cognitive >> func
    [aks, func] >> apim
'''
    },
    "hybrid-cloud": {
        "name": "Hybrid Cloud Architecture",
        "description": "On-premises + ExpressRoute + Azure VNets + Service Bus",
        "template": '''
from diagrams import Diagram, Cluster, Edge
from diagrams.azure.network import VirtualNetworkGateways, ExpressrouteCircuits, VirtualNetworks
from diagrams.azure.compute import AppServices, VM
from diagrams.azure.database import SQLDatabases
from diagrams.azure.integration import ServiceBus
from diagrams.onprem.database import MSSQL
from diagrams.onprem.compute import Server

graph_attr = {{"bgcolor": "white", "pad": "0.8", "nodesep": "0.9", "ranksep": "0.9", "splines": "spline", "fontname": "Arial Bold", "fontsize": "16", "dpi": "200"}}
node_attr = {{"fontname": "Arial Bold", "fontsize": "11", "labelloc": "t"}}

with Diagram("{name}", show=False, filename="{output}", direction="LR", outformat="png", graph_attr=graph_attr, node_attr=node_attr):
    with Cluster("On-Premises"):
        onprem_server = Server("App Server")
        onprem_db = MSSQL("SQL Server")
    with Cluster("Connectivity"):
        expressroute = ExpressrouteCircuits("ExpressRoute")
        vpn = VirtualNetworkGateways("VPN Gateway")
    with Cluster("Azure"):
        with Cluster("VNet"):
            vnet = VirtualNetworks("Hub VNet")
            app = AppServices("App Service")
            sql = SQLDatabases("Azure SQL")
        bus = ServiceBus("Service Bus")
    onprem_server >> expressroute >> vnet
    onprem_db >> Edge(label="Data Sync", style="dashed") >> sql
    app >> bus >> onprem_server
'''
    },
    "api-management": {
        "name": "API-First Architecture",
        "description": "APIM + Functions + Logic Apps + Cosmos DB + Service Bus",
        "template": '''
from diagrams import Diagram, Cluster, Edge
from diagrams.azure.integration import APIManagement, LogicApps, ServiceBus
from diagrams.azure.compute import FunctionApps, AppServices
from diagrams.azure.database import CosmosDb
from diagrams.azure.security import KeyVaults
from diagrams.azure.identity import ActiveDirectory

graph_attr = {{"bgcolor": "white", "pad": "0.8", "nodesep": "0.9", "ranksep": "0.9", "splines": "spline", "fontname": "Arial Bold", "fontsize": "16", "dpi": "200"}}
node_attr = {{"fontname": "Arial Bold", "fontsize": "11", "labelloc": "t"}}

with Diagram("{name}", show=False, filename="{output}", direction="TB", outformat="png", graph_attr=graph_attr, node_attr=node_attr):
    users = ActiveDirectory("Entra ID")
    with Cluster("API Layer"):
        apim = APIManagement("API Management")
    with Cluster("Backend Services"):
        app = AppServices("Core API")
        func = FunctionApps("Async Processor")
        logic = LogicApps("Integrations")
    with Cluster("Data"):
        cosmos = CosmosDb("Cosmos DB")
        bus = ServiceBus("Service Bus")
    kv = KeyVaults("Key Vault")
    users >> apim >> [app, func, logic]
    app >> cosmos
    func >> bus
    logic >> bus
    [app, func, logic] >> kv
'''
    },
}


# ============================================================================
# DIAGRAM GENERATION ENGINE
# ============================================================================

class AzureDiagramGenerator:
    """Generates Azure architecture diagrams and returns base64 PNG images."""

    def __init__(self):
        self.output_dir = tempfile.mkdtemp(prefix="azure_diagrams_")
        self._check_prerequisites()

    def _check_prerequisites(self) -> Dict[str, Any]:
        """Check if required dependencies are available."""
        status = {"diagrams": False, "graphviz": False, "errors": []}
        try:
            import diagrams
            status["diagrams"] = True
        except ImportError:
            status["errors"].append("Python 'diagrams' library not installed. Run: pip install diagrams")

        try:
            result = subprocess.run(["dot", "-V"], capture_output=True, text=True, timeout=10)
            status["graphviz"] = result.returncode == 0 or "graphviz" in result.stderr.lower()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            status["errors"].append("Graphviz not installed. Run: choco install graphviz (Windows)")

        return status

    def get_available_patterns(self) -> Dict[str, Dict[str, str]]:
        """Return list of available diagram patterns."""
        return {
            key: {"name": val["name"], "description": val["description"]}
            for key, val in DIAGRAM_PATTERNS.items()
        }

    def generate_from_pattern(self, pattern_key: str, title: str = None) -> Dict[str, Any]:
        """
        Generate a diagram from a pre-built pattern.

        Args:
            pattern_key: Key from DIAGRAM_PATTERNS
            title: Optional custom title

        Returns:
            Dict with base64_image, filename, pattern info
        """
        if pattern_key not in DIAGRAM_PATTERNS:
            return {"error": f"Unknown pattern '{pattern_key}'. Available: {', '.join(DIAGRAM_PATTERNS.keys())}"}

        pattern = DIAGRAM_PATTERNS[pattern_key]
        name = sanitize_name(title or pattern["name"])
        output_name = f"diagram_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(self.output_dir, output_name).replace("\\", "/")

        code = pattern["template"].format(name=name, output=output_path)
        return self._execute_and_encode(code, output_path, name, pattern_key)

    def generate_from_code(self, diagram_code: str, title: str = "Azure Architecture") -> Dict[str, Any]:
        """
        Generate a diagram from AI-generated Python code.
        Code is validated for security before execution.

        Args:
            diagram_code: Python code using the diagrams library
            title: Diagram title

        Returns:
            Dict with base64_image, filename, or error
        """
        is_valid, errors = validate_code(diagram_code)
        if not is_valid:
            return {"error": f"Code validation failed: {'; '.join(errors)}"}

        output_name = f"diagram_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(self.output_dir, output_name).replace("\\", "/")

        # Inject output path if not already set
        if "filename=" not in diagram_code:
            diagram_code = diagram_code.replace(
                'show=False',
                f'show=False, filename="{output_path}"'
            )
        else:
            # Replace existing filename
            diagram_code = re.sub(
                r'filename\s*=\s*["\'][^"\']*["\']',
                f'filename="{output_path}"',
                diagram_code
            )

        # Ensure PNG output
        if "outformat=" not in diagram_code:
            diagram_code = diagram_code.replace(
                'show=False',
                'show=False, outformat="png"'
            )

        return self._execute_and_encode(diagram_code, output_path, title, "custom")

    def generate_from_resources(self, resources: List[Dict[str, Any]], title: str = "Azure Environment", scope: str = "subscription") -> Dict[str, Any]:
        """
        Generate a diagram from actual Azure resources discovered via Resource Graph.

        Args:
            resources: List of resource dicts with 'type', 'name', 'resourceGroup', 'location'
            title: Diagram title
            scope: 'subscription', 'resource_group', or 'landing_zone'

        Returns:
            Dict with base64_image, filename, resource count
        """
        if not resources:
            return {"error": "No resources provided to generate diagram"}

        # Group resources by resource group and type
        rg_groups = {}
        imports_needed = {}
        var_counter = [0]

        def make_var(name: str) -> str:
            safe = re.sub(r'[^a-zA-Z0-9]', '_', name.lower())
            safe = re.sub(r'_+', '_', safe).strip('_')
            if not safe or safe[0].isdigit():
                safe = 'r_' + safe
            var_counter[0] += 1
            return f"{safe}_{var_counter[0]}"

        for res in resources:
            rg = res.get("resourceGroup", "Unknown")
            res_type = res.get("type", "").lower()
            res_name = res.get("name", "Unknown")

            if rg not in rg_groups:
                rg_groups[rg] = []

            # Map to diagram node
            if res_type in RESOURCE_TYPE_MAP:
                module, cls = RESOURCE_TYPE_MAP[res_type]
            else:
                # Try category fallback
                category = res_type.split("/")[0].split(".")[-1] if "." in res_type else ""
                if category in CATEGORY_FALLBACK:
                    module, cls = CATEGORY_FALLBACK[category]
                else:
                    module, cls = "diagrams.azure.general", "AllResources"

            var = make_var(res_name)
            if module not in imports_needed:
                imports_needed[module] = set()
            imports_needed[module].add(cls)

            rg_groups[rg].append({
                "var": var,
                "cls": cls,
                "label": res_name[:30],
                "module": module
            })

        # Limit for readability (max 60 nodes)
        total_nodes = sum(len(v) for v in rg_groups.values())
        if total_nodes > 60:
            # Aggregate by type within each RG
            for rg in rg_groups:
                type_counts = {}
                for item in rg_groups[rg]:
                    key = (item["cls"], item["module"])
                    if key not in type_counts:
                        type_counts[key] = {"count": 0, "var": item["var"], "cls": item["cls"], "module": item["module"]}
                    type_counts[key]["count"] += 1
                rg_groups[rg] = [
                    {
                        "var": v["var"],
                        "cls": v["cls"],
                        "label": f"{v['cls']} x{v['count']}" if v["count"] > 1 else v["cls"],
                        "module": v["module"]
                    }
                    for v in type_counts.values()
                ]
            # Rebuild imports
            imports_needed = {}
            for rg in rg_groups:
                for item in rg_groups[rg]:
                    if item["module"] not in imports_needed:
                        imports_needed[item["module"]] = set()
                    imports_needed[item["module"]].add(item["cls"])

        # Build code
        output_name = f"diagram_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(self.output_dir, output_name).replace("\\", "/")

        code_lines = []
        code_lines.append("from diagrams import Diagram, Cluster, Edge")
        for module, classes in imports_needed.items():
            cls_list = ", ".join(sorted(classes))
            code_lines.append(f"from {module} import {cls_list}")

        code_lines.append("")
        code_lines.append(f'graph_attr = {{"bgcolor": "white", "pad": "1.2", "nodesep": "0.8", "ranksep": "1.0", "splines": "ortho", "fontname": "Arial Bold", "fontsize": "16", "dpi": "200"}}')
        code_lines.append(f'node_attr = {{"fontname": "Arial Bold", "fontsize": "11", "labelloc": "t"}}')
        code_lines.append("")

        code_lines.append(f'with Diagram("{sanitize_name(title)}", show=False, filename="{output_path}", direction="TB", outformat="png", graph_attr=graph_attr, node_attr=node_attr):')

        # Arrange RGs in rows of 2 using invisible sub-clusters
        RG_COLS = 2
        rg_list = list(rg_groups.keys())
        rg_rows_list = [rg_list[i:i + RG_COLS] for i in range(0, len(rg_list), RG_COLS)]
        rg_anchor_vars = []

        for row_idx, rg_row in enumerate(rg_rows_list):
            code_lines.append(f'    with Cluster("row_{row_idx}", graph_attr={{"style": "invis", "margin": "8"}}):')
            for rg in rg_row:
                safe_rg = sanitize_name(rg)
                items = rg_groups[rg]
                code_lines.append(f'        with Cluster("{safe_rg}"):')
                first_var = None
                for item in items:
                    code_lines.append(f'            {item["var"]} = {item["cls"]}("{item["label"]}")')
                    if first_var is None:
                        first_var = item["var"]
                if first_var:
                    rg_anchor_vars.append(first_var)

        # Invisible edges for vertical stacking
        if len(rg_anchor_vars) > 1:
            code_lines.append("")
            code_lines.append("    # Force vertical layout")
            for i in range(len(rg_anchor_vars) - 1):
                code_lines.append(f'    {rg_anchor_vars[i]} >> Edge(color="transparent", style="invis") >> {rg_anchor_vars[i + 1]}')

        code = "\n".join(code_lines)

        is_valid, errors = validate_code(code)
        if not is_valid:
            return {"error": f"Generated code validation failed: {'; '.join(errors)}", "generated_code": code}

        result = self._execute_and_encode(code, output_path, title, "live_resources")
        result["resource_count"] = total_nodes
        result["resource_group_count"] = len(rg_groups)
        return result

    def generate_comprehensive_diagram(
        self,
        primary_resources: List[Dict[str, Any]],
        context_resources: List[Dict[str, Any]],
        subscription_name: str = "",
        title: str = "Azure Architecture"
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive architecture diagram showing a resource with all its
        dependencies, network topology, and hierarchical context.

        Unlike generate_from_resources (flat icon-per-resource), this creates a rich,
        layered diagram with:
        - Subscription/Region/RG hierarchy
        - Resources grouped by category (Compute, Networking, Data, Security, etc.)
        - Edges showing relationships (data flow, network, security, monitoring)
        - Primary resources visually highlighted

        Args:
            primary_resources: User-selected resources (highlighted in diagram)
            context_resources: Auto-discovered resources from the same RG(s)
            subscription_name: Azure subscription display name
            title: Diagram title
        """
        if not primary_resources:
            return {"error": "No primary resources provided for comprehensive diagram"}

        primary_names = {r["name"].lower() for r in primary_resources}

        # Merge primary + context, dedup by name
        all_resources = list(primary_resources)
        seen = {r["name"].lower() for r in all_resources}
        for r in context_resources:
            if r["name"].lower() not in seen:
                all_resources.append(r)
                seen.add(r["name"].lower())

        # Group resources by RG -> Category
        rg_categories = {}  # {rg_name: {category: [resources]}}
        for r in all_resources:
            rg = r.get("resourceGroup", "Unknown")
            cat = _get_resource_category(r.get("type", ""))
            rg_categories.setdefault(rg, {}).setdefault(cat, []).append(r)

        # Aggregate excess: keep max 8 individual nodes per category per RG
        # Excess nodes get aggregated into "TypeName x{count}" nodes
        MAX_PER_CATEGORY = 8
        for rg in rg_categories:
            for cat in rg_categories[rg]:
                items = rg_categories[rg][cat]
                if len(items) <= MAX_PER_CATEGORY:
                    continue
                # Always keep primary resources
                keep = [r for r in items if r["name"].lower() in primary_names]
                rest = [r for r in items if r["name"].lower() not in primary_names]
                # Keep up to MAX_PER_CATEGORY total (primary + some context)
                slots = MAX_PER_CATEGORY - len(keep)
                if slots > 0:
                    keep.extend(rest[:slots])
                    rest = rest[slots:]
                # Aggregate the rest by type
                if rest:
                    type_counts = {}
                    for r in rest:
                        t = r.get("type", "Unknown").split("/")[-1]
                        type_counts[t] = type_counts.get(t, 0) + 1
                    for t, cnt in type_counts.items():
                        # Create an aggregate node
                        keep.append({
                            "name": f"{t} x{cnt}",
                            "type": rest[0]["type"],  # use first type for icon mapping
                            "resourceGroup": rg,
                            "location": rest[0].get("location", ""),
                            "_aggregate": True
                        })
                rg_categories[rg][cat] = keep

        # Detect edges
        edges = _detect_edges(all_resources, primary_names)

        # Determine region from resources
        regions = set()
        for r in all_resources:
            loc = r.get("location", "")
            if loc:
                regions.add(loc)
        region_label = ", ".join(sorted(regions)) if regions else "Azure"

        # Build diagram variable map and code
        var_counter = [0]
        var_map = {}  # resource_name_lower -> variable_name
        imports_needed = {}  # module -> set of classes

        def make_var(name: str) -> str:
            safe = re.sub(r'[^a-zA-Z0-9]', '_', name.lower())
            safe = re.sub(r'_+', '_', safe).strip('_')
            if not safe or safe[0].isdigit():
                safe = 'r_' + safe
            var_counter[0] += 1
            return f"{safe}_{var_counter[0]}"

        def get_node_info(res):
            """Get the diagram module/class for a resource type."""
            res_type = res.get("type", "").lower()
            if res_type in RESOURCE_TYPE_MAP:
                return RESOURCE_TYPE_MAP[res_type]
            category = res_type.split("/")[0].split(".")[-1] if "." in res_type else ""
            if category in CATEGORY_FALLBACK:
                return CATEGORY_FALLBACK[category]
            return ("diagrams.azure.general", "AllResources")

        # Determine if we should highlight primary resources
        # (only meaningful when there's a mix of primary + context)
        has_context = len(context_resources) > 0

        # Pre-register all nodes
        node_entries = []  # list of (rg, category, var, cls, label, module, is_primary)
        for rg, categories in rg_categories.items():
            for cat, resources_list in categories.items():
                for r in resources_list:
                    module, cls = get_node_info(r)
                    var = make_var(r["name"])
                    var_map[r["name"].lower()] = var
                    is_primary = r["name"].lower() in primary_names

                    # Build enriched label with key properties
                    label_parts = [r["name"][:30]]
                    if is_primary and has_context:
                        label_parts[0] = f">> {label_parts[0]} <<"

                    # Add enriched metadata lines
                    enrichment = []
                    if r.get("vmSize"):
                        enrichment.append(f"Size: {r['vmSize']}")
                    if r.get("diskSizeGB"):
                        enrichment.append(f"{r['diskSizeGB']} GB")
                    if r.get("osType"):
                        enrichment.append(r["osType"])
                    if r.get("privateIP"):
                        enrichment.append(f"IP: {r['privateIP']}")
                    if r.get("publicIPAddr"):
                        enrichment.append(f"PIP: {r['publicIPAddr']}")
                    if r.get("skuName"):
                        enrichment.append(r["skuName"])
                    if r.get("availabilitySet"):
                        enrichment.append(f"AvSet: {r['availabilitySet'][:20]}")

                    # Add up to 2 enrichment lines
                    for detail in enrichment[:2]:
                        label_parts.append(detail)

                    label = "\\n".join(label_parts)

                    if module not in imports_needed:
                        imports_needed[module] = set()
                    imports_needed[module].add(cls)
                    node_entries.append((rg, cat, var, cls, label, module, is_primary))

        # Build the generated Python code
        output_name = f"diagram_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(self.output_dir, output_name).replace("\\", "/")

        code_lines = []
        code_lines.append("from diagrams import Diagram, Cluster, Edge")
        for module, classes in sorted(imports_needed.items()):
            cls_list = ", ".join(sorted(classes))
            code_lines.append(f"from {module} import {cls_list}")

        code_lines.append("")
        code_lines.append('graph_attr = {"bgcolor": "white", "pad": "1.2", "nodesep": "0.8", "ranksep": "1.0", "splines": "ortho", "fontname": "Arial Bold", "fontsize": "14", "dpi": "200"}')
        code_lines.append('node_attr = {"fontname": "Arial", "fontsize": "10", "labelloc": "t"}')
        code_lines.append("")

        safe_title = sanitize_name(title)
        code_lines.append(f'with Diagram("{safe_title}", show=False, filename="{output_path}", direction="TB", outformat="png", graph_attr=graph_attr, node_attr=node_attr):')

        # Subscription cluster
        sub_label = sanitize_name(subscription_name) if subscription_name else "Azure Subscription"
        code_lines.append(f'    with Cluster("{sub_label}", graph_attr={{"bgcolor": "#F0F8FF", "style": "rounded", "fontsize": "13", "fontname": "Arial Bold", "pencolor": "#4A90D9", "penwidth": "2"}}):')

        # Region cluster
        code_lines.append(f'        with Cluster("Region: {sanitize_name(region_label)}", graph_attr={{"bgcolor": "#F5F5F5", "style": "rounded", "fontsize": "12", "fontname": "Arial Bold"}}):')

        # RG clusters with category sub-clusters, arranged in rows of 2
        indent_rg = "            "
        indent_row = "                "
        indent_cat = "                    "
        indent_node = "                        "

        cat_anchor_vars = []  # for invisible edge chaining

        for rg, categories in rg_categories.items():
            safe_rg = sanitize_name(rg)
            code_lines.append(f'{indent_rg}with Cluster("RG: {safe_rg}", graph_attr={{"bgcolor": "#FAFAFA", "style": "rounded,bold", "fontsize": "12", "fontname": "Arial Bold", "pencolor": "#333333", "penwidth": "1.5"}}):')

            cat_order = ["Networking", "Compute", "Data", "Security", "AI", "Integration", "Monitoring", "Management", "Other"]
            sorted_cats = sorted(categories.keys(), key=lambda c: cat_order.index(c) if c in cat_order else 99)

            # Arrange category clusters in rows of 2
            CAT_COLS = 2
            cat_rows = [sorted_cats[i:i + CAT_COLS] for i in range(0, len(sorted_cats), CAT_COLS)]

            for row_idx, cat_row in enumerate(cat_rows):
                code_lines.append(f'{indent_row}with Cluster("cat_row_{rg}_{row_idx}", graph_attr={{"style": "invis", "margin": "4"}}):')

                for cat in cat_row:
                    cat_resources = categories[cat]
                    if not cat_resources:
                        continue
                    style_info = CATEGORY_DISPLAY.get(cat, CATEGORY_DISPLAY["Other"])
                    cat_label = style_info["label"]
                    cat_bg = style_info["bgcolor"]
                    code_lines.append(f'{indent_cat}with Cluster("{cat_label}", graph_attr={{"bgcolor": "{cat_bg}", "style": "rounded,filled", "fontsize": "11", "fontname": "Arial Bold"}}):')

                    first_in_cat = True
                    for entry in node_entries:
                        e_rg, e_cat, e_var, e_cls, e_label, e_module, e_primary = entry
                        if e_rg == rg and e_cat == cat:
                            code_lines.append(f'{indent_node}{e_var} = {e_cls}("{e_label}")')
                            if first_in_cat:
                                cat_anchor_vars.append(e_var)
                                first_in_cat = False

        # Add real relationship edges
        edge_lines = []
        for src_name, tgt_name, label, color, style in edges:
            src_var = var_map.get(src_name.lower())
            tgt_var = var_map.get(tgt_name.lower())
            if src_var and tgt_var:
                if label:
                    edge_lines.append(f'    {src_var} >> Edge(label="{label}", color="{color}", style="{style}") >> {tgt_var}')
                else:
                    edge_lines.append(f'    {src_var} >> Edge(color="{color}", style="{style}") >> {tgt_var}')

        if edge_lines:
            code_lines.append("")
            code_lines.append("    # Resource relationships")
            code_lines.extend(edge_lines)

        # Add invisible edges between category rows to force vertical stacking
        if len(cat_anchor_vars) > 1 and not edge_lines:
            code_lines.append("")
            code_lines.append("    # Force vertical layout")
            for i in range(0, len(cat_anchor_vars) - 1, CAT_COLS):
                next_idx = i + CAT_COLS
                if next_idx < len(cat_anchor_vars):
                    code_lines.append(f'    {cat_anchor_vars[i]} >> Edge(color="transparent", style="invis") >> {cat_anchor_vars[next_idx]}')

        code = "\n".join(code_lines)

        is_valid, errors = validate_code(code)
        if not is_valid:
            return {"error": f"Generated code validation failed: {'; '.join(errors)}", "generated_code": code}

        result = self._execute_and_encode(code, output_path, title, "comprehensive")
        result["resource_count"] = len(all_resources)
        result["resource_group_count"] = len(rg_categories)
        result["primary_count"] = len(primary_resources)
        result["context_count"] = len(all_resources) - len(primary_resources)
        result["edge_count"] = len(edge_lines)
        return result

    def generate_environment_overview(
        self,
        resources: List[Dict[str, Any]],
        title: str = "Azure Environment Overview"
    ) -> Dict[str, Any]:
        """
        Generate a high-level environment diagram showing all subscriptions,
        regions, and resource groups with summarized resource counts.
        Uses grid layout with invisible edges to prevent horizontal-only rendering.
        """
        if not resources:
            return {"error": "No resources provided for environment overview"}

        # Build hierarchy: subscription -> region -> RG -> {type: count}
        hierarchy = {}
        for r in resources:
            sub = r.get("subscriptionName") or "Azure Subscription"
            loc = r.get("location") or "global"
            rg = r.get("resourceGroup", "Unknown")
            rtype = r.get("type", "Unknown").split("/")[-1]
            hierarchy.setdefault(sub, {}).setdefault(loc, {}).setdefault(rg, {})
            hierarchy[sub][loc][rg][rtype] = hierarchy[sub][loc][rg].get(rtype, 0) + 1

        output_name = f"diagram_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(self.output_dir, output_name).replace("\\", "/")

        COLS = 3  # RGs per row inside each region cluster

        code_lines = []
        code_lines.append("from diagrams import Diagram, Cluster, Edge")
        code_lines.append("from diagrams.azure.general import AllResources")
        code_lines.append("from diagrams.azure.compute import VM")
        code_lines.append("from diagrams.azure.network import VirtualNetworks")
        code_lines.append("from diagrams.azure.database import SQL")
        code_lines.append("from diagrams.azure.storage import StorageAccounts")
        code_lines.append("from diagrams.azure.security import KeyVaults")
        code_lines.append("from diagrams.azure.integration import LogicApps")
        code_lines.append("from diagrams.azure.monitor import Monitor")
        code_lines.append("")
        code_lines.append('graph_attr = {"bgcolor": "white", "pad": "1.2", "nodesep": "0.8", "ranksep": "1.2", "splines": "ortho", "fontname": "Arial Bold", "fontsize": "14", "dpi": "200"}')
        code_lines.append('node_attr = {"fontname": "Arial", "fontsize": "9", "labelloc": "b"}')
        code_lines.append("")

        safe_title = sanitize_name(title)
        code_lines.append(f'with Diagram("{safe_title}", show=False, filename="{output_path}", direction="TB", outformat="png", graph_attr=graph_attr, node_attr=node_attr):')

        # Track all row-anchor variables for invisible edges
        all_row_anchors = []
        var_c = [0]

        def nvar():
            var_c[0] += 1
            return f"n_{var_c[0]}"

        # Pick a representative icon for RG based on dominant category
        CAT_ICON_MAP = {
            "Compute": "VM", "Networking": "VirtualNetworks", "Data": "SQL",
            "Security": "KeyVaults", "Integration": "LogicApps",
            "Monitoring": "Monitor", "Management": "AllResources", "Other": "AllResources",
        }

        for sub_name, regions in hierarchy.items():
            safe_sub = sanitize_name(sub_name)
            total_rgs = sum(len(rgs) for rgs in regions.values())
            total_res = sum(sum(sum(tc.values()) for tc in rgs.values()) for rgs in regions.values())
            code_lines.append(f'    with Cluster("{safe_sub}\\n({total_rgs} RGs, {total_res} resources)", graph_attr={{"bgcolor": "#E3F2FD", "style": "rounded", "fontsize": "13", "fontname": "Arial Bold", "pencolor": "#1565C0", "penwidth": "2"}}):')

            for region, rgs in regions.items():
                safe_region = sanitize_name(region)
                region_res = sum(sum(tc.values()) for tc in rgs.values())
                code_lines.append(f'        with Cluster("Region: {safe_region} ({len(rgs)} RGs, {region_res} resources)", graph_attr={{"bgcolor": "#F5F5F5", "style": "rounded", "fontsize": "12"}}):')

                # Build RG list with metadata
                rg_items = []
                for rg_name, type_counts in rgs.items():
                    rg_total = sum(type_counts.values())
                    # Determine dominant category for icon
                    cat_counts = {}
                    for rtype_short, cnt in type_counts.items():
                        cat = _get_resource_category(f"microsoft.unknown/{rtype_short}")
                        cat_counts[cat] = cat_counts.get(cat, 0) + cnt
                    dominant = max(cat_counts, key=cat_counts.get) if cat_counts else "Other"
                    icon_cls = CAT_ICON_MAP.get(dominant, "AllResources")

                    top = sorted(type_counts.items(), key=lambda x: -x[1])[:3]
                    summary = ", ".join(f"{t}: {c}" for t, c in top)
                    if len(type_counts) > 3:
                        summary += f"\\n+{len(type_counts) - 3} more types"

                    rg_items.append({
                        "name": rg_name[:35],
                        "total": rg_total,
                        "summary": summary,
                        "icon": icon_cls,
                    })

                # Arrange in grid: COLS per row using invisible sub-clusters
                rows = [rg_items[i:i + COLS] for i in range(0, len(rg_items), COLS)]

                for row_idx, row in enumerate(rows):
                    row_label = f"row_{region}_{row_idx}"
                    # Invisible cluster for each row
                    code_lines.append(f'            with Cluster("{sanitize_name(row_label)}", graph_attr={{"style": "invis", "margin": "4"}}):')
                    row_first_var = None
                    for rg_info in row:
                        v = nvar()
                        safe_rg = sanitize_name(rg_info["name"])
                        code_lines.append(f'                {v} = {rg_info["icon"]}("{safe_rg}\\n{rg_info["total"]} resources\\n{rg_info["summary"]}")')
                        if row_first_var is None:
                            row_first_var = v
                    if row_first_var:
                        all_row_anchors.append(row_first_var)

        # Add invisible edges between row anchors to force vertical stacking
        if len(all_row_anchors) > 1:
            code_lines.append("")
            code_lines.append("    # Force vertical layout")
            for i in range(len(all_row_anchors) - 1):
                code_lines.append(f'    {all_row_anchors[i]} >> Edge(color="transparent", style="invis") >> {all_row_anchors[i + 1]}')

        code = "\n".join(code_lines)

        is_valid, errors = validate_code(code)
        if not is_valid:
            return {"error": f"Generated code validation failed: {'; '.join(errors)}", "generated_code": code}

        result = self._execute_and_encode(code, output_path, title, "environment_overview")
        result["subscription_count"] = len(hierarchy)
        result["total_resources"] = sum(
            sum(sum(sum(tc.values()) for tc in rgs.values()) for rgs in regions.values())
            for regions in hierarchy.values()
        )
        return result

    def generate_subscription_overview(
        self,
        resources: List[Dict[str, Any]],
        subscription_name: str = "",
        title: str = "Subscription Overview"
    ) -> Dict[str, Any]:
        """
        Generate a subscription-level diagram showing all resource groups
        with resources grouped by category. Uses invisible edges for vertical stacking.
        """
        if not resources:
            return {"error": "No resources provided for subscription overview"}

        # Group by RG -> category -> type -> count
        rg_data = {}
        for r in resources:
            rg = r.get("resourceGroup", "Unknown")
            cat = _get_resource_category(r.get("type", ""))
            rtype = r.get("type", "").lower()
            rtype_short = rtype.split("/")[-1] if "/" in rtype else rtype
            rg_data.setdefault(rg, {}).setdefault(cat, {})
            rg_data[rg][cat][rtype_short] = rg_data[rg][cat].get(rtype_short, 0) + 1

        output_name = f"diagram_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(self.output_dir, output_name).replace("\\", "/")

        code_lines = []
        code_lines.append("from diagrams import Diagram, Cluster, Edge")

        # Collect all needed icon classes from aggregated types
        imports_needed = {}
        node_plan = []  # (rg, cat, var, cls, label)
        var_c = [0]

        def nvar(prefix="r"):
            var_c[0] += 1
            return f"{prefix}_{var_c[0]}"

        for rg, categories in rg_data.items():
            for cat, type_counts in categories.items():
                for rtype_short, count in type_counts.items():
                    full_type = None
                    for full_t in RESOURCE_TYPE_MAP:
                        if full_t.endswith("/" + rtype_short):
                            full_type = full_t
                            break
                    if full_type and full_type in RESOURCE_TYPE_MAP:
                        module, cls = RESOURCE_TYPE_MAP[full_type]
                    else:
                        cat_key = cat.lower()
                        if cat_key in CATEGORY_FALLBACK:
                            module, cls = CATEGORY_FALLBACK[cat_key]
                        else:
                            module, cls = "diagrams.azure.general", "AllResources"

                    imports_needed.setdefault(module, set()).add(cls)
                    label = f"{rtype_short} x{count}" if count > 1 else rtype_short
                    var = nvar()
                    node_plan.append((rg, cat, var, cls, sanitize_name(label[:35])))

        for module, classes in sorted(imports_needed.items()):
            code_lines.append(f"from {module} import {', '.join(sorted(classes))}")

        code_lines.append("")
        code_lines.append('graph_attr = {"bgcolor": "white", "pad": "1.2", "nodesep": "0.6", "ranksep": "1.0", "splines": "ortho", "fontname": "Arial Bold", "fontsize": "14", "dpi": "200"}')
        code_lines.append('node_attr = {"fontname": "Arial", "fontsize": "9", "labelloc": "t"}')
        code_lines.append("")

        safe_title = sanitize_name(title)
        sub_label = sanitize_name(subscription_name) if subscription_name else "Subscription"
        code_lines.append(f'with Diagram("{safe_title}", show=False, filename="{output_path}", direction="TB", outformat="png", graph_attr=graph_attr, node_attr=node_attr):')
        code_lines.append(f'    with Cluster("{sub_label}", graph_attr={{"bgcolor": "#E3F2FD", "style": "rounded", "fontsize": "13", "fontname": "Arial Bold", "pencolor": "#1565C0", "penwidth": "2"}}):')

        cat_order = ["Networking", "Compute", "Data", "Security", "Integration", "Monitoring", "Management", "Other"]

        # Arrange RGs in rows of 2 using invisible sub-clusters
        RG_COLS = 2
        rg_list = list(rg_data.keys())
        rg_rows = [rg_list[i:i + RG_COLS] for i in range(0, len(rg_list), RG_COLS)]

        rg_anchor_vars = []  # first variable from each RG for invisible edge chaining

        for row_idx, rg_row in enumerate(rg_rows):
            # Invisible row cluster
            code_lines.append(f'        with Cluster("rg_row_{row_idx}", graph_attr={{"style": "invis", "margin": "8"}}):')

            for rg in rg_row:
                safe_rg = sanitize_name(rg[:40])
                rg_total = sum(sum(tc.values()) for tc in rg_data[rg].values())
                code_lines.append(f'            with Cluster("RG: {safe_rg}\\n({rg_total} resources)", graph_attr={{"bgcolor": "#FAFAFA", "style": "rounded,bold", "fontsize": "11", "fontname": "Arial Bold", "pencolor": "#333", "penwidth": "1.5"}}):')

                sorted_cats = sorted(rg_data[rg].keys(), key=lambda c: cat_order.index(c) if c in cat_order else 99)
                first_var_in_rg = None
                for cat in sorted_cats:
                    if not rg_data[rg][cat]:
                        continue
                    style = CATEGORY_DISPLAY.get(cat, CATEGORY_DISPLAY["Other"])
                    code_lines.append(f'                with Cluster("{style["label"]}", graph_attr={{"bgcolor": "{style["bgcolor"]}", "style": "rounded,filled", "fontsize": "10"}}):')

                    for entry in node_plan:
                        e_rg, e_cat, e_var, e_cls, e_label = entry
                        if e_rg == rg and e_cat == cat:
                            code_lines.append(f'                    {e_var} = {e_cls}("{e_label}")')
                            if first_var_in_rg is None:
                                first_var_in_rg = e_var

                if first_var_in_rg:
                    rg_anchor_vars.append(first_var_in_rg)

        # Invisible edges to force vertical stacking of RG rows
        if len(rg_anchor_vars) > 1:
            code_lines.append("")
            code_lines.append("    # Force vertical layout between RG rows")
            for i in range(len(rg_anchor_vars) - 1):
                code_lines.append(f'    {rg_anchor_vars[i]} >> Edge(color="transparent", style="invis") >> {rg_anchor_vars[i + 1]}')

        code = "\n".join(code_lines)

        is_valid, errors = validate_code(code)
        if not is_valid:
            return {"error": f"Generated code validation failed: {'; '.join(errors)}", "generated_code": code}

        result = self._execute_and_encode(code, output_path, title, "subscription_overview")
        result["resource_group_count"] = len(rg_data)
        result["resource_count"] = sum(sum(sum(tc.values()) for tc in cats.values()) for cats in rg_data.values())
        return result

    def _execute_and_encode(self, code: str, output_path: str, title: str, pattern: str) -> Dict[str, Any]:
        """Execute diagram code and return base64-encoded PNG."""
        # Write to temp file
        temp_file = os.path.join(self.output_dir, f"gen_{uuid.uuid4().hex[:8]}.py")
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(code)

            env = {
                'PATH': os.environ.get('PATH', ''),
                'PYTHONPATH': os.environ.get('PYTHONPATH', ''),
                'HOME': os.environ.get('HOME', os.environ.get('USERPROFILE', '')),
                'TEMP': os.environ.get('TEMP', ''),
                'TMP': os.environ.get('TMP', ''),
                'USERPROFILE': os.environ.get('USERPROFILE', ''),
                'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''),
                'APPDATA': os.environ.get('APPDATA', ''),
            }

            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=EXECUTION_TIMEOUT,
                env=env,
                cwd=self.output_dir
            )

            if result.returncode != 0:
                return {
                    "error": f"Diagram generation failed: {result.stderr[:500]}",
                    "stdout": result.stdout[:200]
                }

            # Find the output PNG file
            png_path = output_path + ".png"
            if not os.path.exists(png_path):
                # Try to find any PNG in the output dir
                for f in os.listdir(self.output_dir):
                    if f.endswith('.png') and f.startswith('diagram_'):
                        png_path = os.path.join(self.output_dir, f)
                        break

            if not os.path.exists(png_path):
                return {"error": f"Diagram PNG not found at {png_path}. Files: {os.listdir(self.output_dir)}"}

            # Read and encode as base64
            with open(png_path, 'rb') as img_file:
                img_data = img_file.read()

            base64_image = base64.b64encode(img_data).decode('utf-8')
            file_size_kb = len(img_data) / 1024

            # Generate a diagram_id for the image cache
            diagram_id = str(uuid.uuid4())[:8]

            return {
                "success": True,
                "diagram_id": diagram_id,
                "base64_image": base64_image,
                "image_size_kb": round(file_size_kb, 1),
                "title": title,
                "pattern": pattern,
                "format": "png",
                "message": f"Architecture diagram '{title}' generated successfully ({round(file_size_kb, 1)} KB)"
            }

        except subprocess.TimeoutExpired:
            return {"error": f"Diagram generation timed out after {EXECUTION_TIMEOUT} seconds"}
        except Exception as e:
            return {"error": f"Diagram generation failed: {str(e)}"}
        finally:
            # Cleanup temp py file
            try:
                os.unlink(temp_file)
            except:
                pass


# Singleton instance
_diagram_generator = None

def get_diagram_generator() -> AzureDiagramGenerator:
    """Get or create the singleton diagram generator."""
    global _diagram_generator
    if _diagram_generator is None:
        _diagram_generator = AzureDiagramGenerator()
    return _diagram_generator
