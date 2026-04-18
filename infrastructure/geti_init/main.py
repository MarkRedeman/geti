from __future__ import annotations

import logging
import os
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bson import ObjectId
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

from initial_user.create_initial_user import main as create_initial_user_main
from migration_job.create_s3_bucket import S3Client
from migration_job.mongodb_create_service_user import (
    _parse_roles,
    create_user,
    does_user_exist,
)
from migration_job.run_migration import run
from migration_job.utils import create_mongo_client

logger = logging.getLogger("geti_init")
logging.basicConfig(level=logging.INFO)

KAFKA_TOPICS = [
    "annotation_scenes_to_revisit",
    "configuration_changes",
    "dataset_counters_updated",
    "dataset_updated",
    "training_successful",
    "media_deletions",
    "media_preprocessing",
    "media_uploads",
    "new_annotation_scene",
    "predictions_and_metadata_created",
    "project_creations",
    "project_deletions",
    "project_updates",
    "thumbnail_video_missing",
    "model_activated",
    "workflow_event",
    "job_step_details",
    "job_update",
    "on_job_cancelled",
    "on_job_failed",
    "on_job_finished",
    "credits_lease",
]


def _wait_for_tcp(host: str, port: int, timeout_sec: int = 180) -> None:
    deadline = time.time() + timeout_sec
    delay = 0.5
    while time.time() < deadline:
        sock = socket.socket()
        sock.settimeout(2)
        try:
            sock.connect((host, port))
            return
        except OSError:
            time.sleep(delay)
            delay = min(delay * 1.5, 5)
        finally:
            sock.close()
    raise TimeoutError(f"Timed out waiting for {host}:{port}")


def _ensure_dex_db() -> None:
    dex_db = Path("/host_data/dex/dex.db")
    dex_db.parent.mkdir(parents=True, exist_ok=True)
    if dex_db.is_dir():
        for child in dex_db.iterdir():
            if child.is_file():
                child.unlink()
        dex_db.rmdir()
    if not dex_db.exists():
        dex_db.touch()
    dex_db.chmod(0o666)
    logger.info("Dex sqlite path prepared")


def _ensure_auth_proxy_certs() -> None:
    cert_dir = Path("/host_data/auth_proxy/certs")
    cert_dir.mkdir(parents=True, exist_ok=True)
    key = cert_dir / "tls.key"
    crt = cert_dir / "tls.crt"
    if key.exists() and crt.exists():
        key.chmod(0o644)
        crt.chmod(0o644)
        logger.info("Auth proxy certs already exist")
        return

    logger.info("Generating auth proxy certs")
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-nodes",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key),
            "-out",
            str(crt),
            "-days",
            "365",
            "-subj",
            "/CN=geti.localhost",
        ],
        check=True,
    )
    key.chmod(0o644)
    crt.chmod(0o644)


def _create_kafka_topics() -> None:
    kafka_address = os.environ.get("KAFKA_ADDRESS", "kafka:9092")
    logger.info("Creating kafka topics at %s", kafka_address)
    client = KafkaAdminClient(bootstrap_servers=kafka_address, client_id="geti_init")
    existing = set(client.list_topics())
    to_create = [
        NewTopic(name=t, num_partitions=1, replication_factor=1)
        for t in KAFKA_TOPICS
        if t not in existing
    ]
    if to_create:
        try:
            client.create_topics(new_topics=to_create, validate_only=False)
        except TopicAlreadyExistsError:
            logger.info("Kafka topics already exist")
    client.close()
    logger.info("Kafka topics initialized")


def _create_mongo_service_user() -> None:
    db_username_service = os.environ["DATABASE_USERNAME_SERVICE"]
    db_password_service = os.environ["DATABASE_PASSWORD_SERVICE"]
    roles = _parse_roles(os.environ["SERVICE_USER_ALL_DB_ROLES"])
    client = create_mongo_client()
    try:
        if does_user_exist(client, db_username_service):
            logger.info("Mongo service user already exists")
            return
        create_user(
            client=client,
            username=db_username_service,
            password=db_password_service,
            roles=roles,
        )
        logger.info("Mongo service user initialized")
    finally:
        client.close()


def _create_s3_buckets() -> None:
    client = S3Client(
        endpoint=os.environ["S3_ADDRESS"],
        access_key=os.environ["S3_ACCESS_KEY"],
        secret_key=os.environ["S3_SECRET_KEY"],
    )
    bucket_names = [b for b in os.environ["S3_BUCKET"].split(";") if b]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(client.create_bucket, bucket_names))
    logger.info("S3 buckets initialized")


def _seed_initial_user() -> str:
    user_id = create_initial_user_main()
    logger.info("Initial user seeded")
    return user_id


def _ensure_default_user_settings(user_id: str) -> None:
    client = create_mongo_client()
    db_name = os.environ.get("MONGODB_DATABASE_NAME", "geti")
    try:
        collection = client[db_name]["ui_settings"]
        existing_settings = collection.find_one(
            {"user_id": user_id, "project_id": {"$exists": False}}
        )
        if existing_settings is not None:
            logger.info("Default user settings already exist")
            return
        collection.insert_one({"_id": ObjectId(), "user_id": user_id, "settings": "{}"})
        logger.info("Default user settings initialized")
    finally:
        client.close()


def _seed_weights() -> None:
    if os.environ.get("INIT_SEED_WEIGHTS", "0").lower() not in {"1", "true", "yes"}:
        logger.info("Skipping weights seed")
        return

    from weights_uploader.weights_uploader import main as seed_weights_main

    logger.info("Seeding pretrained weights")
    os.environ.setdefault("S3_HOST", "s3:8333")
    os.environ.setdefault("WEIGHTS_DIR", "/tmp/geti-pretrained-weights")
    os.environ.setdefault(
        "CONFIG_DIR",
        "/workspace/infrastructure/geti_init/weights_uploader/pretrained_models",
    )
    seed_weights_main()


def main() -> None:
    logger.info("Starting single init service")

    _ensure_dex_db()
    _ensure_auth_proxy_certs()

    _wait_for_tcp("kafka", 9092)
    _wait_for_tcp("mongodb", 27017)
    _wait_for_tcp("s3", 8333)

    with ThreadPoolExecutor(max_workers=3) as pool:
        fut_kafka = pool.submit(_create_kafka_topics)
        fut_mongo = pool.submit(_create_mongo_service_user)
        fut_s3 = pool.submit(_create_s3_buckets)
        fut_kafka.result()
        fut_mongo.result()
        fut_s3.result()

    run(dry_run=False)

    _wait_for_tcp("platform_account", 5001)
    user_id = _seed_initial_user()
    _ensure_default_user_settings(user_id=user_id)
    _seed_weights()

    logger.info("Single init service completed")


if __name__ == "__main__":
    main()
