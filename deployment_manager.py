"""
Deployment Request Manager with Logic App Integration
Handles resource deployment requests, approval workflows, and execution tracking
"""
import os
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.cosmos import CosmosClient, PartitionKey
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

# Configuration
SERVICE_BUS_CONNECTION = os.getenv("SERVICE_BUS_CONNECTION_STRING")
DEPLOYMENT_QUEUE_NAME = "deployment-requests"
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = "cloudops-agent"
COSMOS_CONTAINER = "deployment-requests"


class DeploymentRequest(BaseModel):
    """Model for deployment request"""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_type: str  # vm, sql, storage, etc.
    resource_name: str
    configuration: Dict[str, Any]
    requester_id: str
    requester_email: str
    requester_name: str
    estimated_cost: float
    status: str = "pending_approval"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    executed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class DeploymentManager:
    """Manages deployment requests and approval workflow"""
    
    def __init__(self):
        self.service_bus_client = None
        self.cosmos_client = None
        self.container = None
        
        # Initialize Service Bus for Logic App trigger
        if SERVICE_BUS_CONNECTION:
            self.service_bus_client = ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION)
        
        # Initialize Cosmos DB for request tracking
        if COSMOS_ENDPOINT and COSMOS_KEY:
            self.cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
            database = self.cosmos_client.create_database_if_not_exists(COSMOS_DATABASE)
            self.container = database.create_container_if_not_exists(
                id=COSMOS_CONTAINER,
                partition_key=PartitionKey(path="/requester_id")
            )
    
    async def submit_deployment_request(
        self,
        resource_type: str,
        resource_name: str,
        configuration: Dict[str, Any],
        user_context: Dict[str, Any],
        estimated_cost: float
    ) -> DeploymentRequest:
        """
        Submit a new deployment request for approval
        
        Args:
            resource_type: Type of resource (vm, sql, storage, etc.)
            resource_name: Name of resource to create
            configuration: Resource configuration details
            user_context: Authenticated user context
            estimated_cost: Estimated monthly cost
            
        Returns:
            DeploymentRequest object with request_id
        """
        # Create deployment request
        request = DeploymentRequest(
            resource_type=resource_type,
            resource_name=resource_name,
            configuration=configuration,
            requester_id=user_context["user_id"],
            requester_email=user_context["email"],
            requester_name=user_context["name"],
            estimated_cost=estimated_cost
        )
        
        # Save to Cosmos DB
        if self.container:
            self.container.create_item(body=request.dict())
            logger.info(f"Saved deployment request {request.request_id} to Cosmos DB")
        
        # Send to Service Bus to trigger Logic App
        if self.service_bus_client:
            await self._send_to_service_bus(request)
            logger.info(f"Sent deployment request {request.request_id} to Service Bus")
        
        return request
    
    async def _send_to_service_bus(self, request: DeploymentRequest):
        """Send deployment request to Service Bus queue"""
        try:
            sender = self.service_bus_client.get_queue_sender(queue_name=DEPLOYMENT_QUEUE_NAME)
            
            message = ServiceBusMessage(
                body=json.dumps(request.dict()),
                content_type="application/json",
                subject=f"Deployment Request: {request.resource_name}",
                message_id=request.request_id,
                correlation_id=request.requester_id
            )
            
            async with sender:
                await sender.send_messages(message)
                
        except Exception as e:
            logger.error(f"Failed to send to Service Bus: {e}")
            raise
    
    def get_request_status(self, request_id: str, requester_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a deployment request
        
        Args:
            request_id: Request ID to check
            requester_id: User ID (for authorization)
            
        Returns:
            Request details or None if not found
        """
        if not self.container:
            return None
        
        try:
            query = f"SELECT * FROM c WHERE c.request_id = '{request_id}'"
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            if items and items[0]["requester_id"] == requester_id:
                return items[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get request status: {e}")
            return None
    
    def update_request_status(
        self,
        request_id: str,
        status: str,
        approved_by: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None
    ):
        """
        Update deployment request status
        Called by Logic App after approval/execution
        
        Args:
            request_id: Request ID to update
            status: New status (approved, rejected, completed, failed)
            approved_by: Email of approver
            result: Execution result
        """
        if not self.container:
            return
        
        try:
            # Get existing request
            query = f"SELECT * FROM c WHERE c.request_id = '{request_id}'"
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            if not items:
                logger.error(f"Request {request_id} not found")
                return
            
            item = items[0]
            item["status"] = status
            
            if status == "approved":
                item["approved_at"] = datetime.utcnow().isoformat()
                item["approved_by"] = approved_by
            elif status in ["completed", "failed"]:
                item["executed_at"] = datetime.utcnow().isoformat()
                item["result"] = result
            
            self.container.upsert_item(body=item)
            logger.info(f"Updated request {request_id} status to {status}")
            
        except Exception as e:
            logger.error(f"Failed to update request status: {e}")
    
    def list_user_requests(
        self,
        user_id: str,
        limit: int = 10
    ) -> list[Dict[str, Any]]:
        """
        List deployment requests for a user
        
        Args:
            user_id: User ID to filter by
            limit: Maximum number of requests to return
            
        Returns:
            List of deployment requests
        """
        if not self.container:
            return []
        
        try:
            query = f"""
                SELECT TOP {limit} * 
                FROM c 
                WHERE c.requester_id = '{user_id}' 
                ORDER BY c.created_at DESC
            """
            
            items = list(self.container.query_items(
                query=query,
                partition_key=user_id
            ))
            
            return items
            
        except Exception as e:
            logger.error(f"Failed to list user requests: {e}")
            return []


# Global instance
_deployment_manager: Optional[DeploymentManager] = None


def get_deployment_manager() -> DeploymentManager:
    """Get or create global DeploymentManager instance"""
    global _deployment_manager
    if _deployment_manager is None:
        _deployment_manager = DeploymentManager()
    return _deployment_manager
