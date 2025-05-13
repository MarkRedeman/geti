# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from session import session, BASE_URL


def get_workspace_identifier():
    organization_response = session.get(
        f"{BASE_URL}/personal_access_tokens/organization"
    ).json()

    # Save the organization ID for future use
    ORGANIZATION_ID = organization_response["organizationId"]

    workspaces_response = session.get(
        f"{BASE_URL}/organizations/{ORGANIZATION_ID}/workspaces"
    ).json()

    WORKSPACE_ID = workspaces_response["workspaces"][0]["id"]

    return (ORGANIZATION_ID, WORKSPACE_ID)


def get_workspace_url():
    (ORGANIZATION_ID, WORKSPACE_ID) = get_workspace_identifier()

    return f"{BASE_URL}/organizations/{ORGANIZATION_ID}/workspaces/{WORKSPACE_ID}"


print(get_workspace_url())
