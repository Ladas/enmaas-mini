# Gateway OIDC configuration

**Integration qualification is in progress.** Local browser tests through the rendered Praxis gateway verify provisioned identity login, unknown-identity denial, no implicit administrator elevation, and deactivation of an existing session. Shared issuer login also reaches observability through its group gate. Current-role checks and shared logout pass locally with the separate PriceTag CSP fix described below. Source builds pin the fix; the published-image mode has not been updated for this lab. Role synchronization and full RHEL acceptance remain pending.

## Identity contract

PriceTag validates the OIDC response and maps the verified `rhatUUID` claim to an existing, active PriceTag partner UUID. Email is display information, not an identity key. OIDC groups do not automatically grant PriceTag administrator or manager roles. The client requests standard `openid profile email` scopes; group claims come from the client mapper, without requiring a custom `groups` scope.

The test Keycloak realm has two confidential clients with separate secrets:

- `observability`: only the explicit observability administrator group passes the proxy.
- `enmaas-mini`: authorization-code flow with PKCE; `rhatUUID` maps to Keycloak's immutable user ID. A matching PriceTag identity must be provisioned through its management API before login.

The local fixture records those UUIDs in its private `identities.json`. Recreating the realm requires deliberately reconciling identity records; matching an existing email must never transfer another identity's spending history or privileges.

## Protected installer input

Create a root-owned, mode `0600` JSON file on the gateway host. Enter the client secret using a protected editor; do not put it in command arguments or shell history.

```json
{
  "issuer_url": "https://keycloak.example:8443/realms/enmaas",
  "client_id": "enmaas-mini",
  "client_secret": "replace-with-the-client-secret",
  "ca_file": "/root/enmaas-inputs/issuer-ca.pem"
}
```

Omit `ca_file` for an issuer with a publicly trusted certificate. The supplied CA file contains public certificates only. Keep the CA signing key off the gateway.

Add this option to the normal installation command:

```sh
--oidc-config /root/enmaas-inputs/oidc.json
```

The installer derives the exact callback as `https://<hostname>:8443/oauth/callback` and the post-logout URL as `https://<hostname>:8443/login`. Register these exact URLs with Keycloak; do not use wildcard redirects. This option does not create the Keycloak client or PriceTag identities.

Only GET `/oauth/login` and `/oauth/callback` are added to the gateway's public route allowlist. PriceTag owns protocol validation and session creation. Development mode, test login and claim-debug output remain disabled. The client secret is written to the protected metering environment file; only the metering container receives the issuer CA mount. Existing inference keys remain separate from browser OIDC login.

## Acceptance still required

- Successful login for the provisioned administrator, manager and team member.
- Rejection of unknown, inactive and mismatched immutable identities.
- State, nonce, issuer, audience, redirect and certificate validation through the gateway.
- Current-role checks, suspension, logout and expiry across both applications.
- No credentials, authorization codes or session cookies in gateway, application or proxy logs.
- Real RHEL network boundaries and CA distribution; the local shared pod is not evidence of host isolation.

## Provision an identity without SQL

This path requires the source-build candidate with PriceTag's partner-user and OIDC APIs. The previously published metering image is not qualified for this lab; use the source-build option until a tested image is published.

On the gateway host, create a root-private profile using the **actual immutable UUID returned by the issuer**. The UUID below is illustrative; do not substitute the email or create a different random UUID.

```json
{
  "user_id": "9fc73c22-ff5a-4037-b8b1-78b2d96b2f38",
  "tags": {
    "email": "alice@example.test",
    "first_name": "Alice",
    "last_name": "Lab"
  }
}
```

From the installed repository on the gateway:

```sh
sudo python3 scripts/pricetag/oidc-user --profile /root/enmaas-inputs/alice.json
```

The helper calls `PUT /api/v1/users/{UUID}` on loopback with a separate partner API secret. It creates or updates display attributes for that UUID; it does **not** issue a key, grant an administrator role or change a budget. It never retries mutations automatically. Conflicting existing identities must be investigated, not merged by email or repaired with SQL.

OIDC-enabled preparation creates the secret in `/etc/praxis-pricetag/partner-secret` and supplies it to metering as `USER_MANAGEMENT_API_SECRET`. The public Praxis listener does not expose `/api/v1/users`. Run provisioning over SSH; do not share this secret with users, clients or the identity provider.

After provisioning, the existing management API sets roles and budgets using the identity's current login (initially its email). For example, save the following in a root-private request file and use the existing `manage` helper:

```json
{"subject": "alice@example.test", "monthly_usd": 5}
```

```sh
sudo python3 scripts/pricetag/manage PUT budgets \
  --input /root/enmaas-inputs/alice-budget.json \
  --output /root/enmaas-inputs/alice-budget-result.json
```

Use a new output path for each operation. Keep the initial SSH-created administrator until the SSO administrator and recovery procedure have been tested. Do not create the same person independently with the legacy `user` helper before provisioning their issuer UUID: that helper allocates its own identity.

## Logout source pin

Source builds use [PriceTag commit 2281e1a](https://github.com/Ladas/pricetag-metering/commit/2281e1a84bfc3b998e7db36bc01bae88130bfcdd), which permits the configured HTTPS issuer origin in the logout confirmation form policy. Same-origin POST validation and same-origin-only impersonation forms remain in place. Current-role changes, confirmed logout and bounded observability-session expiry passed local browser qualification with this change.

Use `--image-mode source` for this lab. The published-image mode still points to the earlier image and is not qualified for this OIDC lifecycle. RHEL acceptance remains separate.
