"""
SageAlpha.ai - Finance Query Chatbot
Flask backend for Azure AI Agent integration
"""

import os
import sys
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder
import logging
from typing import Optional, Dict, Any

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ============================================================================
# AZURE CONFIGURATION
# ============================================================================

def validate_env_variables():
    """Validate all required environment variables."""
    required_vars = {
        'AZURE_SUBSCRIPTION_ID': os.getenv("AZURE_SUBSCRIPTION_ID"),
        'AZURE_RESOURCE_GROUP': os.getenv("AZURE_RESOURCE_GROUP"),
        'AZURE_PROJECT_NAME': os.getenv("AZURE_PROJECT_NAME"),
        'AZURE_PROJECT_ENDPOINT': os.getenv("AZURE_PROJECT_ENDPOINT"),
        'AZURE_AGENT_ID': os.getenv("AZURE_AGENT_ID"),
    }
    
    missing = [k for k, v in required_vars.items() if not v]
    
    if missing:
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info("✓ All environment variables validated")
    return required_vars


# Validate and get configuration
try:
    config = validate_env_variables()
    subscription_id = config['AZURE_SUBSCRIPTION_ID']
    resource_group_name = config['AZURE_RESOURCE_GROUP']
    project_name = config['AZURE_PROJECT_NAME']
    endpoint = config['AZURE_PROJECT_ENDPOINT']
    agent_id = config['AZURE_AGENT_ID']
except ValueError as e:
    logger.error(f"Configuration error: {e}")
    sys.exit(1)

# Initialize Azure AI Project Client
try:
    logger.info("Initializing Azure AI Project Client...")
    project = AIProjectClient(
        credential=DefaultAzureCredential(),
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        project_name=project_name,
        endpoint=endpoint
    )
    logger.info("✓ Connected to Azure AI Project successfully")
except Exception as e:
    logger.error(f"Failed to initialize AIProjectClient: {e}")
    sys.exit(1)

# ============================================================================
# ROUTES
# ============================================================================

@app.route("/", methods=["GET"])
def index():
    """Render home page."""
    try:
        return render_template("index.html")
    except Exception as e:
        logger.error(f"Error rendering index: {e}")
        return jsonify({"error": "Failed to load UI"}), 500


@app.route("/chat", methods=["POST"])
def chat():
    """
    Handle chat messages with Azure AI Agent.
    
    Request JSON:
    {
        "message": "User question",
        "history": [] (optional conversation history)
    }
    
    Response JSON:
    {
        "response": "Agent response",
        "status": "success"
    }
    """
    try:
        # Parse request
        data = request.get_json(silent=True) or {}
        user_message = data.get("message", "").strip()
        
        if not user_message:
            logger.warning("Empty message received")
            return jsonify({"error": "Message is required"}), 400
        
        logger.info(f"Processing message: {user_message[:100]}...")
        
        # Create thread for conversation
        try:
            thread = project.agents.threads.create()
            logger.info(f"✓ Created thread: {thread.id}")
        except Exception as e:
            logger.error(f"Failed to create thread: {e}")
            return jsonify({"error": "Failed to create conversation thread"}), 500
        
        # Send user message
        try:
            project.agents.messages.create(
                thread_id=thread.id,
                role="user",
                content=user_message
            )
            logger.info("✓ Message sent to agent")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return jsonify({"error": "Failed to send message to agent"}), 500
        
        # Run the agent
        try:
            run = project.agents.runs.create_and_process(
                thread_id=thread.id,
                agent_id=agent_id
            )
            logger.info(f"✓ Agent run completed with status: {run.status}")
        except Exception as e:
            logger.error(f"Failed to run agent: {e}")
            return jsonify({"error": "Failed to run agent"}), 500
        
        # Check run status
        if run.status == "failed":
            error_msg = str(getattr(run, 'last_error', 'Unknown error'))
            logger.error(f"Agent run failed: {error_msg}")
            return jsonify({"error": f"Agent error: {error_msg}"}), 500
        
        # Retrieve messages
        try:
            messages = project.agents.messages.list(
                thread_id=thread.id,
                order=ListSortOrder.ASCENDING
            )
            logger.info("✓ Messages retrieved")
        except Exception as e:
            logger.error(f"Failed to retrieve messages: {e}")
            return jsonify({"error": "Failed to retrieve agent response"}), 500
        
        # Extract assistant response
        assistant_reply = extract_assistant_response(messages)
        
        if not assistant_reply:
            logger.warning("No assistant response found")
            assistant_reply = "I apologize, but I couldn't generate a response. Please try again."
        
        logger.info(f"✓ Response generated: {assistant_reply[:100]}...")
        
        return jsonify({
            "response": assistant_reply,
            "status": "success"
        }), 200
    
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}", exc_info=True)
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "SageAlpha.ai"}), 200


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_assistant_response(messages) -> Optional[str]:
    """
    Extract the assistant's text response from messages list.
    Parses the Azure SDK response format to return human-readable text only.
    """
    try:
        for msg in messages:
            if msg.role == "assistant":
                logger.debug(f"Processing assistant message: {type(msg)}")
                
                # Format 1: List of text objects (newest Azure SDK format)
                # Example: [{'type': 'text', 'text': {'value': 'response text', 'annotations': []}}]
                if isinstance(msg.content, list):
                    logger.debug("Message is a list format")
                    for item in msg.content:
                        if isinstance(item, dict):
                            if item.get('type') == 'text':
                                text_obj = item.get('text')
                                if isinstance(text_obj, dict) and 'value' in text_obj:
                                    response_text = text_obj['value']
                                    logger.debug(f"Extracted from list format: {response_text[:50]}...")
                                    return response_text
                
                # Format 2: Direct string content
                if isinstance(msg.content, str):
                    logger.debug("Message is string format")
                    return msg.content
                
                # Format 3: text_messages list (older SDK format)
                if hasattr(msg, 'text_messages') and msg.text_messages:
                    logger.debug("Message has text_messages attribute")
                    for text_msg in msg.text_messages:
                        if hasattr(text_msg, 'value') and text_msg.value:
                            return str(text_msg.value)
                        elif hasattr(text_msg, 'text'):
                            if hasattr(text_msg.text, 'value'):
                                return str(text_msg.text.value)
                            else:
                                return str(text_msg.text)
                
                # Format 4: text attribute
                if hasattr(msg, 'text') and msg.text:
                    logger.debug("Message has text attribute")
                    if isinstance(msg.text, dict) and 'value' in msg.text:
                        return msg.text['value']
                    elif hasattr(msg.text, 'value'):
                        return str(msg.text.value)
                    else:
                        return str(msg.text)
        
        logger.warning("No assistant response found in messages")
        return None
    
    except Exception as e:
        logger.error(f"Error extracting assistant response: {e}", exc_info=True)
        return None


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"
    
    logger.info(f"Starting SageAlpha.ai on port {port}")
    logger.info(f"Debug mode: {debug}")
    
    app.run(
        debug=debug,
        host="0.0.0.0",
        port=port,
        use_reloader=debug
    )