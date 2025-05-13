# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from session import session, TOKEN, BASE_URL

# Include the `x-api-key` header in all API calls to authenticate requests.
headers = {"x-api-key": TOKEN}

organization_response = session.get(
    f"{BASE_URL}/personal_access_tokens/organization"
).json()

# Save the organization ID for future use
ORG_ID = organization_response["organizationId"]

workspaces_response = session.get(
    f"{BASE_URL}/organizations/{ORG_ID}/workspaces"
).json()

# Save the workspace ID for future use
WORKSPACE_ID = workspaces_response["workspaces"][0]["id"]

WORKSPACE_URL = f"{BASE_URL}/organizations/{ORG_ID}/workspaces/{WORKSPACE_ID}"

# Creating a detection project
project_name = "VEHICLE DETECTION PROJECT"
tasks = [
    {
        "task_type": "dataset",
        "title": "Dataset",
    },
    {
        "task_type": "detection",
        "title": "Detection Task",
        "labels": [
            {
                "name": "Vehicle",
                "color": "#ff0000",
                "group": "default_detection",
            },
        ],
    },
]
connections = [
    {
        "from": "Dataset",
        "to": "Detection Task",
    },
]

project_creation_request_data = {
    "name": project_name,
    "pipeline": {
        "connections": connections,
        "tasks": tasks,
    },
}

response = session.post(f"{WORKSPACE_URL}/projects", json=project_creation_request_data)
project_dict = response.json()
