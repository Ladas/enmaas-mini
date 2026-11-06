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
