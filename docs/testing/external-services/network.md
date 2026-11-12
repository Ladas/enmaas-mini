# Lab peer network rules

Run these commands only on the AWS administrator workstation after all three VMs are running. Keep AWS credentials off the VMs. The helper reads each launch journal and verifies the current account, ownership tags, instance state, VPC and attached security group.

## Review and grant

```sh
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
python3 tests/external-services/network.py \
  --account-id "$ACCOUNT_ID" --region "$REGION" --prefix "$RUN_PREFIX"
```

Review the account, resource IDs and three missing rules. Apply requires a separate typed confirmation and revalidates resources afterward:

```sh
python3 tests/external-services/network.py \
  --account-id "$ACCOUNT_ID" --region "$REGION" --prefix "$RUN_PREFIX" --apply
```

| Destination | Source | Purpose |
| --- | --- | --- |
| Keycloak TCP 8443 | Gateway public IP `/32` | Issuer discovery and token exchange |
| Keycloak TCP 8443 | Observability public IP `/32` | Issuer discovery and token exchange |
| Observability TCP 24443 | Gateway security group, private-IP path | Collector mTLS ingestion |

The issuer uses the same public-IP URL for browsers and both clients. Security-group references do not authorize traffic to a peer's public IP, so issuer rules use explicit public `/32` addresses. Telemetry must target the observability **private IP**, included in its certificate SANs, and still requires the dedicated client certificate.

No SSH, database, raw query or administrator port is added. The original workstation SSH/HTTPS rules remain. Unexpected ingress causes refusal rather than automatic removal. If an instance is replaced or its public address changes, review and remove obsolete peer rules explicitly before rerunning.

## Host firewall

Security groups and host firewalls must agree:

- Keycloak installer: workstation `/32`, gateway public `/32`, observability public `/32` for 8443.
- Observability installer: workstation `/32` for browser 8443; gateway **private** `/32` for telemetry 24443.
- No broad subnet or public collector grant is needed.

After grants, use this helper without `--apply` to verify peer ingress. The original VM verifier checks the initial launch contract and may reject these additional rules. This network check does not prove TLS, service readiness or RHEL firewall behavior; test those through the service runbooks.

## Partial failure and cleanup

The command adds only missing rules and never deletes resources. After a partial API failure, inspect current rules and rerun the read-only plan. During cleanup remove the gateway-to-observability security-group reference before deleting either group. See [manual cleanup](cleanup.md).

Cloud-free tests cover exact ports/sources, VPC/address mismatch, ownership, stopped instances, unexpected ingress and already-present rules. Real AWS/RHEL acceptance remains pending.
