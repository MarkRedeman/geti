---
description: Learn how to obtain organization and workspace IDs in Intel® Geti™ for seamless project interaction using REST API endpoints.
---

# Obtain the Organization and Workspace IDs

:::info[Note]
Ensure that all [Prerequisites](./prerequisites.md) are met before proceeding with the steps described in this tutorial.
:::

:::info[Note]
You can also retrieve `organization_id` and `workspace_id` from URL when using Intel® Geti™ UI.

When logging in to Intel® Geti™ you will be redirected to the main page, being the default workspace of your organization.

`<YOUR_HOST_ADDRESS>/organizations/{organization_id}/workspaces/{workspace_id}`
:::

Within Intel® Geti™, projects belong to workspace, and workspace belongs to organizations. Currently we support one workspace per organization.

To interact with a project, we need to determine the `organization_id` and `workspace_id` that it belongs to.

A `GET` request to the `personal_access_tokens/organization` endpoint will return a response containing the ID of the organization that you have access to.

`certifi.where` is used to locate the root certificate that will be used for securing communication with the Intel® Geti™ Platform. If your certificate is not accepted by the server, you can disable the SSL verification (for testing purposes) by setting the `verify` parameter to `False`.

```python title="obtain-ids.py" showLineNumbers
import certifi
import requests

HOST = "https://app.geti.intel.com/"
TOKEN = "{YOUR_API_KEY}"

# Following the information from the API documentation, append the API version to the host URL.
# All endpoints include the API version in their address and rely on this variable.
HOST = HOST + "api/v1/"

# Include the `x-api-key` header in all API calls to authenticate requests.
headers = {"x-api-key": TOKEN}

response = requests.get(
    HOST + "personal_access_tokens/organization", headers=headers, verify=certifi.where()
).json()

# Save the organization ID for future use
ORG_ID = response["organizationId"] # Output: "{your_org_id}"
```

Click [here to view the response specification](/docs/rest-api/openapi-specification#tag/organizations/GET/personal_access_tokens/organization) for the organization endpoint.

After that, you can call the `GET /organizations/{organization_id}/workspaces/` endpoint to get the list of workspaces in the organization. Choose the workspace you want to use and get the `workspace_id` from the response.

```python showLineNumbers
response = requests.get(
    HOST + f"organizations/{ORG_ID}/workspaces", headers=headers, verify=certifi.where()
).json()

WORKSPACE_ID = response["workspaces"][0]["id"] # Output: "{your_workspace_id}"
```

Click [here to view the response specification](/docs/rest-api/openapi-specification#tag/workspaces/GET/organizations/{organization_id}/workspaces) for the workspaces endpoint.

Let's update the base URL, adding the `organization_id`, and `workspace_id` to the HOST name, it will shorten the URL for the following requests.

```python showLineNumbers
BASE_URL = HOST + "organizations/" + ORG_ID + "/" + "workspaces/" + WORKSPACE_ID + "/"

print(BASE_URL) # Output: https://app.geti.intel.com/api/v1/organizations/{your_org_id}/workspaces/{your_workspace_id}/
```