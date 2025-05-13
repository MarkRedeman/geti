# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from os import getenv

from session import session, BASE_URL


def load_image(image_path):
    """Load an image from the specified path."""
    with open(image_path, "rb") as image_file:
        return image_file.read()


def send_image_for_inference(image_data):
    """Send the image data to the live inference endpoint."""

    ORG_ID = getenv("ORGANIZATION_ID")
    WORKSPACE_ID = getenv("WORKSPACE_ID")
    PROJECT_ID = getenv("PROJECT_ID")

    # Base URL for API calls
    WORKSPACE_URL = f"{BASE_URL}/organizations/{ORG_ID}/workspaces/{WORKSPACE_ID}"

    url = f"{WORKSPACE_URL}/projects/{PROJECT_ID}/pipelines/active:predict"
    response = session.post(
        url,
        files={"file": image_data},
    )

    return response


# Example usage
if __name__ == "__main__":
    # Load the image
    image_path = "./data/card.jpeg"
    image_data = load_image(image_path)

    # Send the image for inference
    response = send_image_for_inference(image_data)

    # Check the response
    print(response.json())
