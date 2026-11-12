# External services test lab

**Qualification in progress.** Start with [local Podman tests](local-podman.md). They exercise gateway identity/session boundaries and real metrics/trace delivery; short mock inference/accounting phases also pass locally. Sustained qualification, three-host RHEL installation and RDS acceptance remain pending. Use mocked providers and disposable infrastructure.

| Operation | Instructions | Qualification |
| --- | --- | --- |
| Run without menus | [Headless installation](headless.md) | Explicit choices, protected credential files; fresh RHEL acceptance pending |
| Prepare private TLS bundles | [Certificates](certificates.md) | Generated certificates and rejection tests run locally |
| Install Keycloak | [Keycloak host](keycloak-rhel.md) | Generated rootless systemd units and browser logins tested in the local Linux VM; full RHEL installer pending |
| Install observability | [Observability host](observability-rhel.md) | Quadlet generation, collector configuration and synthetic redaction tested; full host installation pending |
| Connect gateway telemetry | [Gateway relay](gateway-telemetry.md) | Gateway metrics, traces, restricted container logs and host-resource panels pass locally; RHEL relay execution remains pending |
| Connect gateway SSO | [OIDC and identities](oidc.md) | Gateway login, unknown identity denial, session deactivation and shared issuer login tested locally; current-role checks and shared logout pass with a pending PriceTag CSP fix; observability group removal revokes an existing session within the tested refresh window; synchronization into PriceTag roles is not implemented |
| Run traffic phases | [Benchmark](benchmark.md) | Short six-phase local run passes per-user event/token/USD reconciliation and cleanup; sustained/RHEL runs pending |
| Inspect benchmark evidence | [Offline report](report.md) | CPU/memory chart and phase table generated from actual local samples |
| Plan optional RDS | [RDS design and pending work](rds.md) | Plan/apply/recovery and verifier tests use simulated AWS; real deployment pending |
| Remove lab resources | [Cleanup](cleanup.md) | Explicit resource inventory; no automatic deletion |

This lab uses three RHEL VMs: gateway, observability and Keycloak. The normal gateway installer accepts protected TLS and OIDC configuration. A separate lab helper connects gateway telemetry; auxiliary installers belong under `tests/external-services`, not the production quickstart. Optional RDS is a separate provisioning step.

## Provision the three VMs

On the AWS administrator workstation, enter the reviewed repository and reuse the [AWS credential/session setup](../aws-pricetag.md). Keep AWS credentials on this workstation.

```console
source scripts/aws/session.sh
aws_test_credentials
REGION=eu-central-1
SUBNET=''
CLIENT_CIDR=''
RUN_PREFIX="enmaas-lab-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')"
SSH_KEY="$HOME/.secure-single-server-tests/ssh/$RUN_PREFIX"
aws_test_discover
aws_test_key
ssh-add "$SSH_KEY"
source tests/external-services/aws-lab.sh
aws_lab_plan
```

Review all plans, then run:

```console
aws_lab_deploy
aws_lab_info
```

Each VM still requires its own typed billable-launch confirmation. `aws_lab_info` waits for running instances and exports and prints each role’s SSH target, public IP and private IP for the following steps. It does not verify service readiness. Defaults: gateway 32 GiB/150 GiB disk, observability 16 GiB/100 GiB, Keycloak 8 GiB/50 GiB. These are test starting points, not measured capacity claims. All use amd64; no GPU or local LLM is required.

**Partial launch:** inspect `.state/$RUN_PREFIX-ROLE.json`. Resume only the failed role with `aws_test_deploy ROLE tests/external-services/ROLE-vm.json --scenario SCENARIO`; gateway uses `remote-gateway`, others use their role. Do not rerun the full batch after a partial failure. The existing helper retains journals and never deletes resources automatically.

Only SSH and browser HTTPS (8443) from the workstation `/32` are initially allowed. Add only the [reviewed peer rules](network.md); do not open raw database, Prometheus, Loki, Tempo or collector ports publicly. See [design and acceptance](design.md) and [manual AWS cleanup](cleanup.md).

## Implementation and validation order

1. Provision VMs; verify RHEL, disk, architecture and SSH fingerprints.
2. Prepare role-specific certificates, restrict peer-network rules and qualify the Keycloak installer.
3. Qualify observability ingestion, storage, Perses and OIDC authorization on its dedicated host.
4. Configure the gateway to use existing external services; verify identity mappings and telemetry privacy.
5. Run denial/security tests before the mock traffic sequence; validate dashboards with real emitted signals.
6. Optionally provision private RDS and repeat database failure/recovery tests.

Source-level/cloud-free checks for this draft:

```console
python3 tests/aws/auxiliary.py
python3 tests/aws/plan.py
python3 tests/aws/session.py
python3 -m unittest discover -s tests/external-services -p 'test_*.py'
```
