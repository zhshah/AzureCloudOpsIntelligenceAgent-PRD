"""
Bicep Template Generator
Generates Bicep templates instead of ARM - Azure handles API versions automatically!
"""

import json
import logging
import os
import subprocess
import tempfile
from typing import Dict, Optional, Tuple
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class BicepTemplateGenerator:
    """
    Generates Bicep templates using AI
    Bicep automatically uses latest API versions - no hard-coding needed!
    """
    
    def __init__(self, subscription_id: str):
        self.subscription_id = subscription_id
        
        # Initialize OpenAI client
        self.openai_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
    
    def generate_bicep_template(
        self,
        resource_type: str,
        resource_name: str,
        location: str,
        user_requirements: Optional[str] = None
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Generate Bicep template and convert to ARM
        Bicep handles API versions automatically!
        """
        try:
            logger.info(f"📝 Generating Bicep template for {resource_type}")
            
            # Create prompt for Bicep generation
            prompt = f"""Generate a Bicep template for the following Azure resource.
Bicep is Azure's native IaC language and handles API versions automatically.

RESOURCE TYPE: {resource_type}
RESOURCE NAME: {resource_name}
LOCATION: {location}
REQUIREMENTS: {user_requirements or 'Standard configuration with best practices'}

BICEP TEMPLATE RULES:
1. Use clean Bicep syntax (not ARM JSON)
2. Do NOT specify apiVersion - Bicep handles this automatically
3. Include only essential properties
4. Use descriptive parameter names
5. Follow Azure naming conventions

Example Bicep for availability set:
```
resource availset 'Microsoft.Compute/availabilitySets@2025-04-01' = {{
  name: 'myavailset'
  location: 'westeurope'
  properties: {{
    platformFaultDomainCount: 2
    platformUpdateDomainCount: 5
  }}
  sku: {{
    name: 'Aligned'
  }}
}}
```

Generate ONLY the Bicep template code, no explanations."""

            # System message emphasizing Bicep
            system_message = """You are an expert Azure Bicep developer.
Generate clean, production-ready Bicep templates.
ALWAYS use the LATEST API version available for the resource type.
For availability sets, use 2025-04-01 or later."""

            # Call OpenAI
            response = self.openai_client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,  # Deterministic
                max_tokens=2000
            )
            
            bicep_code = response.choices[0].message.content.strip()
            
            # Remove code fences if present
            if bicep_code.startswith("```"):
                lines = bicep_code.split("\n")
                bicep_code = "\n".join(lines[1:-1])
            
            logger.info("✅ Bicep template generated")
            
            # Convert Bicep to ARM using az bicep build
            arm_template = self._convert_bicep_to_arm(bicep_code)
            
            if not arm_template:
                return None, "Failed to convert Bicep to ARM"
            
            logger.info("✅ Bicep converted to ARM successfully")
            return arm_template, None
            
        except Exception as e:
            logger.error(f"❌ Error generating Bicep template: {str(e)}")
            return None, str(e)
    
    def _convert_bicep_to_arm(self, bicep_code: str) -> Optional[Dict]:
        """
        Convert Bicep to ARM using Azure CLI
        """
        try:
            # Write Bicep to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.bicep', delete=False) as f:
                f.write(bicep_code)
                bicep_file = f.name
            
            # Convert using az bicep build
            result = subprocess.run(
                ['az', 'bicep', 'build', '--file', bicep_file, '--stdout'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Clean up temp file
            os.unlink(bicep_file)
            
            if result.returncode != 0:
                logger.error(f"❌ Bicep build failed: {result.stderr}")
                return None
            
            # Parse ARM JSON
            arm_template = json.loads(result.stdout)
            return arm_template
            
        except Exception as e:
            logger.error(f"❌ Error converting Bicep to ARM: {str(e)}")
            return None
    
    def generate_with_retry(
        self,
        resource_type: str,
        resource_name: str,
        location: str,
        resource_group: Optional[str] = None,
        user_requirements: Optional[str] = None,
        max_retries: int = 2
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Generate template with retry logic
        """
        for attempt in range(max_retries):
            logger.info(f"🔄 Generation attempt {attempt + 1}/{max_retries}")
            
            template, error = self.generate_bicep_template(
                resource_type=resource_type,
                resource_name=resource_name,
                location=location,
                user_requirements=user_requirements
            )
            
            if template:
                return template, None
            
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Attempt {attempt + 1} failed: {error}, retrying...")
            
        return None, f"Failed after {max_retries} attempts: {error}"
