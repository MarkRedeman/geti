# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE
"""
Defines train image info
"""

import logging
import os
from dataclasses import dataclass

from dataclasses_json import dataclass_json
from iai_core.entities.model import TrainingFramework, TrainingFrameworkType

logger = logging.getLogger(__name__)


@dataclass_json
@dataclass
class TrainerImageInfo:
    """Trainer image information."""

    train_image_name: str
    render_gid: int = 0  # Should be non-zero value when training with Intel GPUs

    @classmethod
    def create(cls, training_framework: TrainingFramework) -> "TrainerImageInfo":
        """Create trainer image information from the given training framework.

        :param training_framework: Dataclass to choose the trainer image
        """

        if training_framework.type != TrainingFrameworkType.OTX:
            raise ValueError(f"{training_framework.type} type is not supported yet.")

        render_gid = 0
        image_name = os.getenv("TRAINER_RUNTIME_IMAGE", "")
        if not image_name:
            raise ValueError(
                "Cannot resolve trainer image in compose mode. Set TRAINER_RUNTIME_IMAGE for jobs/workflow runtime."
            )
        if render_gid_value := os.getenv("TRAINER_RENDER_GID"):
            render_gid = int(render_gid_value)

        logger.info(
            f"Trainer image has been selected {image_name}, where a model has trainer "
            f"identification for {training_framework.version}."
        )
        return cls(train_image_name=image_name, render_gid=render_gid)

    def to_image_full_name(self) -> str:
        """Get image full name.

        For example, it would be "dev-registry.toolbox.com/impp/ote:2.2.0".
        """
        return self.train_image_name
