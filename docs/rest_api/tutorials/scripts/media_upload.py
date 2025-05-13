# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import os
import json
from session import session
from obtain_ids import get_workspace_url
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

print("\n=== Intel® Geti™ Media Upload Example ===\n")
WORKSPACE_URL = get_workspace_url()

# Get projects in the workspace
print("Getting projects in workspace...")
projects_response = session.get(f"{WORKSPACE_URL}/projects").json()

# Choose a project (first one in this example)
PROJECT_ID = projects_response["projects"][0]["id"]
print(f"Selected project ID: {PROJECT_ID}")

# Get project details to find the dataset ID
print("Getting project details...")
PROJECT_URL = f"{WORKSPACE_URL}/projects/{PROJECT_ID}"
project_details = session.get(PROJECT_URL).json()


# Choose a dataset (using the first one in this example)
DATASET_ID = project_details["datasets"][0]["id"]
print(f"Selected dataset ID: {DATASET_ID}")


def load_image(image_path):
    """Load an image from the specified path."""
    with open(image_path, "rb") as image_file:
        return image_file.read()


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

    if ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".jfif", ".webp"]:
        media_type = "images"
    elif ext in [".mp4", ".avi", ".mov", ".webm", ".mkv", ".m4v"]:
        media_type = "videos"
    else:
        raise ValueError(f"Unsupported file extension: {ext}")

    print(f"Uploading {media_type[:-1]}: {file_path}...")

    # Open the file in binary mode
    with open(file_path, "rb") as media_file:
        # Send the POST request
        upload_url = f"{WORKSPACE_URL}/projects/{PROJECT_ID}/datasets/{DATASET_ID}/media/{media_type}"
        response = session.post(upload_url, files={"file": media_file})

        if response.status_code == 200:
            print(f"Successfully uploaded {media_type[:-1]}: {file_path}")
            return response.json()
        else:
            print(
                f"Failed to upload {media_type[:-1]} (HTTP {response.status_code}): {response.text}"
            )
            return None


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
    if ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]:
        media_type = "images"
    elif ext in [".mp4", ".avi", ".mov", ".webm", ".mkv"]:
        media_type = "videos"
    else:
        raise ValueError(f"Unsupported file extension: {ext}")

    print(f"Starting upload with progress tracking for {file_path}...")

    # Create a monitor to track progress
    def progress_callback(monitor):
        progress = monitor.bytes_read / file_size * 100
        print(f"\rUploading: {progress:.2f}%", end="")

    # Create a MultipartEncoder
    with open(file_path, "rb") as file:
        encoder = MultipartEncoder(
            fields={"file": (filename, file, "application/octet-stream")}
        )

        monitor = MultipartEncoderMonitor(encoder, progress_callback)

        # Make the request
        upload_url = f"{WORKSPACE_URL}/projects/{PROJECT_ID}/datasets/{DATASET_ID}/media/{media_type}"
        response = session.post(
            upload_url,
            data=monitor,
            # Update headers with the encoder's content-type
            headers={"Content-Type": monitor.content_type},
        )

        print()  # New line after progress bar

        if response.status_code == 200:
            print(f"Successfully uploaded file: {file_path}")
            return response.json()
        else:
            print(f"Failed to upload file: {response.text}")
            return None


def get_project_labels(project_id):
    """
    Extract labels from project details response

    Args:
        project_id: The project ID to extract labels from

    Returns:
        A dictionary of labels with their IDs
    """
    print(f"Getting labels for project {project_id}...")

    response = session.get(
        f"{WORKSPACE_URL}/projects/{project_id}",
    )

    if response.status_code != 200:
        print(f"Failed to get project details: {response.text}")
        return None

    all_labels = {}

    # Extract tasks from the pipeline
    tasks = response.json().get("pipeline", {}).get("tasks", [])

    for task in tasks:
        if "labels" in task:
            for label in task["labels"]:
                all_labels[label["name"]] = label["id"]

    return all_labels


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

    if ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".jfif", ".webp"]:
        media_type = "images"
    elif ext in [".mp4", ".avi", ".mov", ".webm", ".mkv", ".m4v"]:
        media_type = "videos"
    else:
        raise ValueError(f"Unsupported file extension: {ext}")

    print(f"Uploading {media_type[:-1]} with labels: {file_path}...")

    # Format the label IDs as JSON
    upload_info = json.dumps({"label_ids": label_ids})

    # Open the file in binary mode
    with open(file_path, "rb") as media_file:
        upload_url = f"{WORKSPACE_URL}/projects/{PROJECT_ID}/datasets/{DATASET_ID}/media/{media_type}"

        # Send the POST request with the file and labels
        response = session.post(
            upload_url,
            files={"file": media_file, "upload_info": (None, upload_info)},
        )

        if response.status_code == 200:
            print(f"Successfully uploaded {media_type[:-1]} with labels: {file_path}")
            return response.json()
        else:
            print(f"Failed to upload {media_type[:-1]}: {response.text}")
            return None


# Main execution starts here

# Example 1: Basic image upload
print("\n=== Basic Media Upload Example ===")
image_path = "./data/card.jpeg"
image_response = upload_media(image_path)
if image_response:
    IMAGE_ID = image_response["id"]
    print(f"Uploaded image ID: {IMAGE_ID}")


# Example 2: Basic video upload
video_path = "./data/video.mp4"
video_response = upload_media(video_path)
if video_response:
    VIDEO_ID = video_response["id"]
    print(f"Uploaded video ID: {VIDEO_ID}")


# Example 3: Uploading with progress tracking
print("\n=== Upload with Progress Tracking Example ===")
large_video_path = "./data/video.mp4"
media_response = upload_with_progress(large_video_path)
if media_response:
    print(f"Uploaded media ID: {media_response['id']}")

# Example 4: Uploading with label assignments
print("\n=== Upload with Label Assignments Example ===")
# Get the project labels
labels = get_project_labels(PROJECT_ID)
if labels:
    print("Labels in the project:")
    for label_name, label_id in labels.items():
        print(f"Label: {label_name}, ID: {label_id}")

    # Examples for different classification scenarios
    print("\n=== Label Assignment Examples ===")

    # Single-label classification
    cat_image_path = "./data/card.jpeg"
    cat_label_id = labels.get("Q")
    if cat_label_id:
        cat_response = upload_media_with_labels(cat_image_path, [cat_label_id])
        if cat_response:
            print(f"Uploaded cat image with ID: {cat_response['id']}")

    # Multi-label classification
    pet_image_path = "./data/card.jpeg"
    cat_label_id = labels.get("Q")
    pet_label_id = labels.get("Clubs")
    if cat_label_id and pet_label_id:
        pet_response = upload_media_with_labels(
            pet_image_path, [cat_label_id, pet_label_id]
        )
        if pet_response:
            print(f"Uploaded pet image with ID: {pet_response['id']}")

    # Anomaly detection
    defect_image_path = "./data/defective_part.jpg"
    normal_image_path = "./data/normal_part.jpg"
    anomalous_label_id = labels.get("Anomalous")
    normal_label_id = labels.get("Normal")

    if anomalous_label_id:
        anomaly_response = upload_media_with_labels(
            defect_image_path, [anomalous_label_id]
        )
        if anomaly_response:
            print(f"Uploaded anomalous image with ID: {anomaly_response['id']}")

    if normal_label_id:
        normal_response = upload_media_with_labels(normal_image_path, [normal_label_id])
        if normal_response:
            print(f"Uploaded normal image with ID: {normal_response['id']}")
