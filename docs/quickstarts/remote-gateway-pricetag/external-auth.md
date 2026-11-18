# External sign-in and supplied TLS

Optional inputs for a **fresh gateway installation**. Configure these on the
gateway host before running the [installer](README.md#3-install). They do not
install an identity provider or request certificates.

## Browser sign-in with OIDC

The default published PriceTag image predates OIDC support and is rejected when
`--oidc-config` is supplied. Use a reviewed compatible source revision; the
local integration deployment exercised
[2281e1a](https://github.com/Ladas/pricetag-metering/commit/2281e1a84bfc3b998e7db36bc01bae88130bfcdd).
Other revisions need their own login, authorization and logout checks.

1. Register a confidential client with your HTTPS OIDC issuer. Allow exactly
   `https://GATEWAY_HOST:8443/oauth/callback` as its redirect URI and
   `https://GATEWAY_HOST:8443/login` as the post-logout redirect. Do not use wildcard redirects.
2. Create a root-owned credential file. Enter the actual client secret through
   the editor, never a shell argument or a committed configuration:

   ```console
   sudo install -m 600 /dev/null /root/gateway-oidc.json
   sudoedit /root/gateway-oidc.json
   ```

   ```json
   {
     "issuer_url": "https://identity.example/realms/gateway",
     "client_id": "gateway",
     "client_secret": "REPLACE_IN_PRIVATE_FILE"
   }
   ```

   For a private issuer CA, add `"ca_file": "/root/issuer-ca.pem"` (root-owned,
   not writable by other users). Optional `issuer_private_ip` maps the issuer's
   DNS name to an RFC1918 IPv4 address inside the metering container; HTTPS still
   validates the issuer's DNS identity. Never put a CA signing key on the gateway.
3. Add these options to your installer command, alongside your normal provider
   options and credentials:

   ```console
   --image-mode source \
   --metering-revision 2281e1a84bfc3b998e7db36bc01bae88130bfcdd \
   --oidc-config /root/gateway-oidc.json
   ```

Only GET `/oauth/login` and GET `/oauth/callback` are added to the public route
allowlist. PriceTag validates OIDC and owns the browser session; development,
test-login and claims-debug modes stay disabled. Inference continues to use MaaS
keys. SSO does not grant an administrator role or create an inference key.

## Register an issuer identity

The tested partner-API contract uses an **immutable issuer UUID**, not a display
name. As an administrator, verify the UUID in your issuer before provisioning it.
Prepare a root-owned mode-0600 JSON profile with this shape:

```json
{
  "user_id": "00000000-0000-4000-8000-000000000001",
  "tags": {
    "email": "bob@example.test",
    "first_name": "Bob",
    "last_name": "Example"
  }
}
```

Then run on the gateway host from the installed repository:

```console
sudo python3 scripts/pricetag/oidc-user --profile /root/bob-profile.json
```

This calls the loopback-only PriceTag partner API using a separate root-private
secret. It does not expose that API publicly or accept roles in the profile.
Manage roles, budgets and keys separately through the [management interfaces](management-api.md).
Non-UUID subjects and automatic issuer lifecycle synchronization are not covered
by this helper.

## Use a supplied gateway certificate

Provide a root-owned directory containing `server.pem` (server certificate and
intermediates), `server.key` (mode 0600) and `ca.pem` (trusted CA certificates).
The directory and certificates must not be writable by other users or symlinks.
Add `--tls-bundle /root/gateway-tls` to the installer command.

The bundle must validate the gateway hostname, `localhost` and `127.0.0.1`,
because existing service checks use loopback. The key must match and the leaf
certificate must have at least seven days remaining. Validation uses real TLS
handshakes before host changes. Only leaf credentials and the public CA are copied.

This path is suitable for a private CA. Public issuers do not issue certificates
for localhost: public HTTPS needs a separate ingress/check design. Certificate
renewal is not automated by this option.

## Verify before enabling access

- Bring the issuer up before starting PriceTag. The tested revision can start
  without OIDC if initial issuer discovery fails; gateway HTTPS readiness alone
  does not qualify SSO. Check `/oauth/login` and complete a browser login/logout.
- Confirm an ordinary user cannot open administration pages and sees only their
  own usage; verify manager scope separately.
- Check inference with an ordinary user's MaaS key. Confirm key revocation and
  budget denial separately from browser sign-out.
- Keep issuer administration, partner APIs and MaaS management private. This
  option does not configure firewall rules or qualify unrestricted public access.
