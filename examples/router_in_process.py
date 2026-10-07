"""Same routing as the proxy, inside your own Python process (no server).
pip install litellm pyyaml

    export UPSTREAM_API_KEY=...   # your ArgoLink key
    python examples/router_in_process.py
"""
import os

import yaml
from litellm import Router

with open(os.path.join(os.path.dirname(__file__), "..", "config.yaml"), encoding="utf-8") as handle:
    config = yaml.safe_load(handle)

model_list = []
for entry in config["model_list"]:
    params = dict(entry["litellm_params"])
    params["api_key"] = os.environ["UPSTREAM_API_KEY"]  # resolve the os.environ/ reference
    model_list.append({"model_name": entry["model_name"], "litellm_params": params,
                       "model_info": entry.get("model_info", {})})

router = Router(
    model_list=model_list,
    model_group_alias=config["router_settings"]["model_group_alias"],
    fallbacks=config["router_settings"]["fallbacks"],
    num_retries=2,
)

reply = router.completion(model="deepseek-v4-pro",
                          messages=[{"role": "user", "content": "Summarise CAP theorem in 2 lines."}])
print(reply.model, reply._hidden_params.get("response_cost"))
print(reply.choices[0].message.content)
