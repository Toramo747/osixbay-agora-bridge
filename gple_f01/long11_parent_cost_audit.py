"""ECO-LONG-11: parental reproductive cost and repeat fertility, closed ledger.

Same six offspring fractions and seeds as ECO-LONG-10. Births are genuine
plant_birth events. We audit exact parent tissue left after transferring a
fraction to each child, then follow whether that same parent dies or reproduces
again. Controls are uncalibrated; no organism injection, resurrection or deploy.
"""
from __future__ import annotations
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

WINDOWS=(12,24,36)


def analyze_case(seed, fraction, ticks=TICKS):
    if fraction not in FRACTIONS or not 1<=ticks<=TICKS:
        raise ValueError("unapproved fraction or duration")
    with tuning(LONG07_CASES[-1]), cohort_settings(8,fraction,.035):
        sim=F01Feeding(seed=seed)
        life=sim.eco.world.genetic.life
        founders={p.identity for p in life.individuals}
        ancestry={pid:0 for pid in founders}
        deposits=seedbank_from_live_parents(sim)
        for d in deposits:
            if d["seed_id"] in ancestry:raise AssertionError("initial seed collision")
            ancestry[d["seed_id"]]=1
        original_mass=sim.eco.world.total_biomass()
        original_water=life.hydro.total_water()
        birth_events=[]
        death_info={}
        annual=[]
        event_offset=len(life.events)
        extinct_tick=None
        max_generation=1
        running_births=collections.Counter()
        for tick in range(1,ticks+1):
            pre={p.identity:(p.age,p.biomass,p.patch,p.species) for p in life.individuals}
            sim.tick(**NORMAL)
            apply_extra_mineralization(sim)
            post={p.identity:p for p in life.individuals}
            for event in life.events[event_offset:]:
                if event["event"]=="plant_birth":
                    parent_id=event["parent_id"]
                    child_id=event["identity"]
                    if child_id in ancestry or parent_id not in ancestry or parent_id not in post:
                        raise AssertionError("untracked parent / duplicate child / missing parent")
                    parent=post[parent_id]
                    if parent.age<8:raise AssertionError("juvenile reproduced")
                    if parent.patch!=event["patch"] or parent.species!=event["species"]:
                        raise AssertionError("parent patch/species mismatch")
                    child_mass=float(event["quantity"])
                    # Original PlantLifecycle takes fraction from the parent's
                    # reconciled biomass, and then leaves the remaining fraction.
                    # Verify this independent relation against the rounded event.
                    expected_child_mass=parent.biomass*fraction/(1-fraction)
                    if not math.isclose(child_mass,expected_child_mass,rel_tol=1e-7,abs_tol=3e-8):
                        raise AssertionError("child mass not funded by post-birth parent")
                    child_generation=ancestry[parent_id]+1
                    ancestry[child_id]=child_generation
                    max_generation=max(max_generation,child_generation)
                    running_births[(parent.patch,parent.species)]+=1
                    birth_events.append(dict(
                        seed=seed,fraction=fraction,tick=tick,
                        patch=event["patch"],species=event["species"],
                        parent_id=parent_id,child_id=child_id,
                        parent_generation=ancestry[parent_id],child_generation=child_generation,
                        parent_age_at_birth=parent.age,
                        parent_mass_after_birth=parent.biomass,
                        parent_mass_before_birth=parent.biomass+expected_child_mass,
                        paid_child_mass=child_mass))
                elif event["event"]=="plant_death":
                    pid=event["identity"]
                    if pid in death_info or pid not in pre:
                        raise AssertionError("unknown/duplicate death")
                    age,biomass,patch,species=pre[pid]
                    death_info[pid]=dict(tick=tick,patch=patch,species=species,
                        generation=ancestry.get(pid,-1),
                        reason=("age_limit" if age+1>=L.MAX_AGE else "non_age_mass_or_stress"),
                        prior_age=age,prior_mass=biomass)
            event_offset=len(life.events)
            for pid in post:
                if pid not in ancestry:raise AssertionError("unearned live plant")
            for obj in sim.eco.world.seeds:
                if obj.identity not in ancestry:raise AssertionError("unearned propagule")
            if extinct_tick is not None and (post or sim.eco.world.seeds):
                raise AssertionError("spontaneous repopulation")
            if not post and not sim.eco.world.seeds and extinct_tick is None:
                extinct_tick=tick
            if not math.isclose(original_mass,sim.eco.world.total_biomass(),rel_tol=1e-10,abs_tol=1e-6):
                raise AssertionError("biomass conservation")
            if not math.isclose(original_water,life.hydro.total_water(),rel_tol=1e-10,abs_tol=1e-6):
                raise AssertionError("water conservation")
            if tick%12==0:
                year=tick//12
                for patch in NODES:
                    web=life.hydro.network.nodes[patch]
                    for species in PRODUCERS:
                        individuals=[p for p in life.individuals if p.patch==patch and p.species==species]
                        annual.append(dict(seed=seed,fraction=fraction,year=year,patch=patch,species=species,
                            living=len(individuals),adults=sum(p.age>=8 for p in individuals),
                            living_mass=sum(p.biomass for p in individuals),
                            parents_alive=sum(p.identity in {e["parent_id"] for e in birth_events} for p in individuals),
                            births_to_date=running_births[(patch,species)],
                            detritus=web.state.detritus,nutrients=web.state.nutrients,
                            producer_stock=getattr(web.state,species)))
        by_parent=collections.defaultdict(list)
        for event in birth_events:by_parent[event["parent_id"]].append(event)
        observed_parents=set(by_parent)
        living_ids={p.identity for p in life.individuals}
        for pid in observed_parents:
            if pid not in living_ids and pid not in death_info:
                raise AssertionError("parent disappeared without audited death")
        for pid,events in by_parent.items():
            events.sort(key=lambda e:e["tick"])
            death=death_info.get(pid)
            for index,event in enumerate(events):
                following=events[index+1]["tick"] if index+1<len(events) else None
                d_tick=death["tick"] if death else None
                if d_tick is not None and d_tick<=event["tick"]:
                    raise AssertionError("parent death precedes own birth event")
                if following is not None and d_tick is not None and following>=d_tick:
                    raise AssertionError("parent reproduced after death")
                event["parent_next_birth_tick"]=following
                event["parent_death_tick"]=d_tick
                event["parent_death_cause"]=death["reason"] if death else None
                event["parent_reproduced_again"]=following is not None
                event["parent_died_before_reproducing_again"]=(d_tick is not None and following is None)
                event["ticks_to_next_birth"]=following-event["tick"] if following else None
                event["ticks_to_parent_death"]=d_tick-event["tick"] if d_tick else None
                for window in WINDOWS:
                    event[f"survived_{window}_ticks"]=(
                        None if event["tick"]+window>ticks else
                        (d_tick is None or d_tick>event["tick"]+window))
        habitat_groups=[]
        for patch in NODES:
            for species in PRODUCERS:
                records=[e for e in birth_events if e["patch"]==patch and e["species"]==species]
                parents={e["parent_id"] for e in records}
                death_causes=collections.Counter(death_info[pid]["reason"] for pid in parents if pid in death_info)
                habitat_groups.append(dict(patch=patch,species=species,
                    births=len(records),distinct_parents=len(parents),
                    total_paid_child_mass=sum(e["paid_child_mass"] for e in records),
                    mean_parent_mass_after_birth=(sum(e["parent_mass_after_birth"] for e in records)/len(records) if records else None),
                    repeat_births=sum(e["parent_reproduced_again"] for e in records),
                    parents_with_multiple_births=sum(len(by_parent[pid])>1 for pid in parents),
                    parent_deaths_by_age=death_causes["age_limit"],
                    parent_deaths_other=death_causes["non_age_mass_or_stress"],
                    parents_alive_at_final=sum(pid in living_ids for pid in parents),
                    birth_events_parent_survives_24=sum(e["survived_24_ticks"] is True for e in records),
                    birth_events_observed_24=sum(e["survived_24_ticks"] is not None for e in records)))
        result=dict(seed=seed,offspring_fraction=fraction,ticks=ticks,
            initial_paid_propagules=len(deposits),founder_plants=len(founders),
            births=len(birth_events),distinct_parents=len(observed_parents),
            parents_with_repeat_births=sum(len(events)>1 for events in by_parent.values()),
            birth_events_with_future_repeat=sum(e["parent_reproduced_again"] for e in birth_events),
            total_paid_child_mass=sum(e["paid_child_mass"] for e in birth_events),
            avg_parent_mass_after_birth=(sum(e["parent_mass_after_birth"] for e in birth_events)/len(birth_events) if birth_events else None),
            parent_death_age=sum(death_info[pid]["reason"]=="age_limit" for pid in observed_parents if pid in death_info),
            parent_death_other=sum(death_info[pid]["reason"]=="non_age_mass_or_stress" for pid in observed_parents if pid in death_info),
            parent_alive_final=sum(pid in living_ids for pid in observed_parents),
            observed_births_24=sum(e["survived_24_ticks"] is not None for e in birth_events),
            survived_births_24=sum(e["survived_24_ticks"] is True for e in birth_events),
            fraction_births_with_surviving_parent_24=(
                sum(e["survived_24_ticks"] is True for e in birth_events)/
                sum(e["survived_24_ticks"] is not None for e in birth_events)
                if any(e["survived_24_ticks"] is not None for e in birth_events) else None),
            final_plants=len(living_ids),final_seeds=len(sim.eco.world.seeds),
            extinction_tick=extinct_tick,max_generation=max_generation,
            habitat_groups=habitat_groups,
            conserved_mass=True,conserved_water=True,no_resurrection=True)
        if sum(g["births"] for g in habitat_groups)!=len(birth_events):
            raise AssertionError("habitat event total mismatch")
        print("verified",seed,fraction,"born",result["births"],
              "repeat_parents",result["parents_with_repeat_births"],
              "survived_24",result["survived_births_24"],
              "extinct",result["extinction_tick"],flush=True)
        return result,annual,birth_events


def main():
    output=Path("long11_results")
    output.mkdir(exist_ok=True)
    cases=[];annual=[];births=[]
    for seed in SEEDS:
        for fraction in FRACTIONS:
            case,rows,events=analyze_case(seed,fraction)
            cases.append(case);annual.extend(rows);births.extend(events)
    for filename,items in (("habitats_annual.csv",annual),
                           ("parent_birth_followup.csv",births)):
        with (output/filename).open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=list(items[0]))
            writer.writeheader();writer.writerows(items)
    result=dict(schema="osixbay.genesis.eco.long11.v1",
        status="counterfactual_not_canonical",
        seeds=list(SEEDS),fractions=list(FRACTIONS),
        ticks_per_run=TICKS,runs=len(cases),annual_rows=len(annual),
        paid_births=len(births),cases=cases,
        limitations=[
            "Post-birth maternal tissue uses exact model split and rounded event quantity",
            "24-tick survival is per birth event; repeat births from same parent are correlated",
            "Parent mortality reason is inferred using age vs other loss; not full physiology",
            "No independent offspring fitness or species-ecology calibration",
            "Original PR88 F01 physiology not coupled authoritatively to PR93",
            "Three patches; 12 abstract ticks per year; no production or deployment"])
    (output/"summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("AUDIT PASS",len(cases),"cases",len(annual),"habitat-years",
          len(births),"parent-paid births",flush=True)


if __name__=="__main__":
    main()
