"""Offline individual life cycles for candidate PROD-A and PROD-B.

Individuals allocate the authoritative producer biomass already present in
FoodWeb. Birth splits existing biomass; deaths move it to detritus. Existing
aggregate P0 food/fruit updates are reconciled across living individuals.
No new biomass, genetics, actual mesh or Godot scene is created.
"""
from dataclasses import dataclass, asdict
import json
import math
from producer_hydration_p0 import ProducerHydrology
from multi_patch_p0 import NODES
from foodweb_p0 import PRODUCERS

SCHEMA="osixbay.genesis.gple.plant-life-p0.v1"
MIN_BIOMASS=0.035
BIRTH_BIOMASS=3.5
BIRTH_FRACTION=0.24
MAX_AGE=120
ADULT_AGE=8
OLD_AGE=90
REPRO_COOLDOWN=20
MAX_INDIVIDUALS_PER_PATCH=24

@dataclass
class Plant:
    identity: str
    patch: str
    species: str
    age: int
    biomass: float
    cooldown: int = 0
    def stage(self):
        if self.age < ADULT_AGE:return "juvenile"
        if self.age < OLD_AGE:return "adult"
        return "senescent"

class PlantLifecycle:
    def __init__(self,seed=11,dry_start=False):
        self.hydro=ProducerHydrology(seed=seed,dry_start=dry_start)
        self.individuals=[]
        self.next_id=1
        self.events=[]
        self.counts={"births":0,"deaths":0,"growth_adjustments":0}
        for patch in NODES:
            for species in PRODUCERS:
                pool=getattr(self.hydro.network.nodes[patch].state,species)
                self._add(patch,species,age=ADULT_AGE,biomass=pool)
        self.audit()

    def _add(self,patch,species,age,biomass):
        pid=f"p{self.next_id:06d}";self.next_id+=1
        self.individuals.append(Plant(pid,patch,species,age,biomass))
        return pid

    def pool(self,patch,species):
        return getattr(self.hydro.network.nodes[patch].state,species)

    def audit(self):
        self.hydro.audit()
        ids=[p.identity for p in self.individuals]
        if len(ids)!=len(set(ids)):raise ValueError("duplicate plant IDs")
        if not isinstance(self.next_id,int) or self.next_id<1:raise ValueError("next ID")
        for p in self.individuals:
            if p.patch not in NODES or p.species not in PRODUCERS or not p.identity.startswith("p"):
                raise ValueError("invalid plant")
            if not isinstance(p.age,int) or p.age<0 or not isinstance(p.cooldown,int) or p.cooldown<0:
                raise ValueError("age/cooldown")
            if not math.isfinite(p.biomass) or p.biomass<=0:raise ValueError("biomass")
        for patch in NODES:
            for species in PRODUCERS:
                individuals=[p for p in self.individuals if p.patch==patch and p.species==species]
                total=sum(p.biomass for p in individuals)
                if not math.isclose(total,self.pool(patch,species),abs_tol=1e-7,rel_tol=1e-10):
                    raise ValueError("individual biomass/pool mismatch")
                if len(individuals)>MAX_INDIVIDUALS_PER_PATCH:
                    raise ValueError("overpopulation")

    def _event(self,kind,p,quantity):
        self.events.append({"tick":self.hydro.network.ticks,
                            "event":kind,"identity":p.identity,
                            "patch":p.patch,"species":p.species,
                            "quantity":round(quantity,8)})

    def tick(self,**hydro_kwargs):
        # P0 FoodWeb updates biomass stock (growth, fruiting, turnover). Reconcile
        # change onto living individuals BEFORE any birth/death, including drought.
        self.hydro.tick(**hydro_kwargs)
        for patch in NODES:
            web=self.hydro.network.nodes[patch]
            for species in PRODUCERS:
                organisms=[p for p in self.individuals if p.patch==patch and p.species==species]
                pool=self.pool(patch,species)
                total=sum(p.biomass for p in organisms)
                if not organisms:
                    # No spontaneous appearance. Unowned stock returns to detritus.
                    if pool>0:web.move(species,"detritus",pool,"orphan_biomass_decay")
                    continue
                if total<=0:raise ValueError("invalid allocated mass")
                ratio=pool/total
                for p in organisms:p.biomass*=ratio
                self.counts["growth_adjustments"]+=1
        living=[]
        newborn=[]
        for p in sorted(self.individuals,key=lambda x:x.identity):
            p.age+=1
            p.cooldown=max(0,p.cooldown-1)
            web=self.hydro.network.nodes[p.patch]
            if p.age>=MAX_AGE or p.biomass<MIN_BIOMASS:
                # Death redistributes body mass into detritus, never deletes it.
                moved=web.move(p.species,"detritus",p.biomass,"plant_death")
                self.counts["deaths"]+=1
                self._event("plant_death",p,moved)
                continue
            living.append(p)
            group_size=sum(q.patch==p.patch and q.species==p.species for q in living+newborn)
            if (p.stage()=="adult" and p.cooldown==0 and p.biomass>=BIRTH_BIOMASS
                    and group_size<MAX_INDIVIDUALS_PER_PATCH):
                # Birth redistributes existing tissue (not a new stock mint).
                child_mass=p.biomass*BIRTH_FRACTION
                p.biomass-=child_mass
                p.cooldown=REPRO_COOLDOWN
                child_id=f"p{self.next_id:06d}"
                self.next_id+=1
                child=Plant(child_id,p.patch,p.species,age=0,biomass=child_mass)
                newborn.append(child)
                self.counts["births"]+=1
                self._event("plant_birth",child,child_mass)
        self.individuals=living+newborn
        self.audit()
        return self.summary()

    def summary(self):
        return {"tick":self.hydro.network.ticks,"alive":len(self.individuals),
                "births":self.counts["births"],"deaths":self.counts["deaths"],
                "biomass":round(self.hydro.network.biomass(),8),
                "water":round(self.hydro.total_water(),8),
                "by_species":{s:sum(p.species==s for p in self.individuals) for s in PRODUCERS},
                "stages":{stage:sum(p.stage()==stage for p in self.individuals)
                          for stage in ("juvenile","adult","senescent")}}

    def snapshot(self):
        return json.dumps({"schema":SCHEMA,"hydro":self.hydro.snapshot(),
                           "individuals":[asdict(p) for p in self.individuals],
                           "next_id":self.next_id,"events":self.events,"counts":self.counts},
                          sort_keys=True,separators=(",",":"))

    @classmethod
    def restore(cls,payload):
        d=json.loads(payload)
        if d.get("schema")!=SCHEMA:raise ValueError("schema")
        obj=object.__new__(cls)
        obj.hydro=ProducerHydrology.restore(d["hydro"])
        obj.individuals=[Plant(**p) for p in d["individuals"]]
        obj.next_id=d["next_id"]
        obj.events=d["events"]
        obj.counts=d["counts"]
        if set(obj.counts)!={"births","deaths","growth_adjustments"}:raise ValueError("counters")
        if any(not isinstance(v,int) or v<0 for v in obj.counts.values()):
            raise ValueError("counter value")
        obj.audit()
        return obj

def experiment(seeds=(11,23,37),ticks=400):
    if not seeds or len(seeds)>20 or not 1<=ticks<=5000:raise ValueError("budget")
    scenarios={
      "normal":{"rain_rate":0.14,"evaporation_rate":0.035},
      "drought":{"rain_rate":0.0,"evaporation_rate":0.09},
      "wet":{"rain_rate":0.5,"evaporation_rate":0.015}
    }
    results=[]
    for seed in seeds:
        for name,rates in scenarios.items():
            w=PlantLifecycle(seed=seed)
            start=w.summary()
            for _ in range(ticks):w.tick(**rates)
            results.append({"seed":seed,"scenario":name,"start":start,"final":w.summary()})
    return {"schema":"osixbay.genesis.gple.plant-life-experiment.v1",
            "status":"synthetic_not_canonical",
            "ticks":ticks,"cases":results,
            "limitations":["Aggregate nutrient biomass and individual allocation use proxy material units",
                           "Birth is allocation of parent tissue, not a biologically validated propagule process",
                           "Age, mortality, and reproduction thresholds are arbitrary placeholders",
                           "No heredity, spatial positions, actual seeds, root systems or Godot assets",
                           "Does not claim independent F01 food energy or world integration"]}
