# Dedicated Keycloak test host

Install a private-CA issuer on a **fresh RHEL test VM**. PostgreSQL, Keycloak and
its Praxis ingress run as rootless `praxis-svc` Quadlet services. This is testing
infrastructure, not a production identity-provider installer.

The public ingress permits only the test realm and static resources. Keycloak
administration binds to host loopback; the database has no published port.
Keep SSH and TCP 8443 restricted to reviewed source addresses. The installer
changes firewalld, never cloud security groups.

## Prepare certificates on the workstation

Use a reviewed checkout and set the three VM addresses. The gateway and
observability addresses define exact OIDC client callbacks; this procedure does
not install either service.

```console
KEYCLOAK_HOST_IP=YOUR_ISSUER_IP
GATEWAY_HOST_IP=YOUR_GATEWAY_IP
OBSERVABILITY_HOST_IP=YOUR_OBSERVABILITY_IP
TLS_DIR="$PWD/.state/issuer-certificates"
python3 tests/external-services/certificates.py \
  --keycloak "$KEYCLOAK_HOST_IP" --gateway "$GATEWAY_HOST_IP" \
  --observability "$OBSERVABILITY_HOST_IP" --output "$TLS_DIR"
```

This creates separate HTTPS and telemetry-client authorities and per-role
bundles, valid for 30 days. **Keep `authorities/` on the workstation.** Transfer
only `keycloak/` to the issuer using verified SSH. Do not disable host-key checks.
The output directory must be new; existing keys are never overwritten.

For example, after verifying the host fingerprint through a trusted channel:

```console
KEYCLOAK_RHEL_HOST="ec2-user@$KEYCLOAK_HOST_IP"
SSH_KEY="$HOME/.ssh/YOUR_KEY"
scp -i "$SSH_KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -r "$TLS_DIR/keycloak" "$KEYCLOAK_RHEL_HOST:~/enmaas-issuer-tls"
```

Copy the reviewed repository commit to that host using the
[quickstart checkout procedure](../../quickstarts/remote-gateway-pricetag/README.md#2-copy-the-checkout),
with `RHEL_HOST` set to this issuer. Do not run the gateway installer on it.

## Prepare and install on RHEL

From the copied repository on the issuer host, set the same three addresses
and the permitted workstation/peer IPv4 CIDRs. Each must be `/24`–`/32`; prefer
individual `/32` addresses. Set them explicitly in this SSH shell.

```console
cd ~/secure-single-server
KEYCLOAK_HOST_IP=YOUR_ISSUER_IP
GATEWAY_HOST_IP=YOUR_GATEWAY_IP
OBSERVABILITY_HOST_IP=YOUR_OBSERVABILITY_IP
WORKSTATION_CIDR=YOUR_WORKSTATION_IP/32
GATEWAY_CIDR=YOUR_GATEWAY_SOURCE_IP/32
OBSERVABILITY_CIDR=YOUR_OBSERVABILITY_SOURCE_IP/32
sudo dnf install -y python3 openssl
sudo install -d -m 700 /root/enmaas-issuer-tls
sudo install -m 600 ~/enmaas-issuer-tls/server.pem ~/enmaas-issuer-tls/server.key \
  ~/enmaas-issuer-tls/ca.pem ~/enmaas-issuer-tls/issuer-ca.pem /root/enmaas-issuer-tls/
sudo python3 tests/external-services/keycloak-host.py \
  --issuer "$KEYCLOAK_HOST_IP" --gateway "$GATEWAY_HOST_IP" \
  --observability "$OBSERVABILITY_HOST_IP" --output /root/enmaas-keycloak-inputs
sudo tests/external-services/install-keycloak /root/enmaas-keycloak-inputs \
  /root/enmaas-issuer-tls/server.pem /root/enmaas-issuer-tls/server.key \
  /root/enmaas-issuer-tls/ca.pem \
  "$WORKSTATION_CIDR" "$GATEWAY_CIDR" "$OBSERVABILITY_CIDR"
```

The generator creates immutable UUIDs and separate random passwords for admin,
Alice and Bob. Client/database/bootstrap secrets are separate. No secret values
are printed. The installer validates private input files, secret sizes,
certificate/key agreement, certificate names and the firewall before starting
services. It refuses existing installation markers, units and secrets.

Optional `--issuer-name identity.example.test --issuer-private-ip 10.0.0.10`
sets a canonical DNS issuer with private backchannel resolution for gateway peers.
Include that DNS name with `--keycloak-name` when generating certificates. DNS
and routing must already exist; these flags do not create them.

## Verify and connect clients

From an allowed workstation, validate the certificate, exact discovery identity,
and rejection of public administration, master-realm and traversal paths:

```console
python3 tests/external-services/keycloak-boundary.py \
  --url "https://$KEYCLOAK_HOST_IP:8443" --ca "$TLS_DIR/keycloak/ca.pem"
```

Inputs for later client installation remain on the issuer:

| Private file under `/root/enmaas-keycloak-inputs/` | Purpose |
| --- | --- |
| `gateway-oidc.json` | Gateway client settings; install on the gateway with its trusted issuer CA. |
| `identities.json` | Immutable UUIDs to provision in PriceTag; matching email alone is insufficient. |
| `observability-client-secret` | Separate observability client; access requires `/observability-admin`. |
| `credentials.json` | Initial test passwords and service secrets; never print the whole file. |

This slice prepares client inputs; gateway OIDC and the observability deployment
are separate integrations. It does not turn an issuer user into a PriceTag
administrator or issue an inference key.

To retrieve only Alice's saved initial password, run on the issuer host:

```console
sudo python3 tests/external-services/keycloak-password.py --user alice --stdout
```

The flag explicitly prints a credential: use a private terminal or pipe the
verified SSH command to a clipboard/password tool. The helper refuses service
secret names. A later password change makes the saved initial value obsolete.

## Failure recovery and qualification

Inspect partial installations before retrying. Never remove a marker or database
volume merely to bypass refusal. Check service status without dumping secrets:

```console
sudo -u praxis-svc env XDG_RUNTIME_DIR="/run/user/$(id -u praxis-svc)" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u praxis-svc)/bus" \
  systemctl --user status lab-keycloak-db.service lab-keycloak.service \
  lab-keycloak-proxy.service --no-pager
```

Local isolated tests cover certificate trust, route/header boundaries and
temporary login lockout. They use Keycloak's embedded development database;
they do not qualify RHEL's PostgreSQL lifecycle, SELinux, firewalld reachability,
reboot, backup or rotation. Run those checks on the target RHEL setup before
accepting it. Unrestricted public access and administrator MFA are not qualified.

Realm import initializes new storage; it is not an upgrade mechanism. The initial
three users are a test fixture, not bulk onboarding. Existing accounts must be
managed through Keycloak's private administration API.
