# Compose user-management notes

This note captures current compose behavior and troubleshooting findings for user creation/invitation flows.

## Service split: `platform_account` vs `platform_user_directory`

- `platform_account`
  - source-of-truth for organizations, workspaces, users, and roles
  - owns role assignment APIs and persists authz state (via SpiceDB integration)
- `platform_user_directory`
  - user-management workflow layer (LDAP create/update, password/reset/invitation workflows)
  - currently serves `POST /api/v1/organizations/{organization_id}/users/create`

Even with manage-users flags enabled, current UI flow still depends on `platform_user_directory` for `/users/create`.

## Required compose flags for create-user flow

For account service:

- `FEATURE_FLAG_CREDIT_SYSTEM=false`
- `FEATURE_FLAG_MANAGE_USERS=true`
- `FEATURE_FLAG_MANAGE_USERS_ROLES=true`

If `FEATURE_FLAG_MANAGE_USERS_ROLES=false`, role endpoints return `Unimplemented` and user-creation flows can fail with `501`.

## Routing requirement

Traefik router priority must keep `/organizations/.*/users/create` on `platform_user_directory` (not `platform_account`).

## Common failure modes seen

### 1) 501 Not Implemented on `/users/create`

Cause: manage-users role feature flag disabled in account service.

Fix: set `FEATURE_FLAG_MANAGE_USERS=true` and `FEATURE_FLAG_MANAGE_USERS_ROLES=true` for `platform_account`.

### 2) 500 Internal Server Error on `/users/create`

Cause: `platform_user_directory` trying to reach account service at `impt-account-service:5001` (k8s DNS name unavailable in compose).

Fix: set compose overrides in `platform_user_directory`:

- `ACCOUNT_SERVICE_HOST=platform_account`
- `ACCOUNT_SERVICE_PORT=5001`

## Longer-term cleanup direction

If we want to remove `platform_user_directory` dependency from compose, we need either:

1. account-native replacements for LDAP-driven create/invite/password flows, or
2. web UI/API flow migration from `/users/create` to account-native endpoints with equivalent behavior.

Until then, keep `platform_user_directory` in the minimal stack for user management.
