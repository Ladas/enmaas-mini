# enMAAS Mini

[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://redhat-et.github.io/enmaas-mini/)
[![Deploy documentation](https://github.com/redhat-et/enmaas-mini/actions/workflows/pages.yml/badge.svg)](https://github.com/redhat-et/enmaas-mini/actions/workflows/pages.yml)

enMAAS Mini is an experimental model-gateway project focused on
[Praxis](https://github.com/praxis-proxy/praxis), PriceTag, and the supporting
deployment components needed to run them on a small RHEL footprint.

> [!IMPORTANT]
> This is an experimental demonstration, not a production-ready platform. Use
> a disposable host for first evaluation and review the linked qualification
> evidence before extending a deployment.

## Components

- **Praxis** routes model traffic, owns provider credentials, and enforces shared token quotas.
- **MaaS and PriceTag** provide finite-lived user keys, USD budgets, metering, and management workflows.
- **vLLM support** provides optional local OpenAI-compatible inference.
- **bootc images** provide repeatable RHEL OS images for standalone Praxis and vLLM deployments.

## Get started

- [Architecture overview](docs/quickstarts/architecture-walkthrough/README.md)
- [All-in-one Praxis gateway](docs/quickstarts/all-in-one/README.md)
- [Remote HTTPS/JWT gateway](docs/quickstarts/remote-gateway/README.md)
- [Remote gateway with PriceTag](docs/quickstarts/remote-gateway-pricetag/README.md)
- [Optional vLLM inference](docs/quickstarts/common/vllm.md)
- [Bootc image guide](bootc/README.md)

## Documentation

The rendered guides are published with GitHub Pages at
[redhat-et.github.io/enmaas-mini](https://redhat-et.github.io/enmaas-mini/).
To build them locally, run:

```console
scripts/docs/serve build
```

## Repository layout

```text
configs/     Praxis, remote-gateway, PriceTag, and vLLM configuration
scripts/     Installation, administration, and documentation tooling
tests/       Offline contracts, container tests, and PriceTag checks
bootc/       RHEL bootc image definitions for Praxis and vLLM
docs/        Published documentation
```
