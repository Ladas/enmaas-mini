# Standalone MaaS and PriceTag images

The [image workflow](../../.github/workflows/pricetag-images.yml) builds two
`linux/amd64` images for the single-server gateway:

| Image repository | Source |
| --- | --- |
| `quay.io/redhat-et/secure-single-server-maas-standalone` | [MaaS standalone revision](https://github.com/Ladas/models-as-a-service/commit/6ac4c80ebc95f590e5f24593ac15bb80c7f9fa1d) |
| `quay.io/redhat-et/secure-single-server-pricetag-metering` | [PriceTag management demo revision](https://github.com/Ladas/pricetag-metering/commit/ce9c6c51b8dff178637003945b517255c54fc853) |

PriceTag includes the management demo, scoped dashboards and the reviewed key, budget and pricing fixes.
The optional provider/model adapter follow-up is excluded. These changes are
fork dependencies, not merged upstream features. MaaS is unchanged.

MaaS uses its source Dockerfile; PriceTag uses the repository's packaging-only
Containerfile. Application commits are fixed in the workflow and checked against
image labels. MaaS base image tags remain upstream-defined and mutable, so a
source revision alone does not imply a byte-for-byte reproducible image.

## Registry setup

Retain the existing public `secure-single-server-*` application repositories
until replacement images have been published and qualified. The repository
move does not require changing image names. Grant
the existing publishing account **Write** on each. The workflow uses the same
`QUAY_USERNAME` and `QUAY_TOKEN` GitHub secrets as the bootc image publisher.
These are stored in the `bootc-image-main` GitHub environment; only upstream
`main` publication runs select it. Other runs select `bootc-image-pr`.
No registry credentials are required by clients pulling these public images.
Configure the environment in **enmaas-mini**; GitHub secrets are not copied
with repository files. Before enabling publication here, disable publication
from the old repository so there is one release owner. Never put publishing
secrets in `bootc-image-pr`.

If image repositories are renamed later, first publish and verify the new
digests, then update installer, manual instructions and workflow together.

## Build, test and publish

Pull requests build both images and run isolated PostgreSQL-backed checks:
standalone startup without Kubernetes, schema migrations, and rejection of
unauthenticated metering events. Tests use ephemeral containers and synthetic
credentials, with ports bound only to loopback. This is a component smoke test;
full gateway authentication, quotas and performance require deployment tests.

Only runs on `redhat-et/enmaas-mini` `main` publish, after both images
pass. Manual dispatch on `main` can publish the initial images:

```console
gh workflow run pricetag-images.yml --repo redhat-et/enmaas-mini --ref main
gh run list --repo redhat-et/enmaas-mini --workflow pricetag-images.yml --limit 5
```

Each image gets `sha-<full enMAAS Mini commit>` as its tag. The run summary
prints exact `repository@sha256:digest` references; use those in deployments.
A rerun can replace a tag because upstream base tags may move; installed digest
references remain fixed. There is no `latest` tag or automatic deployment update.
Publishing two repositories is not atomic: if the second push fails, rerun and
use the two digests from a successful run.

## Test new source versions

Update source SHAs in the workflow and the corresponding build-helper defaults
when qualifying a release. Keep the deployment's expected source revisions in
sync. The MaaS fork remains necessary for the pinned standalone runtime.

To run the component smoke test against locally built images:

```console
sudo python3 tests/pricetag/component-images.py \
  --maas-image localhost/pricetag-maas:standalone \
  --metering-image localhost/pricetag-metering:demo-ce9c6c5
```

ARM64 publication, image signatures and SBOM/provenance publication are not
implemented by this workflow. PostgreSQL and Praxis continue to use their
existing external image repositories.

## Verify the released installer references

The amd64 validation job checks anonymous pulls, image architecture and application
source labels against the installer defaults, independently of source-build CI:

```console
python3 tests/pricetag/published-images.py --engine podman
```

This pulls images using an empty registry credential file; it does not run the
applications or replace deployment qualification. The manual image references,
installer defaults and publisher source/repository settings are also checked by
the offline suite.
