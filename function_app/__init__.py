import logging
import json
import subprocess
import azure.functions as func

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function to execute approved CLI commands from Logic App
    """
    logging.info('CLI Execution function triggered')

    try:
        # Parse request body
        req_body = req.get_json()
        
        request_id = req_body.get('requestId')
        command = req_body.get('command')
        resource_name = req_body.get('resourceName')
        resource_type = req_body.get('resourceType')
        
        logging.info(f"🟢 EXECUTING APPROVED COMMAND")
        logging.info(f"   Request ID: {request_id}")
        logging.info(f"   Resource: {resource_name}")
        logging.info(f"   Type: {resource_type}")
        logging.info(f"   Command: {command}")
        
        if not command:
            return func.HttpResponse(
                json.dumps({"status": "error", "error": "No command provided"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Execute the CLI command
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            logging.info(f"✅ Command executed successfully")
            logging.info(f"   Output: {result.stdout}")
            
            return func.HttpResponse(
                json.dumps({
                    "status": "success",
                    "requestId": request_id,
                    "output": result.stdout,
                    "message": f"Resource {resource_name} deployed successfully"
                }),
                status_code=200,
                mimetype="application/json"
            )
        else:
            logging.error(f"❌ Command failed with exit code {result.returncode}")
            logging.error(f"   Error: {result.stderr}")
            
            return func.HttpResponse(
                json.dumps({
                    "status": "failed",
                    "requestId": request_id,
                    "error": result.stderr,
                    "message": f"Failed to deploy {resource_name}"
                }),
                status_code=500,
                mimetype="application/json"
            )
            
    except subprocess.TimeoutExpired:
        return func.HttpResponse(
            json.dumps({
                "status": "timeout",
                "requestId": request_id,
                "error": "Command execution timed out after 5 minutes"
            }),
            status_code=408,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"❌ Exception during execution: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "error": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )
