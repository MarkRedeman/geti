---
description: |
  This tutorial will guide you through the process of uploading media files to your server using the REST API.
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Uploading Media Files to the Server

Intel® Geti™ provides REST API endpoints for uploading media files (images and videos) to your datasets. This tutorial will guide you through the process of uploading these files, with a focus on handling both small and large files effectively.

:::info[Note]
Ensure that all [Prerequisites](./prerequisites.md) are met and that you have [obtained workspace and organization IDs](./obtain-ids.md) before proceeding with this tutorial.
:::


## Getting Project and Dataset IDs

Before uploading media, you need to identify which project and dataset the media should be added to. if you haven't yet created a project, you can use the [Create a Project](./create-a-project.md) guide for reference.

```python title="media-upload.py"
# Get projects in the workspace
projects_response = requests.get(
    BASE_URL + "projects",
    headers=headers,
    verify=certifi.where()
).json()

# Choose a project (first one in this example)
PROJECT_ID = projects_response["projects"][0]["id"] # Output: {your_project_id}

# Get project details to find the dataset ID
project_details = requests.get(
    BASE_URL + f"projects/{PROJECT_ID}",
    headers=headers,
    verify=certifi.where()
).json()

# Choose a dataset (using the first one in this example)
DATASET_ID = project_details["datasets"][0]["id"] # Output: {your_dataset_id}
```

## Uploading Media

Intel® Geti™ provides separate endpoints for uploading images and videos, but the process is similar for both. Here's a function that can handle both types of media:

```python title="media-upload.py" showLineNumbers
import os

def upload_media(file_path):
    """
    Upload a media file (image or video) to the dataset.

    Args:
        file_path: Path to the media file

    Returns:
        Response from the server containing the uploaded media details
    """
    # Determine if it's an image or video based on file extension
    ext = os.path.splitext(file_path)[1].lower()

    if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.jfif', '.webp']:
        media_type = "images"
    elif ext in ['.mp4', '.avi', '.mov', '.webm', '.mkv', '.m4v']:
        media_type = "videos"
    else:
        raise ValueError(f"Unsupported file extension: {ext}")

    # Open the file in binary mode
    with open(file_path, "rb") as media_file:
        upload_url = BASE_URL + f"projects/{PROJECT_ID}/datasets/{DATASET_ID}/media/{media_type}"

        # Send the POST request
        response = requests.post(
            upload_url,
            headers=headers,
            files={"file": media_file},
            verify=certifi.where()
        )

        if response.status_code == 200:
            print(f"Successfully uploaded {media_type[:-1]}: {file_path}")
            return response.json()
        else:
            print(f"Failed to upload {media_type[:-1]} (HTTP {response.status_code}): {response.text}")
            return None

# Example usage for image
image_response = upload_media("path/to/your/image.jpg")
if image_response:
    IMAGE_ID = image_response["id"]
    print(f"Uploaded image ID: {IMAGE_ID}")

# Example usage for video
video_response = upload_media("path/to/your/video.mp4")
if video_response:
    VIDEO_ID = video_response["id"]
    print(f"Uploaded video ID: {VIDEO_ID}")
```

The function above:
1. Determines the media type (image or video) based on the file extension
2. Uploads the file to the appropriate endpoint
3. Returns the server response containing the media details, including the assigned ID

## Advanced Multipart Uploads

When uploading media files, especially larger ones, you'll want to use [multipart encoding](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/POST#multipart_form_submission) for better control and reliability. While the standard `requests` library handles basic multipart uploads automatically, more complex scenarios benefit from using specialized libraries like `requests-toolbelt`.

### Why Use requests-toolbelt for Multipart Uploads?

The `requests-toolbelt` library provides several important benefits for media uploads:

1. **Progress tracking**: Allows you to monitor the upload progress and provide feedback to users
2. **Better control over headers**: Lets you set precise content types and metadata for your files
3. **Memory efficiency**: Can stream large files without loading them entirely into memory
4. **Improved error handling**: Makes it easier to recover from upload failures

Here's how to use it:

```python title="media-upload.py" showLineNumbers
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
import os

def upload_with_progress(file_path):
    """
    Upload a file using MultipartEncoder with progress monitoring.

    Args:
        file_path: Path to the file to upload

    Returns:
        Response from the server
    """
    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    # Determine media type
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']:
        media_type = "images"
    elif ext in ['.mp4', '.avi', '.mov', '.webm', '.mkv']:
        media_type = "videos"
    else:
        raise ValueError(f"Unsupported file extension: {ext}")

    # Create a MultipartEncoder
    with open(file_path, 'rb') as file:
        encoder = MultipartEncoder(
            fields={
                'file': (filename, file, 'application/octet-stream')
            }
        )

    # Create a monitor to track progress
    def progress_callback(monitor):
        progress = monitor.bytes_read / file_size * 100
        print(f"\rUploading: {progress:.2f}%", end="")

    monitor = MultipartEncoderMonitor(encoder, progress_callback)

    # Update headers with the encoder's content-type
    upload_headers = {
        **headers,
        'Content-Type': monitor.content_type
    }

    # Make the request
    upload_url = BASE_URL + f"projects/{PROJECT_ID}/datasets/{DATASET_ID}/media/{media_type}"
    response = requests.post(
        upload_url,
        data=monitor,
        headers=upload_headers,
        verify=certifi.where()
    )

    print()  # New line after progress bar

    if response.status_code == 200:
        print(f"Successfully uploaded file: {file_path}")
        return response.json()
    else:
        print(f"Failed to upload file: {response.text}")
        return None

# Example usage
media_response = upload_with_progress("path/to/your/large_video.mp4")
```

## Uploading Media with Label Assignments

When uploading media to classification projects, you can assign labels directly during the upload process. This saves time and streamlines your workflow by eliminating the need for a separate annotation step.

### Getting Label IDs

Before assigning labels, you need to retrieve the label IDs from your project:

```python title="media-upload.py" showLineNumbers
def get_project_labels(project_id):
    """
    Extract labels from project details response

    Args:
        project_id: The project ID to extract labels from

    Returns:
        A dictionary of labels with their IDs
    """
    response = requests.get(
        BASE_URL + f"projects/{project_id}",
        headers=headers,
        verify=certifi.where()
    )

    if response.status_code != 200:
        print(f"Failed to get project details: {response.text}")
        return None

    all_labels = {}

    # Extract tasks from the pipeline
    tasks = response.json().get('pipeline', {}).get('tasks', [])

    for task in tasks:
        if 'labels' in task:
            for label in task['labels']:
                all_labels[label['name']] = label['id']

    return all_labels

# Get the project labels
labels = get_project_labels(PROJECT_ID)
print("Labels in the project:")
for label_name, label_id in labels.items():
    print(f"Label: {label_name}, ID: {label_id}")
```

### Uploading Images with Label Assignments

You can upload media with label assignments using the `upload_info` parameter:

:::tip
Refer to [this REST doc](/docs/rest-api/openapi-specification#tag/media/POST/organizations/{organization_id}/workspaces/{workspace_id}/projects/{project_id}/datasets/{dataset_id}/media/images) for more details on upload request.
:::

```python title="media-upload.py" showLineNumbers
import json

def upload_media_with_labels(file_path, label_ids):
    """
    Upload a media file with label assignments

    Args:
        file_path: Path to the media file
        label_ids: List of label IDs to assign to the media

    Returns:
        Response from the server containing the uploaded media details
    """
    # Determine if it's an image or video based on file extension
    ext = os.path.splitext(file_path)[1].lower()

    if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.jfif', '.webp']:
        media_type = "images"
    elif ext in ['.mp4', '.avi', '.mov', '.webm', '.mkv', '.m4v']:
        media_type = "videos"
    else:
        raise ValueError(f"Unsupported file extension: {ext}")

    # Format the label IDs as JSON
    upload_info = json.dumps({"label_ids": label_ids})

    # Open the file in binary mode
    with open(file_path, "rb") as media_file:
        upload_url = BASE_URL + f"projects/{PROJECT_ID}/datasets/{DATASET_ID}/media/{media_type}"

        # Send the POST request with the file and labels
        response = requests.post(
            upload_url,
            headers=headers,
            files={
                "file": media_file,
                "upload_info": (None, upload_info)
            },
            verify=certifi.where()
        )

        if response.status_code == 200:
            print(f"Successfully uploaded {media_type[:-1]} with labels: {file_path}")
            return response.json()
        else:
            print(f"Failed to upload {media_type[:-1]}: {response.text}")
            return None
```

### Examples for Different Classification Scenarios

Depending on your project type, label assignments work differently:

<Tabs>
    <TabItem value="singleLabel" label="Single-Label Classification">

        ```python title="media-upload.py" showLineNumbers
        # For a single-label classification project, you provide exactly one label ID:
        cat_label_id = labels.get("cat")
        upload_media_with_labels("path/to/cat_image.jpg", [cat_label_id])
        ```

    </TabItem>
    <TabItem value="multiLabel" label="Multi-Label Classification">

        ```python title="media-upload.py" showLineNumbers
        # For multi-label classification, you can assign multiple labels to the same media:
        cat_label_id = labels.get("cat")
        pet_label_id = labels.get("pet")
        upload_media_with_labels("path/to/cat_image.jpg", [cat_label_id, pet_label_id])
        ```

    </TabItem>
    <TabItem value="anomalyDetection" label="Anomaly Detection">

        ```python title="media-upload.py" showLineNumbers
        # For an anomalous image, you can assign the "Anomalous" label
        anomalous_label_id = labels.get("Anomalous")
        upload_media_with_labels("path/to/defective_part.jpg", [anomalous_label_id])

        # For a normal image, you can assign the "Normal" label
        normal_label_id = labels.get("Normal")
        upload_media_with_labels("path/to/normal_part.jpg", [normal_label_id])
        ```

    </TabItem>
</Tabs>

The label assignment feature is particularly useful for:
- Pre-labeling media during the upload process
- Batch importing pre-labeled datasets
- Creating a test dataset with known ground truth
- Streamlining the annotation workflow for classification projects

:::info
Label assignment during upload only works for classification projects. For detection, segmentation, and other project types, you'll need to use the annotation endpoints after uploading the media.
:::

## Best Practices

1. **File Size Consideration**:
   - For files smaller than 100MB, use standard upload
   - For files larger than 100MB, use multipart upload with progress monitoring, as it allows for better handling of large files by splitting them into smaller parts, reducing the risk of upload failures and improving reliability.

2. **Supported Formats**:
   - Images: .jpg, .jpeg, .png, .bmp, .tiff, .jfif, .webp
   - Videos: .mp4, .avi, .mkv, .mov, .webm, .m4v

3. **Error Handling**: Always check the response status code and handle errors appropriately.

4. **Upload Monitoring**: For large files, implement progress tracking to keep users informed.

5. **Upload Optimization**:
   - Consider compressing large files before uploading
   - For videos, choose appropriate codecs and bitrates

The complete working script for uploading media files is available in the [media-upload.py](./scripts/media_upload.py).
