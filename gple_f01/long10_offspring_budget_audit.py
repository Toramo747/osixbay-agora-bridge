"""ECO-LONG-10: parent-paid offspring biomass tradeoff, 100 notional years.

Six fractions of parent tissue are varied ONE AT A TIME against the same
ECO-LONG-09 balanced reference. No unearned matter, animals or respawns.
Maturity is a nominal age threshold; becoming a parent requires a real birth
event. All biological quantities are uncalibrated abstract model units.
"""
from __future__ import annotations
import collections
import csv
import json
import math
from pathlib import Path

from f01_feeding_bridge_p0 import F01Feeding
from long08_cohort_mortality_audit import cohort_settings
from long07_generational_renewal import tuning, CASES as LONG07_CASES
from long05_detritus_seedbank_audit import seedbank_from_live_parents, apply_extra_mineralization
from stress_ecosystem_dm089 import NORMAL
from multi_patch_p0 import NODES
from foodweb_p0 import PRODUCERS

SEEDS=(11,23,37)
TICKS=1200
FRACTIONS=(0.12,0.18,0.24,0.32,0.40,0.48)
YEARTICKS=12

def run_case(seed,fraction,ticks=TICKS):
    if fraction not in FRACTIONS or not 1<=ticks<=TICKS:
        raise ValueError("fraction or duration outside audited experiment")
    with tuning(LONG07_CASES[-1]), cohort_settings(8,fraction,0.035):
        sim=F01Feeding(seed=seed)
        life=sim.eco.world.genetic.life
        original_founders={p.identity for p in life.individuals}
        ancestry={p.identity:(0,p.species,p.patch) for p in life.individuals}
        paid=seedbank_from_live_parents(sim)
        for item in paid:
            sid=item["seed_id"]
            if sid in ancestry:raise AssertionError("duplicate initial seed identity")
            ancestry[sid]=(1,item["species"],item["patch"])
        initial_mass=sim.eco.world.total_biomass()
        initial_water=life.hydro.total_water()
        matured=set(original_founders)
        germinated=set()
        reproductive_parents=set()
        seed_births=set()
        living_start=set(original_founders)
        birth_records=[]
        stage_events={
            "germinated":collections.defaultdict(set),
            "matured":collections.defaultdict(set),
            "reproductive_parents":collections.defaultdict(set)
        }
        cohort_by_year=[]
        event_start=len(life.events)
        extinct_tick=None
        highest_gen=1
        for tick in range(1,ticks+1):
            pre_live={p.identity for p in life.individuals}
            pre_seeds={s.identity for s in sim.eco.world.seeds}
            sim.tick(**NORMAL)
            apply_extra_mineralization(sim)
            for ev in life.events[event_start:]:
                if ev["event"]!="plant_birth":continue
                child,parent=ev["identity"],ev["parent_id"]
                if child in ancestry or parent not in ancestry:
                    raise AssertionError("duplicate child or untraceable parent")
                generation=ancestry[parent][0]+1
                ancestry[child]=(generation,ev["species"],ev["patch"])
                highest_gen=max(highest_gen,generation)
                seed_births.add(child)
                reproductive_parents.add(parent)
                stage_events["reproductive_parents"][(ev["patch"],ev["species"],ancestry[parent][0])].add(parent)
                mass=float(ev["quantity"])
                if not math.isfinite(mass) or mass<=0:raise AssertionError("unpaid child mass")
                birth_records.append(dict(seed=seed,offspring_fraction=fraction,
                    tick=tick,patch=ev["patch"],species=ev["species"],
                    parent_generation=ancestry[parent][0],
                    child_generation=generation,birth_mass=mass,
                    child_id=child,parent_id=parent))
            event_start=len(life.events)
            for p in life.individuals:
                if p.identity not in ancestry:raise AssertionError("untracked plant")
                gen,species,_=ancestry[p.identity]
                if p.identity not in pre_live and p.identity not in original_founders and p.identity not in germinated:
                    if p.identity not in pre_seeds:
                        raise AssertionError("plant germinated without tracked seed")
                    germinated.add(p.identity)
                    stage_events["germinated"][(p.patch,species,gen)].add(p.identity)
                if p.age>=8 and p.identity not in matured:
                    matured.add(p.identity)
                    stage_events["matured"][(p.patch,species,gen)].add(p.identity)
            for s in sim.eco.world.seeds:
                if s.identity not in ancestry:
                    raise AssertionError("untracked propagule")
            if extinct_tick is not None and (life.individuals or sim.eco.world.seeds):
                raise AssertionError("spontaneous resurrection")
            if not life.individuals and not sim.eco.world.seeds and extinct_tick is None:
                extinct_tick=tick
            if not math.isclose(initial_mass,sim.eco.world.total_biomass(),rel_tol=1e-10,abs_tol=1e-6):
                raise AssertionError("mass not conserved")
            if not math.isclose(initial_water,life.hydro.total_water(),rel_tol=1e-10,abs_tol=1e-6):
                raise AssertionError("water not conserved")
            if tick%YEARTICKS==0:
                year=tick//YEARTICKS
                for patch in NODES:
                    web=life.hydro.network.nodes[patch]
                    for species in PRODUCERS:
                        group=[p for p in life.individuals if p.patch==patch and p.species==species]
                        for gen in range(max(4,highest_gen+1)):
                            cohort=[p for p in group if ancestry[p.identity][0]==gen]
                            cohort_by_year.append(dict(seed=seed,fraction=fraction,year=year,patch=patch,
                                species=species,generation=gen,alive=len(cohort),
                                adults=sum(p.age>=8 for p in cohort),
                                mean_mass=(sum(p.biomass for p in cohort)/len(cohort) if cohort else 0.0),
                                total_live_mass=sum(p.biomass for p in cohort),
                                local_producer_stock=getattr(web.state,species),
                                local_detritus=web.state.detritus,
                                local_nutrients=web.state.nutrients))
        if not reproductive_parents.issubset(matured):
            raise AssertionError("juvenile parent was counted")
        if not germinated.issubset(set(ancestry)-original_founders):
            raise AssertionError("founder incorrectly germinated")
        if any(p not in germinated for p in reproductive_parents-original_founders):
            raise AssertionError("a descendant parent never germinated")
        generations=[]
        for gen in range(highest_gen+1):
            ids={p for p,(g,_,_) in ancestry.items() if g==gen}
            records=[r for r in birth_records if r["child_generation"]==gen]
            generations.append(dict(generation=gen,individuals_known=len(ids),
                genuinely_born=len(records),
                germinated=len(ids&germinated),matured=len(ids&matured),
                reproduced=len(ids&reproductive_parents),
                maturity_to_parent_ratio=(len(ids&reproductive_parents)/len(ids&matured)
                                           if ids&matured else None),
                total_allocated_birth_mass=sum(r["birth_mass"] for r in records),
                mean_birth_mass=(sum(r["birth_mass"] for r in records)/len(records) if records else None)))
        habitats=[]
        for patch in NODES:
            for species in PRODUCERS:
                for gen in range(highest_gen+1):
                    k=(patch,species,gen)
                    births=[r for r in birth_records if r["patch"]==patch
                            and r["species"]==species and r["child_generation"]==gen]
                    habitats.append(dict(patch=patch,species=species,generation=gen,
                        births=len(births),
                        birth_mass=sum(r["birth_mass"] for r in births),
                        germinated=len(stage_events["germinated"][k]),
                        matured=len(stage_events["matured"][k]),
                        distinct_parents=len(stage_events["reproductive_parents"][k])))
        result=dict(seed=seed,offspring_fraction=fraction,ticks=ticks,
            initial_paid_seedbank=len(paid),original_founders=len(original_founders),
            total_births=len(birth_records),
            total_birth_mass=sum(r["birth_mass"] for r in birth_records),
            final_plants=len(life.individuals),final_propagules=len(sim.eco.world.seeds),
            extinction_tick=extinct_tick,highest_generation=highest_gen,
            generations=generations,habitats=habitats,
            germinated_individuals=len(germinated),
            matured_descendants=len(matured-original_founders),
            reproducing_descendants=len(reproductive_parents-original_founders),
            biomass_conserved=True,water_conserved=True,no_respawn=True)
        if sum(g["genuinely_born"] for g in generations)!=len(birth_records):
            raise AssertionError("birth event ledger mismatch")
        print("verified",seed,fraction,"born",len(birth_records),
              "matured",result["matured_descendants"],
              "descendant_parents",result["reproducing_descendants"],
              "depth",highest_gen,"live",result["final_plants"],flush=True)
        return result,cohort_by_year,birth_records

def main():
    out=Path("long10_results");out.mkdir(exist_ok=True)
    cases=[];annual=[];births=[]
    for seed in SEEDS:
        for fraction in FRACTIONS:
            summary,rows,events=run_case(seed,fraction)
            cases.append(summary);annual.extend(rows);births.extend(events)
    for name,records in (("cohort_by_year.csv",annual),("parent_paid_births.csv",births)):
        with (out/name).open("w",newline="",encoding="utf-8") as file:
            writer=csv.DictWriter(file,fieldnames=list(records[0]))
            writer.writeheader();writer.writerows(records)
    report=dict(schema="osixbay.genesis.eco.long10.v1",
        status="counterfactual_not_ecologically_calibrated",
        seeds=list(SEEDS),offspring_fractions=list(FRACTIONS),runs=len(cases),
        ticks_each=TICKS,annual_rows=len(annual),birth_records=len(births),
        cases=cases,notes=[
            "Matured is defined by age >= 8; reproduced requires a real parent event",
            "Initial six parent-paid propagules counted as generation one but not as runtime births",
            "Offspring mass is rounded event mass, not an independent conservation ledger",
            "Birth events can represent multiple offspring from one actual parent",
            "No new biomass, no resurrection or organism injection",
            "Only three synthetic habitats, uncalibrated coefficients and twelve ticks per symbolic year",
            "PR88 original F01 physiology still not integrated with ecological proxy",
            "No Godot, Cloudflare, Agora, Kaggle, merge or deployment"])
    (out/"summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("AUDIT PASS",len(cases),"cases",len(annual),"annual rows",len(births),"paid births",flush=True)

if __name__=="__main__":main()
