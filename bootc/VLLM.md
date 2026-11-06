# vLLM bootc deployment

The `vllm-cpu` and `vllm-gpu` images install a repeatable RHEL environment for
local OpenAI-compatible inference. They do not include Praxis, cloud-provider
credentials, or a remote gateway.

## Select and boot an image

```console
sudo bootc switch quay.io/redhat-et/enmaas-mini-vllm-cpu:v0.1
sudo bootc status
sudo systemctl reboot
```

Use `enmaas-mini-vllm-gpu:v0.1` for an NVIDIA host. After reboot, verify the
service:

```console
systemctl status secure-single-server-vllm.service
journalctl -u secure-single-server-vllm.service -b
```

## Connect a gateway

From a separate Praxis gateway host, use the private vLLM endpoint:

```console
sudo scripts/common/install --vllm-endpoint VLLM_PRIVATE_IP:8000
```

Keep port 8000 on a private network. Do not expose vLLM directly to the
internet.
