# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import os

import pytest
from iai_core.entities.model import TrainingFramework, TrainingFrameworkType

from jobs_common.runtime_helpers.trainer_image_info import TrainerImageInfo


class TestTrainerImageInfo:
    def test_create_compose_uses_runtime_env(self, monkeypatch):
        monkeypatch.setenv("TRAINER_RUNTIME_IMAGE", "registry/otx2:compose")
        monkeypatch.setenv("TRAINER_RENDER_GID", "1001")
        training_framework = TrainingFramework(type=TrainingFrameworkType.OTX, version="2.1.0")

        trainer_image_info = TrainerImageInfo.create(training_framework)

        assert trainer_image_info.to_image_full_name() == "registry/otx2:compose"
        assert trainer_image_info.render_gid == 1001

    def test_create_compose_requires_runtime_image(self, monkeypatch):
        monkeypatch.delenv("TRAINER_RUNTIME_IMAGE", raising=False)
        training_framework = TrainingFramework(type=TrainingFrameworkType.OTX, version="2.1.0")

        with pytest.raises(ValueError, match="TRAINER_RUNTIME_IMAGE"):
            _ = TrainerImageInfo.create(training_framework)
