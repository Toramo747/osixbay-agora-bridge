"""ECO-LONG-12: patch occupancy and reproductive-cohort turnover.

Observational audit using identical ECO-LONG-11 scenarios. Adult = age>=8
and age<90 (actually reproductive stage), eligible = adult+biomass>=BIRTH_BIOMASS
+ cooldown==0. Eligibility is a proxy, not a guarantee of actual birth.
No new organisms or biomass; every birth event has a traced parent.
"""
import collections
import csv
import json
import math
from pathlib import Path
from f01_feeding_bridge_p0 import F01Feeding
from long10_offspring_budget_audit import FRACTIONS, SEEDS, TICKS
from long08_cohort_mortality_audit import cohort_settings
from long07_generational_renewal import tuning, CASES as LONG07_CASES
from long05_detritus_seedbank_audit import seedbank_from_live_parents, apply_extra_mineralization
from stress_ecosystem_dm089 import NORMAL
from multi_patch_p0 import NODES
from foodweb_p0 import PRODUCERS
import plant_lifecycle_p0 as L

GROUPS=tuple((p,s) for p in NODES for s in PRODUCERS)

def run_case(seed, fraction, ticks=TICKS):
    if fraction not in FRACTIONS or not 1<=ticks<=TICKS:
        raise ValueError("outside experiment")
    with tuning(LONG07_CASES[-1]),cohort_settings(8,fraction,.035):
        sim=F01Feeding(seed=seed)
        life=sim.eco.world.genetic.life
        ancestors={p.identity:0 for p in life.individuals}
        paid=seedbank_from_live_parents(sim)
        for d in paid:
            if d["seed_id"] in ancestors:raise AssertionError("duplicate paid seed")
            ancestors[d["seed_id"]]=1
        mass=sim.eco.world.total_biomass()
        water=life.hydro.total_water()
        events_at=len(life.events)
        counts=collections.defaultdict(lambda:collections.Counter())
        timelines=collections.defaultdict(list)
        annual=[]
        alive_ever=set()
        irreversibly_extinct=False
        global_extinction_tick=None
        total_births=0
        max_gen=1
        for tick in range(1,ticks+1):
            before_plants={p.identity for p in life.individuals}
            before_seeds={s.identity for s in sim.eco.world.seeds}
            sim.tick(**NORMAL)
            apply_extra_mineralization(sim)
            births_this_tick=collections.Counter()
            for ev in life.events[events_at:]:
                if ev["event"]=="plant_birth":
                    if ev["parent_id"] not in ancestors or ev["identity"] in ancestors:
                        raise AssertionError("untraceable birth")
                    gen=ancestors[ev["parent_id"]]+1
                    ancestors[ev["identity"]]=gen
                    max_gen=max(max_gen,gen)
                    births_this_tick[(ev["patch"],ev["species"])]+=1
                    total_births+=1
            events_at=len(life.events)
            for p in life.individuals:
                if p.identity not in ancestors:raise AssertionError("untracked living plant")
                if p.identity not in before_plants and p.identity not in before_seeds:
                    raise AssertionError("plant entered without paid seed")
            for s in sim.eco.world.seeds:
                if s.identity not in ancestors:raise AssertionError("untracked seed")
            if irreversibly_extinct and (life.individuals or sim.eco.world.seeds):
                raise AssertionError("resurrection")
            if not life.individuals and not sim.eco.world.seeds:
                irreversibly_extinct=True
                if global_extinction_tick is None:global_extinction_tick=tick
            if not math.isclose(mass,sim.eco.world.total_biomass(),abs_tol=1e-6,rel_tol=1e-10):
                raise AssertionError("biomass")
            if not math.isclose(water,life.hydro.total_water(),abs_tol=1e-6,rel_tol=1e-10):
                raise AssertionError("water")
            for patch,species in GROUPS:
                k=(patch,species)
                plants=[p for p in life.individuals if p.patch==patch and p.species==species]
                seeds=[s for s in sim.eco.world.seeds if s.patch==patch and s.species==species]
                adults=[p for p in plants if L.ADULT_AGE<=p.age<L.OLD_AGE]
                eligible=[p for p in adults if p.cooldown==0 and p.biomass>=L.BIRTH_BIOMASS]
                state=(bool(plants),bool(seeds),bool(adults),bool(eligible))
                timeline=timelines[k]
                if timeline:
                    old=timeline[-1]["state"]
                    if old[0] and not state[0]:counts[k]["lost_live_occupancy"]+=1
                    if not old[0] and state[0]:counts[k]["regained_live_occupancy"]+=1
                    if old[2] and not state[2]:counts[k]["lost_adult_cohort"]+=1
                    if not old[2] and state[2]:counts[k]["regained_adult_cohort"]+=1
                    if old[3] and not state[3]:counts[k]["lost_reproductive_eligibility"]+=1
                counts[k]["occupied_plant_ticks"]+=int(state[0])
                counts[k]["adult_plant_ticks"]+=int(state[2])
                counts[k]["eligible_plant_ticks"]+=int(state[3])
                counts[k]["no_plant_no_seed_ticks"]+=int(not state[0] and not state[1])
                counts[k]["births"]+=births_this_tick[k]
                timeline.append(dict(tick=tick,state=state,adults=len(adults),eligible=len(eligible),
                                     live=len(plants),seeds=len(seeds),births=births_this_tick[k],
                                     max_gen=max((ancestors[p.identity] for p in plants),default=-1)))
                if tick%12==0:
                    annual.append(dict(seed=seed,fraction=fraction,year=tick//12,
                        patch=patch,species=species,plants=len(plants),dormant=len(seeds),
                        adults=len(adults),eligible=len(eligible),
                        births_to_date=counts[k]["births"],
                        age_depth=timeline[-1]["max_gen"],
                        patch_nutrients=life.hydro.network.nodes[patch].state.nutrients))
        groups=[]
        for patch,species in GROUPS:
            k=(patch,species)
            t=timelines[k]
            nonempty=[x["tick"] for x in t if x["live"] or x["seeds"]]
            last_adult=next((x["tick"] for x in reversed(t) if x["adults"]),None)
            last_birth=next((x["tick"] for x in reversed(t) if x["births"]),None)
            groups.append(dict(patch=patch,species=species,initial_plants=1,
                last_occupied_tick=max(nonempty) if nonempty else None,
                last_adult_tick=last_adult,last_birth_tick=last_birth,
                final_plants=t[-1]["live"],final_seeds=t[-1]["seeds"],
                **dict(counts[k])))
        if sum(g["births"] for g in groups)!=total_births:
            raise AssertionError("births not reconciled")
        result=dict(seed=seed,fraction=fraction,ticks=ticks,
            initial_paid_seeds=len(paid),births=total_births,max_generation=max_gen,
            global_extinction_tick=global_extinction_tick,
            remaining_plants=len(life.individuals),remaining_seeds=len(sim.eco.world.seeds),
            habitats=groups,mass_conserved=True,water_conserved=True,no_respawn=True)
        print("verified",seed,fraction,"last adult",max((g["last_adult_tick"] or 0 for g in groups)),
              "global extinct",global_extinction_tick,flush=True)
        return result,annual

def main():
    out=Path("long12_results");out.mkdir(exist_ok=True)
    cases=[];annual=[]
    for seed in SEEDS:
        for f in FRACTIONS:
            case,rows=run_case(seed,f)
            cases.append(case);annual.extend(rows)
    with (out/"habitat_cohort_annual.csv").open("w",newline="",encoding="utf-8") as fp:
        w=csv.DictWriter(fp,fieldnames=list(annual[0]));w.writeheader();w.writerows(annual)
    report=dict(schema="osixbay.genesis.eco.long12.v1",
        status="observational_uncalibrated_not_canonical",
        runs=len(cases),ticks_per_run=TICKS,annual_rows=len(annual),
        seeds=list(SEEDS),fractions=list(FRACTIONS),cases=cases,
        limitations=["Reproductive eligibility is age, stock, cooldown proxy; not fertility itself",
            "Plant occupancy and seed occupancy measured by patch and species",
            "Zero adult intervals may recover only from preexisting living plants or paid seeds",
            "Three synthetic habitats; 12 ticks per symbolic year",
            "F01 original PR88 remains separate; no merge, deploy or new biomass"])
    (out/"summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("AUDIT PASS",len(cases),"cases",len(annual),"habitat-years",flush=True)
if __name__=="__main__":main()
