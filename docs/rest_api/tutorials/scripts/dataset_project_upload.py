# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import os
import time
from tusclient.client import TusClient

from session import session  # , BASE_URL
from obtain_ids import get_workspace_url


# Base URL for API calls
WORKSPACE_URL = get_workspace_url()


def upload_dataset_standard(file_path):
    """
    Upload a dataset using standard upload (for files < 100MB)

    Args:
        file_path: Path to the dataset archive file

    Returns:
        The file_id if successful, None otherwise
    """
    with open(file_path, "rb") as f:
        response = session.post(
            f"{WORKSPACE_URL}/datasets/uploads",
            files={"file": f},
        )

    if response.status_code == 200:
        file_id = response.json()["file_id"]
        print(f"Upload successful. File ID: {file_id}")
        return file_id
    else:
        print(f"Upload failed: {response.text}")
        return None


def upload_dataset_tus(file_path, chunk_size=10 * 1024 * 1024):
    """
    Upload a dataset using TUS protocol for resumable uploads (for files > 100MB)

    Args:
        file_path: Path to the dataset archive file
        chunk_size: Size of chunks in bytes (default: 10MB)

    Returns:
        The file_id if successful, None otherwise
    """
    # Create TUS client
    tus_client = TusClient(
        f"{WORKSPACE_URL}/datasets/uploads/resumable",
        headers=session.headers,
    )

    # Create an uploader for this specific file
    uploader = tus_client.uploader(
        file_path=file_path,
        chunk_size=chunk_size,
        metadata={"filename": os.path.basename(file_path)},
    )

    try:
        uploader.upload()
        print("\nUpload complete!")
    except Exception as e:
        print(f"\nUpload error: {str(e)}")
        print("You can resume this upload later using the same uploader")
        return None

    # Get file_id from the URL
    file_id = uploader.url.split("/")[-1]
    print(f"Upload complete. File ID: {file_id}")
    return file_id


def resume_tus_upload(file_path, previous_upload_url, chunk_size=10 * 1024 * 1024):
    """
    Resume an interrupted TUS upload

    Args:
        file_path: Path to the dataset archive file
        previous_upload_url: URL from a previous upload attempt
        chunk_size: Size of chunks in bytes (default: 10MB)

    Returns:
        The file_id if successful, None otherwise
    """
    # Create TUS client
    tus_client = TusClient(
        f"{WORKSPACE_URL}/datasets/uploads/resumable",
        headers=session.headers,
    )

    # Create an uploader for the previously started upload
    uploader = tus_client.uploader(
        file_path=file_path, chunk_size=chunk_size, url=previous_upload_url
    )

    try:
        uploader.upload()
        print("\nUpload complete!")
    except Exception as e:
        print(f"\nUpload error: {str(e)}")
        return None

    # Get file_id from the URL
    file_id = uploader.url.split("/")[-1]
    print(f"Uploaded file_id: {file_id}")
    return file_id


def upload_project_tus(file_path, chunk_size=10 * 1024 * 1024):
    """
    Upload a project archive using TUS protocol

    Args:
        file_path: Path to the project archive file
        chunk_size: Size of chunks in bytes (default: 10MB)

    Returns:
        The file_id if successful, None otherwise
    """
    # Create TUS client
    tus_client = TusClient(
        f"{WORKSPACE_URL}/projects/uploads/resumable",
        headers=session.headers,
    )

    # Create an uploader with progress reporting
    uploader = tus_client.uploader(
        file_path=file_path,
        chunk_size=chunk_size,
        metadata={"filename": os.path.basename(file_path)},
    )

    try:
        uploader.upload()
        print("\nUpload complete!")
    except Exception as e:
        print(f"\nUpload error: {str(e)}")
        print("You can resume this upload later using the same uploader")
        return None, uploader.url

    # Get file_id from the URL
    file_id = uploader.url.split("/")[-1]
    print(f"Uploaded file_id: {file_id}")
    return file_id, uploader.url


def cancel_tus_upload(upload_url):
    """
    Cancel an ongoing TUS upload

    Args:
        upload_url: URL of the ongoing upload

    Returns:
        True if successful, False otherwise
    """
    cancel_resp = session.delete(
        upload_url,
        headers={"Tus-Resumable": "1.0.0"},
    )

    if cancel_resp.status_code == 204:
        print("Upload canceled successfully")
        return True
    else:
        print(f"Failed to cancel upload: {cancel_resp.status_code}")
        return False


def prepare_dataset_for_import(file_id):
    """
    Prepare a dataset for import as a new project

    Args:
        file_id: The file ID of the uploaded dataset

    Returns:
        The job_id if successful, None otherwise
    """
    prepare_resp = session.post(
        f"{WORKSPACE_URL}/datasets:prepare-for-import?file_id={file_id}",
    )

    if prepare_resp.status_code == 200:
        job_id = prepare_resp.json().get("job_id")
        print(f"Prepare job started. Job ID: {job_id}")
        return job_id
    else:
        print(f"Prepare failed: {prepare_resp.text}")
        return None


def import_dataset_as_new_project(file_id, project_name, task_type, labels):
    """
    Import a dataset as a new project

    Args:
        file_id: The file ID of the uploaded dataset
        project_name: Name for the new project
        task_type: Type of task (classification, detection, segmentation, etc.)
        labels: List of labels for the project

    Returns:
        The job_id if successful, None otherwise
    """
    import_resp = session.post(
        f"{WORKSPACE_URL}/projects:import-from-dataset",
        json={
            "file_id": file_id,
            "project_name": project_name,
            "task_type": task_type,
            "labels": labels,
        },
    )

    if import_resp.status_code == 200:
        job_id = import_resp.json().get("job_id")
        print(f"Import job started. Job ID: {job_id}")
        return job_id
    else:
        print(f"Import failed: {import_resp.text}")
        return None


def import_dataset_to_existing_project(
    file_id, project_id, dataset_name, labels_map=None
):
    """
    Import a dataset into an existing project

    Args:
        file_id: The file ID of the uploaded dataset
        project_id: ID of the existing project
        dataset_name: Name for the imported dataset
        labels_map: Dictionary mapping source label IDs to target label IDs

    Returns:
        The job_id if successful, None otherwise
    """
    # First, prepare the dataset for the existing project
    prepare_resp = session.post(
        f"{WORKSPACE_URL}/projects/{project_id}/datasets:prepare-for-import",
        json={"file_id": file_id},
    )

    if prepare_resp.status_code == 200:
        job_id = prepare_resp.json().get("job_id")
        print(f"Prepare job started. Job ID: {job_id}")

        # Wait for the prepare job to complete
        job_state = poll_until_complete(job_id)

        if job_state == "COMPLETED":
            # Then import the dataset into the project
            import_data = {"file_id": file_id, "dataset_name": dataset_name}

            if labels_map:
                import_data["labels_map"] = labels_map

            import_resp = session.post(
                f"{WORKSPACE_URL}/projects/{project_id}:import-from-dataset",
                json=import_data,
            )

            if import_resp.status_code == 200:
                import_job_id = import_resp.json().get("job_id")
                print(f"Import job started. Job ID: {import_job_id}")
                return import_job_id
            else:
                print(f"Import failed: {import_resp.text}")
                return None
        else:
            print(f"Prepare job did not complete successfully: {job_state}")
            return None
    else:
        print(f"Prepare failed: {prepare_resp.text}")
        return None


def import_project(file_id, new_project_name=None):
    """
    Import a project archive

    Args:
        file_id: The file ID of the uploaded project archive
        new_project_name: Optional new name for the imported project

    Returns:
        The job_id if successful, None otherwise
    """
    import_data = {"file_id": file_id}

    if new_project_name:
        import_data["project_name"] = new_project_name

    import_resp = session.post(
        f"{WORKSPACE_URL}/projects:import",
        json=import_data,
    )

    if import_resp.status_code == 200:
        job_id = import_resp.json().get("job_id")
        print(f"Project import job started. Job ID: {job_id}")
        return job_id
    else:
        print(f"Project import failed: {import_resp.text}")
        return None


def check_job_status(job_id):
    """
    Check the status of a job

    Args:
        job_id: The ID of the job to check

    Returns:
        The job state if successful, None otherwise
    """
    job_resp = session.get(
        f"{WORKSPACE_URL}/jobs/{job_id}",
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
            print(f'Step name: "{step_name}", progress: {progress}%')

        if job_state == "finished":
            # For import jobs, extract the new project ID from metadata
            metadata = job_data.get("metadata", {})
            if "project_id" in metadata:
                print(f"New Project ID: {metadata['project_id']}")

        return job_state
    else:
        print(f"Failed to get job status: {job_resp.status_code}")
        return None


def poll_until_complete(job_id, interval=5, max_tries=60):
    """
    Poll job status until completion

    Args:
        job_id: The ID of the job to poll
        interval: Polling interval in seconds
        max_tries: Maximum number of polling attempts

    Returns:
        The final job state if completed, None if timed out
    """
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
if __name__ == "__main__":
    # Example: Dataset upload
    print("\n--- UPLOADING DATASET ---")
    file_path = "./data/project-dataset.zip"
    file_size = os.path.getsize(file_path)

    # Choose upload method based on file size
    if file_size < 100 * 1024 * 1024:  # Less than 100MB
        print("Using standard upload")
        file_id = upload_dataset_standard(file_path)
    else:
        print("Using TUS resumable upload")
        file_id = upload_dataset_tus(file_path)

    if file_id:
        # Example: Prepare dataset for import
        print("\n--- PREPARING DATASET FOR IMPORT ---")
        job_id = prepare_dataset_for_import(file_id)

        if job_id:
            # Wait for preparation to complete
            print("\n--- WAITING FOR PREPARATION TO COMPLETE ---")
            job_state = poll_until_complete(job_id)

            if job_state == "finished":
                # Example: Import dataset as new project
                print("\n--- IMPORTING DATASET AS NEW PROJECT ---")
                import_job_id = import_dataset_as_new_project(
                    file_id=file_id,
                    project_name="Dataset Import Test",
                    task_type="detection",
                    labels=[
                        {
                            "name": "asdf",
                            "color": "#00ff00",
                            "group": "default_detection",
                        }
                    ],
                )

                if import_job_id:
                    print("\n--- WAITING FOR IMPORT TO COMPLETE ---")
                    poll_until_complete(import_job_id)

    # Example: Project upload with TUS
    print("\n--- UPLOADING PROJECT ARCHIVE ---")
    project_file_path = "./data/card-classification.zip"
    project_file_id, upload_url = upload_project_tus(project_file_path)

    if project_file_id:
        # Example: Import project
        print("\n--- IMPORTING PROJECT ---")
        project_import_job_id = import_project(
            file_id=project_file_id, new_project_name="Project Import Test"
        )

        if project_import_job_id:
            print("\n--- WAITING FOR PROJECT IMPORT TO COMPLETE ---")
            poll_until_complete(project_import_job_id)
