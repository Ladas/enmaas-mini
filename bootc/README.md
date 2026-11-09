# RHEL bootc images

The bootc build supports two standalone image families:

```text
praxis      Shared Praxis gateway
vllm-cpu    Local vLLM inference without NVIDIA components
vllm-gpu    Local vLLM inference with NVIDIA 580 open drivers
```

All images build directly from a reviewed RHEL 9 bootc base. They are intended
for x86_64 Linux Podman builders.

## Build

```console
export RHEL_BOOTC_IMAGE=registry.redhat.io/rhel9/rhel-bootc@sha256:DIGEST
sudo bootc/build praxis localhost/enmaas-mini
sudo bootc/build vllm-cpu localhost/enmaas-mini
sudo bootc/build vllm-gpu localhost/enmaas-mini
```

Set `RHSM_ORG_ID` and `RHSM_ACTIVATION_KEY` together on a builder that needs
subscription registration. AWS PAYG builders can set `AWS_RHUI_REGION`.

## Deploy

The target must already be a bootc-managed RHEL host. A package-based RHEL
installation cannot use `bootc switch`.

```console
sudo bootc switch IMAGE:TAG
sudo bootc status
sudo systemctl reboot
```

## Image behavior

- Application containers are pulled on first boot, not embedded in the OS image.
- Praxis uses a dedicated rootless service account and in-memory quota profile.
- vLLM images do not include Praxis or cloud-provider credentials.
- The GPU image includes the NVIDIA 580 open driver and Container Toolkit.

See the [vLLM deployment guide](VLLM.md) for service setup.

## Optional GitHub image builds

Static bootc checks run without registry credentials. Actual RHEL image builds
are opt-in: set the **repository variable** `BOOTC_IMAGE_BUILDS_ENABLED=true`
only after configuring the protected `bootc-image-main` environment:

| Setting | Kind | Purpose |
| --- | --- | --- |
| `RHEL_BOOTC_IMAGE` | Environment variable | Reviewed RHEL bootc base image reference |
| `REDHAT_REGISTRY_USERNAME`, `REDHAT_REGISTRY_PASSWORD` | Environment secrets | Pull the entitled RHEL base |
| `RHSM_ORG_ID`, `RHSM_ACTIVATION_KEY` | Environment secrets | Build-time package access |
| `QUAY_USERNAME`, `QUAY_TOKEN` | Environment secrets | Publish selected images to their Quay repositories |

Restrict this environment to reviewed `main` runs. The optional
`bootc-image-pr` environment is for reviewed, same-repository build-only PRs;
use required reviewers and do not grant Quay publishing credentials there.
Fork PRs cannot run the credentialed build job. The official repository guard
also prevents a fork's own `main` from using this publication path.

Without the opt-in variable the workflow reports that image builds are disabled;
this is **not** image qualification. When enabled, missing inputs fail with their
setting names, never their values. Image publication still requires a successful
build and test. Repository/environment secrets must be configured separately
after a repository move. This setup is independent of the public MaaS/PriceTag
application images used by the Quadlet installer.
