"""Point the OpenAI SDK at the LiteLLM proxy. pip install openai

    export LITELLM_MASTER_KEY=sk-...   # the proxy's key, not the upstream key
    python examples/openai_client.py
"""
import os

from openai import OpenAI

client = OpenAI(base_url=os.environ.get("PROXY_URL", "http://localhost:4000/v1"),
                api_key=os.environ["LITELLM_MASTER_KEY"])

# 1. A model group alias: "cheap" resolves to the two-deployment "budget" group.
reply = client.chat.completions.create(
    model="cheap",
    messages=[{"role": "user", "content": "Name three uses of a bloom filter."}],
)
print(reply.model, "->", reply.choices[0].message.content)

# 2. Streaming from a Claude deployment (LiteLLM translates to /v1/messages upstream).
stream = client.chat.completions.create(
    model="claude-sonnet-5",
    messages=[{"role": "user", "content": "Write a haiku about retries."}],
    stream=True,
)
for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()

# 3. Responses API with reasoning effort (GPT models take tools + reasoning here).
response = client.responses.create(model="gpt-6-sol", input="Is 2^61-1 prime? Answer yes or no.",
                                   reasoning={"effort": "low"})
print(response.output_text)
