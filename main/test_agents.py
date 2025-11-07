from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

sub = "07d6f50a-2271-43a0-b6fa-5ad5e769ff67"
rg  = "openai-personal-rg"
endpoint = "https://sagea-mhlblh5n-eastus2.services.ai.azure.com"

print("Connecting…")
client = AIProjectClient(
    credential=DefaultAzureCredential(),
    subscription_id=sub,
    resource_group_name=rg,
    project_name=None,   # leave None to list
    endpoint=endpoint
)

try:
    projects = client.projects.list()
    print("\nProjects visible under this subscription/resource group:")
    for p in projects:
        print("→", p.name)
except Exception as e:
    print("❌  Error listing projects:", e)
