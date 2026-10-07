# LiteLLM Gateway for GPT-6 Sol, Claude Opus 5, DeepSeek and GLM

A ready-to-run [LiteLLM](https://github.com/BerriAI/litellm) proxy config that puts ten chat models from [ArgoLink](https://argolink.io/gh-litellm-gateway)'s OpenAI- and Anthropic-compatible API behind one endpoint and one key, with aliases, a weighted model group, fallbacks, and spend tracking at the prices ArgoLink actually charges.

[config.yaml](./config.yaml) · [Quick start](#quick-start) · [Models](#models-in-configyaml) · [Routing](#aliases-weighted-groups-and-fallbacks) · [Cost tracking](#cost-tracking) · [FAQ](#faq)

<sub>Last checked 2026-10-07. Prices come from ArgoLink's public catalog (revision `0315cdd070b19ded`). The config was loaded by LiteLLM 1.104.0 and exercised against a local mock upstream that recorded each request path and header (table below); no live traffic was sent. Unofficial: not affiliated with BerriAI or the LiteLLM project.</sub>

## How a request travels

| Your app calls the proxy | Deployment prefix | LiteLLM calls upstream | Auth header it sends |
|---|---|---|---|
| `POST /v1/chat/completions` | `openai/` | `https://argolink.io/v1/chat/completions` | `Authorization: Bearer …` |
| `POST /v1/responses` | `openai/` | `https://argolink.io/v1/responses` | `Authorization: Bearer …` |
| `POST /v1/chat/completions` (Claude) | `anthropic/` | `https://argolink.io/v1/messages`, translated | `x-api-key: …` |
| `POST /v1/messages` | `anthropic/` | `https://argolink.io/v1/messages` | `x-api-key: …` |

The two `api_base` values differ on purpose. An `openai/` deployment takes the base that ends in `/v1`. For an `anthropic/` deployment LiteLLM appends `/v1/messages` itself, so its base is the bare origin `https://argolink.io`; adding `/v1` there produces `/v1/v1/messages`, which returns 404.

Why route Claude through `anthropic/` at all? ArgoLink also converts Chat Completions for Claude models, but `/v1/messages` is the endpoint its Claude pages recommend, and the Anthropic route keeps `cache_control`, thinking blocks and tool-use blocks native.

## Models in config.yaml

| Model group (alias) | LiteLLM `model` | ArgoLink price, input / output per 1M tokens | Watch out for |
|---|---|---:|---|
| `gpt-6-sol` (`smart`) | `openai/gpt-6-sol` | $0.60 / $3.00 | On Chat Completions it calls tools only with `reasoning_effort: none`; send tool + reasoning work to `/v1/responses` |
| `gpt-5.6-luna` | `openai/gpt-5.6-luna` | $0.06 / $0.36 | Cheapest GPT in the catalog; used as the last fallback |
| `claude-opus-5` (`claude`) | `anthropic/claude-opus-5` | $2.00 / $10.00 | Thinking can be turned off only at effort `high` or lower |
| `claude-sonnet-5` | `anthropic/claude-sonnet-5` | $0.80 / $4.00 | `temperature`, `top_p`, `top_k` must stay at their defaults; any other value returns 400 |
| `grok-4.6` | `openai/grok-4.6` | $0.60 / $1.80 | Always reasons |
| `deepseek-v4-pro` | `openai/deepseek-v4-pro` | $0.528 / $1.584 | Billed 2× on weekdays 09:00–12:00 and 14:00–18:00 Beijing time |
| `deepseek-v4.1-flash` | `openai/deepseek-v4.1-flash` | $0.12 / $0.48 | Same peak-hour rule; reads images |
| `glm-5.3` | `openai/glm-5.3` | $1.12 / $3.52 | Thinking cannot be disabled |
| `glm-5.3-flash` | `openai/glm-5.3-flash` | $0.12 / $0.40 | `low` effort runs as `high` |
| `kimi-k2.6` | `openai/kimi-k2.6` | $0.76 / $3.20 | Thinking stays off until you send `reasoning_effort` |
| `budget` (`cheap`) | two deployments, weighted 3:1 | $0.12 input either way | `deepseek-v4.1-flash` ×3, `glm-5.3-flash` ×1 |

Prices and caveats: the model pages at `argolink.io/en/models/<id>`, read 2026-10-07. The catalog lists 28 chat models; `python scripts/gen_config.py --all-chat` writes a config with every one of them.

## Quick start

With pip:

```bash
git clone https://github.com/lennoxhollister/litellm-gateway && cd litellm-gateway
pip install 'litellm[proxy]'
export UPSTREAM_API_KEY=...                             # an ArgoLink API key
export LITELLM_MASTER_KEY=sk-$(openssl rand -hex 16)    # what your apps will send
litellm --config config.yaml --port 4000
```

With Docker (image name from the LiteLLM docs):

```bash
cp .env.example .env    # fill in both keys
docker compose up -d
```

Then call it like any OpenAI endpoint:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "smart", "messages": [{"role": "user", "content": "One sentence on idempotency."}]}'
```

More calls, including `/v1/responses` and `/v1/messages`, are in [examples/curl.sh](./examples/curl.sh). [examples/openai_client.py](./examples/openai_client.py) uses the OpenAI SDK with streaming, and [examples/router_in_process.py](./examples/router_in_process.py) runs the same routing inside a Python process, without a server.

## Aliases, weighted groups and fallbacks

Everything sits in `router_settings`:

```yaml
router_settings:
  routing_strategy: simple-shuffle
  model_group_alias: {"smart": "gpt-6-sol", "claude": "claude-opus-5", "cheap": "budget"}
  fallbacks: [{"claude-opus-5": ["claude-sonnet-5", "gpt-6-sol"]}, {"gpt-6-sol": ["claude-sonnet-5"]},
              {"deepseek-v4-pro": ["glm-5.3"]}, {"budget": ["gpt-5.6-luna"]}]
  num_retries: 2
  timeout: 600
```

- **Aliases** let apps ask for `smart` or `cheap` while you change what those mean in one file. Requests for exact IDs such as `gpt-6-sol` stay pinned to that model.
- **Weighted group**: two deployments share the name `budget`, and `simple-shuffle` picks by their `weight`, so about three requests in four go to DeepSeek V4.1 Flash. In the mock run, four `cheap` calls went three to DeepSeek and one to GLM.
- **Fallbacks** move to the next group after `num_retries` failures. LiteLLM reports the hop in the `x-litellm-attempted-fallbacks` response header; in the mock run, a group whose upstream answered 503 was served by its fallback with that header at `1`.
- **Other strategies** in the LiteLLM docs: `least-busy`, `usage-based-routing-v2`, `latency-based-routing` and `cost-based-routing`. Cost-based routing reads the `model_info` costs below, so it chooses correctly between deployments of one group.

## Cost tracking

Each deployment carries ArgoLink's per-token price in `model_info`:

```yaml
    model_info:
      input_cost_per_token: 0.0000006        # $0.60 / 1M
      output_cost_per_token: 0.000003        # $3.00 / 1M
      cache_read_input_token_cost: 0.00000006
      cache_creation_input_token_cost: 0.00000075
```

Without these lines LiteLLM uses its own cost map, which holds list prices or nothing: in the mock run, an `openai/deepseek-v4-pro` deployment without `model_info` was logged at $0. With them, the `x-litellm-response-cost` header and the spend logs use the real rates (10 input and 20 output tokens on `deepseek-v4-pro` logged $0.00003696).

Three billing rules LiteLLM cannot see, so its totals come out low when they apply:

| Rule (from the model pages) | Applies to | Effect on the bill |
|---|---|---|
| Peak hours | `deepseek-v4-pro`, `deepseek-v4.1-flash` | weekdays 09:00–12:00 and 14:00–18:00 Beijing time cost 2× |
| Long context | GPT models with a 272K threshold, GPT-6 Sol included | a prompt over 272K tokens bills output at 1.5× and every other token at 2× |
| Fast mode | GPT models | `service_tier: priority` bills every token at 2× (2.5× on GPT-5.5) |

Budgets: LiteLLM's docs state that `max_budget`, virtual keys and per-key budgets need a database. With this file alone the proxy authenticates with the master key and logs the cost of each request, but it does not stop spending. For a hard stop, run LiteLLM with Postgres or cap spend on the upstream account.

## Refresh the prices

```bash
python scripts/gen_config.py > config.yaml                      # live catalog, the curated 10
python scripts/gen_config.py --models gpt-6-sol,claude-opus-5 > config.small.yaml
python scripts/gen_config.py --all-chat > config.all.yaml       # all 28 chat models
```

The script reads `https://argolink.io/api/catalog/v1/models` (public, no key), applies the prefix rule above and rewrites the costs. It sends its own `User-Agent`, because the API's CDN answers Python's default `Python-urllib/x.y` agent with 403 (error 1010).

## What this setup does not cover

- **Video** (`seedance-2.5`, `wan-3`, `minimax-h3` and others) is an asynchronous job API, `POST /v1/videos/generations` then `GET /v1/videos/{request_id}`, and is not OpenAI-shaped. Call it directly.
- **Images** go to `/v1/images/generations` with model-specific fields; they were not tested through LiteLLM here.
- **Embeddings**: the ArgoLink catalog lists no embedding model as of 2026-10-07.

## FAQ

**Is there a router that sends simple requests to cheaper DeepSeek models?**
With this config you choose by name: point light traffic at `cheap` and hard prompts at `smart`. LiteLLM also documents a beta [auto routing](https://docs.litellm.ai/docs/proxy/auto_routing) feature that sorts prompts into complexity tiers; it is not configured or tested in this repo. Qwen models are not in the ArgoLink catalog as of 2026-10-07.

**How do I pin a version and still keep a moving alias?**
Call exact IDs (`claude-opus-5`, `gpt-6-sol`) where behaviour must not change, and use `model_group_alias` for the names you want to repoint later. The upstream IDs carry no `-latest` suffix; when a model is replaced, the catalog maps the old ID to the new one (for example `deepseek-v4-pro-0813` became `deepseek-v4-pro`).

**Can one OpenAI SDK client reach GPT, Claude, DeepSeek and GLM?**
Yes, through the proxy. Every group answers on `/v1/chat/completions`, and LiteLLM converts the Claude calls to the Messages format upstream.

**Will the proxy stop me at a monthly budget?**
Not without a database, as above. It still records the cost of every request.

**Why did a request to `claude-sonnet-5` fail with 400?**
Usually a non-default `temperature` or `top_p`. Claude Sonnet 5 accepts only the defaults there.

**Do I need LiteLLM at all?**
No. ArgoLink is already one OpenAI-compatible base URL, `https://argolink.io/v1`. The proxy adds what that alone does not give you: your own keys per team, aliases, cross-model fallbacks, request logs and per-request cost.

## Tests

```bash
pip install pytest pyyaml          # add litellm to also run the Router check
pytest tests/
```

The tests regenerate `config.yaml` from the saved catalog snapshot and require an exact match, check every prefix and base URL against the provider rule, check each cost against the catalog price, and check that aliases and fallbacks point at defined groups. With `litellm` installed, one more test builds a `Router` from the file and answers a request with `mock_response`, offline.

## License

MIT. LiteLLM is a project of BerriAI and is licensed separately.
