# Architecture overview

enMAAS Mini separates client access, model routing, and accounting:

```text
client → MaaS/PriceTag gateway → Praxis → provider or vLLM
```

## Responsibilities

- **Client:** Uses a finite-lived key or JWT and never holds provider secrets.
- **MaaS/PriceTag:** Authenticates the caller, records usage, and enforces USD budgets.
- **Praxis:** Selects the approved provider, holds provider credentials, and applies token quotas.
- **vLLM:** Optionally supplies a local OpenAI-compatible endpoint.

## Security boundary

The gateway is the only component with provider credentials. Remote access is
terminated with TLS and authenticated before requests reach Praxis. vLLM and
management ports remain private unless a guide explicitly changes that boundary.

## Next step

Follow the [remote gateway with PriceTag guide](../remote-gateway-pricetag/README.md).
