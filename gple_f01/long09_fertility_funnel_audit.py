"""ECO-LONG-09 — verified descendant fertility funnel by patch and generation.

No simulation physics is modified. The cohort experiment uses the exact six
ECO-LONG-08 counterfactual scenarios and parent-paid initial seeds. This audit
separates ancestry, germination, maturation and actual reproduction. A plant
counts as reproductive only if it appears as a parent in a real plant_birth
event, NOT merely for reaching adult age. Snapshot/ledger constraints persist.

Important: patch is the patch where the stage/event occurred. Initial banked
seeds are generation 1, but do not count as offspring born during the run.
"""
from __future__ import annotations
import collections
import csv
import json
import math
from pathlib import Path

from f01_feeding_bridge_p0 import F01Feeding
from long08_cohort_mortality_audit import SEEDS, SCENARIOS, cohort_settings
from long07_generational_renewal import CASES as LONG07_CASES, tuning
from long05_detritus_seedbank_audit import seedbank_from_live_parents, apply_extra_mineralization
from stress_ecosystem_dm089 import NORMAL
from multi_patch_p0 import NODES
from foodweb_p0 import PRODUCERS

TICKS=1200
KEYS=("known", "germinated", "matured", "reproduced", "deceased", "seed_expired")
def key(patch,species,generation):
    return (patch,species,int(generation))

def audit_case(seed,scenario,ticks=TICKS):
    name,adult_age,birth_fraction,min_mass=scenario
    with tuning(LONG07_CASES[-1]), cohort_settings(adult_age,birth_fraction,min_mass):
        sim=F01Feeding(seed=seed)
        life=sim.eco.world.genetic.life
        # id -> immutable lineage attributes; current stage observations are sets
        ancestry={p.identity:(0,p.species,p.patch) for p in life.individuals}
        original_founders=set(ancestry)
        initial_paid=seedbank_from_live_parents(sim)
        for item in initial_paid:
            sid=item["seed_id"]
            if sid in ancestry:raise AssertionError("seed identity collision")
            ancestry[sid]=(1,item["species"],item["patch"])
        seen_births=set()
        matured=set(p.identity for p in life.individuals if p.age>=adult_age)
        germinated=set()
        actual_parents=set()
        deceased=set()
        expired=set()
        counts={k:collections.Counter() for k in KEYS}
        for p in life.individuals:
            counts["known"][key(p.patch,p.species,0)]+=1
            counts["matured"][key(p.patch,p.species,0)]+=1
        for item in initial_paid:
            counts["known"][key(item["patch"],item["species"],1)]+=1
        event_offset=len(life.events)
        total_initial_mass=sim.eco.world.total_biomass()
        total_initial_water=life.hydro.total_water()
        saw_extinction=False
        annual=[]
        last_birth_tick=None
        last_actual_germination_tick=None
        stage_ticks=collections.Counter()
        for tick in range(1,ticks+1):
            prev_plants={p.identity:(p.patch,p.species,p.age,p.biomass) for p in life.individuals}
            prev_seeds={s.identity:(s.patch,s.species) for s in sim.eco.world.seeds}
            sim.tick(**NORMAL)
            apply_extra_mineralization(sim)
            new_events=life.events[event_offset:]
            event_offset=len(life.events)
            for event in new_events:
                if event["event"]=="plant_birth":
                    child=event["identity"]; parent=event["parent_id"]
                    if parent not in ancestry or child in ancestry:
                        raise AssertionError("broken or duplicate lineage")
                    parent_gen=ancestry[parent][0]
                    generation=parent_gen+1
                    ancestry[child]=(generation,event["species"],event["patch"])
                    seen_births.add(child)
                    counts["known"][key(event["patch"],event["species"],generation)]+=1
                    if parent not in actual_parents:
                        actual_parents.add(parent)
                        pg,ps,_=ancestry[parent]
                        # Use event location, which may differ from germination patch.
                        counts["reproduced"][key(event["patch"],ps,pg)]+=1
                    last_birth_tick=tick
                elif event["event"]=="plant_death":
                    pid=event["identity"]
                    if pid not in ancestry or pid in deceased:
                        raise AssertionError("invalid plant death")
                    deceased.add(pid)
                    gen,species,_=ancestry[pid]
                    counts["deceased"][key(event["patch"],species,gen)]+=1
            current_plants={p.identity:p for p in life.individuals}
            current_seeds={s.identity:s for s in sim.eco.world.seeds}
            for pid,p in current_plants.items():
                if pid not in ancestry:
                    raise AssertionError("living plant without parent")
                gen,species,_=ancestry[pid]
                if pid not in original_founders and pid not in germinated and pid not in prev_plants:
                    # New child in a current-tick birth event is escrowed into a
                    # propagule, not an adult. Genuine plant entry must come from seed.
                    if pid in prev_seeds:
                        germinated.add(pid)
                        counts["germinated"][key(p.patch,species,gen)]+=1
                        last_actual_germination_tick=tick
                    else:
                        raise AssertionError("plant appeared without seed germination")
                if p.age>=adult_age and pid not in matured:
                    matured.add(pid)
                    counts["matured"][key(p.patch,species,gen)]+=1
                stage_ticks[key(p.patch,species,gen)]+=1
            for sid,s in current_seeds.items():
                if sid not in ancestry:
                    raise AssertionError("seed created without ancestor")
            for sid,(patch,species) in prev_seeds.items():
                if sid not in current_seeds and sid not in current_plants:
                    if sid not in expired:
                        expired.add(sid)
                        gen,_,_=ancestry[sid]
                        counts["seed_expired"][key(patch,species,gen)]+=1
            if saw_extinction and (current_plants or current_seeds):
                raise AssertionError("unpaid organism resurrection")
            if not current_plants and not current_seeds:
                saw_extinction=True
            if not math.isclose(sim.eco.world.total_biomass(),total_initial_mass,rel_tol=1e-10,abs_tol=1e-6):
                raise AssertionError("mass conservation violated")
            if not math.isclose(life.hydro.total_water(),total_initial_water,rel_tol=1e-10,abs_tol=1e-6):
                raise AssertionError("water conservation violated")
            if tick%12==0:
                for patch in NODES:
                    web=life.hydro.network.nodes[patch]
                    for species in PRODUCERS:
                        group=[p for p in life.individuals if p.patch==patch and p.species==species]
                        for generation in sorted(set([0,1,2,3]+[ancestry[p.identity][0] for p in group])):
                            selected=[p for p in group if ancestry[p.identity][0]==generation]
                            k=key(patch,species,generation)
                            annual.append(dict(seed=seed,scenario=name,year=tick//12,
                                patch=patch,species=species,generation=generation,
                                live=len(selected),adults=sum(p.age>=adult_age for p in selected),
                                mass=sum(p.biomass for p in selected),
                                first_recorded=counts["known"][k],germinated=counts["germinated"][k],
                                matured=counts["matured"][k],reproductive_individuals=counts["reproduced"][k],
                                plant_deaths=counts["deceased"][k],seed_expirations=counts["seed_expired"][k],
                                patch_nutrients=web.state.nutrients,patch_detritus=web.state.detritus,
                                patch_producer_mass=getattr(web.state,species)))
        all_ids=set(ancestry)
        if any(x not in all_ids for x in matured|germinated|actual_parents|deceased|expired):
            raise AssertionError("unknown lineage identity")
        if not actual_parents.issubset(matured):
            raise AssertionError("reproducing individual never became adult")
        for pid in actual_parents:
            if ancestry[pid][0]>0 and pid not in germinated:
                raise AssertionError("unpaid descendant reproduced")
        groups=[]
        unique_groups=sorted(set().union(*(set(c) for c in counts.values())))
        for patch,species,generation in unique_groups:
            k=key(patch,species,generation)
            groups.append(dict(patch=patch,species=species,generation=generation,
                **{field:counts[field][k] for field in KEYS},
                adult_plant_ticks=stage_ticks[k]))
        by_generation=[]
        for generation in sorted({x[0] for x in ancestry.values()}):
            ids={pid for pid,(g,_,_) in ancestry.items() if g==generation}
            by_generation.append(dict(generation=generation,
                known=len(ids),germinated=len(ids & germinated),
                matured=len(ids & matured),reproduced=len(ids & actual_parents),
                died=len(ids & deceased),
                # Fertility funnel is measured among genuinely germinated individuals.
                germinated_to_matured=len(ids & germinated & matured),
                matured_to_reproduced=len(ids & matured & actual_parents)))
        final=dict(seed=seed,scenario=name,ticks=ticks,
            first_no_plants_or_seeds=(None if not saw_extinction else next((r["year"] for r in annual if r["live"]==0),None)),
            surviving_plants=len(life.individuals),dormant_seeds=len(sim.eco.world.seeds),
            last_birth_tick=last_birth_tick,last_germination_tick=last_actual_germination_tick,
            original_founders=len(original_founders),paid_initial_propagules=len(initial_paid),
            total_plant_birth_events=len(seen_births),max_generation=max(x[0] for x in ancestry.values()),
            generations=by_generation,habitats=groups,
            biomass_conserved=True,water_conserved=True,no_respawn=True,
            interpretation="adult maturity is an observed threshold, reproduction requires parent event")
        print("verified",seed,name,"born",len(seen_births),
              "matured_descendants",sum(r["matured"] for r in by_generation if r["generation"]>0),
              "reproducing_descendants",sum(r["reproduced"] for r in by_generation if r["generation"]>0),
              "remaining",final["surviving_plants"],flush=True)
        return final,annual

def main():
    target=Path("long09_results");target.mkdir(exist_ok=True)
    results=[];rows=[]
    for seed in SEEDS:
        for scenario in SCENARIOS:
            summary,detail=audit_case(seed,scenario)
            results.append(summary);rows.extend(detail)
    with (target/"cohort_fertility_by_year_patch.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    report=dict(schema="osixbay.genesis.eco.long09.v1",
       status="controlled_observational_not_canonical",
       seeds=list(SEEDS),scenarios=[list(x) for x in SCENARIOS],
       ticks_each=TICKS,runs=len(results),annual_rows=len(rows),
       cases=results,
       notes=[
           "Counts describe unique individuals, not annual probabilities",
           "Patch attributed to stage/event; descendants can move via propagules",
           "Initial paid propagules count as generation 1 but not newly born during the test",
           "Maturity is an age threshold, fertilization/pollination is not modeled",
           "No original PR88 F01 physiology integration",
           "Mass and water are synthetic stock proxies, 12 ticks per notional year",
           "No Godot, Cloudflare, Agora, merge or deployment"])
    (target/"summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("AUDIT PASS",len(results),"cases",len(rows),"cohort rows",flush=True)
if __name__=="__main__":main()
