# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from grpc_interfaces.account_service.client import AccountServiceClient


class AccountServiceConnection:
    def __init__(self) -> None:
        self.client = AccountServiceClient(metadata_getter=lambda: ())
