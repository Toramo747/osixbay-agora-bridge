"""DM-088: isolated F01 food+water survival proxy over conservative ECO-P0.

This remains a NON-CANONICAL synthetic organism, not the original PR #88 F01.
FoodWeb performs the single food->f01_reserve transfer. Drinking moves finite
surface water to tracked F01 tissue, followed by transpiration/return to
atmosphere. Neither proxy produces material or water. The wrapper cannot
introduce the original F01 anatomy/reproduction without a separate adapter.
"""
import json
import math
from microfauna_p0 import MicroWorld
from multi_patch_p0 import NODES

SCHEMA = "osixbay.genesis.gple.f01-feeding-bridge.v2"
FOOD = ("fruit_a", "fruit_b", "biofilm", "microfauna")
MAX_TISSUE_WATER = 0.25
WATER_LOSS_FRACTION = 0.12
MIN_MEAL = 0.01
MAX_STARVATION_TICKS = 30
MAX_THIRST_TICKS = 20

def finite_nonnegative(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0

class F01Feeding:
    def __init__(self, seed=11):
        self.eco = MicroWorld(seed=seed)
        self.f01 = {
            p: {"identity": "f01-" + p, "energy": 0.5,
                "hydration": 0.0, "consumed": 0.0, "water_consumed": 0.0,
                "starvation_ticks": 0, "thirst_ticks": 0,
                "alive": True, "death_reason": None}
            for p in NODES
        }
        self.audit()

    def _hydro(self):
        return self.eco.world.genetic.life.hydro

    def audit(self):
        self.eco.audit()
        if set(self.f01) != set(NODES):
            raise ValueError("F01 patches")
        hydro = self._hydro()
        for p, a in self.f01.items():
            if (a.get("identity") != "f01-" + p
                    or not isinstance(a.get("alive"), bool)
                    or a.get("death_reason") not in (None, "thirst", "starvation")
                    or (a["alive"] is False) != (a["death_reason"] is not None)):
                raise ValueError("F01 identity or life state")
            if (not finite_nonnegative(a.get("energy")) or a["energy"] > 1
                    or not finite_nonnegative(a.get("hydration")) or a["hydration"] > 1
                    or not finite_nonnegative(a.get("consumed"))
                    or not finite_nonnegative(a.get("water_consumed"))):
                raise ValueError("F01 nonfinite vital state")
            for key in ("starvation_ticks", "thirst_ticks"):
                if not isinstance(a.get(key), int) or isinstance(a[key], bool) or a[key] < 0:
                    raise ValueError("F01 invalid counter")
            if not math.isclose(a["hydration"],
                                min(1.0, hydro.f01_tissue_water[p] / MAX_TISSUE_WATER),
                                abs_tol=1e-8):
                raise ValueError("F01 hydration does not match actual water")
            if not a["alive"] and hydro.f01_tissue_water[p] > 1e-9:
                raise ValueError("dead F01 retains water")

    def tick(self, **kwargs):
        if "override_consumers_by_patch" in kwargs or "override_consumers" in kwargs:
            raise ValueError("F01 survival controls consumers")
        hydro = self._hydro()
        net = hydro.network
        offsets = {p: len(net.nodes[p].events) for p in NODES}
        # Exactly one living F01 per patch; a dead individual cannot eat.
        self.eco.tick(override_consumers_by_patch={
            p: 1 if self.f01[p]["alive"] else 0 for p in NODES}, **kwargs)
        meals = {}
        for p in NODES:
            actor = self.f01[p]
            events = net.nodes[p].events[offsets[p]:]
            food = [e for e in events if e["event"] == "f01_consumption"
                    and e["source"] in FOOD and e["target"] == "f01_reserve"]
            quantity = sum(e["quantity"] for e in food)
            if not actor["alive"]:
                if quantity > 0:
                    raise AssertionError("dead actor consumed food")
                meals[p] = {"alive": False, "consumed": 0.0, "water": 0.0,
                            "death_reason": actor["death_reason"]}
                continue
            actor["consumed"] += quantity
            actor["energy"] = max(0.0, min(1.0, actor["energy"] - 0.025 + quantity * 0.12))
            actor["starvation_ticks"] = 0 if quantity >= MIN_MEAL else actor["starvation_ticks"] + 1
            # The previous tick's water is partly released to the atmospheric stock.
            loss = hydro.f01_tissue_water[p] * WATER_LOSS_FRACTION
            hydro.f01_tissue_water[p] -= loss
            hydro.atmosphere += loss
            # Drinking transfers EXISTING water, capped by actual surface stocks.
            want = max(0.0, MAX_TISSUE_WATER - hydro.f01_tissue_water[p])
            sip = min(want, hydro.network.water[p])
            hydro.network.water[p] -= sip
            hydro.f01_tissue_water[p] += sip
            actor["water_consumed"] += sip
            actor["hydration"] = min(1.0, hydro.f01_tissue_water[p] / MAX_TISSUE_WATER)
            actor["thirst_ticks"] = 0 if actor["hydration"] >= 0.12 else actor["thirst_ticks"] + 1
            if actor["thirst_ticks"] >= MAX_THIRST_TICKS:
                actor["alive"] = False
                actor["death_reason"] = "thirst"
            elif actor["energy"] <= 0.0:
                # A tiny meal must not prevent death once metabolic energy
                # is exhausted. The previous AND guard allowed immortal
                # F01 proxies at exactly zero energy under a steady trickle.
                actor["alive"] = False
                actor["death_reason"] = "starvation"
            elif actor["starvation_ticks"] >= MAX_STARVATION_TICKS and actor["energy"] <= 0.08:
                actor["alive"] = False
                actor["death_reason"] = "starvation"
            if not actor["alive"]:
                # Return retained water to the environment on death.
                hydro.atmosphere += hydro.f01_tissue_water[p]
                hydro.f01_tissue_water[p] = 0.0
                actor["hydration"] = 0.0
            meals[p] = {"food": {k: round(sum(e["quantity"] for e in food
                         if e["source"] == k), 8) for k in FOOD},
                        "consumed": round(quantity, 8), "water": round(sip, 8),
                        "energy": round(actor["energy"], 6),
                        "hydration": round(actor["hydration"], 6),
                        "starvation_ticks": actor["starvation_ticks"],
                        "thirst_ticks": actor["thirst_ticks"],
                        "alive": actor["alive"], "death_reason": actor["death_reason"]}
        # PatchNetwork owns only surface water: move its accounting baseline
        # after surface -> F01 tissue flows. Global hydro.initial_water is FIXED.
        hydro.network.water_initial = sum(hydro.network.water.values())
        self.audit()
        return {"tick": net.ticks, "meals": meals,
                "biomass": round(self.eco.world.total_biomass(), 8),
                "water": round(hydro.total_water(), 8)}

    def snapshot(self):
        return json.dumps({"schema": SCHEMA, "eco": self.eco.snapshot(), "f01": self.f01},
                          sort_keys=True, separators=(",", ":"))

    @classmethod
    def restore(cls, payload):
        d = json.loads(payload)
        if d.get("schema") != SCHEMA:
            raise ValueError("schema")
        x = object.__new__(cls)
        x.eco = MicroWorld.restore(d["eco"])
        x.f01 = d["f01"]
        x.audit()
        return x
