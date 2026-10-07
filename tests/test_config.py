"""Offline checks for config.yaml. No network, no API key.

    pip install pytest pyyaml
    pytest tests/
"""
import json
import os
import sys
from decimal import Decimal

import pytest
import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import gen_config  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "catalog-2026-10-07.json")


@pytest.fixture(scope="module")
def config():
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture(scope="module")
def catalog():
    with open(FIXTURE, encoding="utf-8") as handle:
        return {m["id"]: m for m in json.load(handle)["items"]}


def test_config_is_reproducible_from_the_catalog_snapshot():
    with open(FIXTURE, encoding="utf-8") as handle:
        rendered = gen_config.render(json.load(handle), gen_config.DEFAULT_MODELS)
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as handle:
        assert handle.read() == rendered


def test_every_model_exists_and_uses_the_right_provider_route(config, catalog):
    for entry in config["model_list"]:
        params = entry["litellm_params"]
        prefix, model_id = params["model"].split("/", 1)
        assert model_id in catalog, model_id
        if catalog[model_id]["provider_id"] == "anthropic":
            # LiteLLM appends /v1/messages to the base itself.
            assert (prefix, params["api_base"]) == ("anthropic", "https://argolink.io")
        else:
            assert (prefix, params["api_base"]) == ("openai", "https://argolink.io/v1")
        assert params["api_key"] == "os.environ/UPSTREAM_API_KEY"


def test_costs_match_catalog_prices_per_token(config, catalog):
    for entry in config["model_list"]:
        model_id = entry["litellm_params"]["model"].split("/", 1)[1]
        effective = catalog[model_id]["pricing"]["effective"]
        info = entry["model_info"]
        for field, key in [("input_cost_per_token", "input_per_million"),
                           ("output_cost_per_token", "output_per_million")]:
            expected = Decimal(str(effective[key])) / Decimal(1_000_000)
            assert Decimal(str(info[field])) == expected, (model_id, field)


def test_fallbacks_and_aliases_point_at_defined_groups(config):
    names = {entry["model_name"] for entry in config["model_list"]}
    router = config["router_settings"]
    for rule in router["fallbacks"]:
        for source, targets in rule.items():
            assert source in names
            assert targets and all(t in names for t in targets)
    assert all(target in names for target in router["model_group_alias"].values())


def test_budget_group_has_two_weighted_deployments(config):
    budget = [e["litellm_params"] for e in config["model_list"] if e["model_name"] == "budget"]
    assert [(p["model"], p["weight"]) for p in budget] == [
        ("openai/deepseek-v4.1-flash", 3),
        ("openai/glm-5.3-flash", 1),
    ]


def test_unknown_model_is_rejected():
    with open(FIXTURE, encoding="utf-8") as handle:
        catalog = json.load(handle)
    with pytest.raises(SystemExit):
        gen_config.render(catalog, ["not-a-model"])


def test_litellm_router_accepts_the_config(config):
    """Runs only when litellm is installed; mock_response keeps it offline."""
    litellm = pytest.importorskip("litellm")
    os.environ.setdefault("UPSTREAM_API_KEY", "test")
    model_list = []
    for entry in config["model_list"]:
        params = dict(entry["litellm_params"])
        params["api_key"] = "test"
        model_list.append({"model_name": entry["model_name"], "litellm_params": params,
                           "model_info": entry.get("model_info", {})})
    router = litellm.Router(model_list=model_list,
                            model_group_alias=config["router_settings"]["model_group_alias"])
    reply = router.completion(model="smart", messages=[{"role": "user", "content": "ping"}],
                              mock_response="pong")
    assert reply.choices[0].message.content == "pong"
