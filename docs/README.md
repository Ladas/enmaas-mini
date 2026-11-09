# Documentation map

enMAAS Mini focuses on Praxis model routing, PriceTag metering and budgets,
and the small set of deployment components needed to operate them.

## Start here

1. Read the [architecture overview](quickstarts/architecture-walkthrough/README.md).
2. Choose a [deployment method](deployment-methods.md).
3. For user keys and USD budgets, follow the
   [remote gateway with PriceTag guide](quickstarts/remote-gateway-pricetag/README.md).

## Guides

- [All-in-one gateway](quickstarts/all-in-one/README.md)
- [Remote HTTPS/JWT gateway](quickstarts/remote-gateway/README.md)
- [Remote gateway with PriceTag](quickstarts/remote-gateway-pricetag/README.md)
- [Common gateway configuration](quickstarts/common/README.md)
- [Optional vLLM inference](quickstarts/common/vllm.md)
- [Bootc image guide](../bootc/README.md)

## Operations

- [Testing guide](testing/README.md)
- [AWS deployment runbook](testing/aws-pricetag.md)
- [PriceTag pilot limits and qualification](testing/pricetag.md)
- [PriceTag performance procedure](testing/pricetag-perf.md)

## Preview locally

```console
scripts/docs/serve build
scripts/docs/serve
```
