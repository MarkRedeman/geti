# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

"""Execution type enum used by scheduler runtime paths."""

from enum import Enum


class ExecutionType(Enum):
    """Main vs revert execution discriminator."""

    MAIN = "MAIN"
    REVERT = "REVERT"
