"""
Conversation State Manager
Handles multi-turn dialogues for resource creation and advisory conversations
"""

from typing import Dict, List, Optional, Any
from enum import Enum
import json
import uuid


class ConversationPhase(Enum):
    """Phases in a conversation"""
    INITIAL = "initial"
    GATHERING_REQUIREMENTS = "gathering_requirements"
    PROVIDING_RECOMMENDATIONS = "providing_recommendations"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    EXECUTING = "executing"
    COMPLETED = "completed"


class ResourceType(Enum):
    """Types of resources that can be created"""
    VIRTUAL_MACHINE = "virtual_machine"
    SQL_DATABASE = "sql_database"
    STORAGE_ACCOUNT = "storage_account"
    APP_SERVICE = "app_service"
    FUNCTION_APP = "function_app"
    UNKNOWN = "unknown"


class ConversationState:
    """Represents the state of an ongoing conversation"""
    
    def __init__(self, conversation_id: str = None):
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.phase = ConversationPhase.INITIAL
        self.resource_type = ResourceType.UNKNOWN
        self.intent = None  # CREATE, MODIFY, DELETE, QUERY
        self.requirements = {}  # Gathered requirements
        self.recommendations = []  # Recommendations provided
        self.confirmation_pending = None  # What action is pending confirmation
        self.context_switches = []  # Track context switches (e.g., VM -> SQL PaaS)
        self.collected_params = {}  # Parameters collected so far
        self.missing_params = []  # Parameters still needed
        self.advisory_notes = []  # Technical advisory notes provided
        
    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            "conversation_id": self.conversation_id,
            "phase": self.phase.value,
            "resource_type": self.resource_type.value,
            "intent": self.intent,
            "requirements": self.requirements,
            "recommendations": self.recommendations,
            "confirmation_pending": self.confirmation_pending,
            "context_switches": self.context_switches,
            "collected_params": self.collected_params,
            "missing_params": self.missing_params,
            "advisory_notes": self.advisory_notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConversationState':
        """Deserialize from dictionary"""
        state = cls(data.get("conversation_id"))
        state.phase = ConversationPhase(data.get("phase", "initial"))
        state.resource_type = ResourceType(data.get("resource_type", "unknown"))
        state.intent = data.get("intent")
        state.requirements = data.get("requirements", {})
        state.recommendations = data.get("recommendations", [])
        state.confirmation_pending = data.get("confirmation_pending")
        state.context_switches = data.get("context_switches", [])
        state.collected_params = data.get("collected_params", {})
        state.missing_params = data.get("missing_params", [])
        state.advisory_notes = data.get("advisory_notes", [])
        return state


class ConversationManager:
    """Manages conversation states for multi-turn interactions"""
    
    # Required parameters for each resource type
    RESOURCE_REQUIREMENTS = {
        ResourceType.VIRTUAL_MACHINE: {
            "required": ["name", "size", "os_type", "location", "resource_group"],
            "optional": ["disk_size_gb", "disk_type", "network", "availability_zone"]
        },
        ResourceType.SQL_DATABASE: {
            "required": ["name", "server_name", "tier", "location", "resource_group"],
            "optional": ["collation", "max_size_gb", "backup_retention_days"]
        },
        ResourceType.STORAGE_ACCOUNT: {
            "required": ["name", "location", "resource_group", "sku"],
            "optional": ["kind", "access_tier", "enable_https_only"]
        }
    }
    
    # Recommendations based on workload
    WORKLOAD_RECOMMENDATIONS = {
        "sql": {
            "message": "💡 **Technical Recommendation**: For SQL workloads, Azure SQL PaaS offers significant advantages:\n\n"
                      "- ✅ **Managed Service**: Automatic backups, patching, high availability\n"
                      "- ✅ **Cost Efficiency**: Pay only for what you use, no OS overhead\n"
                      "- ✅ **Performance**: Built-in query optimization and performance insights\n"
                      "- ✅ **Security**: Advanced threat protection and encryption\n\n"
                      "Would you like me to configure Azure SQL Database instead of a VM with SQL Server?",
            "alternative": ResourceType.SQL_DATABASE
        },
        "web": {
            "message": "💡 **Technical Recommendation**: For web applications, Azure App Service provides:\n\n"
                      "- ✅ **Simplified Deployment**: Built-in CI/CD and deployment slots\n"
                      "- ✅ **Auto-scaling**: Automatic scale based on load\n"
                      "- ✅ **Managed Platform**: No OS maintenance required\n"
                      "- ✅ **Cost Effective**: Multiple apps on same plan\n\n"
                      "Would you like to use Azure App Service instead?",
            "alternative": ResourceType.APP_SERVICE
        }
    }
    
    # VM size recommendations based on workload
    VM_SIZE_RECOMMENDATIONS = {
        "sql": {
            "development": "Standard_D2s_v3 (2 vCPU, 8 GB RAM) - $70/month",
            "production": "Standard_E4s_v3 (4 vCPU, 32 GB RAM, optimized for memory-intensive workloads) - $200/month",
            "high_performance": "Standard_M8ms (8 vCPU, 218 GB RAM, ultra-low latency) - $700/month"
        },
        "general": {
            "small": "Standard_B2s (2 vCPU, 4 GB RAM) - $30/month",
            "medium": "Standard_D4s_v3 (4 vCPU, 16 GB RAM) - $140/month",
            "large": "Standard_D8s_v3 (8 vCPU, 32 GB RAM) - $280/month"
        }
    }
    
    def __init__(self):
        """Initialize conversation manager"""
        self.active_conversations: Dict[str, ConversationState] = {}
        
    def start_conversation(self, user_message: str) -> ConversationState:
        """Start a new conversation based on user intent"""
        state = ConversationState()
        
        # Detect intent
        message_lower = user_message.lower()
        if any(word in message_lower for word in ["create", "provision", "deploy", "set up", "setup"]):
            state.intent = "CREATE"
            state.phase = ConversationPhase.GATHERING_REQUIREMENTS
            
            # Detect resource type
            if "vm" in message_lower or "virtual machine" in message_lower:
                state.resource_type = ResourceType.VIRTUAL_MACHINE
            elif "sql" in message_lower or "database" in message_lower:
                state.resource_type = ResourceType.SQL_DATABASE
            elif "storage" in message_lower:
                state.resource_type = ResourceType.STORAGE_ACCOUNT
        
        self.active_conversations[state.conversation_id] = state
        return state
    
    def get_next_question(self, state: ConversationState) -> Optional[str]:
        """Get next question to ask user based on conversation state"""
        resource_type = state.resource_type
        collected = state.collected_params
        
        if resource_type not in self.RESOURCE_REQUIREMENTS:
            return None
        
        requirements = self.RESOURCE_REQUIREMENTS[resource_type]
        
        # Check required parameters
        for param in requirements["required"]:
            if param not in collected:
                return self._format_question(param, resource_type)
        
        # All required params collected
        return None
    
    def _format_question(self, param: str, resource_type: ResourceType) -> str:
        """Format a question for a specific parameter"""
        questions = {
            "name": "What would you like to name this resource?",
            "size": "What size would you like? (e.g., Standard_D2s_v3)",
            "os_type": "Which operating system? (Windows or Linux)",
            "location": "Which Azure region? (e.g., eastus, westeurope)",
            "resource_group": "Which resource group should this be created in?",
            "server_name": "What should the server name be?",
            "tier": "Which service tier? (Basic, Standard, or Premium)",
            "sku": "Which SKU? (Standard_LRS, Standard_GRS, Premium_LRS)",
            "disk_size_gb": "What disk size in GB? (default: 128 GB)",
            "disk_type": "Which disk type? (Standard_LRS, Premium_SSD, Ultra_SSD)"
        }
        
        return questions.get(param, f"Please provide the {param.replace('_', ' ')}:")
    
    def process_user_response(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """
        Process user response and update conversation state
        Returns dict with: {
            "question": next question or None,
            "recommendation": any recommendation to show,
            "ready_for_confirmation": bool,
            "context_switch": bool (if switching resource types)
        }
        """
        result = {
            "question": None,
            "recommendation": None,
            "ready_for_confirmation": False,
            "context_switch": False
        }
        
        # Check for workload-based recommendations
        message_lower = user_message.lower()
        
        # Check if user mentioned SQL workload
        if state.resource_type == ResourceType.VIRTUAL_MACHINE:
            if any(word in message_lower for word in ["sql", "database", "mssql", "mysql", "postgres"]):
                # Offer PaaS recommendation
                rec = self.WORKLOAD_RECOMMENDATIONS["sql"]
                result["recommendation"] = rec["message"]
                state.recommendations.append(rec)
                state.phase = ConversationPhase.PROVIDING_RECOMMENDATIONS
                return result
        
        # Continue gathering requirements
        next_question = self.get_next_question(state)
        
        if next_question:
            result["question"] = next_question
        else:
            # All requirements gathered, ready for confirmation
            result["ready_for_confirmation"] = True
            state.phase = ConversationPhase.AWAITING_CONFIRMATION
        
        return result
    
    def generate_creation_summary(self, state: ConversationState) -> str:
        """Generate summary of what will be created"""
        if state.resource_type == ResourceType.VIRTUAL_MACHINE:
            params = state.collected_params
            summary = f"""
### 📋 Resource Creation Summary

I'm ready to create the following Virtual Machine:

**Resource Details:**
- **Name**: {params.get('name', 'N/A')}
- **Size**: {params.get('size', 'N/A')}
- **OS**: {params.get('os_type', 'N/A')}
- **Location**: {params.get('location', 'N/A')}
- **Resource Group**: {params.get('resource_group', 'N/A')}
- **Disk Size**: {params.get('disk_size_gb', '128')} GB
- **Disk Type**: {params.get('disk_type', 'Standard_LRS')}

**Estimated Monthly Cost**: ~${self._estimate_cost(state)}

**⚠️ Admin Confirmation Required**

To proceed with creation, please confirm:
- Type **"YES"** to create this resource
- Type **"NO"** to cancel or modify parameters
"""
            return summary
        
        return "Ready to create resource. Please confirm."
    
    def _estimate_cost(self, state: ConversationState) -> str:
        """Estimate monthly cost for resource"""
        if state.resource_type == ResourceType.VIRTUAL_MACHINE:
            size = state.collected_params.get('size', '').lower()
            if 'd2s' in size:
                return "70"
            elif 'd4s' in size:
                return "140"
            elif 'd8s' in size:
                return "280"
        return "varies"
    
    def get_conversation_state(self, conversation_id: str) -> Optional[ConversationState]:
        """Get conversation state by ID"""
        return self.active_conversations.get(conversation_id)
    
    def end_conversation(self, conversation_id: str):
        """End and clean up conversation"""
        if conversation_id in self.active_conversations:
            del self.active_conversations[conversation_id]


# Singleton instance
_conversation_manager = None

def get_conversation_manager() -> ConversationManager:
    """Get singleton conversation manager"""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
