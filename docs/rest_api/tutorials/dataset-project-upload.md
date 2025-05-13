---
description: "Learn how to upload datasets and projects to Intel® Geti™ using the REST API, including standard and resumable (TUS) uploads, and how to import as a new project."
---

# Dataset & Project Upload

This tutorial explains how to upload dataset and project archives as ZIP files to Intel® Geti™ using the REST API, and how to import them. You have two primary methods for uploading:

1.  **Standard Upload:** This is a straightforward, single HTTP POST request. It's simpler to implement but less reliable for large files or unstable connections. If the connection drops, the entire upload fails and must be restarted from the beginning. It's suitable for smaller archives (typically under 100MB).
2.  **Resumable Upload (TUS protocol):** This method uses the [TUS protocol](https://tus.io/) to break the file into smaller chunks and upload them sequentially. It's more robust against network interruptions, as failed chunks can be retried, and the entire upload can be resumed if interrupted. This is the recommended method for large archives (over 100MB) or when network stability is a concern.

This guide covers both methods for datasets and projects.

:::info[Note]
Ensure that all [Prerequisites](./prerequisites.md) are met and that you have [obtained workspace and organization IDs](./obtain-ids.md) before proceeding with this tutorial.
:::

## Dataset Upload

Datasets can be uploaded and imported as new projects or to existing projects.

### File Upload

#### Standard Dataset Upload (for files < 100MB)

Use the standard upload endpoint for small dataset archives:

```python title="dataset-upload.py" showLineNumbers
import requests

BASE_URL = "https://your-geti-instance/api/v2/organizations/{organization_id}/workspaces/{workspace_id}/"
API_TOKEN = "your_api_token_here"
headers = {"x-api-key": API_TOKEN}

with open("my_dataset.zip", "rb") as f:
    response = requests.post(
        BASE_URL + "datasets/uploads",
        headers=headers,
        files={"file": f},
        verify=True
    )

if response.status_code == 200:
    file_id = response.json()["file_id"]
    print(f"Upload successful. File ID: {file_id}")
else:
    print(f"Upload failed: {response.text}")
```

#### Resumable Dataset Upload with TUS (for large files)

For large archives (>100MB), use the TUS protocol for resumable uploads. This allows you to resume interrupted uploads.

```python title="dataset-upload-tus.py" showLineNumbers
import os
from tusclient.client import TusClient

BASE_URL = "https://your-geti-instance/api/v2/organizations/{organization_id}/workspaces/{workspace_id}/"
API_TOKEN = "your_api_token_here"
headers = {"x-api-key": API_TOKEN}

file_path = "my_dataset.zip"
file_size = os.path.getsize(file_path)

# Create TUS client
tus_client = TusClient(
    BASE_URL + "datasets/uploads/resumable",
    headers=headers
)

# Create an uploader for this specific file
uploader = tus_client.uploader(
    file_path=file_path,
    chunk_size=10 * 1024 * 1024,  # 10MB chunks
    metadata={
        "filename": os.path.basename(file_path)
    }
)

# Upload the file
print(f"Starting upload of {file_path} ({file_size} bytes)")
uploader.upload()

# Get file_id from the URL
file_id = uploader.url.split("/")[-1]
print(f"Upload complete. File ID: {file_id}")
```

### Import Dataset

#### Prepare Dataset for Import

After uploading, prepare the dataset for import as a new project:

```python title="prepare-import.py" showLineNumbers
prepare_resp = requests.post(
    BASE_URL + "datasets:prepare-for-import",
    headers=headers,
    json={"file_id": file_id},
    verify=True
)
if prepare_resp.status_code == 200:
    job_id = prepare_resp.json().get("job_id")
    print(f"Prepare job started. Job ID: {job_id}")
else:
    print(f"Prepare failed: {prepare_resp.text}")
```

#### Import Dataset as a New Project

Once preparation is complete, import the dataset as a new project:

```python title="import-project.py" showLineNumbers
import_resp = requests.post(
    BASE_URL + "projects:import-from-dataset",
    headers=headers,
    json={
        "file_id": file_id,
        "project_name": "My Imported Project",
        "task_type": "classification",  # or detection, segmentation, etc.
        "labels": [{
            "name": "cat",
            "color": "#00ff00",
            "group": "default_detection"
        }]  # adjust as needed
    },
    verify=True
)
if import_resp.status_code == 200:
    job_id = import_resp.json().get("job_id")
    print(f"Import job started. Job ID: {job_id}")
else:
    print(f"Import failed: {import_resp.text}")
```

#### Import Dataset into an Existing Project

You can also import a dataset into an existing project:

```python title="import-to-existing.py" showLineNumbers
# First, prepare the dataset for the existing project
prepare_resp = requests.post(
    BASE_URL + f"projects/{project_id}/datasets:prepare-for-import",
    headers=headers,
    json={"file_id": file_id},
    verify=True
)

if prepare_resp.status_code == 200:
    job_id = prepare_resp.json().get("job_id")
    print(f"Prepare job started. Job ID: {job_id}")

    # Wait for the prepare job to complete...

    # Then import the dataset into the project
    import_resp = requests.post(
        BASE_URL + f"projects/{project_id}:import-from-dataset",
        headers=headers,
        json={
            "file_id": file_id,
            "dataset_name": "Imported Dataset",  # Name for the new dataset
            "labels_map": {
                "source_label_id": "target_label_id"  # Map source labels to target labels
            }
        },
        verify=True
    )

    if import_resp.status_code == 200:
        import_job_id = import_resp.json().get("job_id")
        print(f"Import job started. Job ID: {import_job_id}")
    else:
        print(f"Import failed: {import_resp.text}")
else:
    print(f"Prepare failed: {prepare_resp.text}")
```

## Project Upload

You can also upload complete project archives (including all datasets, models, and configurations) to Intel® Geti™ using the REST API. This is especially useful for migrating projects between environments or maintaining backups.

:::warning[Warning]
Maximum project archive size allowed for upload is 40GB.
:::

### Resumable Project Upload with TUS

Project archives are typically large, so it's recommended to always use the TUS protocol for resumable uploads:

```python title="project-upload-tus.py" showLineNumbers
import os
import time
from tusclient.client import TusClient

BASE_URL = "https://your-geti-instance/api/v2/organizations/{organization_id}/workspaces/{workspace_id}/"
API_TOKEN = "your_api_token_here"
headers = {"x-api-key": API_TOKEN}

file_path = "my_project.zip"

# Create TUS client
tus_client = TusClient(
    BASE_URL + "projects/uploads/resumable",
    headers=headers
)

# Create an uploader with progress reporting
uploader = tus_client.uploader(
    file_path=file_path,
    chunk_size=10 * 1024 * 1024,  # 10MB chunks
    metadata={
        "filename": os.path.basename(file_path)
    }
)

print(f"Starting upload of {file_path} ({uploader.file_size} bytes)")
try:
    uploader.upload()
    print("\nUpload complete!")
except Exception as e:
    print(f"\nUpload error: {str(e)}")
    print("You can resume this upload later using the same uploader")

# Get file_id from the URL
file_id = uploader.url.split("/")[-1]
print(f"Uploaded file_id: {file_id}")
```

:::info[Note]
You can also use the standard upload endpoint for smaller project archives, but TUS is recommended for larger files. Please refer to  the [Standard Dataset Upload](#standard-dataset-upload-for-files--100mb) section for the standard upload code. It will be similar to the project upload code except the endpoint will be `projects/uploads`.
:::

### Import the Project

After uploading, import the project archive:

```python title="import-full-project.py" showLineNumbers
import_resp = requests.post(
    BASE_URL + "projects:import",
    headers=headers,
    json={
        "file_id": file_id,
        # Optionally rename the project
        "project_name": "New Project Name"
    },
    verify=True
)

if import_resp.status_code == 200:
    job_id = import_resp.json().get("job_id")
    print(f"Project import job started. Job ID: {job_id}")
else:
    print(f"Project import failed: {import_resp.text}")
```

:::info[Note]
Next steps is general for both dataset and project import. Example code is provided for project upload, but the same applies to dataset upload.
:::

## Resume an Interrupted Upload

If an upload is interrupted, you can resume it using tus-py-client:

```python title="resume-tus-upload.py" showLineNumbers
import os
from tusclient.client import TusClient

BASE_URL = "https://your-geti-instance/api/v2/organizations/{organization_id}/workspaces/{workspace_id}/"
API_TOKEN = "your_api_token_here"
headers = {"x-api-key": API_TOKEN}

file_path = "my_project.zip"
previous_upload_url = "previous_upload_url_here"  # URL from a previous upload attempt

# Create TUS client
tus_client = TusClient(
    BASE_URL + "projects/uploads/resumable",
    headers=headers
)

# Create an uploader for the previously started upload
uploader = tus_client.uploader(
    file_path=file_path,
    chunk_size=10 * 1024 * 1024,
    url=previous_upload_url
)

print(f"Resuming upload of {file_path} from {uploader.offset} bytes")
uploader.upload()
print("\nUpload complete!")

# Get file_id from the URL
file_id = uploader.url.split("/")[-1]
print(f"Uploaded file_id: {file_id}")
```

## Pause or Cancel an Upload

To cancel an ongoing TUS upload using tus-py-client:

```python title="cancel-upload.py" showLineNumbers
# Assuming you have an existing uploader instance
uploader.stop_upload()  # Pause upload

# To delete/cancel completely
import requests

cancel_resp = requests.delete(
    uploader.url,
    headers={
        "x-api-key": API_TOKEN,
        "Tus-Resumable": "1.0.0"
    },
    verify=True
)

if cancel_resp.status_code == 204:
    print("Upload canceled successfully")
else:
    print(f"Failed to cancel upload: {cancel_resp.status_code}")
```

## Monitor Job Status

You can monitor the status of the import job using the `/jobs` endpoint:

```python title="monitor-job.py" showLineNumbers
def check_job_status(job_id):
    job_resp = requests.get(
        BASE_URL + f"jobs/{job_id}",
        headers=headers,
        verify=True
    )

    if job_resp.status_code == 200:
        job_data = job_resp.json()
        job_state = job_data.get("state", "")
        steps = job_data.get("steps", [])

        print(f"Job Status: {job_state}")

        if len(steps) > 0:
            step = steps[0]
            step_name = step.get("step_name", "")
            progress = max(step.get("progress", 0), 0)
            print(f"Step name: \"{step_name}\", progress: {progress}%")

        if job_state == "finished":
            # For import jobs, extract the new project ID from metadata
            metadata = job_data.get("metadata", {})
            if "project_id" in metadata:
                print(f"New Project ID: {metadata['project_id']}")

        return job_state
    else:
        print(f"Failed to get job status: {job_resp.status_code}")
        return None

# Poll job status until completion
def poll_until_complete(job_id, interval=5, max_tries=60):
    tries = 0
    while tries < max_tries:
        job_state = check_job_status(job_id)

        if job_state in ["finished", "failed", "canceled"]:
            print(f"Job finished with state: {job_state}")
            return job_state

        print(f"Waiting {interval} seconds for next update...")
        time.sleep(interval)
        tries += 1

    print(f"Polling timed out after {max_tries} attempts")
    return None

# Example usage
poll_until_complete(job_id)
```

---

## Tips & Code Examples

**Tips:**
- Use TUS for all datasets uploads to ensure reliability in case of instable connection, especially for files larger than 100MB.
- Use the job monitoring endpoints to track progress of import/export operations.
- When importing datasets into existing projects, carefully map the labels to ensure proper integration.
- For more details, see the [OpenAPI specification](/docs/rest-api/openapi-specification).

The complete code examples are available in the [dataset-project-upload.py](./scripts/dataset_project_upload.py).
