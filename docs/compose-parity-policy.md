# Compose Parity Policy (Local Development)

## Purpose

Define what "near-production parity" means for Docker Compose local runs and
make unsupported behavior explicit.

Current target agreed for this phase:

- **Parity level:** API + state parity where in scope
- **Unsupported behavior policy:**
  - API paths: return explicit **501 Not Implemented** with clear reason
  - Background loops/workers: log explicit warning and continue safely
- **Auth mode:** `AUTH_MODE=mock` (local only)
- **Credits:** out-of-scope in compose for now (keep service running, ignore feature)

---

## In Scope (Now)

### 1) Jobs service (`interactive_ai/services/jobs`)

Goal in compose:

- Compose runtime must support scheduler state transitions and execution
  lifecycles for all job types from the API/state-machine perspective.
- If a specific job type path is not yet implemented, behavior must be explicit
  (documented + clear failure), not silent fallback.

Current boundary:

- Compose-only scheduler execution path is active (no Flyte runtime branch).
- Event/update/recovery/cancellation paths are compose-native.
- Resource manager Kubernetes loop is unavailable in compose; startup warns and
  initializes minimal GPU capacity for schedulability.

### 2) Auth behavior (cross-service)

Current boundary:

- Compose uses `AUTH_MODE=mock` for local velocity and reproducibility.
- This mode is intentionally insecure and must stay local-only.

Directional roadmap note:

- Future local auth should move toward simpler real-auth integration (e.g.
  Authelia-backed flow) and remove unnecessary LDAP/SpiceDB complexity from
  local developer workflows.

---

## Explicitly Out of Scope (Now)

### Credits system

- Compose keeps credit-related services available to avoid wiring breakage.
- Credit behavior is currently out-of-scope for parity enforcement.
- Compose policy and acceptance do not require credit flow parity.

---

## Unsupported Behavior Contract

When compose cannot provide equivalent behavior:

1. **API endpoints**
   - Return `501 Not Implemented`
   - Include actionable detail in response and server logs

2. **Background loops / startup-only tasks**
   - Log explicit warning at startup/attempt
   - Avoid crash loops
   - Keep unaffected paths functional

---

## Required Compose Acceptance Checks

Run these checks after compose-related changes.

### A) Jobs policy compose behavior

Command:

```bash
PYTHONPATH=tests:app uv run pytest tests/unit/policy/test_main.py -q
```

Pass criteria:

- Compose mode skips Kubernetes resource manager loop without crashing.
- Compose initialization sets default GPU capacity when absent.
- Existing GPU capacity is not overwritten.

### B) User directory compose fallbacks

Command:

```bash
cd platform/services/user_directory
PYTHONPATH=tests:app .venv/bin/pytest \
  tests/unit/service_connection/k8s_client/test_apis.py \
  tests/unit/service_connection/k8s_client/test_config_maps.py \
  tests/unit/service_connection/k8s_client/test_secrets.py \
  tests/unit/service_connection/test_smtp_client.py \
  tests/unit/test_endpoints/test_invite_user.py \
  tests/unit/test_endpoints/test_password_reset.py -q
```

Pass criteria:

- Compose mode reads secrets/config values from env/defaults, not K8s API.
- Invitation/password-reset flows function without Kubernetes dependencies.
- Email template resolution works in compose fallback mode.

### C) Observability compose behavior

Command:

```bash
cd platform/services/observability
PYTHONPATH=tests:app uv run pytest \
  tests/unit/common/test_platform.py \
  tests/unit/test_endpoints/test_logs.py \
  tests/unit/service_connection/k8s_client/test_apis.py \
  tests/unit/service_connection/k8s_client/test_cluster_info.py -q
```

Pass criteria:

- Compose fallback installation datetime path works without K8s config map.
- Unsupported log types map to explicit 501 behavior.
- K8s-dependent clients remain guarded in compose mode.

---

## Change Control for This Policy

Any PR that changes compose runtime behavior for in-scope areas must:

1. Update this policy if boundaries/expectations changed.
2. Include acceptance command output for affected sections.
3. Keep unsupported behavior explicit (501 or warning contract).

---

## CI Enforcement

- Main CI includes a dedicated **Compose parity acceptance** job.
- The job executes `make compose-parity`, which runs the required checks above.
- The required-status-checks gate depends on this job, so regressions block merge.
