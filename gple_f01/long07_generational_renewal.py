"""ECO-LONG-07 — causal generational renewal screen on existing finite material.

Counterfactual coefficient changes only; every birth pays existing parent biomass
and every germination spends an existing propagule. Not calibrated biology.
"""
from __future__ import annotations
import contextlib
import csv
import json
import math
import pathlib
import foodweb_p0 as F
import plant_lifecycle_p0 as L
from long05_detritus_seedbank_audit import seedbank_from_live_parents, apply_extra_mineralization
from long06_generation_chain_audit import parameters as generation_parameters, state
from f01_feeding_bridge_p0 import F01Feeding
from stress_ecosystem_dm089 import NORMAL

SEEDS=(11,23,37)
TICKS=1200
YEAR=12
# (name, growth multiplier, fruit fraction, turnover fraction, minimum birth mass,
#  birth cooldown, maximum age, additional closed-ledger mineralization)
CASES=(
    ("baseline",1.0,.055,.012,3.5,20,120,False),
    ("growth_x2",2.0,.055,.012,3.5,20,120,False),
    ("lower_repro_threshold",1.0,.055,.012,2.0,20,120,False),
    ("shorter_repro_interval",1.0,.055,.012,3.5,8,120,False),
    ("lower_fruiting_loss",1.0,.022,.012,3.5,20,120,False),
    ("lower_vegetative_turnover",1.0,.055,.004,3.5,20,120,False),
    ("growth_plus_repro",2.0,.055,.012,2.0,8,120,False),
    ("balanced_screen",2.0,.033,.006,2.0,12,180,True),
)
@contextlib.contextmanager
def tuning(scenario):
    name,growth,fruit,turnover,birth,cooldown,max_age,extra=scenario
    if not (1<=growth<=3 and 0<=fruit<=.1 and 0<=turnover<=.1
            and .1<=birth<=5 and 1<=cooldown<=50 and 60<=max_age<=300):
        raise ValueError("unsafe screen parameters")
    originals=(F.PRODUCER_GROWTH_MULTIPLIER,F.FRUITING_FRACTION,
               F.PRODUCER_TURNOVER_FRACTION,L.BIRTH_BIOMASS,
               L.REPRO_COOLDOWN,L.MAX_AGE)
    with generation_parameters(65,3,.45,.45,max_age):
        try:
            F.PRODUCER_GROWTH_MULTIPLIER=growth
            F.FRUITING_FRACTION=fruit
            F.PRODUCER_TURNOVER_FRACTION=turnover
            L.BIRTH_BIOMASS=birth
            L.REPRO_COOLDOWN=cooldown
            yield
        finally:
            (F.PRODUCER_GROWTH_MULTIPLIER,F.FRUITING_FRACTION,
             F.PRODUCER_TURNOVER_FRACTION,L.BIRTH_BIOMASS,
             L.REPRO_COOLDOWN,L.MAX_AGE)=originals

def run_case(seed, scenario, ticks=TICKS):
    name,*_=scenario
    with tuning(scenario):
        sim=F01Feeding(seed=seed)
        life=sim.eco.world.genetic.life
        founder_ids={p.identity for p in life.individuals}
        # The initial paid seedbank is a controlled perturbation in EVERY arm.
        deposits=seedbank_from_live_parents(sim)
        lineage={identity:0 for identity in founder_ids}
        for seed_info in deposits:
            lineage[seed_info["seed_id"]]=lineage[seed_info["parent_id"]]+1
        mass=sim.eco.world.total_biomass()
        water=life.hydro.total_water()
        rows=[]
        event_offset=len(life.events)
        irreversibly_extinct=False
        maximum_depth=0
        last_birth_tick=None
        last_germination_tick=None
        max_live= len(life.individuals)
        saw_unpaid_birth=False
        for tick in range(1,ticks+1):
            prior_births=life.counts["births"]
            prior_germinated=sim.eco.world.germinated
            sim.tick(**NORMAL)
            if scenario[-1]:
                apply_extra_mineralization(sim)
            for ev in life.events[event_offset:]:
                if ev["event"]=="plant_birth":
                    parent=ev["parent_id"]
                    if parent not in lineage:
                        saw_unpaid_birth=True
                        raise AssertionError("untracked parent")
                    if ev["identity"] in lineage:
                        raise AssertionError("duplicate offspring")
                    lineage[ev["identity"]]=lineage[parent]+1
                    maximum_depth=max(maximum_depth,lineage[ev["identity"]])
            event_offset=len(life.events)
            if life.counts["births"]>prior_births:last_birth_tick=tick
            if sim.eco.world.germinated>prior_germinated:last_germination_tick=tick
            for p in life.individuals:
                if p.identity not in lineage:
                    raise AssertionError("untracked living plant")
            for prop in sim.eco.world.seeds:
                if prop.identity not in lineage:
                    raise AssertionError("untracked propagule")
            total_live=len(life.individuals)
            total_seeds=len(sim.eco.world.seeds)
            if irreversibly_extinct and (total_live or total_seeds):
                raise AssertionError("spontaneous respawn after extinction")
            if not total_live and not total_seeds:
                irreversibly_extinct=True
            max_live=max(max_live,total_live)
            if not math.isclose(sim.eco.world.total_biomass(),mass,rel_tol=1e-10,abs_tol=1e-6):
                raise AssertionError("biomass changed")
            if not math.isclose(life.hydro.total_water(),water,rel_tol=1e-10,abs_tol=1e-6):
                raise AssertionError("water changed")
            if tick % YEAR==0:
                row=state(sim)
                alive_depth=max((lineage[p.identity] for p in life.individuals),default=-1)
                rows.append(dict(seed=seed,scenario=name,year=tick//YEAR,**row,
                                 maximum_ancestry_depth=maximum_depth,
                                 maximum_live_ancestry_depth=alive_depth))
        final=state(sim)
        surviving_depth=max((lineage[p.identity] for p in life.individuals),default=-1)
        result=dict(seed=seed,scenario=name,ticks=ticks,final=final,
                    max_live_plants=max_live,generations_created=maximum_depth,
                    max_surviving_generation=surviving_depth,
                    last_birth_tick=last_birth_tick,
                    last_germination_tick=last_germination_tick,
                    parent_paid_seedbank=len(deposits),
                    no_untracked_birth=not saw_unpaid_birth,
                    all_material_conserved=True,
                    all_water_conserved=True,
                    no_respawn=True,
                    stable_100_year_population=(ticks==1200 and final["plants"]>0
                         and maximum_depth>=3))
        print("verified",seed,name,"plants",final["plants"],
              "max_depth",maximum_depth,"germinated",final["seeds_germinated"],
              flush=True)
        return result,rows

def main():
    folder=pathlib.Path("long07_results")
    folder.mkdir(exist_ok=True)
    summary=[];rows=[]
    for seed in SEEDS:
        for scenario in CASES:
            case,annual=run_case(seed,scenario)
            summary.append(case);rows.extend(annual)
    with (folder/"annual_100_years.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    report=dict(schema="osixbay.genesis.eco.long07.v1",
                status="uncalibrated_counterfactual_not_canonical",
                scenarios=[list(s) for s in CASES],seeds=list(SEEDS),
                runs=len(summary),ticks_each=TICKS,
                annual_rows=len(rows),cases=summary,
                time_basis="12 synthetic ticks/year; not physical planet time",
                limitations=[
                    "No metabolic/physiological F01 PR88 integration",
                    "No population stability claim without actual validated ongoing generations",
                    "Rates hypothetical; no field calibration; three synthetic patches",
                    "All arms use same parent-paid starting seeds; closed mass and water accounting",
                    "No World worker, Godot, production merge or deploy"])
    (folder/"summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("AUDIT PASS",len(summary),"runs",len(rows),"annual rows",flush=True)

if __name__=="__main__":main()
