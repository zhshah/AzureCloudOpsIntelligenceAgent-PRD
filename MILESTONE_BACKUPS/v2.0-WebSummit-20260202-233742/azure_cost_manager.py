"""
Azure Cost Management API Integration
Handles all cost-related queries using Azure Cost Management API
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import QueryDefinition, QueryTimePeriod, TimeframeType, QueryDataset, QueryAggregation, QueryGrouping
import json


class AzureCostManager:
    def __init__(self):
        """Initialize Azure Cost Management client"""
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        
        # Use Managed Identity if in production, otherwise use credentials
        use_managed_identity = os.getenv("USE_MANAGED_IDENTITY", "false").lower() == "true"
        
        if use_managed_identity:
            self.credential = DefaultAzureCredential()
        else:
            self.credential = DefaultAzureCredential()
        
        self.client = CostManagementClient(self.credential)
        
    def get_current_month_costs(self, scope: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current month's costs
        
        Args:
            scope: Azure scope (subscription, resource group, or resource)
        """
        try:
            if not scope:
                scope = f"/subscriptions/{self.subscription_id}"
            
            # Define query for current month
            now = datetime.utcnow()
            start_date = now.replace(day=1)
            end_date = now
            
            query = QueryDefinition(
                type="Usage",
                timeframe=TimeframeType.CUSTOM,
                time_period=QueryTimePeriod(
                    from_property=start_date,
                    to=end_date
                ),
                dataset=QueryDataset(
                    granularity="Daily",
                    aggregation={
                        "totalCost": QueryAggregation(name="Cost", function="Sum")
                    }
                )
            )
            
            result = self.client.query.usage(scope=scope, parameters=query)
            return self._format_cost_result(result)
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_costs_by_service(self, scope: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """
        Get costs grouped by Azure service
        
        Args:
            scope: Azure scope
            days: Number of days to look back
        """
        try:
            if not scope:
                scope = f"/subscriptions/{self.subscription_id}"
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            query = QueryDefinition(
                type="Usage",
                timeframe=TimeframeType.CUSTOM,
                time_period=QueryTimePeriod(
                    from_property=start_date,
                    to=end_date
                ),
                dataset=QueryDataset(
                    granularity="None",
                    aggregation={
                        "totalCost": QueryAggregation(name="Cost", function="Sum")
                    },
                    grouping=[
                        QueryGrouping(type="Dimension", name="ServiceName")
                    ]
                )
            )
            
            result = self.client.query.usage(scope=scope, parameters=query)
            return self._format_service_cost_result(result)
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_daily_costs(self, scope: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """
        Get daily cost trends
        
        Args:
            scope: Azure scope
            days: Number of days to look back
        """
        try:
            if not scope:
                scope = f"/subscriptions/{self.subscription_id}"
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            query = QueryDefinition(
                type="Usage",
                timeframe=TimeframeType.CUSTOM,
                time_period=QueryTimePeriod(
                    from_property=start_date,
                    to=end_date
                ),
                dataset=QueryDataset(
                    granularity="Daily",
                    aggregation={
                        "totalCost": QueryAggregation(name="Cost", function="Sum")
                    }
                )
            )
            
            result = self.client.query.usage(scope=scope, parameters=query)
            return self._format_daily_cost_result(result)
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_costs_by_resource_group(self, scope: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """
        Get costs grouped by resource group
        
        Args:
            scope: Azure scope
            days: Number of days to look back
        """
        try:
            if not scope:
                scope = f"/subscriptions/{self.subscription_id}"
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            query = QueryDefinition(
                type="Usage",
                timeframe=TimeframeType.CUSTOM,
                time_period=QueryTimePeriod(
                    from_property=start_date,
                    to=end_date
                ),
                dataset=QueryDataset(
                    granularity="None",
                    aggregation={
                        "totalCost": QueryAggregation(name="Cost", function="Sum")
                    },
                    grouping=[
                        QueryGrouping(type="Dimension", name="ResourceGroupName")
                    ]
                )
            )
            
            result = self.client.query.usage(scope=scope, parameters=query)
            return self._format_resource_group_cost_result(result)
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_resource_costs(self, scope: Optional[str] = None, days: int = 30, top: int = 10) -> Dict[str, Any]:
        """
        Get costs for individual resources (top N most expensive)
        
        Args:
            scope: Azure scope
            days: Number of days to look back
            top: Number of top resources to return
        """
        try:
            if not scope:
                scope = f"/subscriptions/{self.subscription_id}"
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            query = QueryDefinition(
                type="Usage",
                timeframe=TimeframeType.CUSTOM,
                time_period=QueryTimePeriod(
                    from_property=start_date,
                    to=end_date
                ),
                dataset=QueryDataset(
                    granularity="None",
                    aggregation={
                        "totalCost": QueryAggregation(name="Cost", function="Sum")
                    },
                    grouping=[
                        QueryGrouping(type="Dimension", name="ResourceId")
                    ]
                )
            )
            
            result = self.client.query.usage(scope=scope, parameters=query)
            return self._format_resource_cost_result(result, top)
            
        except Exception as e:
            return {"error": str(e)}
    
    def _format_cost_result(self, result) -> Dict[str, Any]:
        """Format cost query result"""
        try:
            total_cost = 0.0
            daily_costs = []
            
            if hasattr(result, 'rows') and result.rows:
                for row in result.rows:
                    cost = float(row[0]) if row and len(row) > 0 else 0.0
                    total_cost += cost
                    if len(row) > 1:
                        daily_costs.append({
                            "date": str(row[1]),
                            "cost": cost
                        })
            
            return {
                "total_cost": round(total_cost, 2),
                "currency": "USD",
                "daily_breakdown": daily_costs
            }
        except Exception as e:
            return {"error": f"Failed to format result: {str(e)}"}
    
    def _format_service_cost_result(self, result) -> Dict[str, Any]:
        """Format service cost result"""
        try:
            services = []
            total_cost = 0.0
            
            if hasattr(result, 'rows') and result.rows:
                for row in result.rows:
                    cost = float(row[0]) if row and len(row) > 0 else 0.0
                    service_name = str(row[1]) if len(row) > 1 else "Unknown"
                    total_cost += cost
                    services.append({
                        "service": service_name,
                        "cost": round(cost, 2)
                    })
            
            # Sort by cost descending
            services.sort(key=lambda x: x["cost"], reverse=True)
            
            return {
                "total_cost": round(total_cost, 2),
                "currency": "USD",
                "services": services
            }
        except Exception as e:
            return {"error": f"Failed to format result: {str(e)}"}
    
    def _format_daily_cost_result(self, result) -> Dict[str, Any]:
        """Format daily cost result"""
        try:
            daily_costs = []
            total_cost = 0.0
            
            if hasattr(result, 'rows') and result.rows:
                for row in result.rows:
                    cost = float(row[0]) if row and len(row) > 0 else 0.0
                    date = str(row[1]) if len(row) > 1 else ""
                    total_cost += cost
                    daily_costs.append({
                        "date": date,
                        "cost": round(cost, 2)
                    })
            
            return {
                "total_cost": round(total_cost, 2),
                "currency": "USD",
                "daily_costs": daily_costs
            }
        except Exception as e:
            return {"error": f"Failed to format result: {str(e)}"}
    
    def _format_resource_group_cost_result(self, result) -> Dict[str, Any]:
        """Format resource group cost result"""
        try:
            resource_groups = []
            total_cost = 0.0
            
            if hasattr(result, 'rows') and result.rows:
                for row in result.rows:
                    cost = float(row[0]) if row and len(row) > 0 else 0.0
                    rg_name = str(row[1]) if len(row) > 1 else "Unknown"
                    total_cost += cost
                    resource_groups.append({
                        "resource_group": rg_name,
                        "cost": round(cost, 2)
                    })
            
            # Sort by cost descending
            resource_groups.sort(key=lambda x: x["cost"], reverse=True)
            
            return {
                "total_cost": round(total_cost, 2),
                "currency": "USD",
                "resource_groups": resource_groups
            }
        except Exception as e:
            return {"error": f"Failed to format result: {str(e)}"}
    
    def _format_resource_cost_result(self, result, top: int) -> Dict[str, Any]:
        """Format resource cost result"""
        try:
            resources = []
            total_cost = 0.0
            
            if hasattr(result, 'rows') and result.rows:
                for row in result.rows:
                    cost = float(row[0]) if row and len(row) > 0 else 0.0
                    resource_id = str(row[1]) if len(row) > 1 else "Unknown"
                    total_cost += cost
                    
                    # Extract resource name from ID
                    resource_name = resource_id.split('/')[-1] if '/' in resource_id else resource_id
                    
                    resources.append({
                        "resource_name": resource_name,
                        "resource_id": resource_id,
                        "cost": round(cost, 2)
                    })
            
            # Sort by cost descending and take top N
            resources.sort(key=lambda x: x["cost"], reverse=True)
            top_resources = resources[:top]
            
            return {
                "total_cost": round(total_cost, 2),
                "currency": "USD",
                "top_resources": top_resources,
                "count": len(top_resources)
            }
        except Exception as e:
            return {"error": f"Failed to format result: {str(e)}"}
