"""
Quick test script to verify tag filtering is working
"""
from azure_resource_manager import AzureResourceManager

# Initialize manager
manager = AzureResourceManager()

print("=" * 80)
print("Testing Tag Filtering")
print("=" * 80)

# Test 1: Get all resources with CostCenter tag (any value)
print("\n1. Testing: Resources with 'CostCenter' tag (any value)")
result1 = manager.get_resources_by_tag("CostCenter")
if result1 and 'data' in result1:
    print(f"   Found {len(result1['data'])} resources with CostCenter tag")
    if result1['data']:
        print(f"   Sample: {result1['data'][0]['ResourceName']}")
        print(f"   Tags: {result1['data'][0].get('Tags', {})}")
else:
    print("   ERROR or NO RESULTS")
    print(f"   Response: {result1}")

# Test 2: Get resources with CostCenter=IT
print("\n2. Testing: Resources with 'CostCenter' = 'IT'")
result2 = manager.get_resources_by_tag("CostCenter", "IT")
if result2 and 'data' in result2:
    print(f"   Found {len(result2['data'])} resources")
    if result2['data']:
        for i, res in enumerate(result2['data'][:3]):  # Show first 3
            print(f"   {i+1}. {res['ResourceName']} - Tags: {res.get('Tags', {})}")
else:
    print("   ERROR or NO RESULTS")
    print(f"   Response: {result2}")

# Test 3: Get resources with CostCenter=Finance Department
print("\n3. Testing: Resources with 'CostCenter' = 'Finance Department'")
result3 = manager.get_resources_by_tag("CostCenter", "Finance Department")
if result3 and 'data' in result3:
    print(f"   Found {len(result3['data'])} resources")
    if result3['data']:
        for i, res in enumerate(result3['data'][:3]):  # Show first 3
            print(f"   {i+1}. {res['ResourceName']} - Tags: {res.get('Tags', {})}")
else:
    print("   ERROR or NO RESULTS")
    print(f"   Response: {result3}")

# Test 4: List all unique tag names in subscription
print("\n4. Testing: Get all unique tags in subscription")
query_all_tags = """
Resources
| project tags
| mvexpand bagexpansion=array tags
| project key=tostring(bag_keys(tags)[0])
| distinct key
| order by key asc
"""
result4 = manager.query_resources(query_all_tags)
if result4 and 'data' in result4:
    print(f"   Found {len(result4['data'])} unique tag names:")
    for tag in result4['data'][:20]:  # Show first 20
        print(f"   - {tag.get('key', 'N/A')}")
else:
    print("   ERROR")

print("\n" + "=" * 80)
print("Test Complete")
print("=" * 80)
