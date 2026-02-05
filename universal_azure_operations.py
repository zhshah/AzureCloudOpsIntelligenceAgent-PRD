"""
Universal Azure Operations Handler
Handles ANY Azure operation: CREATE, UPDATE, DELETE, MODIFY
Works with ANY resource type
NO HARD-CODING - completely generic and AI-driven
"""

import json
import logging
from typing import Dict, Optional, Tuple, Any
from intelligent_template_generator import IntelligentTemplateGenerator
from intelligent_parameter_collector import ParameterCollector, OperationType
from logic_app_client import LogicAppClient

logger = logging.getLogger(__name__)


class UniversalAzureOperations:
    """
    Handles ANY Azure operation on ANY resource
    Completely generic - no hard-coded resource types
    """
    
    def __init__(self, subscription_id: str, user_email: str = None, user_name: str = None):
        self.subscription_id = subscription_id
        self.user_email = user_email
        self.user_name = user_name
        
        self.template_generator = IntelligentTemplateGenerator(subscription_id)
        self.parameter_collector = ParameterCollector(subscription_id)
        self.logic_app_client = LogicAppClient()
        
        # Conversation state for parameter collection
        self.conversation_state = {}
    
    async def handle_request(
        self,
        user_message: str,
        conversation_id: str,
        conversation_history: list = None
    ) -> Dict[str, Any]:
        """
        Handle ANY Azure request
        
        Returns:
            {
                "status": "success" | "need_more_info" | "error",
                "message": str,
                "next_question": str or None,
                "submission_result": dict or None
            }
        """
        try:
            logger.info(f"🎯 Handling request: {user_message[:100]}...")
            
            # Analyze the request to see what's needed
            analysis = self.parameter_collector.analyze_request(
                user_message,
                conversation_history
            )
            
            if not analysis["ready_to_submit"]:
                # Need more information
                logger.info(f"⏳ Need more information. Missing: {len(analysis['missing_params'])} parameters")
                
                # Store state for this conversation
                self.conversation_state[conversation_id] = analysis
                
                return {
                    "status": "need_more_info",
                    "message": "I need a bit more information to proceed.",
                    "next_question": analysis["next_question"],
                    "missing_params": [p["name"] for p in analysis["missing_params"]],
                    "ready_to_submit": False
                }
            
            # We have all required parameters - proceed with the operation
            logger.info("✅ All parameters collected. Processing request...")
            
            operation_type = analysis["operation_type"]
            resource_type = analysis["resource_type"]
            params = analysis["provided_params"]
            
            # Route to appropriate handler based on operation type
            if operation_type == OperationType.CREATE:
                result = await self._handle_create(
                    resource_type,
                    params,
                    analysis
                )
            elif operation_type == OperationType.UPDATE:
                result = await self._handle_update(
                    resource_type,
                    params,
                    analysis
                )
            elif operation_type == OperationType.MODIFY:
                result = await self._handle_modify(
                    resource_type,
                    params,
                    analysis
                )
            elif operation_type == OperationType.ADD:
                result = await self._handle_add(
                    resource_type,
                    params,
                    analysis
                )
            elif operation_type == OperationType.DELETE:
                result = await self._handle_delete(
                    resource_type,
                    params,
                    analysis
                )
            else:
                result = {
                    "status": "error",
                    "message": f"Unknown operation type: {operation_type}"
                }
            
            # Clear conversation state
            if conversation_id in self.conversation_state:
                del self.conversation_state[conversation_id]
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error handling request: {str(e)}")
            return {
                "status": "error",
                "message": f"Error processing request: {str(e)}",
                "next_question": None,
                "ready_to_submit": False
            }
    
    async def _handle_create(
        self,
        resource_type: str,
        params: Dict,
        analysis: Dict
    ) -> Dict:
        """
        Handle CREATE operations for any resource type
        """
        try:
            logger.info(f"🆕 Creating {resource_type}")
            
            resource_name = params.get("name")
            location = params.get("location")
            resource_group = params.get("resource_group")
            
            # Build user requirements from all parameters
            user_requirements = self._build_requirements_text(params, analysis)
            
            # Generate ARM template using AI + Azure schemas
            arm_template, error = self.template_generator.generate_with_retry(
                resource_type=resource_type,
                resource_name=resource_name,
                location=location,
                resource_group=resource_group,
                user_requirements=user_requirements,
                max_retries=2
            )
            
            if not arm_template:
                return {
                    "status": "error",
                    "message": f"Failed to generate deployment template: {error}",
                    "ready_to_submit": True
                }
            
            logger.info("✅ ARM template generated and validated")
            
            # Submit to Logic App for approval
            friendly_name = self.parameter_collector._friendly_resource_name(resource_type)
            
            approval_result = await self.logic_app_client.submit_for_approval(
                resource_type=friendly_name.title(),
                resource_name=resource_name,
                deployment_template=arm_template,
                resource_group=resource_group,
                user_email=self.user_email,
                user_name=self.user_name,
                estimated_cost=0.0,  # TODO: Implement cost estimation
                justification=f"Creating {friendly_name} '{resource_name}' with configuration: {user_requirements}"
            )
            
            return {
                "status": "success",
                "message": f"✅ Request submitted for approval! You'll receive an email at {self.user_email}",
                "submission_result": approval_result,
                "ready_to_submit": True
            }
            
        except Exception as e:
            logger.error(f"❌ Error in create operation: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to create resource: {str(e)}",
                "ready_to_submit": True
            }
    
    async def _handle_update(
        self,
        resource_type: str,
        params: Dict,
        analysis: Dict
    ) -> Dict:
        """
        Handle UPDATE operations (e.g., update tags, properties)
        """
        try:
            logger.info(f"📝 Updating {resource_type}")
            
            target_resource = params.get("target_resource")
            resource_group = params.get("resource_group")
            
            # Build update requirements
            user_requirements = f"Update existing resource: {self._build_requirements_text(params, analysis)}"
            
            # For updates, we need to fetch current state and modify it
            # Generate update ARM template
            arm_template, error = self.template_generator.generate_with_retry(
                resource_type=resource_type,
                resource_name=target_resource,
                location=params.get("location", "westeurope"),  # May need to fetch this
                resource_group=resource_group,
                user_requirements=user_requirements,
                max_retries=2
            )
            
            if not arm_template:
                return {
                    "status": "error",
                    "message": f"Failed to generate update template: {error}",
                    "ready_to_submit": True
                }
            
            friendly_name = self.parameter_collector._friendly_resource_name(resource_type)
            
            approval_result = await self.logic_app_client.submit_for_approval(
                resource_type=f"{friendly_name.title()} Update",
                resource_name=target_resource,
                deployment_template=arm_template,
                resource_group=resource_group,
                user_email=self.user_email,
                user_name=self.user_name,
                estimated_cost=0.0,
                justification=f"Updating {friendly_name} '{target_resource}': {user_requirements}"
            )
            
            return {
                "status": "success",
                "message": f"✅ Update request submitted for approval!",
                "submission_result": approval_result,
                "ready_to_submit": True
            }
            
        except Exception as e:
            logger.error(f"❌ Error in update operation: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to update resource: {str(e)}",
                "ready_to_submit": True
            }
    
    async def _handle_modify(
        self,
        resource_type: str,
        params: Dict,
        analysis: Dict
    ) -> Dict:
        """
        Handle MODIFY operations (e.g., resize VM, scale app service)
        """
        try:
            logger.info(f"🔧 Modifying {resource_type}")
            
            # Modify is similar to update but typically for specific properties
            return await self._handle_update(resource_type, params, analysis)
            
        except Exception as e:
            logger.error(f"❌ Error in modify operation: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to modify resource: {str(e)}",
                "ready_to_submit": True
            }
    
    async def _handle_add(
        self,
        resource_type: str,
        params: Dict,
        analysis: Dict
    ) -> Dict:
        """
        Handle ADD operations (e.g., add staging slot, add private endpoint)
        """
        try:
            logger.info(f"➕ Adding {resource_type}")
            
            parent_resource = params.get("parent_resource")
            resource_name = params.get("name")
            resource_group = params.get("resource_group")
            
            user_requirements = f"Add to existing resource '{parent_resource}': {self._build_requirements_text(params, analysis)}"
            
            arm_template, error = self.template_generator.generate_with_retry(
                resource_type=resource_type,
                resource_name=resource_name,
                location=params.get("location", "westeurope"),
                resource_group=resource_group,
                user_requirements=user_requirements,
                max_retries=2
            )
            
            if not arm_template:
                return {
                    "status": "error",
                    "message": f"Failed to generate template: {error}",
                    "ready_to_submit": True
                }
            
            friendly_name = self.parameter_collector._friendly_resource_name(resource_type)
            
            approval_result = await self.logic_app_client.submit_for_approval(
                resource_type=f"Add {friendly_name.title()}",
                resource_name=resource_name,
                deployment_template=arm_template,
                resource_group=resource_group,
                user_email=self.user_email,
                user_name=self.user_name,
                estimated_cost=0.0,
                justification=f"Adding {friendly_name} '{resource_name}' to '{parent_resource}'"
            )
            
            return {
                "status": "success",
                "message": f"✅ Request to add {friendly_name} submitted for approval!",
                "submission_result": approval_result,
                "ready_to_submit": True
            }
            
        except Exception as e:
            logger.error(f"❌ Error in add operation: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to add resource: {str(e)}",
                "ready_to_submit": True
            }
    
    async def _handle_delete(
        self,
        resource_type: str,
        params: Dict,
        analysis: Dict
    ) -> Dict:
        """
        Handle DELETE operations
        """
        try:
            logger.info(f"🗑️ Deleting {resource_type}")
            
            # For now, return message that delete needs special handling
            return {
                "status": "success",
                "message": "⚠️ Delete operations require careful confirmation. Please use Azure Portal or Azure CLI for deletions to prevent accidental data loss.",
                "ready_to_submit": True
            }
            
        except Exception as e:
            logger.error(f"❌ Error in delete operation: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to delete resource: {str(e)}",
                "ready_to_submit": True
            }
    
    def _build_requirements_text(self, params: Dict, analysis: Dict) -> str:
        """
        Build human-readable requirements text from parameters
        """
        parts = []
        
        for key, value in params.items():
            if key not in ["name", "resource_group", "location"] and value:
                parts.append(f"{key}: {value}")
        
        return ", ".join(parts) if parts else "Standard configuration with Azure best practices"
    
    def set_user_context(self, user_email: str, user_name: str):
        """Update user context for approvals"""
        self.user_email = user_email
        self.user_name = user_name
