# Mock provider tests

`tests/mocked-provider.py` exercises gateway contracts without paid provider
calls. It has offline and container-based gateway suites:

```console
python3 tests/mocked-provider.py --suite offline --engine docker
python3 tests/mocked-provider.py --suite gateways --engine docker
```

The suites cover provider substitution, routing, quota behavior, shared-gateway
profiles, and error propagation. Evidence is written under `evidence/`; inspect
it before treating a run as qualification.
