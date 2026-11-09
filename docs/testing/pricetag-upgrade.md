# Qualify a PriceTag source upgrade

Use mock providers and disposable databases. A passing Go test is not a passing
gateway upgrade: retain the API, browser, accounting and RHEL gates below.
Keep released installer defaults until the candidate passes all gates and its
replacement image is published and verified.

## Where to run

| Environment | Coverage |
| --- | --- |
| Workstation with Podman | Offline tests and real-Praxis routing tests using disposable containers. |
| Disposable Linux VM with rootful Podman | Full PostgreSQL/MaaS/PriceTag/Praxis API and browser deployment. The runner changes host deployment paths and refuses an existing installation. |
| Dedicated mock RHEL VM | Installer, rootless Quadlets, SELinux, restart behavior, complete demo and resource benchmarks. |

On macOS, the complete container deployment runner must run **inside a disposable
Linux VM**, with the checkout and source available there. Running its `sudo`
command on macOS is not equivalent. A RHEL/Fedora Podman VM also does not reproduce
GitHub's Ubuntu kernel/AppArmor environment; CI must pass separately.

## 1. Validate the selected source

Run from the enMAAS Mini checkout. Set the source to the reviewed PriceTag checkout:

```sh
METERING_SOURCE=/absolute/path/to/pricetag-metering
python3 tests/mocked-provider.py --suite offline --engine podman
python3 tests/pricetag/metering-unit.py --source "$METERING_SOURCE"
```

`metering-unit.py` runs `go test ./...` with an isolated PostgreSQL instance and
synthetic credentials. It removes its own containers/network afterward. Without
`DATABASE_URL`, many direct Go storage tests skip; do not count them as migration
qualification. Also run `go vet ./...` in the source checkout.

Run the candidate's UI unit tests and browser tests where present. Update them
to the retained upstream UI; preserve ownership, role, CSRF/origin, impersonation,
demotion, expiry, revocation and cross-team denial assertions.

## 2. Build an immutable candidate

After signing the source changes, build from their exact commit. Uncommitted
changes are not included: the helper builds a `git archive` of the chosen SHA.

```sh
test -z "$(git -C "$METERING_SOURCE" status --porcelain)" &&
METERING_REVISION=$(git -C "$METERING_SOURCE" rev-parse HEAD) &&
sudo python3 scripts/pricetag/build-metering \
  --source "$METERING_SOURCE" --revision "$METERING_REVISION" \
  --platform linux/amd64 --tag localhost/pricetag-metering:upgrade
```

Use the same CPU architecture as the target host. Build/import MaaS and acquire
Praxis using the [manual image instructions](../quickstarts/remote-gateway-pricetag/manual.md).
Root-owned Podman images must be tested with root-owned Podman here; importing
into the RHEL service account is a separate installer step.

## 3. Run the complete container suite

On the disposable Linux VM, install the pinned browser dependency and its OS
libraries as described in [the demo suite guide](pricetag-demo-ci.md). Set
`MAAS_IMAGE` and `PRAXIS_IMAGE` to the qualified references available in root's
image store:

```sh
METERING_IMAGE=localhost/pricetag-metering:upgrade
sudo python3 tests/pricetag/database-smoke.py &&
sudo python3 tests/pricetag/container-demo.py \
  --maas-image "$MAAS_IMAGE" --metering-image "$METERING_IMAGE" \
  --praxis-image "$PRAXIS_IMAGE" \
  --node-modules "$PWD/tests/pricetag/browser/node_modules" \
  --output "/var/tmp/pricetag-upgrade-$(date +%s)"
```

This exercises CLI/API/browser operations and synthetic inference. Keep logs
private; share only sanitized results. Containers and generated credentials are
removed by the runner. Retained diagnostics may contain sensitive test material.

## 4. Qualify the benchmark RHEL installation

First preserve the existing mock deployment's database, image IDs and protected
configuration. Test schema migration on a **database clone**. Do not point an
unqualified image at the only copy, and do not assume reverting its image can
undo migrations.

For a fresh mock host, follow the [management demo installation](pricetag-management-demo.md)
and select source/image overrides from [image options](../quickstarts/remote-gateway-pricetag/images.md).
The installer is not an in-place upgrade command. Preserve the baseline or use
a fresh test VM before following its installation steps.

After candidate activation, run from the checkout on benchmark RHEL:

```sh
sudo python3 tests/pricetag/demo-suite \
  --node-modules "$PWD/tests/pricetag/browser/node_modules" \
  --output "/root/pricetag-admin/upgrade-acceptance-$(date +%s)" &&
sudo python3 scripts/pricetag/benchmark --requests 20
```

When testing against a cloned database with a different name, add
`--database-name YOUR_CLONE_NAME` to `benchmark` (and to standalone `observe` or
`perf verify` runs). This keeps ledger checks and storage measurements on the
upgraded database.

The suite includes native routing, user/key lifecycle, public boundaries,
pricing, quotas, personal/team scopes and impersonation. For longer load and
CPU/memory/disk/WAL evidence, follow [the benchmark guide](pricetag-perf.md).
Tests retain synthetic accounting history; keep this separate from a presentation
or real-provider deployment.

## Release gate

- All existing behavioral and security assertions pass against the candidate.
- Fresh-schema and previous-release database migration tests pass; recorded
  charges and raw/rollup totals remain consistent.
- Current-role and personal-key checks still hold with standalone MaaS and no
  Kubernetes API. New OIDC code is not implicitly enabled.
- Image source labels match the signed candidate; source build, installer,
  publication and CI pins agree. Check public pull access before changing defaults.
- Fresh RHEL install/restart and measured mock workload pass. Keep a separate
  explicit qualification for external PostgreSQL or real provider credentials.
