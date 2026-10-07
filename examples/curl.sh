#!/usr/bin/env bash
# Calls against a running proxy (litellm --config config.yaml, or docker compose up).
set -euo pipefail
PROXY=${PROXY:-http://localhost:4000}
KEY=${LITELLM_MASTER_KEY:?set LITELLM_MASTER_KEY}

# Model groups the proxy exposes (aliases included)
curl -sS "$PROXY/v1/models" -H "Authorization: Bearer $KEY"

# OpenAI-style chat: "smart" is an alias for gpt-6-sol
curl -sS "$PROXY/v1/chat/completions" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model": "smart", "messages": [{"role": "user", "content": "One sentence on idempotency."}]}'

# Responses API: LiteLLM forwards openai/ deployments to the upstream /v1/responses
curl -sS "$PROXY/v1/responses" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model": "gpt-6-sol", "input": "One sentence on idempotency.", "reasoning": {"effort": "low"}}'

# Anthropic Messages shape: anthropic/ deployments go to the upstream /v1/messages
curl -sS "$PROXY/v1/messages" \
  -H "x-api-key: $KEY" -H "anthropic-version: 2023-06-01" -H "Content-Type: application/json" \
  -d '{"model": "claude-opus-5", "max_tokens": 256, "messages": [{"role": "user", "content": "One sentence on idempotency."}]}'
