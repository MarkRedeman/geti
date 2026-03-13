# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import json
import logging
import os
from pathlib import Path
import shutil
import threading

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class OvmsConfigManager:
    """Manage OVMS models.json for compose-mode hot-reload."""

    def __init__(self) -> None:
        models_dir = os.environ.get("OVMS_MODELS_DIR", "/ovms_models")
        self.models_dir = Path(models_dir)
        self.config_path = self.models_dir / "models.json"

    def model_dir(self, pipeline_name: str) -> Path:
        return self.models_dir / pipeline_name

    def _read(self) -> dict:
        if self.config_path.exists():
            return json.loads(self.config_path.read_text())
        return {"model_config_list": []}

    def _write(self, cfg: dict) -> None:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.config_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cfg, indent=2))
        tmp.replace(self.config_path)

    def add_model(self, pipeline_name: str) -> None:
        with _lock:
            cfg = self._read()
            model_config_list = cfg.get("model_config_list", [])
            names = {item.get("config", {}).get("name") for item in model_config_list if isinstance(item, dict)}
            if pipeline_name in names:
                return
            model_config_list.append(
                {
                    "config": {
                        "name": pipeline_name,
                        "base_path": f"/models/{pipeline_name}",
                    }
                }
            )
            cfg["model_config_list"] = model_config_list
            self._write(cfg)
            logger.info(f"OVMS config: added model {pipeline_name}")

    def sync_model_directory(self, pipeline_name: str, source_dir: str | Path) -> None:
        source_path = Path(source_dir)
        target_path = self.model_dir(pipeline_name)
        if target_path.exists():
            shutil.rmtree(target_path)
        shutil.copytree(source_path, target_path)
        logger.info(f"OVMS config: synced model directory for {pipeline_name}")

    def remove_model_directory(self, pipeline_name: str) -> None:
        target_path = self.model_dir(pipeline_name)
        if target_path.exists():
            shutil.rmtree(target_path)
            logger.info(f"OVMS config: removed model directory for {pipeline_name}")

    def remove_model(self, pipeline_name: str) -> None:
        with _lock:
            cfg = self._read()
            model_config_list = cfg.get("model_config_list", [])
            cfg["model_config_list"] = [
                item for item in model_config_list if item.get("config", {}).get("name") != pipeline_name
            ]
            self._write(cfg)
            logger.info(f"OVMS config: removed model {pipeline_name}")
