# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import json
import logging
import os
from pathlib import Path
import stat
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
            cfg = json.loads(self.config_path.read_text())
            cfg.setdefault("model_config_list", [])
            cfg.setdefault("mediapipe_config_list", [])
            return cfg
        return {"model_config_list": [], "mediapipe_config_list": []}

    def _is_graph_export(self, pipeline_name: str) -> bool:
        target_path = self.model_dir(pipeline_name)
        return (target_path / "graph.pbtxt").exists() and (target_path / "config.json").exists()

    def _load_graph_submodels(self, pipeline_name: str) -> list[dict]:
        config_path = self.model_dir(pipeline_name) / "config.json"
        if not config_path.exists():
            return []

        try:
            graph_cfg = json.loads(config_path.read_text())
        except json.JSONDecodeError:
            logger.warning(f"OVMS config: invalid graph subconfig for {pipeline_name}: {config_path}")
            return []

        submodels: list[dict] = []
        for item in graph_cfg.get("model_config_list", []):
            model_cfg = item.get("config", {})
            model_name = model_cfg.get("name")
            base_path = model_cfg.get("base_path")
            if not model_name or not base_path:
                continue

            absolute_base_path = base_path if str(base_path).startswith("/") else f"/models/{pipeline_name}/{base_path}"
            submodels.append(
                {
                    "config": {
                        **model_cfg,
                        "name": model_name,
                        "base_path": absolute_base_path,
                    }
                }
            )

        return submodels

    def _write(self, cfg: dict) -> None:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.config_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cfg, indent=2))
        tmp.replace(self.config_path)

    def add_model(self, pipeline_name: str) -> None:
        with _lock:
            cfg = self._read()
            model_config_list = cfg.get("model_config_list", [])
            mediapipe_config_list = cfg.get("mediapipe_config_list", [])

            model_config_list = [
                item for item in model_config_list if item.get("config", {}).get("name") != pipeline_name
            ]
            mediapipe_config_list = [item for item in mediapipe_config_list if item.get("name") != pipeline_name]
            model_config_list = [
                item
                for item in model_config_list
                if not str(item.get("config", {}).get("base_path", "")).startswith(f"/models/{pipeline_name}/")
            ]

            if self._is_graph_export(pipeline_name=pipeline_name):
                mediapipe_config_list.append({"name": pipeline_name})
                model_config_list.extend(self._load_graph_submodels(pipeline_name=pipeline_name))
            else:
                model_config_list.append(
                    {
                        "config": {
                            "name": pipeline_name,
                            "base_path": f"/models/{pipeline_name}",
                        }
                    }
                )

            cfg["model_config_list"] = model_config_list
            cfg["mediapipe_config_list"] = mediapipe_config_list
            self._write(cfg)
            logger.info(f"OVMS config: added model {pipeline_name}")

    def sync_model_directory(self, pipeline_name: str, source_dir: str | Path) -> None:
        source_path = Path(source_dir)
        target_path = self.model_dir(pipeline_name)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        # Ensure OVMS container user can traverse/read model directories from the
        # shared bind mount in compose mode.
        self.models_dir.chmod(
            self.models_dir.stat().st_mode
            | stat.S_IRUSR
            | stat.S_IWUSR
            | stat.S_IXUSR
            | stat.S_IRGRP
            | stat.S_IXGRP
            | stat.S_IROTH
            | stat.S_IXOTH
        )
        if target_path.exists():
            shutil.rmtree(target_path)
        shutil.copytree(source_path, target_path)

        # Normalize exported layout only for plain-model exports.
        # Graph exports rely on graph.pbtxt + config.json where nested model
        # directories are referenced by relative base_path values in subconfig.
        is_graph_export = (target_path / "graph.pbtxt").exists() and (target_path / "config.json").exists()

        # Some plain exports place IR files under <model_id>/1/, while OVMS expects
        # version directories directly under base_path (e.g. <base_path>/1/).
        has_numeric_versions = any(p.is_dir() and p.name.isdigit() for p in target_path.iterdir())
        if not is_graph_export and not has_numeric_versions:
            wrapped_model_dirs = [p for p in target_path.iterdir() if p.is_dir() and (p / "1" / "model.xml").exists()]
            if len(wrapped_model_dirs) == 1:
                wrapped_model_dir = wrapped_model_dirs[0]
                normalized_version_dir = target_path / "1"
                if normalized_version_dir.exists():
                    shutil.rmtree(normalized_version_dir)
                shutil.move(str(wrapped_model_dir / "1"), str(normalized_version_dir))
                if wrapped_model_dir.exists() and len(list(wrapped_model_dir.iterdir())) == 0:
                    wrapped_model_dir.rmdir()

        for directory in [target_path, *[p for p in target_path.rglob("*") if p.is_dir()]]:
            directory.chmod(0o755)
        for file_path in [p for p in target_path.rglob("*") if p.is_file()]:
            file_path.chmod(0o644)
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
            mediapipe_config_list = cfg.get("mediapipe_config_list", [])
            cfg["model_config_list"] = [
                item for item in model_config_list if item.get("config", {}).get("name") != pipeline_name
            ]
            cfg["model_config_list"] = [
                item
                for item in cfg["model_config_list"]
                if not str(item.get("config", {}).get("base_path", "")).startswith(f"/models/{pipeline_name}/")
            ]
            cfg["mediapipe_config_list"] = [item for item in mediapipe_config_list if item.get("name") != pipeline_name]
            self._write(cfg)
            logger.info(f"OVMS config: removed model {pipeline_name}")
