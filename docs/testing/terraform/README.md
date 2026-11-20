# AWS Terraform test deployments

Create dedicated AWS infrastructure for one gateway or three service hosts.
The module is tested with Terraform's mocked AWS provider. **Live AWS permissions
and end-to-end installation remain unqualified.** It does not create an IAM role.
Use a reviewed, group-scoped assume-role profile; do not use administrator credentials
as a fallback. The earlier AWS helper's permission fragments are not automatically
sufficient for Terraform's update and deletion operations.

## 1. Prepare inputs once

Install Terraform 1.14.0 and use an existing SSH key. Create `deployment.json`
outside the repository with these nonsecret fields:

```json
{
  "account_id": "YOUR_ACCOUNT_ID",
  "region": "eu-central-1",
  "group": "demo",
  "topology": "full",
  "ami_id": "YOUR_RHEL_AMI_ID",
  "ami_owner_id": "VERIFIED_PUBLISHER_ACCOUNT_ID",
  "availability_zones": ["eu-central-1a"],
  "ssh_cidrs": ["YOUR_WORKSTATION_IP/32"],
  "https_cidrs": ["YOUR_WORKSTATION_IP/32"],
  "ssh_public_key": "YOUR_SSH_PUBLIC_KEY"
}
```

Choose `single` for only the gateway. `full` adds Keycloak and observability.
No private key, AWS key, provider key or database password belongs in this file.
Select an exact RHEL x86_64 AMI and independently verify its publisher.

The initial module exposes SSH and HTTPS only to explicit `/32` addresses.
Private service rules use security-group references. Egress is unrestricted.
It creates no RDS, DNS records, public certificates or application services.

## 2. Plan and apply

Run from this checkout. The helper uses a private state directory per deployment
under `~/.local/state/enmaas-terraform` and snapshots the module files there.
A profile name refers to your existing AWS configuration; the helper stores no
AWS credentials. Ambient AWS keys and Terraform argument overrides are removed
from its child environment so they cannot override the selected profile.

```sh
DEPLOYMENT=$(python3 tests/terraform/deploy.py init --config /absolute/path/deployment.json --profile YOUR_SCOPED_PROFILE) &&
python3 tests/terraform/deploy.py plan "$DEPLOYMENT" &&
python3 tests/terraform/deploy.py show "$DEPLOYMENT"
```

Review the plan, including account, region, resources and cost implications. Then:

```sh
python3 tests/terraform/deploy.py apply "$DEPLOYMENT" --confirm "apply $DEPLOYMENT" &&
python3 tests/terraform/deploy.py info "$DEPLOYMENT"
```

Applying creates billable resources. The helper applies the saved plan and checks
its digest. A failed apply preserves the state and plan for inspection; inspect
actual state and create a new plan before attempting recovery. No automatic deletion
occurs. Root disks are encrypted and instances require IMDSv2.

## 3. Install services

The three-host coordinator is a dependency of the external-services work. This
branch does not include it yet. Use its reviewed checkout for installation after
that dependency is available. Terraform inventory is converted to its configuration
by `services-config`; the export itself does not connect to hosts.

Create `installer.json` outside the repository:

```json
{
  "revision": "REVIEWED_40_CHARACTER_COMMIT",
  "source_repository": "https://github.com/redhat-et/enmaas-mini.git",
  "ssh_key": "/absolute/path/to/private-key",
  "known_hosts": "/absolute/path/to/verified-known-hosts",
  "tls_directory": "/absolute/path/to/new-private-tls-directory",
  "issuer_name": "identity.example.test",
  "workstation_cidr": "YOUR_WORKSTATION_IP/32"
}
```

Verify host fingerprints independently before creating `known_hosts`. For the
private-CA/IP lab, configure workstation resolution for the chosen issuer name
using the coordinator guide. Terraform does not create that DNS record.

```sh
SERVICES_CONFIG=$(python3 tests/terraform/deploy.py services-config "$DEPLOYMENT" --options /absolute/path/installer.json)
```

From the checkout containing the reviewed coordinator, preview then install:

```sh
python3 tests/external-services/services.py --config "$SERVICES_CONFIG"
python3 tests/external-services/services.py --config "$SERVICES_CONFIG" --state "$HOME/.local/state/enmaas-services/$DEPLOYMENT" --confirm "install $DEPLOYMENT"
python3 tests/external-services/services.py --config "$SERVICES_CONFIG" --access
```

The handoff selects local databases and a 10,000-user synthetic population. Consult
the external-services guide for mock traffic, CA trust, benchmark scenarios and
provider replacement. The single-host topology uses the gateway quickstart instead.

## List and delete

```sh
python3 tests/terraform/deploy.py list
python3 tests/terraform/deploy.py info "$DEPLOYMENT"
python3 tests/terraform/deploy.py destroy-plan "$DEPLOYMENT"
python3 tests/terraform/deploy.py show "$DEPLOYMENT"
```

Export any required data first. After reviewing deletion:

```sh
python3 tests/terraform/deploy.py apply "$DEPLOYMENT" --confirm "destroy $DEPLOYMENT"
```

Deletion includes VM root disks. Retain state until AWS deletion is verified.
State limits the resources Terraform manages; IAM must independently enforce group
ownership. Do not manage these resources with the original AWS helper too.

## Test without AWS credentials

```sh
terraform -chdir=infra/terraform/aws init -backend=false
terraform -chdir=infra/terraform/aws validate
terraform -chdir=infra/terraform/aws test
python3 -m unittest discover -s tests/terraform -v
```

Provider downloads require network access. Tests use mocked AWS resources, including
apply and teardown; they do not create cloud infrastructure. They validate module
and CLI behavior, not AWS IAM enforcement or RHEL service installation.
