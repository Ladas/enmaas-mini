# Deployment methods

Choose the smallest deployment that meets your access-control and budgeting
requirements.

| Goal | Guide |
| --- | --- |
| Run one shared Praxis gateway on a host | [All-in-one gateway](quickstarts/all-in-one/README.md) |
| Serve remote clients over HTTPS with JWTs | [Remote gateway](quickstarts/remote-gateway/README.md) |
| Add user keys, budgets, and USD metering | [Remote gateway with PriceTag](quickstarts/remote-gateway-pricetag/README.md) |
| Use local OpenAI-compatible inference | [vLLM guide](quickstarts/common/vllm.md) |
| Deploy a repeatable RHEL OS image | [Bootc guide](../bootc/README.md) |

All methods keep provider credentials in the gateway deployment. Clients
receive only their own gateway credentials or short-lived keys.
