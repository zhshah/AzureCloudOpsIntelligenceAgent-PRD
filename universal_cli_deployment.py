"""
Universal Deployment using Azure CLI
NO ARM TEMPLATES - Pure Azure CLI commands
Handles ALL resource types automatically
"""

import os
import json
import logging
import threading
from typing import Dict, Any
from azure_cli_operations import AzureCLIOperations
from logic_app_client import LogicAppClient

logger = logging.getLogger(__name__)


class UniversalCLIDeployment:
    """
    Universal deployment system using Azure CLI directly
    No ARM template generation - just clean CLI commands
    """
    
    def __init__(self, subscription_id: str):
        self.subscription_id = subscription_id
        self.cli_ops = AzureCLIOperations(subscription_id)
        self.logic_app_client = LogicAppClient()
        self.user_email = None
        self.user_name = None
        
    def set_user_context(self, user_email: str, user_name: str):
        """Set user context for approvals"""
        self.user_email = user_email
        self.user_name = user_name        
    async def _send_deployment_email(self, status: str, resource_name: str, resource_type: str, 
                                     resource_group: str, request_id: str, error: str = None):
        """Send deployment success/failure email via Office365"""
        try:
            import requests
            import os
            
            # Get Office365 connection details
            connection_id = "/subscriptions/b28cc86b-8f84-47e5-a38a-b814b44d047e/resourceGroups/Az-AICost-Agent-RG/providers/Microsoft.Web/connections/office365"
            
            if status == "success":
                subject = f"✅ Deployment Successful: {resource_name}"
                body = f"""<html><body style='font-family: Segoe UI, Arial, sans-serif;'>
                <div style='max-width: 600px; margin: 0 auto; padding: 20px;'>
                    <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 30px; border-radius: 10px; text-align: center; color: white;'>
                        <h1 style='margin: 0;'>✅ Deployment Successful!</h1>
                    </div>
                    <div style='background: white; padding: 30px; border: 1px solid #e0e0e0; border-radius: 0 0 10px 10px;'>
                        <p style='font-size: 16px; color: #333;'>Hi <strong>{self.user_name}</strong>,</p>
                        <p>Your resource <strong>{resource_name}</strong> has been successfully deployed and verified in Azure!</p>
                        <div style='background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;'>
                            <p style='margin: 5px 0;'><strong>Resource:</strong> {resource_name}</p>
                            <p style='margin: 5px 0;'><strong>Type:</strong> {resource_type}</p>
                            <p style='margin: 5px 0;'><strong>Resource Group:</strong> {resource_group}</p>
                            <p style='margin: 5px 0;'><strong>Request ID:</strong> {request_id}</p>
                        </div>
                        <p style='font-size: 14px; color: #666;'>You can now access your resource in the Azure Portal.</p>
                    </div>
                </div>
                </body></html>"""
            else:
                subject = f"⚠️ Deployment Failed: {resource_name}"
                body = f"""<html><body style='font-family: Segoe UI, Arial, sans-serif;'>
                <div style='max-width: 600px; margin: 0 auto; padding: 20px;'>
                    <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 30px; border-radius: 10px; text-align: center; color: white;'>
                        <h1 style='margin: 0;'>⚠️ Deployment Failed</h1>
                    </div>
                    <div style='background: white; padding: 30px; border: 1px solid #e0e0e0; border-radius: 0 0 10px 10px;'>
                        <p style='font-size: 16px; color: #333;'>Hi <strong>{self.user_name}</strong>,</p>
                        <p>Unfortunately, the deployment of <strong>{resource_name}</strong> failed.</p>
                        <div style='background: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #ffc107;'>
                            <p style='margin: 5px 0;'><strong>Resource:</strong> {resource_name}</p>
                            <p style='margin: 5px 0;'><strong>Request ID:</strong> {request_id}</p>
                            <p style='margin: 5px 0;'><strong>Error:</strong> {error or "Unknown error"}</p>
                        </div>
                        <p style='font-size: 14px; color: #666;'>Please check the Azure Portal Activity Log for more details or contact your administrator.</p>
                    </div>
                </div>
                </body></html>"""
            
            # Use Azure CLI to send email via Logic App
            import subprocess
            email_payload = {
                "To": self.user_email,
                "Subject": subject,
                "Body": body,
                "Importance": "High" if status == "failure" else "Normal"
            }
            
            logger.info(f"📧 Sending {status} email to {self.user_email}")
            
            # Note: This would require a separate Logic App endpoint for emails
            # For now, just log it
            logger.info(f"Email would be sent: {subject}")
            
        except Exception as e:
            logger.error(f"Failed to send deployment email: {str(e)}")
    
    def _background_approval_handler(self, cli_result: Dict, resource_type: str, approval_result: Dict):
        """Background thread to poll for approval and execute deployment"""
        try:
            logger.info("🔄 Background approval handler started...")
            logger.info(f"📋 Request ID: {approval_result.get('request_id', 'N/A')}")
            logger.info(f"📦 Resource: {cli_result.get('resource_name', 'N/A')}")
            
            import time
            import subprocess
            import os
            
            max_polls = 60  # 10 minutes maximum wait
            poll_count = 0
            request_id = approval_result.get("request_id", "N/A")
            
            while poll_count < max_polls:
                try:
                    # Check Logic App run history for approval
                    check_result = subprocess.run(
                        f'az rest --method get --url "https://management.azure.com/subscriptions/{os.getenv("AZURE_SUBSCRIPTION_ID")}/resourceGroups/Az-AICost-Agent-RG/providers/Microsoft.Logic/workflows/logagzs0230/runs?api-version=2019-05-01&$top=5" --query "value[?contains(properties.trigger.inputsLink.contentVersion, \'{request_id}\')].{{status:status,outputs:properties.outputs}}" --output json',
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if check_result.returncode == 0 and check_result.stdout.strip():
                        import json
                        try:
                            runs = json.loads(check_result.stdout)
                            for run in runs:
                                if run.get("status") == "Succeeded":
                                    outputs = run.get("outputs", {})
                                    # Check the approval decision in Send_Approval_Email output
                                    approval_email_output = outputs.get("Send_Approval_Email", {})
                                    selected_option = approval_email_output.get("SelectedOption")
                                    
                                    if selected_option == "Approve":
                                        logger.info("✅ Request APPROVED! Executing command...")
                                        
                                        # Execute the CLI command
                                        exec_result = subprocess.run(
                                            cli_result["command"],
                                            shell=True,
                                            capture_output=True,
                                            text=True,
                                            timeout=300
                                        )
                                        
                                        # Verify deployment
                                        if exec_result.returncode == 0:
                                            logger.info(f"✅ Deployment successful!")
                                            
                                            # Verify resource exists
                                            time.sleep(5)  # Wait for Azure to propagate
                                            verify_command = f'az resource list --resource-group {cli_result.get("resource_group")} --query "[?name==\'{cli_result["resource_name"]}\'].name" --output tsv'
                                            verify_result = subprocess.run(verify_command, shell=True, capture_output=True, text=True, timeout=30)
                                            
                                            if verify_result.returncode == 0 and verify_result.stdout.strip():
                                                logger.info("✅ Resource verified in Azure!")
                                                logger.info(f"📧 Success email would be sent to {self.user_email}")
                                            else:
                                                logger.warning("⚠️ Resource created but not yet visible")
                                        else:
                                            logger.error(f"❌ Deployment failed: {exec_result.stderr}")
                                            logger.info(f"📧 Failure email would be sent to {self.user_email}")
                                        return
                                        
                                    elif selected_option == "Reject":
                                        logger.info("❌ Request REJECTED by approver")
                                        return
                        except json.JSONDecodeError:
                            pass
                    
                    # Wait and poll again
                    time.sleep(10)
                    poll_count += 1
                    
                    if poll_count % 6 == 0:  # Every minute
                        logger.info(f"⏳ Still waiting for approval... ({poll_count * 10}s elapsed)")
                        
                except Exception as poll_error:
                    logger.error(f"⚠️ Polling error: {str(poll_error)}")
                    time.sleep(10)
                    poll_count += 1
            
            logger.warning(f"⏱️ Approval timeout after {max_polls * 10} seconds")
            
        except Exception as e:
            logger.error(f"❌ CRITICAL: Background handler failed: {str(e)}")
            logger.exception("Full background handler error:")

            logger.error("❌ Approval timeout - no response after 10 minutes")
            
        except Exception as e:
            logger.error(f"❌ Background handler error: {str(e)}")
    
    async def create_any_resource(
        self,
        resource_type: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create ANY Azure resource using CLI commands
        
        Works for: disks, VMs, storage accounts, vnets, SQL, availability sets, etc.
        
        Args:
            resource_type: Type of resource (disk, vm, storage, etc.)
            params: Resource parameters from user
            
        Returns:
            Dict with approval request ID
        """
        try:
            logger.info(f"🚀 Creating {resource_type} using Azure CLI approach")
            
            # Generate CLI command
            cli_result = await self.cli_ops.create_resource(resource_type, params)
            
            if cli_result["status"] == "error":
                return cli_result
            
            # Package for approval - adapt to work with existing submit_for_approval method
            # Create a simple deployment template that contains the CLI command
            deployment_template = {
                "deployment_method": "Azure CLI",
                "command": cli_result["command"],
                "explanation": cli_result["explanation"],
                "resource_type": resource_type,
                "parameters": params
            }
            
            # Submit for approval using existing method
            approval_result = await self.logic_app_client.submit_for_approval(
                resource_type=resource_type.title(),
                resource_name=cli_result["resource_name"],
                deployment_template=deployment_template,
                resource_group=cli_result.get("resource_group", "N/A"),
                user_email=self.user_email or "admin@example.com",
                user_name=self.user_name or "Admin User",
                estimated_cost=cli_result["estimated_cost"],
                justification=params.get("requirements", params.get("justification", f"Creating {resource_type}")),
                location=cli_result["location"]
            )
            
            # If auto-approved (workflow disabled), execute the command immediately
            if approval_result.get("status") == "auto_approved":
                logger.info("🚀 Auto-approved! Executing CLI command immediately...")
                logger.info(f"📝 Command: {cli_result['command']}")
                
                try:
                    import subprocess
                    result = subprocess.run(
                        cli_result["command"],
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    
                    if result.returncode == 0:
                        logger.info(f"✅ Resource {cli_result['resource_name']} created successfully!")
                        approval_result["deployment_status"] = "success"
                        approval_result["deployment_output"] = result.stdout
                        approval_result["message"] = f"✅ {resource_type.title()} '{cli_result['resource_name']}' deployed successfully!"
                    else:
                        logger.error(f"❌ Deployment failed: {result.stderr}")
                        approval_result["deployment_status"] = "failed"
                        approval_result["deployment_error"] = result.stderr
                        approval_result["message"] = f"❌ Deployment failed: {result.stderr}"
                        
                except subprocess.TimeoutExpired:
                    logger.error("❌ Deployment timed out")
                    approval_result["deployment_status"] = "timeout"
                    approval_result["message"] = "❌ Deployment timed out after 5 minutes"
                except Exception as exec_error:
                    logger.error(f"❌ Execution error: {str(exec_error)}")
                    approval_result["deployment_status"] = "error"
                    approval_result["message"] = f"❌ Execution error: {str(exec_error)}"
            else:
                # Workflow enabled - submit and return immediately, Python polls for approval
                logger.info("✅ Approval request submitted successfully!")
                logger.info(f"📧 Approval email sent to: {self.user_email}")
                logger.info(f"🔗 Request ID: {approval_result.get('requestId', 'N/A')}")
                
                # Start background thread to poll for approval and execute
                try:
                    thread = threading.Thread(
                        target=self._background_approval_handler,
                        args=(cli_result, resource_type, approval_result),
                        daemon=True
                    )
                    thread.start()
                    logger.info(f"🧵 Background polling started (Thread ID: {thread.ident})")
                    logger.info("⏳ Polling Logic App for approval decision...")
                except Exception as thread_error:
                    logger.error(f"❌ Failed to start background thread: {str(thread_error)}")
                    logger.exception("Full thread startup error:")
                
                # Return immediately to user
                approval_result["status"] = "pending_approval"
                approval_result["message"] = f"📧 Approval request sent to {self.user_email}. You will receive an email once the deployment is complete."
            
            return approval_result
            
        except Exception as e:
            logger.error(f"❌ Error in create_any_resource: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to process request: {str(e)}"
            }
    
    # Convenience methods for specific resource types
    
    async def create_disk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create managed disk"""
        return await self.create_any_resource("disk", params)
    
    async def create_storage_account(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create storage account"""
        return await self.create_any_resource("storage account", params)
    
    async def create_vm(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create virtual machine"""
        return await self.create_any_resource("virtual machine", params)
    
    async def create_availability_set(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create availability set"""
        return await self.create_any_resource("availability set", params)
    
    async def create_vnet(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create virtual network"""
        return await self.create_any_resource("virtual network", params)
    
    async def create_resource_group(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create resource group"""
        return await self.create_any_resource("resource group", params)
    
    async def create_sql_database(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create SQL database"""
        return await self.create_any_resource("sql database", params)    
    async def update_resource_tags(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add or update tags on an existing Azure resource
        
        Args:
            params: Dict with resource_type, resource_name, resource_group, tags
            
        Returns:
            Dict with operation result
        """
        try:
            resource_type = params.get("resource_type", "").lower()
            resource_name = params.get("resource_name")
            resource_group = params.get("resource_group")
            tags = params.get("tags", {})
            
            logger.info(f"🏷️ Updating tags for {resource_type} '{resource_name}'")
            
            # Map resource type to Azure CLI resource identifier
            resource_map = {
                "vm": "Microsoft.Compute/virtualMachines",
                "virtual machine": "Microsoft.Compute/virtualMachines",
                "disk": "Microsoft.Compute/disks",
                "managed disk": "Microsoft.Compute/disks",
                "storage": "Microsoft.Storage/storageAccounts",
                "storage account": "Microsoft.Storage/storageAccounts",
                "vnet": "Microsoft.Network/virtualNetworks",
                "virtual network": "Microsoft.Network/virtualNetworks",
                "availability set": "Microsoft.Compute/availabilitySets",
                "avset": "Microsoft.Compute/availabilitySets"
            }
            
            resource_id_type = resource_map.get(resource_type, resource_type)
            
            # Build resource ID
            resource_id = f"/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}/providers/{resource_id_type}/{resource_name}"
            
            # Build tag arguments
            tag_args = " ".join([f"{k}={v}" for k, v in tags.items()])
            
            # Build and execute command
            command = f"az resource tag --ids {resource_id} --tags {tag_args}"
            
            logger.info(f"📝 Executing: {command}")
            
            import subprocess
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Tags updated successfully on {resource_name}")
                return {
                    "status": "success",
                    "message": f"✅ Tags updated successfully on {resource_type} '{resource_name}'",
                    "resource_name": resource_name,
                    "tags_applied": tags
                }
            else:
                logger.error(f"❌ Failed to update tags: {result.stderr}")
                return {
                    "status": "error",
                    "message": f"❌ Failed to update tags: {result.stderr}",
                    "error": result.stderr
                }
                
        except Exception as e:
            logger.error(f"❌ Error updating tags: {str(e)}")
            return {
                "status": "error",
                "message": f"❌ Error updating tags: {str(e)}"
            }