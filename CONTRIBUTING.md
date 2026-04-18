# Contributing to Geti™

## Welcome! 🌟

Thank you for your interest in contributing to Geti™. This guide will help you understand our project structure,
development workflow, and contribution guidelines.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Security](#security)
- [How to Contribute](#how-to-contribute)
- [Development Guidelines](#development-guidelines)
- [Sign your work](#sign-your-work)
- [License](#license)

## Code of Conduct

This project and everyone participating in it are governed by the [`CODE_OF_CONDUCT`](CODE_OF_CONDUCT.md) document. By
participating, you are expected to adhere to this code.

## Security

Read the [`Security Policy`](SECURITY.md).

## How to Contribute

### Contribute Code Changes

If you'd like to help improve Geti™, pick one of the issues listed in [GitHub
Issues](https://github.com/open-edge-platform/geti/issues) and submit
a [Pull Request](https://github.com/open-edge-platform/geti/pulls) to address it.
Note: Before you start working on it, please make sure the change hasn’t already been implemented.

### Report Bugs

If you encounter a bug, please open an issue in [`Github Issues`](https://github.com/open-edge-platform/geti/issues).
Be sure to include all the information requested in the bug report template to help us understand and resolve the issue
quickly.

### Suggest Enhancements

Intel welcomes suggestions for new features and improvements. Follow these steps to make a suggestion:

- Check if there's already a similar suggestion in [`Github Issues`](https://github.com/open-edge-platform/geti/issues).
- If not, please open a new issue and provide the information requested in the feature request template.

### Submit Pull Requests

Before submitting a pull request, ensure you follow these guidelines:

- Fork the repository and create your branch from `main`.
- Follow the [`Development Guidelines`](#development-guidelines) in this document.
- Test your changes thoroughly.
- Document your changes (in code, readme, etc.).
- Submit your pull request, detailing the changes and linking to any relevant issues.
- Wait for a review. Intel will review your pull request as soon as possible and provide you with feedback.
  You can expect a merge once your changes are validated with automatic tests and approved by maintainers.

## Development Guidelines

### Project Overview

Geti™ project is a monorepo designed to support independent development and release of multiple related
subprojects while maintaining a cohesive platform. Our architecture allows for flexible and modular development across
different components.

### Repository Structure

#### Directory Layout

```
├── Makefile.shared-*             # Shared build targets for different languages (go, js, python)
├── interactive_ai/               # Group of components
│   ├── services/                 # Group-specific libraries
│   ├── workflows/                # Nested group of components
│   ├── libs/                     # Nested group of components
│   └── makefile                  # Group-level build orchestration
├── libs/                         # Cross-project shared libraries
└── makefile                      # Project-level build orchestration
```

#### Component Structure

Each component typically includes:

- `app/`: Source code
- `chart/`: Helm chart for Kubernetes deployment
- `Dockerfile`: Container build specifications
- `makefile`: Component-specific build targets
- `version`: Component version tracking file

#### Library Types

1. **Group-Specific Libraries**
    - Scoped to specific service groups
    - Minimize rebuild dependencies
    - Prevent unnecessary cross-component coupling

2. **Cross-Project Libraries**
    - Shared across entire monorepo
    - Kept minimal to reduce rebuild impact
    - Contains universal utilities and shared resources

### Getting Started

#### Prerequisites

Before you begin, ensure you have:

- Docker with Compose support
- make (optional)

#### Setup Steps (Compose-first)

1. Clone the repository
2. Prepare local runtime configuration and certificates
    ```bash
    make compose-prepare-certs
    ```
3. Bootstrap Mongo/S3 migrations
    ```bash
    make compose-bootstrap
    ```
4. Start local stack
    ```bash
    docker compose up -d --build
    ```
5. Run smoke checks through Traefik
    ```bash
    make compose-smoke
    ```

#### Local Auth Mock Mode (local-only)

Local compose uses mock auth by default:

- `AUTH_MODE=mock`
- `DEPLOYMENT_MODE=compose`

In this mode, identity and authorization checks are bypassed for local development.
Do not use this mode in shared or production environments.

#### Unsupported / Placeholder features in compose mode

Current compose migration intentionally keeps some paths disabled or placeholder:

- `interactive_ai_inference_gateway` returns `404` for all routes in compose mode.
- KServe/Kubernetes-backed model serving is replaced by compose-native registry behavior in model_registration.
- Jobs execution uses compose local executor simulation mode by default (`LOCAL_EXECUTOR_MODE=simulate`).

For compose setup and current local behavior, see `docs/compose/getting-started-with-compose.md` and `docs/compose/README.md`.

#### Kubernetes/Helm path (non-default)

Kubernetes + Helm flow is still available for environments that require it, but it is no longer the default local
development path.

### Local Development

#### Building a project or component

```bash
# Navigate to the component directory
cd path/to/component

# Build the component
make build-image

# Run tests
make tests
```

#### Build Targets

- `clean`: Remove build artifacts
- `lint`: Run linter in "fix" mode to automatically correct code where possible
- `static-code-analysis`: Run static analysis/linters in read-only mode
- `test-unit`: Run unit tests
- `test-integration`: Run integration tests
- `test-component`: Run component-specific tests
- `test`: Run all types of tests
- `coverage`: Run tests and generate a coverage profile
- `build`: Create binaries
- `publish`: Publish artifacts to registries
- `build-image`: Build a container image
- `build-chart`: Build a helm chart
- `publish-image`: Publish a container image
- `lint-chart`: Lint a helm chart
- `clean-chart`: Clean built charts
- `publish-chart`: Publish a helm chart
- `list-image`: List component Docker images
- `list-umbrella-chart`: List umbrella charts

## Sign your work

Please use the sign-off line at the end of the patch. Your signature certifies that you wrote the patch or otherwise
have the right to pass it on as an open-source patch. The rules are pretty simple: if you can certify
the below (from [developercertificate.org](http://developercertificate.org/)):

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
660 York Street, Suite 102,
San Francisco, CA 94110 USA

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.

Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

Then you just add a line to every git commit message:

    Signed-off-by: Joe Smith <joe.smith@email.com>

Use your real name (sorry, no pseudonyms or anonymous contributions.)

If you set your `user.name` and `user.email` git configs, you can sign your
commit automatically with `git commit -s`.

## License

Geti™ is licensed under the terms in [LICENSE](LICENSE). By contributing to the project, you agree
to the license and copyright terms therein and release your contribution under these terms.
