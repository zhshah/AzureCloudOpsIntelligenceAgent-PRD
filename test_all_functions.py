"""
Comprehensive Test Suite for Azure CloudOps Intelligence Agent
Tests all functions across all categories to ensure proper operation
"""

import os
import sys
import json
from datetime import datetime

# Set subscription ID for testing
os.environ['AZURE_SUBSCRIPTION_ID'] = os.environ.get('AZURE_SUBSCRIPTION_ID', '')

from azure_resource_manager import AzureResourceManager
from entra_id_manager import EntraIDManager

def test_function(obj, func_name, desc):
    """Test a single function and return results"""
    try:
        func = getattr(obj, func_name)
        result = func()
        count = result.get('count', result.get('total_records', 0))
        data_len = len(result.get('data', []))
        error = result.get('error')
        
        if error:
            return ('FAIL', desc, f"Error: {str(error)[:60]}", count)
        elif count == 0 and data_len == 0:
            return ('WARN', desc, "No data returned (may be expected)", count)
        else:
            # Validate data structure
            data = result.get('data', [])
            if data and isinstance(data, list) and len(data) > 0:
                first_item = data[0]
                if isinstance(first_item, dict):
                    keys = list(first_item.keys())
                    return ('PASS', desc, f"Fields: {', '.join(keys[:4])}...", count)
            return ('PASS', desc, f"Count: {count}", count)
    except Exception as e:
        return ('FAIL', desc, f"Exception: {str(e)[:60]}", 0)


def run_all_tests():
    """Run all tests and generate report"""
    print("=" * 80)
    print("COMPREHENSIVE TEST SUITE - Azure CloudOps Intelligence Agent")
    print(f"Test Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    rm = AzureResourceManager()
    em = EntraIDManager()
    
    results = []
    
    # =====================================================
    # CATEGORY 1: RESOURCE MANAGEMENT
    # =====================================================
    print("\n" + "=" * 60)
    print("CATEGORY 1: RESOURCE MANAGEMENT")
    print("=" * 60)
    
    resource_tests = [
        ('get_all_resources_detailed', 'All Resources Detailed'),
        ('get_resource_count_by_type', 'Resource Count by Type'),
        ('get_all_vms', 'All Virtual Machines'),
        ('get_storage_accounts', 'Storage Accounts (basic)'),
        ('get_all_databases', 'All Databases'),
        ('get_all_vnets', 'All Virtual Networks'),
        ('get_resources_without_tags', 'Resources Without Tags'),
        ('get_unused_resources', 'Unused Resources'),
        ('get_tag_compliance_summary', 'Tag Compliance Summary'),
        ('get_multi_region_distribution', 'Multi Region Distribution'),
    ]
    
    for func_name, desc in resource_tests:
        status, name, msg, cnt = test_function(rm, func_name, desc)
        results.append((status, 'Resource Management', name, msg, cnt))
        print(f"  [{status}] {name}: {msg}")
    
    # =====================================================
    # CATEGORY 2: STORAGE ACCOUNTS
    # =====================================================
    print("\n" + "=" * 60)
    print("CATEGORY 2: STORAGE ACCOUNTS")
    print("=" * 60)
    
    storage_tests = [
        ('get_storage_accounts_detailed', 'Storage Accounts Detailed'),
        ('get_storage_accounts_public_access', 'Storage Public Access'),
        ('get_storage_accounts_with_private_endpoints_detailed', 'Storage Private Endpoints'),
        ('get_storage_accounts_empty', 'Empty Storage Accounts'),
        ('get_storage_accounts_unused', 'Unused Storage Accounts'),
        ('get_storage_accounts_capacity', 'Storage Capacity'),
        ('get_file_shares', 'File Shares'),
        ('get_file_shares_with_ad_auth', 'File Shares with AD Auth'),
        ('get_storage_accounts_with_lifecycle_policy', 'Storage Lifecycle Policies'),
        ('get_storage_cost_optimization', 'Storage Cost Optimization'),
    ]
    
    for func_name, desc in storage_tests:
        status, name, msg, cnt = test_function(rm, func_name, desc)
        results.append((status, 'Storage Accounts', name, msg, cnt))
        print(f"  [{status}] {name}: {msg}")
    
    # =====================================================
    # CATEGORY 3: AZURE BACKUP
    # =====================================================
    print("\n" + "=" * 60)
    print("CATEGORY 3: AZURE BACKUP")
    print("=" * 60)
    
    backup_tests = [
        ('get_vms_with_backup', 'VMs with Backup'),
        ('get_vms_without_backup', 'VMs without Backup'),
        ('get_file_shares_with_backup', 'File Shares with Backup'),
        ('get_file_shares_without_backup', 'File Shares without Backup'),
        ('get_managed_disks_with_backup', 'Managed Disks with Backup'),
        ('get_managed_disks_without_backup', 'Managed Disks without Backup'),
        ('get_shared_disks', 'Shared Disks'),
        ('get_storage_blobs_with_backup', 'Blob Backup'),
        ('get_sql_databases_with_backup', 'SQL Database Backup'),
        ('get_sql_managed_instance_with_backup', 'SQL MI Backup'),
        ('get_backup_vaults_summary', 'Backup Vaults Summary'),
        ('get_backup_jobs_failed', 'Failed Backup Jobs'),
    ]
    
    for func_name, desc in backup_tests:
        status, name, msg, cnt = test_function(rm, func_name, desc)
        results.append((status, 'Azure Backup', name, msg, cnt))
        print(f"  [{status}] {name}: {msg}")
    
    # =====================================================
    # CATEGORY 4: ENTRA ID (AZURE AD)
    # =====================================================
    print("\n" + "=" * 60)
    print("CATEGORY 4: ENTRA ID (AZURE AD)")
    print("=" * 60)
    
    entra_tests = [
        ('get_entra_id_overview', 'Entra ID Overview'),
        ('get_users_not_signed_in_30_days', 'Users Inactive 30+ Days'),
        ('get_users_sync_stopped', 'Users Sync Stopped'),
        ('get_orphaned_guest_accounts', 'Orphaned Guest Accounts'),
        ('get_privileged_role_users', 'Privileged Role Users'),
        ('get_global_admins', 'Global Administrators'),
        ('get_custom_roles', 'Custom Roles'),
        ('get_unused_applications', 'Unused Applications'),
        ('get_devices', 'All Devices'),
        ('get_stale_devices', 'Stale Devices'),
        ('get_app_registrations', 'App Registrations'),
        ('get_enterprise_apps', 'Enterprise Applications'),
        ('get_groups', 'All Groups'),
        ('get_empty_groups', 'Empty Groups'),
        ('get_conditional_access_policies', 'Conditional Access Policies'),
        ('get_conditional_access_policies_disabled', 'Disabled CA Policies'),
        ('get_conditional_access_without_mfa', 'CA Policies without MFA'),
    ]
    
    for func_name, desc in entra_tests:
        status, name, msg, cnt = test_function(em, func_name, desc)
        results.append((status, 'Entra ID', name, msg, cnt))
        print(f"  [{status}] {name}: {msg}")
    
    # =====================================================
    # CATEGORY 5: SECURITY & COMPLIANCE
    # =====================================================
    print("\n" + "=" * 60)
    print("CATEGORY 5: SECURITY & COMPLIANCE")
    print("=" * 60)
    
    security_tests = [
        ('get_paas_without_private_endpoints', 'PaaS without Private Endpoints'),
        ('get_resources_with_public_access', 'Resources with Public Access'),
        ('get_policy_compliance_status', 'Policy Compliance Status'),
        ('get_non_compliant_resources', 'Non-Compliant Resources'),
        ('get_policy_recommendations', 'Policy Recommendations'),
        ('get_policy_exemptions', 'Policy Exemptions'),
    ]
    
    for func_name, desc in security_tests:
        status, name, msg, cnt = test_function(rm, func_name, desc)
        results.append((status, 'Security', name, msg, cnt))
        print(f"  [{status}] {name}: {msg}")
    
    # =====================================================
    # CATEGORY 6: UPDATE MANAGEMENT
    # =====================================================
    print("\n" + "=" * 60)
    print("CATEGORY 6: UPDATE MANAGEMENT")
    print("=" * 60)
    
    update_tests = [
        ('get_vm_pending_updates', 'VMs Pending Updates'),
        ('get_arc_pending_updates', 'Arc Pending Updates'),
        ('get_vm_pending_reboot', 'VMs Pending Reboot'),
        ('get_arc_pending_reboot', 'Arc Pending Reboot'),
        ('get_update_compliance_summary', 'Update Compliance Summary'),
        ('get_failed_updates', 'Failed Updates'),
    ]
    
    for func_name, desc in update_tests:
        status, name, msg, cnt = test_function(rm, func_name, desc)
        results.append((status, 'Update Management', name, msg, cnt))
        print(f"  [{status}] {name}: {msg}")
    
    # =====================================================
    # CATEGORY 7: AZURE ARC
    # =====================================================
    print("\n" + "=" * 60)
    print("CATEGORY 7: AZURE ARC")
    print("=" * 60)
    
    arc_tests = [
        ('get_arc_machines', 'Arc Machines'),
        ('get_arc_sql_servers', 'Arc SQL Servers'),
        ('get_arc_agents_not_reporting', 'Arc Agents Not Reporting'),
    ]
    
    for func_name, desc in arc_tests:
        status, name, msg, cnt = test_function(rm, func_name, desc)
        results.append((status, 'Azure Arc', name, msg, cnt))
        print(f"  [{status}] {name}: {msg}")
    
    # =====================================================
    # CATEGORY 8: APP SERVICES
    # =====================================================
    print("\n" + "=" * 60)
    print("CATEGORY 8: APP SERVICES")
    print("=" * 60)
    
    app_tests = [
        ('get_app_services_detailed', 'App Services Detailed'),
        ('get_app_services_without_appinsights', 'App Services without App Insights'),
        ('get_app_services_public_access', 'App Services Public Access'),
    ]
    
    for func_name, desc in app_tests:
        status, name, msg, cnt = test_function(rm, func_name, desc)
        results.append((status, 'App Services', name, msg, cnt))
        print(f"  [{status}] {name}: {msg}")
    
    # =====================================================
    # CATEGORY 9: AKS
    # =====================================================
    print("\n" + "=" * 60)
    print("CATEGORY 9: AKS (KUBERNETES)")
    print("=" * 60)
    
    aks_tests = [
        ('get_aks_clusters', 'AKS Clusters'),
        ('get_aks_public_access', 'AKS Public Access'),
        ('get_aks_private_access', 'AKS Private Access'),
        ('get_aks_without_monitoring', 'AKS without Monitoring'),
    ]
    
    for func_name, desc in aks_tests:
        status, name, msg, cnt = test_function(rm, func_name, desc)
        results.append((status, 'AKS', name, msg, cnt))
        print(f"  [{status}] {name}: {msg}")
    
    # =====================================================
    # CATEGORY 10: SQL DATABASES
    # =====================================================
    print("\n" + "=" * 60)
    print("CATEGORY 10: SQL DATABASES")
    print("=" * 60)
    
    sql_tests = [
        ('get_sql_databases_detailed', 'SQL Databases Detailed'),
        ('get_sql_managed_instances', 'SQL Managed Instances'),
        ('get_sql_public_access', 'SQL Public Access'),
        ('get_postgresql_servers', 'PostgreSQL Servers'),
        ('get_postgresql_public_access', 'PostgreSQL Public Access'),
        ('get_mysql_servers', 'MySQL Servers'),
        ('get_mysql_public_access', 'MySQL Public Access'),
        ('get_cosmosdb_accounts', 'CosmosDB Accounts'),
        ('get_cosmosdb_public_access', 'CosmosDB Public Access'),
    ]
    
    for func_name, desc in sql_tests:
        status, name, msg, cnt = test_function(rm, func_name, desc)
        results.append((status, 'SQL/Databases', name, msg, cnt))
        print(f"  [{status}] {name}: {msg}")
    
    # =====================================================
    # CATEGORY 11: MONITORING
    # =====================================================
    print("\n" + "=" * 60)
    print("CATEGORY 11: MONITORING")
    print("=" * 60)
    
    monitoring_tests = [
        ('get_vms_without_azure_monitor', 'VMs without Azure Monitor'),
        ('get_arc_machines_without_azure_monitor', 'Arc without Azure Monitor'),
        ('get_tag_inventory', 'Tag Inventory'),
        ('get_apim_instances', 'API Management Instances'),
        ('get_vmss', 'VM Scale Sets'),
    ]
    
    for func_name, desc in monitoring_tests:
        status, name, msg, cnt = test_function(rm, func_name, desc)
        results.append((status, 'Monitoring', name, msg, cnt))
        print(f"  [{status}] {name}: {msg}")
    
    # =====================================================
    # SUMMARY
    # =====================================================
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in results if r[0] == 'PASS')
    warned = sum(1 for r in results if r[0] == 'WARN')
    failed = sum(1 for r in results if r[0] == 'FAIL')
    total = len(results)
    
    print(f"\nTotal Tests: {total}")
    print(f"  PASSED: {passed} ({100*passed/total:.1f}%)")
    print(f"  WARNED: {warned} ({100*warned/total:.1f}%)")
    print(f"  FAILED: {failed} ({100*failed/total:.1f}%)")
    
    if failed > 0:
        print("\n" + "-" * 60)
        print("FAILED TESTS:")
        print("-" * 60)
        for status, cat, name, msg, cnt in results:
            if status == 'FAIL':
                print(f"  [{cat}] {name}: {msg}")
    
    # Return results for further analysis
    return results


if __name__ == "__main__":
    results = run_all_tests()
