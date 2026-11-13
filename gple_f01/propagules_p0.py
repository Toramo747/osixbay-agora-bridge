"""DM-086: conservative propagule bank, dispersal and germination P0.

Seed mass is escrowed OUTSIDE the existing FoodWeb pools. Both the local
FoodWeb baseline and network baseline are adjusted when material crosses this
boundary; total network biomass + propagules remains conserved. No geometry.
"""
from dataclasses import dataclass,asdict
import json,math
from plant_genetics_p0 import GeneticPlants,GENES
from plant_lifecycle_p0 import Plant,MAX_INDIVIDUALS_PER_PATCH
from multi_patch_p0 import NODES
from foodweb_p0 import PRODUCERS

SCHEMA="osixbay.genesis.gple.propagules-p0.v1"
SEED_LIFETIME=65
GERMINATION_AGE=3
MIN_MOISTURE=0.45
MAX_SEEDS=300
# Counterfactual dispersion parameter; default retains original P0 behavior.
DISPERSAL_PROBABILITY=0.45

@dataclass
class Propagule:
    identity:str
    species:str
    patch:str
    biomass:float
    age:int
    parent_id:str
    genes:dict

class PropaguleWorld:
    def __init__(self,seed=11,connections=None):
        self.genetic=GeneticPlants(seed=seed)
        if connections is not None:
            self.genetic.life.hydro.network.connections=self.genetic.life.hydro.network._validate_connections(connections)
        self.seeds=[]
        self.created=0
        self.germinated=0
        self.expired=0
        self.dispersed=0
        self.original_biomass=self.total_biomass()
        self.audit()

    def total_biomass(self):
        return self.genetic.life.hydro.network.biomass()+sum(s.biomass for s in self.seeds)

    def _transfer(self,patch,field,quantity,into_network):
        if not math.isfinite(quantity) or quantity<0:raise ValueError("invalid quantity")
        net=self.genetic.life.hydro.network
        web=net.nodes[patch]
        if into_network:
            setattr(web.state,field,getattr(web.state,field)+quantity)
            web.initial_total+=quantity
            net.biomass_initial+=quantity
        else:
            if getattr(web.state,field)+1e-10<quantity:raise ValueError("insufficient biomass")
            setattr(web.state,field,getattr(web.state,field)-quantity)
            web.initial_total-=quantity
            net.biomass_initial-=quantity
        web.validate()
        net.audit()

    def audit(self):
        self.genetic.audit()
        if len(self.seeds)>MAX_SEEDS:raise ValueError("seed capacity")
        ids={p.identity for p in self.genetic.life.individuals}
        for seed in self.seeds:
            if seed.identity in ids:raise ValueError("seed/plant collision")
            ids.add(seed.identity)
            if seed.patch not in NODES or seed.species not in PRODUCERS or not seed.parent_id:
                raise ValueError("seed identity")
            if not math.isfinite(seed.biomass) or seed.biomass<=0 or not isinstance(seed.age,int) or seed.age<0:
                raise ValueError("seed mass/age")
            if set(seed.genes)!=set(GENES) or any(not math.isfinite(x) or not .65<=x<=1.35 for x in seed.genes.values()):
                raise ValueError("seed genes")
        if not math.isclose(self.total_biomass(),self.original_biomass,rel_tol=1e-10,abs_tol=1e-7):
            raise ValueError("escrow biomass not conserved")
        if any(not isinstance(v,int) or v<0 for v in (self.created,self.germinated,self.expired,self.dispersed)):
            raise ValueError("counter")

    def _destination(self,origin):
        links=self.genetic.life.hydro.network.connections
        neighbors=sorted(b if a==origin else a for a,b in links if origin in (a,b))
        if neighbors and self.genetic.rng.random()<DISPERSAL_PROBABILITY:
            return neighbors[self.genetic.rng.randrange(len(neighbors))]
        return origin

    def tick(self,**kwargs):
        model=self.genetic
        life=model.life
        before=len(life.events)
        model.tick(**kwargs)
        newborn_events={e["identity"]:e for e in life.events[before:] if e["event"]=="plant_birth"}
        kept=[]
        for plant in life.individuals:
            event=newborn_events.get(plant.identity)
            if event is None or len(self.seeds)>=MAX_SEEDS:
                kept.append(plant)
                continue
            # The newborn was already paid for by its parent. Transfer its mass
            # from producer stock to an escrowed propagule.
            self._transfer(plant.patch,plant.species,plant.biomass,False)
            dest=self._destination(plant.patch)
            if dest!=plant.patch:self.dispersed+=1
            self.seeds.append(Propagule(plant.identity,plant.species,dest,
                                        plant.biomass,0,event["parent_id"],
                                        dict(model.genes.pop(plant.identity))))
            self.created+=1
        life.individuals=kept
        # Germination checks available water, carrying capacity and maturity.
        remaining=[]
        for seed in self.seeds:
            seed.age+=1
            patch=seed.patch
            hydro=life.hydro
            available=hydro.network.water[patch]+hydro.groundwater[patch]
            threshold=MIN_MOISTURE*12/max(.65,seed.genes["drought_tolerance"])
            occupancy=sum(p.patch==patch and p.species==seed.species for p in life.individuals)
            if seed.age>=SEED_LIFETIME:
                self._transfer(patch,"detritus",seed.biomass,True)
                self.expired+=1
            elif seed.age>=GERMINATION_AGE and available>=threshold and occupancy<MAX_INDIVIDUALS_PER_PATCH:
                self._transfer(patch,seed.species,seed.biomass,True)
                life.individuals.append(Plant(seed.identity,patch,seed.species,0,seed.biomass))
                model.genes[seed.identity]=dict(seed.genes)
                self.germinated+=1
            else:remaining.append(seed)
        self.seeds=remaining
        self.audit()
        return self.summary()

    def summary(self):
        return {"tick":self.genetic.life.hydro.network.ticks,
                "alive":len(self.genetic.life.individuals),
                "dormant":len(self.seeds),
                "created":self.created,"germinated":self.germinated,
                "expired":self.expired,"dispersed":self.dispersed,
                "total_biomass":round(self.total_biomass(),8),
                "total_water":round(self.genetic.life.hydro.total_water(),8)}

    def snapshot(self):
        return json.dumps({"schema":SCHEMA,"genetic":self.genetic.snapshot(),
                           "seeds":[asdict(s) for s in self.seeds],
                           "created":self.created,"germinated":self.germinated,
                           "expired":self.expired,"dispersed":self.dispersed,
                           "original_biomass":self.original_biomass},
                          sort_keys=True,separators=(",",":"))

    @classmethod
    def restore(cls,payload):
        d=json.loads(payload)
        if d.get("schema")!=SCHEMA:raise ValueError("schema")
        obj=object.__new__(cls)
        obj.genetic=GeneticPlants.restore(d["genetic"])
        obj.seeds=[Propagule(**s) for s in d["seeds"]]
        obj.created=d["created"];obj.germinated=d["germinated"]
        obj.expired=d["expired"];obj.dispersed=d["dispersed"]
        obj.original_biomass=d["original_biomass"]
        obj.audit()
        return obj

def experiment(seeds=(11,23,37),ticks=300):
    if not seeds or len(seeds)>20 or not 1<=ticks<=5000:raise ValueError("budget")
    results=[]
    for seed in seeds:
        for label,rates in {
            "normal":{"rain_rate":.14,"evaporation_rate":.035},
            "drought":{"rain_rate":0,"evaporation_rate":.09},
            "wet":{"rain_rate":.5,"evaporation_rate":.015}}.items():
            world=PropaguleWorld(seed=seed)
            for _ in range(ticks):world.tick(**rates)
            results.append({"seed":seed,"scenario":label,"final":world.summary()})
    return {"schema":"osixbay.genesis.gple.propagule-experiment.v1",
            "status":"synthetic_not_canonical","ticks":ticks,"cases":results,
            "limitations":["No real seeds, pollen, dispersal vectors, position or Godot scene",
                           "Seed mass is escrowed from living tissue, no material creation",
                           "Patch-level moisture only, no local germination microclimate",
                           "Artificial maturation and viability thresholds"]}
