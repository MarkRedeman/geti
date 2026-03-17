# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from unittest.mock import patch

from job.models.trainer import _create_ephemeral_storage_resources


class _DummyCompiledDatasetShards:
    def __init__(self, is_null: bool):
        self._is_null = is_null

    def is_null(self) -> bool:
        return self._is_null


class _DummyOptimizationConfig:
    def __init__(self, is_null: bool):
        self.compiled_dataset_shards = _DummyCompiledDatasetShards(is_null=is_null)


def test_create_ephemeral_storage_resources_handles_null_compiled_shards() -> None:
    optimization_cfg = _DummyOptimizationConfig(is_null=True)

    resources = _create_ephemeral_storage_resources(optimization_cfg)

    assert resources.requests == 1024**3
    assert resources.limits == 1024**3
    assert resources.work_dir_size_limit == 1024**3


@patch("job.models.trainer.EphemeralStorageResources.create_from_compiled_dataset_shards")
def test_create_ephemeral_storage_resources_uses_compiled_shards_when_available(mock_create_from_shards) -> None:
    optimization_cfg = _DummyOptimizationConfig(is_null=False)
    mock_create_from_shards.return_value = object()

    result = _create_ephemeral_storage_resources(optimization_cfg)

    assert result is mock_create_from_shards.return_value
    mock_create_from_shards.assert_called_once_with(
        compiled_dataset_shards=optimization_cfg.compiled_dataset_shards,
        ephemeral_storage_safety_margin=5 * (1024**3),
    )
