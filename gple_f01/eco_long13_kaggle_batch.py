"""ECO-LONG-13: offline CPU experiment for Kaggle (no network or GPU).

The runner compares per-patch pre-tick *potential* (age, cooldown and biomass
before intra-tick growth) with actual plant_birth events after the tick.
Because the simulator changes biomass within a tick, this is a diagnostic
screen, not an exact prediction of births. All individuals and seeds come
from audited conserved stocks; no injection or automatic respawn.

Usage: python gple_f01/eco_long13_kaggle_batch.py --seeds 11,23,37 --ticks 1200
Outputs: summary.json, cohorts.csv, events.csv under --outdir.
"""
from __future__ import annotations
import argparse
import collections
import csv
import json
import math
import os
from pathlib import Path

from f01_feeding_bridge_p0 import F01Feeding
from long10_offspring_budget_audit import FRACTIONS
from long07_generational_renewal import tuning, CASES as LONG07_CASES
from long08_cohort_mortality_audit import cohort_settings
from long05_detritus_seedbank_audit import seedbank_from_live_parents, apply_extra_mineralization
from stress_ecosystem_dm089 import NORMAL
from multi_patch_p0 import NODES
from foodweb_p0 import PRODUCERS
import plant_lifecycle_p0 as L

GROUPS=tuple((patch,species) for patch in NODES for species in PRODUCERS)
YEAR=12

def evaluate(seed:int, fraction:float, ticks:int=1200):
    if fraction not in FRACTIONS or not 1<=ticks<=2400 or seed<0 or seed>2147483647:
        raise ValueError("outside controlled experimental bounds")
    with tuning(LONG07_CASES[-1]), cohort_settings(8,fraction,.035):
        sim=F01Feeding(seed=seed)
        life=sim.eco.world.genetic.life
        founders={p.identity for p in life.individuals}
        ancestry={pid:0 for pid in founders}
        paid=seedbank_from_live_parents(sim)
        for p in paid:
            sid=p["seed_id"]
            if sid in ancestry:raise AssertionError("seed collision")
            ancestry[sid]=1
        start_mass=sim.eco.world.total_biomass()
        start_water=life.hydro.total_water()
        event_at=len(life.events)
        cumulative=collections.Counter()
        cohorts=[]
        events=[]
        extinct=None
        max_generation=1
        for tick in range(1,ticks+1):
            before={p.identity:p for p in life.individuals}
            before_seeds={s.identity for s in sim.eco.world.seeds}
            pre={}
            for patch,species in GROUPS:
                group=[p for p in life.individuals if (p.patch,p.species)==(patch,species)]
                adult=[p for p in group if L.ADULT_AGE<=p.age+1<L.OLD_AGE]
                # The cooldown is decremented in PlantLifecycle.tick.
                rested=[p for p in adult if p.cooldown<=1]
                ready=[p for p in rested if p.biomass>=L.BIRTH_BIOMASS]
                pre[(patch,species)]=dict(living=len(group),adults=len(adult),
                    cooldown_ready=len(rested),potential=len(ready),
                    juvenile=sum(p.age+1<L.ADULT_AGE for p in group))
            sim.tick(**NORMAL)
            apply_extra_mineralization(sim)
            born=collections.Counter()
            young_deaths=collections.Counter()
            adult_deaths=collections.Counter()
            for event in life.events[event_at:]:
                k=(event["patch"],event["species"])
                if event["event"]=="plant_birth":
                    parent=event["parent_id"];child=event["identity"]
                    if parent not in ancestry or child in ancestry:
                        raise AssertionError("unpaid/untracked birth")
                    ancestry[child]=ancestry[parent]+1
                    max_generation=max(max_generation,ancestry[child])
                    born[k]+=1
                    events.append(dict(seed=seed,fraction=fraction,tick=tick,
                        patch=k[0],species=k[1],event="birth",
                        identity=child,parent=parent,generation=ancestry[child]))
                elif event["event"]=="plant_death":
                    who=event["identity"]
                    if who not in before:raise AssertionError("untracked death")
                    if before[who].age+1<L.ADULT_AGE:young_deaths[k]+=1
                    else:adult_deaths[k]+=1
                    events.append(dict(seed=seed,fraction=fraction,tick=tick,
                        patch=k[0],species=k[1],event="death",
                        identity=who,parent="",generation=ancestry.get(who,-1)))
            event_at=len(life.events)
            for p in life.individuals:
                if p.identity not in ancestry:raise AssertionError("untracked living plant")
                if p.identity not in before and p.identity not in before_seeds:
                    raise AssertionError("spontaneous living plant")
            for s in sim.eco.world.seeds:
                if s.identity not in ancestry:raise AssertionError("untracked seed")
            if extinct is not None and (life.individuals or sim.eco.world.seeds):
                raise AssertionError("organism respawn")
            if not life.individuals and not sim.eco.world.seeds and extinct is None:
                extinct=tick
            if not math.isclose(sim.eco.world.total_biomass(),start_mass,rel_tol=1e-10,abs_tol=1e-6):
                raise AssertionError("mass was not conserved")
            if not math.isclose(life.hydro.total_water(),start_water,rel_tol=1e-10,abs_tol=1e-6):
                raise AssertionError("water was not conserved")
            for patch,species in GROUPS:
                k=(patch,species)
                snap=pre[k]
                cumulative[(k,"potential_ticks")]+=int(snap["potential"]>0)
                cumulative[(k,"births")]+=born[k]
                cumulative[(k,"juvenile_deaths")]+=young_deaths[k]
                cumulative[(k,"adult_deaths")]+=adult_deaths[k]
                if tick%YEAR==0:
                    plants=[p for p in life.individuals if (p.patch,p.species)==k]
                    seeds=[s for s in sim.eco.world.seeds if (s.patch,s.species)==k]
                    cohorts.append(dict(seed=seed,fraction=fraction,year=tick//YEAR,patch=patch,
                        species=species,pre_live=snap["living"],pre_adults=snap["adults"],
                        pre_cooldown_ready=snap["cooldown_ready"],pre_potential=snap["potential"],
                        pre_juveniles=snap["juvenile"],births_on_year=cumulative[(k,"births")],
                        juvenile_deaths_to_date=cumulative[(k,"juvenile_deaths")],
                        adult_deaths_to_date=cumulative[(k,"adult_deaths")],
                        post_live=len(plants),post_seeds=len(seeds),
                        local_nutrients=life.hydro.network.nodes[patch].state.nutrients,
                        local_detritus=life.hydro.network.nodes[patch].state.detritus))
        totals=dict(seed=seed,fraction=fraction,ticks=ticks,
            initial_founders=len(founders),initial_paid_seeds=len(paid),
            births=sum(v for (k,name),v in cumulative.items() if name=="births"),
            juvenile_deaths=sum(v for (k,name),v in cumulative.items() if name=="juvenile_deaths"),
            adult_deaths=sum(v for (k,name),v in cumulative.items() if name=="adult_deaths"),
            potential_ticks=sum(v for (k,name),v in cumulative.items() if name=="potential_ticks"),
            last_generation=max_generation,global_extinction_tick=extinct,
            final_plants=len(life.individuals),final_seeds=len(sim.eco.world.seeds),
            mass_conserved=True,water_conserved=True,no_respawn=True)
        return totals,cohorts,events

def _write_csv(path,records,fields):
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--seeds",default="11,23,37",help="comma-separated integer seeds, max 50")
    parser.add_argument("--ticks",type=int,default=1200)
    parser.add_argument("--outdir",default="long13_results")
    args=parser.parse_args(argv)
    seeds=[int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    if not seeds or len(seeds)>50 or len(set(seeds))!=len(seeds):
        raise ValueError("1-50 unique seeds required")
    if any(s<0 or s>2147483647 for s in seeds):
        raise ValueError("seed outside bounds")
    if not 12<=args.ticks<=2400 or args.ticks%12:
        raise ValueError("tick count must be 12..2400 and multiple of 12")
    target=Path(args.outdir)
    target.mkdir(parents=True,exist_ok=True)
    cases=[];annual=[];events=[]
    for seed in seeds:
        for fraction in FRACTIONS:
            case,yearly,records=evaluate(seed,fraction,args.ticks)
            cases.append(case);annual.extend(yearly);events.extend(records)
            print("verified",seed,fraction,"births",case["births"],
                  "end_plants",case["final_plants"],flush=True)
    _write_csv(target/"cohorts.csv",annual,[
        "seed","fraction","year","patch","species","pre_live","pre_adults",
        "pre_cooldown_ready","pre_potential","pre_juveniles","births_on_year",
        "juvenile_deaths_to_date","adult_deaths_to_date","post_live","post_seeds",
        "local_nutrients","local_detritus"])
    _write_csv(target/"events.csv",events,[
        "seed","fraction","tick","patch","species","event","identity","parent","generation"])
    report=dict(schema="osixbay.genesis.eco.long13.kaggle.v1",status="offline_noncanonical",
        source_commit="feature/genesis-eco-long13-kaggle-batch-20261114",
        ticks_per_symbolic_year=12,seed_count=len(seeds),fractions=list(FRACTIONS),
        cases=cases,annual_rows=len(annual),event_count=len(events),
        limitations=["Pre-tick potential excludes same-tick growth/reconciliation",
            "Cooldown is decremented during model tick; proxy uses pre-cooldown<=1",
            "No guaranteed birth from potential; post-tick eligibility can mislead",
            "Not a biologically calibrated planetary model",
            "F01 proxy differs from pinned original PR88 physiology",
            "No internet, no external resource injection, no deployment"])
    (target/"summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("AUDIT PASS",len(cases),"runs",len(annual),"annual records",flush=True)
    return report
if __name__=="__main__":main()
