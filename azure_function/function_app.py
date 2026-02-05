import azure.functions as func
import logging
import json
import subprocess
import time

app = func.FunctionApp()

@app.route(route="execute-deployment", auth_level=func.AuthLevel.FUNCTION)
def execute_deployment(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function to execute approved deployment commands
    Called by Logic App after approval
    """
    logging.info('🚀 Deployment execution function triggered')

    try:
        # Parse request body from Logic App
        req_body = req.get_json()
        
        command = req_body.get('command')
        resource_name = req_body.get('resourceName')
        resource_group = req_body.get('resourceGroup')
        resource_type = req_body.get('resourceType')
        request_id = req_body.get('requestId')
        
        if not command:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "Missing command parameter"}),
                status_code=400,
                mimetype="application/json"
            )
        
        logging.info(f"📋 Request ID: {request_id}")
        logging.info(f"📦 Resource: {resource_name}")
        logging.info(f"💻 Command: {command}")
        
        # Execute Azure CLI command
        logging.info("⚡ Executing CLI command...")
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            logging.info("✅ Command executed successfully")
            
            # Wait for Azure propagation
            time.sleep(5)
            
            # Verify resource exists
            logging.info("🔍 Verifying resource in Azure...")
            verify_command = f'az resource list --resource-group {resource_group} --query "[?name==\'{resource_name}\'].name" --output tsv'
            verify_result = subprocess.run(
                verify_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if verify_result.returncode == 0 and verify_result.stdout.strip():
                logging.info(f"✅ Resource '{resource_name}' verified in Azure!")
                return func.HttpResponse(
                    json.dumps({
                        "status": "success",
                        "message": f"✅ {resource_type} '{resource_name}' deployed successfully!",
                        "resourceName": resource_name,
                        "resourceGroup": resource_group,
                        "requestId": request_id,
                        "output": result.stdout
                    }),
                    status_code=200,
                    mimetype="application/json"
                )
            else:
                logging.warning("⚠️ Resource created but verification failed")
                return func.HttpResponse(
                    json.dumps({
                        "status": "partial",
                        "message": f"⚠️ Command executed but resource verification failed",
                        "resourceName": resource_name,
                        "requestId": request_id,
                        "output": result.stdout
                    }),
                    status_code=200,
                    mimetype="application/json"
                )
        else:
            logging.error(f"❌ Command failed: {result.stderr}")
            return func.HttpResponse(
                json.dumps({
                    "status": "failed",
                    "message": f"❌ Deployment failed: {result.stderr}",
                    "resourceName": resource_name,
                    "requestId": request_id,
                    "error": result.stderr
                }),
                status_code=500,
                mimetype="application/json"
            )
            
    except subprocess.TimeoutExpired:
        logging.error("❌ Command timed out after 5 minutes")
        return func.HttpResponse(
            json.dumps({
                "status": "timeout",
                "message": "❌ Deployment timed out after 5 minutes",
                "requestId": request_id
            }),
            status_code=500,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"❌ Error: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": f"❌ Error: {str(e)}",
                "requestId": request_id
            }),
            status_code=500,
            mimetype="application/json"
        )
