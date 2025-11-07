"""
Comprehensive Azure Agent Debugging Script
Run this to identify what's wrong with your Azure setup
"""

import os
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
import traceback

# Load environment variables
load_dotenv()

print("=" * 60)
print("🔍 STEP 1: Checking Environment Variables")
print("=" * 60)

subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
resource_group_name = os.getenv("AZURE_RESOURCE_GROUP")
project_name = os.getenv("AZURE_PROJECT_NAME")
endpoint = os.getenv("AZURE_PROJECT_ENDPOINT")
agent_id = os.getenv("AZURE_AGENT_ID")

vars_to_check = {
    "AZURE_SUBSCRIPTION_ID": subscription_id,
    "AZURE_RESOURCE_GROUP": resource_group_name,
    "AZURE_PROJECT_NAME": project_name,
    "AZURE_PROJECT_ENDPOINT": endpoint,
    "AZURE_AGENT_ID": agent_id,
}

for var_name, var_value in vars_to_check.items():
    status = "✓" if var_value else "✗"
    display_value = var_value[:50] + "..." if var_value and len(var_value) > 50 else var_value
    print(f"{status} {var_name}: {display_value}")

missing_vars = [k for k, v in vars_to_check.items() if not v]
if missing_vars:
    print(f"\n❌ MISSING VARIABLES: {', '.join(missing_vars)}")
    print("Fix your .env file and retry.\n")
    exit(1)

print("\n" + "=" * 60)
print("🔍 STEP 2: Authenticating with Azure")
print("=" * 60)

try:
    credential = DefaultAzureCredential()
    print("✓ DefaultAzureCredential initialized")
    
    # Try to get a token to verify credentials work
    token = credential.get_token("https://management.azure.com/.default")
    print("✓ Successfully obtained Azure token")
except Exception as e:
    print(f"✗ Authentication failed: {e}")
    print("\nFix: Run 'az login' and make sure you're authenticated")
    exit(1)

print("\n" + "=" * 60)
print("🔍 STEP 3: Connecting to AIProjectClient")
print("=" * 60)

try:
    client = AIProjectClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        project_name=project_name,
        endpoint=endpoint
    )
    print("✓ AIProjectClient initialized successfully")
except Exception as e:
    print(f"✗ Failed to create AIProjectClient: {e}")
    traceback.print_exc()
    exit(1)

print("\n" + "=" * 60)
print("🔍 STEP 4: Listing Available Projects")
print("=" * 60)

try:
    projects = client.projects.list()
    project_list = list(projects)
    
    if not project_list:
        print("⚠️  No projects found in this subscription/resource group")
    else:
        print(f"✓ Found {len(project_list)} project(s):")
        for p in project_list:
            print(f"  → {p.name} (ID: {getattr(p, 'id', 'N/A')})")
            if p.name == project_name:
                print(f"    ✓ This matches your AZURE_PROJECT_NAME")
except Exception as e:
    print(f"✗ Failed to list projects: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("🔍 STEP 5: Verifying Agent Exists")
print("=" * 60)

try:
    agent = client.agents.get(agent_id)
    print(f"✓ Agent found: {agent.id}")
    print(f"  Name: {getattr(agent, 'name', 'N/A')}")
    print(f"  Model: {getattr(agent, 'model', 'N/A')}")
except Exception as e:
    print(f"✗ Agent not found or error retrieving: {e}")
    print(f"\nTrying to list all agents in the project...")
    
    try:
        agents = client.agents.list()
        agent_list = list(agents)
        
        if not agent_list:
            print("❌ NO AGENTS FOUND in this project")
            print("\nYou need to create an agent first!")
            print("See: https://learn.microsoft.com/en-us/azure/ai-services/agents/")
        else:
            print(f"✓ Found {len(agent_list)} agent(s):")
            for a in agent_list:
                print(f"  → {a.id}")
                if hasattr(a, 'name'):
                    print(f"    Name: {a.name}")
    except Exception as list_error:
        print(f"✗ Failed to list agents: {list_error}")
        traceback.print_exc()

print("\n" + "=" * 60)
print("🔍 STEP 6: Test Agent Call")
print("=" * 60)

try:
    print("Creating thread...")
    thread = client.agents.threads.create()
    print(f"✓ Thread created: {thread.id}")
    
    print("Sending test message...")
    client.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content="Hello, what is 2+2?"
    )
    print("✓ Message sent")
    
    print("Running agent...")
    run = client.agents.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent_id
    )
    print(f"✓ Run completed with status: {run.status}")
    
    if run.status == "failed":
        print(f"❌ Run failed: {run.last_error}")
    else:
        print("✓ Getting agent response...")
        messages = client.agents.messages.list(thread_id=thread.id)
        
        for msg in messages:
            if msg.role == "assistant":
                print(f"✓ Assistant response received")
                # Try different ways to access the content
                if hasattr(msg, 'content'):
                    print(f"  Content: {msg.content}")
                elif hasattr(msg, 'text_messages'):
                    print(f"  Text messages found: {len(msg.text_messages)}")
                    for text_msg in msg.text_messages:
                        if hasattr(text_msg, 'value'):
                            print(f"  Value: {text_msg.value}")
                break
                
except Exception as e:
    print(f"✗ Test failed: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("✅ Debug Complete!")
print("=" * 60)