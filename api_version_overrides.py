# API Version Override Mapping
# Maps resource types to their correct API versions
# This is a pragmatic solution until we can reliably get AI to use correct versions

API_VERSION_OVERRIDES = {
    "Microsoft.Compute/availabilitySets": "2025-04-01",
    "Microsoft.Storage/storageAccounts": "2023-05-01",
    "Microsoft.Network/virtualNetworks": "2024-05-01",
    "Microsoft.Network/networkInterfaces": "2024-05-01",
    "Microsoft.Network/publicIPAddresses": "2024-05-01",
    "Microsoft.Network/networkSecurityGroups": "2024-05-01",
    "Microsoft.Compute/virtualMachines": "2025-04-01",
    "Microsoft.Resources/resourceGroups": "2024-03-01",
}

def get_correct_api_version(resource_type: str) -> str:
    """
    Get the correct API version for a resource type
    Returns override if available, otherwise returns latest known version
    """
    return API_VERSION_OVERRIDES.get(resource_type, "2024-01-01")
