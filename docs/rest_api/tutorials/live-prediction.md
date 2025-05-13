---
description: "Learn how to use the Intel® Geti™ REST API for live inference, including loading images and uploading them to the live prediction endpoint."
---

# Live Prediction

This tutorial provides a step-by-step guide on using the Intel® Geti™ REST API for live inference in a simple Detection Project. According to the [Intel® Geti™ REST API documentation](https://docs.geti.intel.com/docs/rest-api/openapi-specification#tag/predictions/POST/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/pipelines/{pipeline_id}:predict), live inference requires sending a `POST` request to the `/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/pipelines/active:predict` endpoint.

:::info[Note]
Before proceeding with this tutorial, ensure that:
- All [Prerequisites](./prerequisites.md) are met.
- You have [Obtained Workspace and Organization IDs](./obtain-ids.md).
- You have successfully [Created a Project](create-a-project.md) and obtained the `project ID`.
- Media has been added to the dataset.
- The project has been annotated.
- The project has been successfully trained.
:::

## Load an Image

To perform inference, first load the image you want to send:

```python title="live-prediction.py" showLineNumbers
image_path = 'path/to/your/image.jpg'
with open(image_path, 'rb') as image_file:
    image_data = image_file.read()
```

## Send Image to Live Inference Endpoint

Define the API endpoint URL and headers, including your API key for authentication. Use the `requests` library to send a `POST` request with the image data. The `certifi.where` function is used to locate the root certificate for securing communication with the Intel® Geti™ Platform. 

```python title="live-prediction.py" showLineNumbers
BASE_URL = "https://your-geti-instance/api/v1/organizations/{organization_id}/workspaces/{workspace_id}"
API_TOKEN = "your_api_token_here"
headers = {"x-api-key": API_TOKEN}

requests.post(
    BASE_URL + f"/projects/{PROJECT_ID}/pipelines/active:predict",
    headers=headers,
    files={"file": image_data},
    verify=certifi.where()
)
```

## Understand the Predictions Output Structure

The predictions output contains the following key components:

- **Labels**: An array of labels describing the prediction. Each label includes:
    - **id**: The ID of the predicted label for the detected object.
    - **probability**: The estimated probability of the prediction.
- **Shape**: Describes the shape of the detected object. For a detection project, this is always a `RECTANGLE`, with:
    - **type**: The type of shape (e.g., `RECTANGLE`,`ROTATED_RECTANGLE`, `ELLIPSE`, `POLYGON` or `KEYPOINT`).
    - **x**: The x-coordinate of the rectangle's left side (in pixels).
    - **y**: The y-coordinate of the rectangle's top side (in pixels).
    - **width**: The width of the rectangle (in pixels).
    - **height**: The height of the rectangle (in pixels).
- **Created**: Creation date

```json showLineNumbers
{
  "predictions": [
    {
      "labels": [
        {
          "id": "{label_id}",
          "probability": 0.87
        }
      ],
      "shape": {
        "type": "RECTANGLE",
        "x": 25,
        "y": 40,
        "height": 34,
        "width": 28
      }
    }
  ],
  "created": "2021-09-08T12:43:22.290000+00:00"
}
```

The complete code examples can be found in the [live-prediction.py](./scripts/live_prediction.py) script.
