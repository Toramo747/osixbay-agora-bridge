"""ECO-LONG-05: controlled detritus and propagule-bank experiment.

Four cases differ only in (i) extra conservative mineralization after a tick,
and (ii) an initial bank of actual seed mass escrowed from living parent plants.
NO species respawn, material injection, arbitrary world source, or Godot.
Not canonical F01 or a calibrated ecological forecast.
"""
from __future__ import annotations
import csv
import json
import math
import pathlib

from f01_feeding_bridge_p0 import F01Feeding
from multi_patch_p0 import NODES
from propagules_p0 import Propagule
from stress_ecosystem_dm089 import NORMAL, _metrics
from long04_starvation_audit import import_path, INTEROP, interop_snapshot

TICKS = 1200
YEAR_TICKS = 12
SEEDS = (11, 23, 37)
SCENARIOS = (
    ("reference", False, False),
    ("extra_mineralization", True, False),
    ("parent_paid_seedbank", False, True),
    ("extra_mineralization_and_seedbank", True, True),
)
SEED_FRACTION = 0.0625
EXTRA_MINERALIZATION_CAP = 0.24
EXTRA_MINERALIZATION_RATE = 0.025


def stock_totals(sim):
    hydro = sim.eco.world.genetic.life.hydro
    names = ("nutrients", "producer_a", "producer_b", "fruit_a",
             "fruit_b", "biofilm", "microfauna", "detritus", "f01_reserve")
    result = {field: sum(getattr(hydro.network.nodes[p].state, field)
                         for p in NODES) for field in names}
    result["escrowed_seeds"] = sum(s.biomass for s in sim.eco.world.seeds)
    return result


def seedbank_from_live_parents(sim):
    """Split preexisting living biomass into traceable, escrowed propagules.

    The experimental initial condition is NOT spontaneous generation:
    after each split, exactly the detached material leaves the living plant
    pool and enters the bank; the combined original biomass remains fixed.
    """
    world = sim.eco.world
    if world.genetic.life.hydro.network.ticks:
        raise ValueError("initial bank is only allowed before the first tick")
    if world.seeds:
        raise ValueError("initial seedbank must be empty")
    if len(world.genetic.life.individuals) != 6:
        raise ValueError("expected exactly six starting adults")
    baseline_mass = world.total_biomass()
    records = []
    for parent in sorted(world.genetic.life.individuals,
                         key=lambda p: p.identity):
        mass = parent.biomass * SEED_FRACTION
        if mass <= 0 or parent.biomass - mass <= 0.035:
            raise ValueError("insufficient living parent biomass")
        parent.biomass -= mass
        world._transfer(parent.patch, parent.species, mass, False)
        seed = Propagule(
            identity="seedbank-" + parent.identity,
            species=parent.species, patch=parent.patch,
            biomass=mass, age=0, parent_id=parent.identity,
            genes=dict(world.genetic.genes[parent.identity])
        )
        world.seeds.append(seed)
        world.created += 1
        records.append({"seed_id": seed.identity, "parent_id": parent.identity,
                        "species": parent.species, "patch": parent.patch,
                        "escrowed_mass": mass})
    sim.audit()
    if not math.isclose(world.total_biomass(), baseline_mass, abs_tol=1e-8):
        raise AssertionError("seedbank minted or destroyed biomass")
    return records


def apply_extra_mineralization(sim):
    """One measured detritus -> nutrients counterfactual flux per patch."""
    total = 0.0
    net = sim.eco.world.genetic.life.hydro.network
    for patch in NODES:
        web = net.nodes[patch]
        amount = min(EXTRA_MINERALIZATION_CAP,
                     web.state.detritus * EXTRA_MINERALIZATION_RATE)
        total += web.move("detritus", "nutrients", amount,
                          "counterfactual_extra_mineralization")
    sim.audit()
    return total


def advance(sim, boosted=False):
    sim.tick(**NORMAL)
    moved = apply_extra_mineralization(sim) if boosted else 0.0
    sim.audit()
    return moved


def sample(sim, scenario, seed, year, extra_cumulative):
    m = _metrics(sim)
    s = stock_totals(sim)
    return dict(seed=seed, scenario=scenario, year=year,
                tick=m["tick"], f01_alive=m["f01_alive"],
                f01_starved=m["f01_deaths"]["starvation"],
                f01_thirst=m["f01_deaths"]["thirst"],
                plants_alive=m["plants_alive"],
                propagules_dormant=m["propagules_dormant"],
                propagules_created=m["propagules_created"],
                propagules_germinated=m["propagules_germinated"],
                propagules_expired=m["propagules_expired"],
                microfauna_alive=m["microfauna_alive"],
                nutrients=s["nutrients"], detritus=s["detritus"],
                fruits=s["fruit_a"] + s["fruit_b"],
                producer_mass=s["producer_a"] + s["producer_b"],
                biofilm=s["biofilm"], dormant_seed_mass=s["escrowed_seeds"],
                biomass=m["biomass"], water=m["water"],
                counterfactual_extra_flux=extra_cumulative)


def run():
    contract = import_path(INTEROP, "genesis_long05_pr92_contract")
    folder = pathlib.Path("long05_results")
    folder.mkdir(exist_ok=True)
    rows, cases, snapshots = [], [], []
    for seed in SEEDS:
        for name, boosted, banked in SCENARIOS:
            sim = F01Feeding(seed=seed)
            original = _metrics(sim)
            deposit = seedbank_from_live_parents(sim) if banked else []
            reference_mass = sim.eco.world.total_biomass()
            reference_water = sim.eco.world.genetic.life.hydro.total_water()
            no_producers_or_seeds_seen = False
            first_extinct_tick, last_seed_tick = None, None
            cumulative_extra = 0.0
            for tick in range(1, TICKS + 1):
                cumulative_extra += advance(sim, boosted=boosted)
                m = _metrics(sim)
                if not m["plants_alive"] and not m["propagules_dormant"]:
                    no_producers_or_seeds_seen = True
                if no_producers_or_seeds_seen and (m["plants_alive"] or
                                                   m["propagules_dormant"]):
                    raise AssertionError("unpaid spontaneous recolonization")
                if first_extinct_tick is None and not m["plants_alive"]:
                    first_extinct_tick = tick
                if last_seed_tick is None and not m["propagules_dormant"]:
                    last_seed_tick = tick
                if not math.isclose(reference_mass, sim.eco.world.total_biomass(),
                                    rel_tol=1e-10, abs_tol=1e-6):
                    raise AssertionError("biomass conservation")
                if not math.isclose(reference_water,
                                    sim.eco.world.genetic.life.hydro.total_water(),
                                    rel_tol=1e-10, abs_tol=1e-6):
                    raise AssertionError("water conservation")
                if tick % YEAR_TICKS == 0:
                    year = tick // YEAR_TICKS
                    rows.append(sample(sim, name, seed, year, cumulative_extra))
                    if year in (1, 10, 100):
                        doc = interop_snapshot(sim, contract, seed)
                        doc["world_id"] = "genesis-eco-long05-experiment"
                        doc["world_version"] = "eco-long05-candidate"
                        assert contract.validate(doc)
                        snapshots.append({"seed":seed, "scenario":name,
                                          "year":year, "snapshot":doc})
            final=sample(sim,name,seed,100,cumulative_extra)
            cases.append({"seed":seed,"scenario":name,
                          "initial_biomass":original["biomass"],
                          "parent_paid_seedbank":deposit,
                          "first_zero_plants_tick":first_extinct_tick,
                          "first_zero_seeds_tick":last_seed_tick,
                          "final":final,"biomass_conserved":True,
                          "water_conserved":True,"no_resurrection":True})
            print("verified",seed,name,
                  "plants",final["plants_alive"],
                  "seeds",final["propagules_dormant"],
                  "F01",final["f01_alive"],
                  "detritus",round(final["detritus"],3),flush=True)
    with (folder/"annual_100_years.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary={
        "schema":"osixbay.genesis.eco.long05.causal-experiment.v1",
        "status":"experimental_not_canonical",
        "time_basis":"12 ticks per symbolic year; not planetary/terrestrial astronomy",
        "seeds":list(SEEDS),
        "scenarios":[{"name":a,"extra_mineralization":b,"initial_paid_seedbank":c}
                     for a,b,c in SCENARIOS],
        "seed_mass_fraction":SEED_FRACTION,
        "extra_mineralization":{"per_patch_cap":EXTRA_MINERALIZATION_CAP,
                                 "fraction_of_detritus":EXTRA_MINERALIZATION_RATE},
        "runs":len(cases),"ticks_per_run":TICKS,
        "annual_rows":len(rows),"interop_snapshots":len(snapshots),
        "cases":cases,
        "limitations":[
            "Only six initial experimental producers, three patches and three F01 proxies",
            "Initial propagules are deliberately escrowed counterfactuals, not observed ecology",
            "Extra mineralization is a controlled hypothetical rate, not calibrated chemistry",
            "No propagule has unlimited viability; no artificial respawn",
            "Physical F01 PR88 remains separate; no true genetic adaptation of F01",
            "No planetary terrain, climate, Godot, Cloudflare, merge or deploy"]
    }
    (folder/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    (folder/"interop_samples.json").write_text(json.dumps(snapshots,indent=2)+"\n",encoding="utf-8")
    print("AUDIT PASS",len(cases),"cases",len(rows),"annual rows",
          len(snapshots),"interop snapshots",flush=True)


if __name__ == "__main__":
    run()
