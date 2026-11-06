# Testing guide

The repository separates fast offline contracts, container tests, and
deployment-specific checks.

## Offline checks

```console
python3 -m unittest discover -s tests/common -p 'test_*.py'
python3 -m unittest discover -s tests/pricetag -p 'test_*.py'
python3 -m unittest discover -s bootc/tests -p 'test_*.py'
shellcheck -x bootc/build bootc/scripts/*
```

macOS system Bash 3.2 cannot run every shell contract. Use Linux with Bash 4+
for the complete offline suite.

## Container checks

With Docker or Podman available, run:

```console
python3 tests/mocked-provider.py --suite offline --engine docker
python3 tests/mocked-provider.py --suite gateways --engine docker
```

## PriceTag checks

- [Pilot limits and qualification](pricetag.md)
- [Demo CI procedure](pricetag-demo-ci.md)
- [Management demo](pricetag-management-demo.md)
- [Performance procedure](pricetag-perf.md)
- [AWS runbook](aws-pricetag.md)

## AWS support

The AWS helpers can provision all-in-one, remote-gateway, and vLLM scenarios.
See [AWS operations](aws-operations.md) for access, recovery, and cleanup.
