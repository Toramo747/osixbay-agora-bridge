"""ECO-LONG-04: original PR93 GPLE stress runner, sampled at 12 ticks per notional year.
This is an audit harness, NOT a merged F01 physiology or planet-scale model.
"""
from __future__ import annotations
import csv
import importlib.util
import json
import pathlib
import sys
from f01_feeding_bridge_p0 import F01Feeding
from stress_ecosystem_dm089 import SCENARIOS, _rates, _metrics, _waterless_initial_condition
ROOT = pathlib.Path(__file__).resolve().parents[2]  # worktree root; lab/ and sources/ are siblings
INTEROP = ROOT / "sources" / "pr92" / "genesis_interop_v1" / "contract.py"
ORIGINAL = ROOT / "sources" / "pr88" / "genesis" / "fauna01" / "sim.py"
SEEDS = (11, 23, 37)
TICKS = 1200
YEAR = 12

def import_path(filename, modname):
    spec = importlib.util.spec_from_file_location(modname, filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod

def interop_snapshot(sim, contract, seed):
    eco = sim.eco
    world = eco.world
    hydro = world.genetic.life.hydro
    patches = ("forest", "shore", "rock")
    entities = []
    stocks = []
    for patch in patches:
        actor = sim.f01[patch]
        entities.append({"id": actor["identity"], "type": "f01",
                         "patch_id": patch,
                         "state": {"alive": actor["alive"],
                                   "energy_proxy": actor["energy"],
                                   "hydration_proxy": actor["hydration"]}})
        state = hydro.network.nodes[patch].state
        for field in ("nutrients", "producer_a", "producer_b", "fruit_a", "fruit_b",
                      "biofilm", "microfauna", "detritus", "f01_reserve"):
            stocks.append({"patch_id": patch, "resource": field,
                           "quantity": getattr(state, field),
                           "unit": "abstract_mass"})
        for name, quantity in (("water.surface", hydro.network.water[patch]),
                               ("water.ground", hydro.groundwater[patch]),
                               ("water.f01_tissue", hydro.f01_tissue_water[patch])):
            stocks.append({"patch_id": patch, "resource": name,
                           "quantity": quantity, "unit": "abstract_water"})
    stocks.append({"patch_id": "forest", "resource": "water.atmosphere",
                   "quantity": hydro.atmosphere, "unit": "abstract_water"})
    doc = {"schema": contract.SCHEMA, "kind": "snapshot",
           "world_id": "genesis-eco-long04-lab",
           "world_version": "pr93-candidate",
           "seed": seed, "tick": hydro.network.ticks,
           "provenance": "synthetic_fixture", "transform": None,
           "patches": list(patches), "entities": entities, "stocks": stocks}
    assert contract.validate(doc)
    return doc

def run():
    contract = import_path(INTEROP, "genesis_contract_pr92")
    original = import_path(ORIGINAL, "genesis_f01_original_pr88")
    reference = {str(seed): original.demonstration(seed=seed, ticks=80) for seed in SEEDS}
    target = pathlib.Path("long04_results")
    target.mkdir(exist_ok=True)
    rows, cases, samples = [], [], []
    for seed in SEEDS:
        for scenario in SCENARIOS:
            sim = F01Feeding(seed=seed)
            if scenario == "no_water_extinction":
                _waterless_initial_condition(sim)
            initial = _metrics(sim)
            for tick in range(1, TICKS + 1):
                sim.tick(**_rates(scenario, tick - 1, TICKS))
                for actor in sim.f01.values():
                    if actor["alive"] and actor["energy"] <= 0.0:
                        raise AssertionError("living F01 with depleted metabolic energy")
                if tick % YEAR == 0:
                    m = _metrics(sim)
                    rows.append({"seed": seed, "scenario": scenario, "year": tick//YEAR,
                                 "f01_starved": m["f01_deaths"]["starvation"],
                                 "f01_thirst": m["f01_deaths"]["thirst"],
                                 "f01_total_meals": m["f01_cumulative_meals"],
                                 "detritus": sum(getattr(sim.eco.world.genetic.life.hydro.network.nodes[p].state, "detritus") for p in ("forest","shore","rock")),
                                 "available_nutrients": sum(getattr(sim.eco.world.genetic.life.hydro.network.nodes[p].state, "nutrients") for p in ("forest","shore","rock")),
                                 "f01_alive": m["f01_alive"], "plants_alive": m["plants_alive"],
                                 "microfauna_alive": m["microfauna_alive"],
                                 "biomass": m["biomass"], "water": m["water"],
                                 "plant_births": m["plant_births"], "plant_deaths": m["plant_deaths"],
                                 "microfauna_births": m["microfauna_births"],
                                 "microfauna_deaths": m["microfauna_deaths"]})
                    if tick//YEAR in (1, 10, 100):
                        doc = interop_snapshot(sim, contract, seed)
                        samples.append({"scenario": scenario, "seed": seed,
                                        "year": tick//YEAR, "snapshot": doc})
            final = _metrics(sim)
            assert abs(initial["biomass"] - final["biomass"]) < 1e-5
            assert abs(initial["water"] - final["water"]) < 1e-5
            cases.append({"scenario": scenario, "seed": seed,
                          "extinction_reason":final["f01_deaths"],
                          "end_detritus":sum(sim.eco.world.genetic.life.hydro.network.nodes[p].state.detritus for p in ("forest","shore","rock")),
                          "end_nutrients":sum(sim.eco.world.genetic.life.hydro.network.nodes[p].state.nutrients for p in ("forest","shore","rock")),
                          "starting": initial,
                          "ending": final, "biomass_conserved": True, "water_conserved": True})
            print("verified", seed, scenario, final["f01_alive"], flush=True)
    fields = list(rows[0])
    with (target / "annual_100_years.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    report = {"schema": "osixbay.genesis.eco.long04.v1",
              "status": "synthetic_starvation_fix_original_ecop0_no_full_pr88_coupling",
              "time_basis": "12 synthetic ticks per notional year; no astronomical calibration",
              "source_prs": {"f01_reference": 88, "world_adapter": 89,
                             "eco": 93, "interop": 92},
              "seeds": list(SEEDS), "scenarios": list(SCENARIOS),
              "years": 100, "ticks_each": TICKS, "runs": len(cases),
              "original_f01_parallel_reference": reference,
              "cases": cases, "annual_rows": len(rows),
              "interop_samples_validated": len(samples),
              "limitations": ["PR93 P0 ecological proxy, modified only in isolated branch to kill F01 when energy is exhausted",
                              "PR88 F01 reference executed separately; no coupled physiology",
                              "PR89 World adapter tested separately, no persistent Worker or real habitat",
                              "PR92 stateless contract validation, not authoritative reconciliation",
                              "No F01 reproduction/ageing or realistic energy calibration; nutrient/detritus recycling remains a possible bottleneck",
                              "No Godot, production, Cloudflare, Kaggle or merge"]}
    (target / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (target / "interop_samples.json").write_text(json.dumps(samples, indent=2) + "\n", encoding="utf-8")
    print("AUDIT PASS", len(cases), "runs", len(rows), "annual rows", len(samples),
          "interop snapshots", flush=True)

if __name__ == "__main__":
    run()

# CI push trigger: offline ECO-LONG-04 audit only; no deployment.
