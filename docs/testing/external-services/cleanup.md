# Manual AWS cleanup

Run cleanup from the AWS administrator workstation or console. The lab helper never deletes resources. Keep the launch journals and export sanitized benchmark evidence before deleting anything. Match the account, region, run prefix and resource IDs; names alone are insufficient ownership evidence.

## Print the deletion inventory

In the AWS administrator terminal used for provisioning, print only the non-secret ownership/resource fields from the three launch journals:

```sh
(
  set -euo pipefail
  for role in gateway keycloak observability; do
    jq --arg role "$role" \
      '{Role:$role, AccountId, Region, Prefix, InstanceId, SecurityGroupId, KeyPairName, ApplyStatus}' \
      "$AWS_TEST_REPO/.state/$RUN_PREFIX-$role.json"
  done
)
```

In the matching AWS account and region:

1. Stop the benchmark and retain the selected evidence.
2. If RDS was created, decide on its final snapshot/backup retention, disable deletion protection deliberately, and delete the lab database. Wait for completion before removing its group dependencies.
3. Terminate the three recorded EC2 instances; wait until their network interfaces are released.
4. Remove the lab security-group references, then delete the recorded groups and any lab-owned RDS group.
5. Delete the recorded imported key pairs and any remaining lab-owned EBS volumes. Check retained RDS snapshots/backups and its subnet/parameter groups separately.
6. Check AWS for remaining run-prefix tags and charges. Keep journals until reconciliation is complete, then remove local keys/trust only when no longer needed.

A partial launch can have no instance but still have a security group or key pair. Inspect every journal, including unfinished operations; do not treat an absent field as proof that AWS created nothing. The tables below identify additional retained state.

## Resources created by the current three-VM helper

| Resource | What to check and remove |
| --- | --- |
| Three EC2 instances | Stop traffic, export evidence, then terminate gateway, Keycloak and observability instances. Stopping alone retains storage charges. |
| EBS volumes | Check each root volume's `DeleteOnTermination`; inspect unattached volumes afterward. Delete only volumes belonging to this run. |
| Three security groups | Remove lab inter-group references first, then delete groups after instances/ENIs release them. Do not remove shared VPC groups. |
| Imported EC2 key pairs | The existing helper imports a per-launch key-pair resource; inspect the names/IDs in each role's journal. Delete each owned AWS key-pair entry after instances are gone. |
| Local SSH key and journals | Keep while recovery/evidence is needed, then remove deliberately. Deleting an EC2 key-pair entry does not delete your local private key. |

The three-VM helper reuses the selected VPC/subnet and creates no NAT gateway, load balancer, DNS zone, IAM role, RDS or S3 bucket. The separate optional RDS helper creates only its reviewed database, subnet group, parameter group and security group; RDS manages the master-password secret. Do not delete shared network infrastructure. Check the console for unexpected residual resources rather than treating this list as proof that no other resources exist.

## Resources created only when optional RDS apply is selected

| Resource | Manual decision |
| --- | --- |
| RDS instance | Disable deletion protection only after approval. Choose whether to keep a final snapshot/retained automated backups; retained storage continues billing. |
| RDS snapshots, subnet group, parameter group and security group | Inventory/delete separately when no longer needed; snapshots can contain identities, keys and usage history. Do not delete a shared subnet group. |
| Secrets Manager entries | Delete only lab-owned bootstrap/application secrets under an explicit recovery-window policy; credentials must also be revoked. |
| Elastic IP, DNS records, load balancers, NAT, log groups or buckets | None are created by this draft. If added manually/later, track their IDs/tags and remove them explicitly; these can outlive VMs. |
| Private CA/service credentials | Revoke or retire the entire lab trust domain and OIDC clients, remove lab CA trust from clients, and remove local service keys when no longer needed. |

Use each `.state/RUN_PREFIX-ROLE.json` and the selected RDS recovery journal as the starting inventory. The RDS journal records planned names, completed resource IDs/ARNs and any pending operation; inspect pending operations for ambiguous success before deleting or retrying. verify actual AWS resources and billing after cleanup. Do not paste journal or secret contents into public PR evidence.

## State on retained VMs

Terminating a VM with its root EBS volume removes its local files. If retaining a VM, inventory these separately before reusing it:

| Host | Retained state |
| --- | --- |
| Gateway | Application databases and keys; relay Quadlet/drop-ins and Podman secrets; `enmaas-host-metrics` service/timer; `/etc/enmaas-telemetry-lab`; the service account's private `~/.local/share/enmaas-telemetry-logs`; `enmaas-lab-gateway-log-positions` volume. |
| Keycloak | Realm/client configuration, issuer keys, PostgreSQL volume, service-account secrets and root-private bootstrap inputs. Removing a container alone does not revoke issued tokens or remove its database. |
| Observability | OAuth client/cookie secrets, private TLS material, Perses configuration and Prometheus/Loki/Tempo volumes. Logs and traces can reveal operational metadata even after message redaction. |
| RDS bootstrap | `/root/pricetag-external-db` contains application credentials and the recovery journal. The master credential remains managed by RDS/Secrets Manager; do not confuse removing local files with revoking database roles. |

For a retained gateway, stop the host-metrics timer and relay before removing their configuration. Remove the three `service-logs.conf` drop-ins and the gateway `telemetry.conf` drop-in, reload the user systemd manager, and restart MaaS, PriceTag and the gateway before deleting the private log directory or position volume. Keep application units, secrets and database volumes. Confirm that inference still works before removing retired telemetry credentials. No uninstall command automatically performs these destructive steps.

## Local test fixtures

Use the matching `ENMAAS_LAB_INSTANCE` with `tests/external-services/local.py down`. It removes only the labelled fixture pod and secrets; named data volumes and private `.state` files remain. The local Podman runbook lists the default fixture's volume names. For a named fixture, inspect the matching `enmaas-INSTANCE-*` resources rather than running a global prune.

The isolated RDS-role and file-log runtime tests remove their own randomly named containers, volumes and secrets on normal completion or handled failure. After interruption, inspect resources labelled for the test before removing them. Keep private evidence until review is complete; never upload the whole `.state` directory.
