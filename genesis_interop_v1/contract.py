"""Genesis DM-091 intermodule envelope v1: strict offline validation only.

No production writer, no Web/Cloudflare deployment, no canonical real-world
coordinates. Contract uses synthetic fixtures until a verified Godot export
can supply scene hash, transform and coordinate mapping.
"""
import math

SCHEMA = "osixbay.genesis.interop.v1"
KINDS = {"snapshot", "event"}
EVENTS = {"consume", "drink", "birth", "death", "move", "communicate", "observe"}
MASS_UNITS = {"abstract_mass", "abstract_water"}
VALID_TYPES = {"plant", "propagule", "microfauna", "f01", "actor"}
MAX_ENTITIES = 10000
MAX_STOCKS = 20000

def _key(v):
    return isinstance(v, str) and 1 <= len(v) <= 128 and v.strip() == v and v.isprintable()

def _int(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0

def _amount(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0

def _exact(d, required, optional=()):
    return isinstance(d, dict) and set(required) <= set(d) and set(d) <= (set(required) | set(optional))

def _require(condition, message):
    if not condition:
        raise ValueError(message)

def _transform(transform):
    required = ("source_scene", "scene_hash", "horizontal", "up", "unit", "origin_m", "cell_size_m")
    _require(_exact(transform, required), "invalid transform shape")
    _require(_key(transform["source_scene"]) and _key(transform["scene_hash"]), "scene provenance")
    _require(transform["horizontal"] == "XZ" and transform["up"] == "Y"
             and transform["unit"] == "m", "coordinate convention")
    _require(isinstance(transform["origin_m"], list)
             and len(transform["origin_m"]) == 3
             and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                     and math.isfinite(x) for x in transform["origin_m"]), "origin_m")
    _require(_amount(transform["cell_size_m"]) and transform["cell_size_m"] > 0, "cell_size_m")

def validate(payload):
    common = ("schema", "kind", "world_id", "world_version", "seed", "tick", "provenance")
    _require(isinstance(payload, dict), "payload must be object")
    kind = payload.get("kind")
    _require(kind in KINDS, "unsupported kind")
    _require(payload.get("schema") == SCHEMA, "schema mismatch")
    for name in ("world_id", "world_version", "provenance"):
        _require(_key(payload.get(name)), name)
    _require(_int(payload.get("tick")) and _int(payload.get("seed")), "tick/seed")
    if kind == "snapshot":
        expected = common + ("patches", "entities", "stocks", "transform")
        _require(_exact(payload, expected), "snapshot fields")
        _require(payload["provenance"] in ("synthetic_fixture", "verified_godot_export"), "snapshot provenance")
        tr = payload["transform"]
        if tr is not None:
            _require(payload["provenance"] == "verified_godot_export", "unverified coordinate transform")
            _transform(tr)
        elif payload["provenance"] == "verified_godot_export":
            raise ValueError("verified export requires transform")
        patches = payload["patches"]
        _require(isinstance(patches, list) and 0 < len(patches) <= 1024
                 and all(_key(x) for x in patches) and len(set(patches)) == len(patches), "patches")
        entities = payload["entities"]
        _require(isinstance(entities, list) and len(entities) <= MAX_ENTITIES, "entity count")
        ids = set()
        for e in entities:
            _require(_exact(e, ("id", "type", "patch_id", "state"), ("position_m",)), "entity shape")
            _require(_key(e["id"]) and e["id"] not in ids
                     and e["type"] in VALID_TYPES and e["patch_id"] in patches, "entity id/type/patch")
            ids.add(e["id"])
            _require(isinstance(e["state"], dict), "entity state")
            _require("position_m" not in e or tr is not None, "unverified entity coordinates")
            if "position_m" in e:
                p = e["position_m"]
                _require(isinstance(p, list) and len(p) == 3
                         and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                 and math.isfinite(x) for x in p), "position_m")
        stocks = payload["stocks"]
        _require(isinstance(stocks, list) and len(stocks) <= MAX_STOCKS, "stock count")
        stock_keys = set()
        for s in stocks:
            _require(_exact(s, ("patch_id", "resource", "quantity", "unit")), "stock shape")
            k = (s["patch_id"], s["resource"], s["unit"])
            _require(s["patch_id"] in patches and _key(s["resource"])
                     and s["unit"] in MASS_UNITS and _amount(s["quantity"])
                     and k not in stock_keys, "invalid or duplicated stock")
            stock_keys.add(k)
    else:
        required = common + ("event_id", "event_type", "patch_id", "actor_id", "idempotency_key", "payload")
        _require(_exact(payload, required), "event fields")
        _require(payload["provenance"] in ("synthetic_fixture", "authoritative_world"), "event provenance")
        _require(_key(payload["event_id"]) and _key(payload["patch_id"])
                 and _key(payload["actor_id"]) and _key(payload["idempotency_key"]), "event identity")
        _require(payload["event_type"] in EVENTS, "event type")
        body = payload["payload"]
        _require(isinstance(body, dict), "event payload")
        if payload["event_type"] in ("consume", "drink"):
            _require(_exact(body, ("source", "target", "quantity", "unit")), "transfer payload")
            _require(_key(body["source"]) and _key(body["target"])
                     and body["source"] != body["target"]
                     and _amount(body["quantity"]) and body["quantity"] > 0
                     and body["unit"] in MASS_UNITS, "invalid transfer")
        if payload["event_type"] == "communicate":
            _require(_exact(body, ("channel", "utterance_id", "perceived_by")), "communication payload")
            _require(all(_key(body[x]) for x in ("channel", "utterance_id", "perceived_by")), "communication fields")
    return True

def fixture_snapshot():
    return {
        "schema": SCHEMA, "kind": "snapshot", "world_id": "genesis-lab",
        "world_version": "eco-p0", "seed": 11, "tick": 0,
        "provenance": "synthetic_fixture", "transform": None,
        "patches": ["forest", "shore", "rock"],
        "entities": [{"id": "f01-forest", "type": "f01", "patch_id": "forest",
                      "state": {"energy_proxy": 0.5, "alive": True}}],
        "stocks": [{"patch_id": "forest", "resource": "water.surface",
                    "quantity": 18.0, "unit": "abstract_water"}]
    }

def fixture_event():
    return {"schema": SCHEMA, "kind": "event", "world_id": "genesis-lab",
            "world_version": "eco-p0", "seed": 11, "tick": 1,
            "provenance": "synthetic_fixture", "event_id": "lab:1",
            "event_type": "drink", "patch_id": "forest", "actor_id": "f01-forest",
            "idempotency_key": "lab:drink:1",
            "payload": {"source": "water.surface", "target": "f01.tissue_water",
                        "quantity": 0.25, "unit": "abstract_water"}}
