# External identity tests

The issuer slice provides a shared realm generator, protected RHEL Quadlet
inputs, a dedicated-host installer and isolated security probes.

[RHEL setup and boundaries](../../docs/testing/external-services/keycloak-rhel.md)

Run unit contracts without cloud credentials or containers:

```console
python3 -m unittest discover -s tests/external-services/unit -v
bash -n tests/external-services/install-keycloak
shellcheck -x tests/external-services/install-keycloak
```

With a running local Podman engine, run independent temporary fixtures:

```console
python3 tests/external-services/issuer-routes-runtime.py
python3 tests/external-services/issuer-lockout.py
```

The route test publishes no host ports and checks canonical issuer metadata,
forged forwarding headers, forbidden administration/master-realm paths and
encoded traversal. The lockout test publishes a random loopback port, verifies
successful login, rejection during temporary lockout and recovery. Allow roughly
two minutes for the real configured lockout period.

Both use synthetic credentials and remove their own test containers/secrets.
They do not touch the running gateway or benchmark. CI executes unit and runtime
checks with pinned images; local rootless Podman and CI's sudo Podman execution
are separate evidence from the RHEL Quadlet installation.

`realm.py` contains configuration only; it must not import monitoring, local
deployment or benchmark modules. `images.json` records the issuer's pinned
images. The role certificate generator also prepares future gateway and
telemetry bundles, with separate HTTPS and client-authentication trust.
