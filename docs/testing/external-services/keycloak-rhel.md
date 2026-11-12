# Dedicated RHEL Keycloak test host

**RHEL qualification pending.** The generated Quadlets started as rootless systemd services in a local Podman Linux VM. Issuer discovery, public admin/master rejection, traversal probes and persona logins through Praxis passed there. RHEL firewalld, SELinux, reboot recovery and the complete installer still require testing. Use a disposable test VM.

## Host prerequisites

Use the reviewed repository checkout on this host. Install the tools needed to generate inputs before running the installer:

```sh
sudo dnf install -y python3 python3-pyyaml openssl
```

## Prepare

Use the Keycloak VM from the three-host AWS lab. Keep SSH restricted to your workstation. TCP 8443 must be reachable from the workstation, gateway and observability hosts. This installer changes the host firewall, not AWS security groups.

From the repository on the Keycloak host, prepare protected inputs with the three public IPv4 addresses:

```sh
sudo python3 tests/external-services/keycloak-host.py \
  --issuer "$KEYCLOAK_HOST_IP" \
  --gateway "$GATEWAY_HOST_IP" \
  --observability "$OBSERVABILITY_HOST_IP" \
  --output /root/enmaas-keycloak-inputs
```

The generator creates a dedicated realm, immutable UUIDs for three test users, separate gateway/observability client secrets, and Quadlet definitions. Passwords remain in the private `credentials.json`; they are not printed. Existing inputs are never overwritten.

Supply a matching server certificate/key and public issuer CA, owned by root with mode `0600`. The server certificate must cover the issuer IP and `localhost` (the loopback administration endpoint). Generate/sign certificates on the workstation: do not copy the CA signing key to this VM.

## Install

Run from the repository on the issuer host. List narrow source networks for the workstation and the two peer VMs; use the addresses actually seen by the host firewall.

```sh
sudo tests/external-services/install-keycloak \
  /root/enmaas-keycloak-inputs \
  /root/enmaas-tls/server.pem \
  /root/enmaas-tls/server.key \
  /root/enmaas-tls/ca.pem \
  "$WORKSTATION_CIDR" "$GATEWAY_SOURCE_CIDR" "$OBSERVABILITY_SOURCE_CIDR"
```

The service account is `praxis-svc`. Containers are rootless, capability-dropped and managed by its user systemd instance with lingering enabled. Database state is a named volume. Application credentials are imported as Podman secrets; only their consuming containers receive them.

| Endpoint | Boundary |
| --- | --- |
| Public HTTPS `8443` | Praxis allows `/realms/enmaas-lab/` and `/resources/`; other routes return 404. Source IP restrictions remain in AWS and firewalld. |
| Keycloak administration HTTPS `127.0.0.1:18443` | Host-local administration over SSH; no public admin route. No SSH tunnel is required by this runbook. |
| Keycloak HTTP `8080` | Container network only, consumed by the local HTTPS proxy. |
| PostgreSQL `5432` | Container network only; no host port. |

Do not use the temporary bootstrap administrator as a permanent operating account. The administrative account setup and recovery procedure still need qualification. The three realm users and passwords are test fixtures, not production onboarding.

## Connect the other services

The generator creates separate gateway and observability client files. From the **administrator workstation**, transfer only those files through SSH to their consuming hosts. The commands refuse existing destination files and do not print secret values:

```sh
(
  set -euo pipefail
  SSH_OPTS=(-i "$SSH_KEY" -o IdentitiesOnly=yes)
  ssh "${SSH_OPTS[@]}" "$GATEWAY_RHEL_HOST" \
    'sudo install -d -m 0700 /root/enmaas-inputs'
  ssh "${SSH_OPTS[@]}" "$OBSERVABILITY_RHEL_HOST" \
    'sudo install -d -m 0700 /root/enmaas-inputs'
  ssh "${SSH_OPTS[@]}" "$KEYCLOAK_RHEL_HOST" \
    'sudo cat /root/enmaas-keycloak-inputs/gateway-oidc.json' | \
    ssh "${SSH_OPTS[@]}" "$GATEWAY_RHEL_HOST" \
    "sudo sh -c 'umask 077; set -C; cat > /root/enmaas-inputs/oidc.json'"
  ssh "${SSH_OPTS[@]}" "$KEYCLOAK_RHEL_HOST" \
    'sudo cat /root/enmaas-keycloak-inputs/observability-client-secret' | \
    ssh "${SSH_OPTS[@]}" "$OBSERVABILITY_RHEL_HOST" \
    "sudo sh -c 'umask 077; set -C; cat > /root/enmaas-inputs/observability-client-secret'"
  ssh "${SSH_OPTS[@]}" "$GATEWAY_RHEL_HOST" \
    "sudo sh -c 'test ! -e /root/enmaas-inputs/issuer-ca.pem && install -m 0600 /root/enmaas-tls/issuer-ca.pem /root/enmaas-inputs/issuer-ca.pem'"
)
```

Do not transfer the issuer's entire `credentials.json` or its bootstrap administrator password. If a pipe fails, inspect the destination before retrying; it may contain an incomplete file. Both configuration validators reject empty or malformed inputs before installation.

Continue with [gateway OIDC setup](oidc.md) and the [observability installer](observability-rhel.md). Provision the UUIDs recorded in `identities.json` through the partner API before attempting gateway SSO; matching email addresses alone do not establish identity. Observability uses its separate client and explicit administrator group.

## Inspect or recover

```sh
sudo -u praxis-svc env \
  XDG_RUNTIME_DIR="/run/user/$(id -u praxis-svc)" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u praxis-svc)/bus" \
  systemctl --user status lab-keycloak-db.service lab-keycloak.service \
  lab-keycloak-proxy.service --no-pager
```

The installer refuses an existing `/etc/enmaas-keycloak-lab` marker, unit or secret. After a partial failure, inspect the services and inputs rather than deleting state or recreating credentials. Do not publish raw logs or private input files.

After startup, verify the public boundary from a permitted source:

```sh
python3 tests/external-services/keycloak-boundary.py \
  --url "https://${KEYCLOAK_HOST_IP}:8443" --ca /path/to/issuer-ca.pem
```

For local ARM testing, use a native Praxis image with the same verified source revision; an AMD64 image under emulation failed upstream connections with an unsupported socket option. Do not treat an emulated-image failure as a RHEL result.

Before RHEL acceptance, verify certificate/SAN checks, exact issuer discovery, public admin and master-realm denial (including encoded/normalized paths), all persona logins, restricted peer access, reboot recovery and secret/certificate rotation. The local shared-pod tests do not replace these checks.
