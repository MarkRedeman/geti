# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE
#
# Minimal stub for the `ldap` (python-ldap) package used in unit tests
# where the real C extension cannot be compiled (missing libldap-dev headers).
# Only constants / exception classes referenced at *import time* are provided.

OPT_REFERRALS = 0
SCOPE_SUBTREE = 2
MOD_REPLACE = 2
MOD_DELETE = 3


class LDAPError(Exception):
    pass


class dn:
    @staticmethod
    def escape_dn_chars(s: str) -> str:
        return s


def initialize(*args, **kwargs):
    raise NotImplementedError("ldap stub: initialize() not available in test environment")
