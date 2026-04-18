# Compose Troubleshooting

## Training job fails immediately (state: `failed`)

### Symptom

Training jobs are created and scheduled, but fail almost immediately.

Typical worker log error (`interactive_ai_jobs_worker`):

```text
Unable to find image 'ghcr.io/<...>/interactive_ai/workflows_train:main' locally
docker: Error response from daemon: Head "https://ghcr.io/v2/.../manifests/main": denied.
```

Job usually ends with `exit=125` and transitions to `READY_FOR_REVERT` then `failed`.

### Root cause

The jobs worker launches workflow containers with nested `docker run`.
If required workflow/trainer images are not present locally, Docker attempts to pull from GHCR.
In local environments without registry access, pull fails (`denied`) and training fails.

### Required local images

- `ghcr.io/<registry>/interactive_ai/workflows_train:<tag>`
- `ghcr.io/<registry>/interactive_ai/workflows_optimize:<tag>`
- `ghcr.io/<registry>/interactive_ai/workflows_dataset_import_export:<tag>`
- `ghcr.io/<registry>/interactive_ai/workflows_project_import_export:<tag>`
- `ghcr.io/<registry>/interactive_ai/workflows_model_test:<tag>`
- `ghcr.io/<registry>/interactive_ai/otx_v2_gpu:<tag>`
- `ghcr.io/<registry>/interactive_ai/otx_v2_xpu:<tag>`

### Fix

Build workflow/trainer images locally:

```bash
docker compose build \
  interactive_ai_workflows_train \
  interactive_ai_workflows_optimize \
  interactive_ai_workflows_model_test \
  interactive_ai_workflows_dataset_import_export \
  interactive_ai_workflows_project_import_export \
  interactive_ai_workflows_otx_v2_gpu \
  interactive_ai_workflows_otx_v2_xpu
```

Restart jobs services:

```bash
docker compose restart interactive_ai_jobs_worker interactive_ai_jobs_scheduler
```

Then submit a new training job (failed jobs do not auto-recover).

### Verification

Check images exist locally:

```bash
docker images --format '{{.Repository}}:{{.Tag}}' | rg 'interactive_ai/(workflows_train|workflows_optimize|workflows_dataset_import_export|workflows_project_import_export|workflows_model_test|otx_v2_gpu|otx_v2_xpu):'
```

Optional nested-run smoke check from worker container:

```bash
docker compose exec interactive_ai_jobs_worker docker run --rm --network geti ghcr.io/<registry>/interactive_ai/workflows_train:<tag> python -V
```

If this command succeeds, training workflow container launch path is healthy.
