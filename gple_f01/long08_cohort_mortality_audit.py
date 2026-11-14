"""ECO-LONG-08: cohort and death-cause audit of synthetic plant generations.

No organism injection: experimental controls adjust only thresholds and partition
parent biomass. Death causes are inferred from age at previous tick plus event
identity and must be treated as diagnostic classifications, not physiology.
"""
from __future__ import annotations
import collections
import contextlib
import csv
import json
import math
from pathlib import Path
import plant_lifecycle_p0 as L
from long07_generational_renewal import CASES as LONG07_CASES, tuning
from long05_detritus_seedbank_audit import seedbank_from_live_parents, apply_extra_mineralization, stock_totals
from long06_generation_chain_audit import state
from f01_feeding_bridge_p0 import F01Feeding
from stress_ecosystem_dm089 import NORMAL
from multi_patch_p0 import NODES
from foodweb_p0 import PRODUCERS

SEEDS=(11,23,37)
TICKS=1200
SCENARIOS=(
    ("balanced_reference",8,.24,.035),
    ("early_adult",4,.24,.035),
    ("smaller_offspring",8,.12,.035),
    ("larger_offspring",8,.40,.035),
    ("lower_minimum_mass",8,.24,.015),
    ("combined_cohort",4,.12,.015),
)

@contextlib.contextmanager
def cohort_settings(adult_age, birth_fraction, min_mass):
    if not (1<=adult_age<90 and .05<=birth_fraction<=.5 and 0<min_mass<.1):
        raise ValueError("bounded candidate parameters required")
    original=(L.ADULT_AGE,L.BIRTH_FRACTION,L.MIN_BIOMASS)
    try:
        L.ADULT_AGE=adult_age
        L.BIRTH_FRACTION=birth_fraction
        L.MIN_BIOMASS=min_mass
        yield
    finally:
        L.ADULT_AGE,L.BIRTH_FRACTION,L.MIN_BIOMASS=original

def run_case(seed,scenario,ticks=TICKS):
    name,adult_age,birth_fraction,min_mass=scenario
    with tuning(LONG07_CASES[-1]), cohort_settings(adult_age,birth_fraction,min_mass):
        sim=F01Feeding(seed=seed)
        life=sim.eco.world.genetic.life
        founders={p.identity for p in life.individuals}
        deposited=seedbank_from_live_parents(sim)
        depths={p:0 for p in founders}
        for d in deposited:depths[d["seed_id"]]=1
        initial_mass=sim.eco.world.total_biomass()
        initial_water=life.hydro.total_water()
        event_index=len(life.events)
        deaths=collections.Counter()
        deaths_by_patch=collections.Counter()
        births_by_patch=collections.Counter()
        births_by_generation=collections.Counter()
        maturity_observations=collections.Counter()
        max_live_depth=0
        highest_depth=1
        first_global_extinction=None
        max_live=0
        annual=[]
        for tick in range(1,ticks+1):
            old={p.identity:(p.age,p.biomass,p.patch,p.species) for p in life.individuals}
            old_births=life.counts["births"]
            sim.tick(**NORMAL)
            apply_extra_mineralization(sim)
            seen_events=life.events[event_index:]
            event_index=len(life.events)
            for ev in seen_events:
                if ev["event"]=="plant_birth":
                    parent=ev["parent_id"]
                    if parent not in depths:raise AssertionError("unknown parent")
                    child=ev["identity"]
                    if child in depths:raise AssertionError("identity reused")
                    depths[child]=depths[parent]+1
                    highest_depth=max(highest_depth,depths[child])
                    births_by_patch[(ev["patch"],ev["species"])]+=1
                    births_by_generation[depths[child]]+=1
                elif ev["event"]=="plant_death":
                    pid=ev["identity"]
                    if pid not in old:
                        raise AssertionError("untracked deceased plant")
                    age,mass,patch,species=old[pid]
                    # An age>=MAX_AGE at update guarantees age-triggered death;
                    # otherwise distinguish non-age loss without inventing a diagnosis.
                    kind="age_limit" if age+1>=L.MAX_AGE else "non_age_mass_or_stress"
                    deaths[kind]+=1
                    deaths_by_patch[(kind,patch,species)]+=1
            if life.counts["births"]-old_births != sum(ev["event"]=="plant_birth" for ev in seen_events):
                raise AssertionError("birth event/counter mismatch")
            for p in life.individuals:
                if p.identity not in depths:raise AssertionError("untracked living plant")
                if p.age>=L.ADULT_AGE:
                    maturity_observations[(p.patch,p.species,depths[p.identity])]+=1
            for s in sim.eco.world.seeds:
                if s.identity not in depths:raise AssertionError("untracked propagule")
            if first_global_extinction is not None and (life.individuals or sim.eco.world.seeds):
                raise AssertionError("spontaneous repopulation")
            if not life.individuals and not sim.eco.world.seeds and first_global_extinction is None:
                first_global_extinction=tick
            max_live=max(max_live,len(life.individuals))
            max_live_depth=max(max_live_depth,max((depths[p.identity] for p in life.individuals),default=0))
            if not math.isclose(sim.eco.world.total_biomass(),initial_mass,abs_tol=1e-6,rel_tol=1e-10):
                raise AssertionError("material ledger changed")
            if not math.isclose(life.hydro.total_water(),initial_water,abs_tol=1e-6,rel_tol=1e-10):
                raise AssertionError("water ledger changed")
            if tick%12==0:
                stocks=stock_totals(sim)
                for patch in NODES:
                    web=life.hydro.network.nodes[patch]
                    for species in PRODUCERS:
                        group=[p for p in life.individuals if p.patch==patch and p.species==species]
                        adults=[p for p in group if p.age>=L.ADULT_AGE]
                        annual.append(dict(seed=seed,scenario=name,year=tick//12,patch=patch,species=species,
                            live=len(group),adult=len(adults),juvenile=len(group)-len(adults),
                            producer_mass=getattr(web.state,species),mean_mass=(sum(p.biomass for p in group)/len(group) if group else 0),
                            max_mass=max((p.biomass for p in group),default=0),
                            juveniles_mass=sum(p.biomass for p in group if p.age<L.ADULT_AGE),
                            nutrients=web.state.nutrients,detritus=web.state.detritus,
                            biomass=sim.eco.world.total_biomass(),water=life.hydro.total_water(),
                            depth=max((depths[p.identity] for p in group),default=-1),
                            births_total=life.counts["births"],seed_germinations=sim.eco.world.germinated))
        result=dict(seed=seed,scenario=name,parameters=dict(adult_age=adult_age,birth_fraction=birth_fraction,min_biomass=min_mass),
            final_plants=len(life.individuals),final_seeds=len(sim.eco.world.seeds),
            first_irreversible_extinction_tick=first_global_extinction,
            maximum_live_plants=max_live,highest_birth_generation=highest_depth,
            max_live_generation=max_live_depth,
            birth_events=life.counts["births"],death_events=life.counts["deaths"],
            age_deaths=deaths["age_limit"],non_age_deaths=deaths["non_age_mass_or_stress"],
            classified_deaths=sum(deaths.values()),
            births_by_patch={f"{k[0]}.{k[1]}":v for k,v in births_by_patch.items()},
            deaths_by_patch={f"{k[0]}.{k[1]}.{k[2]}":v for k,v in deaths_by_patch.items()},
            births_by_generation=dict(sorted(births_by_generation.items())),
            adult_observations_by_patch={f"{k[0]}.{k[1]}.g{k[2]}":v for k,v in maturity_observations.items()},
            seed_germinations=sim.eco.world.germinated,
            seed_expirations=sim.eco.world.expired,
            original_paid_seeds=len(deposited),conserved=True,no_resurrection=True)
        if result["classified_deaths"]!=result["death_events"]:
            raise AssertionError("unclassified plant death")
        print("verified",seed,name,"plants",result["final_plants"],"births",result["birth_events"],
              "age_deaths",result["age_deaths"],"other_deaths",result["non_age_deaths"],
              "depth",highest_depth,flush=True)
        return result,annual

def main():
    output=Path("long08_results")
    output.mkdir(exist_ok=True)
    cases=[];rows=[]
    for seed in SEEDS:
        for scenario in SCENARIOS:
            case,annual=run_case(seed,scenario)
            cases.append(case);rows.extend(annual)
    with (output/"cohorts_by_year_patch.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    report=dict(schema="osixbay.genesis.eco.long08.v1",status="experimental_not_canonical",
        seeds=list(SEEDS),scenarios=[list(c) for c in SCENARIOS],runs=len(cases),
        ticks_per_run=TICKS,cohort_rows=len(rows),cases=cases,
        mortality_note="Non-age cause inferred by elimination; combines low biomass and genetic stress",
        limitations=[
            "No F01 physiology PR88 coupled to PR93; no real species demography",
            "Mass and water abstract; 12 ticks is one notional year",
            "All settings counterfactual, not biochemically calibrated",
            "Plant death event does not encode a native reason; categories are inferred",
            "No resurrections or imported resource stocks; Godot/Cloudflare untouched"])
    (output/"summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("AUDIT PASS",len(cases),"cases",len(rows),"cohort rows",flush=True)
if __name__=="__main__":main()
