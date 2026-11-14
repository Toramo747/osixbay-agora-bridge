"""DM-085: synthetic heritable producer traits, no canonical biological claims.

Composition over the existing conservative plant life and hydrology engines.
Genes alter post-growth survival costs and reproductive cooldown. All costs
move biomass to detritus. Birth inherits parent traits with bounded mutations.
"""
import json, math, random
from plant_lifecycle_p0 import PlantLifecycle
from multi_patch_p0 import NODES
from foodweb_p0 import PRODUCERS

SCHEMA="osixbay.genesis.gple.plant-genetics-p0.v1"
GENES=("drought_tolerance","heat_tolerance","growth_efficiency","reproduction_cost")
BOUNDS=(0.65,1.35)
BASE={"drought_tolerance":1.0,"heat_tolerance":1.0,
      "growth_efficiency":1.0,"reproduction_cost":1.0}
MUTATION_PROBABILITY=0.30
MUTATION_AMPLITUDE=0.07

class GeneticPlants:
    def __init__(self,seed=11,dry_start=False,mutation_probability=MUTATION_PROBABILITY):
        if not isinstance(seed,int) or isinstance(seed,bool):raise ValueError("seed")
        if not isinstance(mutation_probability,(float,int)) or isinstance(mutation_probability,bool) or not 0<=mutation_probability<=1:raise ValueError("mutation probability")
        self.life=PlantLifecycle(seed=seed,dry_start=dry_start)
        self.rng=random.Random(seed+100009)
        self.mutation_probability=mutation_probability
        self.genes={p.identity:dict(BASE) for p in self.life.individuals}
        self.mutations=0
        self.selection_deaths=0
        self.audit()

    def audit(self):
        self.life.audit()
        if set(self.genes)!={p.identity for p in self.life.individuals}:
            raise ValueError("gene/plant identity mismatch")
        for g in self.genes.values():
            if set(g)!=set(GENES) or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) or not BOUNDS[0]<=x<=BOUNDS[1] for x in g.values()):
                raise ValueError("invalid genotype")
        if not isinstance(self.mutations,int) or self.mutations<0 or not isinstance(self.selection_deaths,int) or self.selection_deaths<0:
            raise ValueError("invalid counters")

    def _mutate(self,parent):
        child=dict(parent)
        for name in GENES:
            if self.rng.random()<self.mutation_probability:
                delta=self.rng.uniform(-MUTATION_AMPLITUDE,MUTATION_AMPLITUDE)
                child[name]=round(max(BOUNDS[0],min(BOUNDS[1],parent[name]+delta)),8)
                if child[name]!=parent[name]:self.mutations+=1
        return child

    def tick(self,**kwargs):
        start_events=len(self.life.events)
        self.life.tick(**kwargs)
        births=[e for e in self.life.events[start_events:] if e["event"]=="plant_birth"]
        # Record parent genotypes before any post-birth stress death.
        for event in births:
            parent_id=event["parent_id"]
            if parent_id not in self.genes:raise ValueError("parent missing")
            self.genes[event["identity"]]=self._mutate(self.genes[parent_id])
        alive={p.identity for p in self.life.individuals}
        self.genes={pid:g for pid,g in self.genes.items() if pid in alive}
        survivors=[]
        for p in self.life.individuals:
            gene=self.genes[p.identity]
            hydro=self.life.hydro
            surface=hydro.network.water[p.patch]
            tissue=sum(hydro.producer_water[p.patch].values())
            # Synthetic environmental stress. Baseline threshold is independent
            # of producer biomass; no physical units or real-world fit implied.
            moisture=min(1.0,(surface+tissue)/12.0)
            temperature={"forest":18.0,"shore":20.0,"rock":25.0}[p.patch]
            heat=max(0.0,(temperature-20.0)/15.0)
            drought=max(0.0,1.0-moisture)
            # More tolerant individuals lose less material under stress.
            stress=0.007*drought/gene["drought_tolerance"]+0.004*heat/gene["heat_tolerance"]
            stress*=2.0-gene["growth_efficiency"]
            loss=min(p.biomass,p.biomass*stress)
            if loss>0:
                moved=hydro.network.nodes[p.patch].move(p.species,"detritus",loss,"genetic_stress")
                p.biomass-=moved
            # Reproduction cost changes delay but does not mint biomass.
            if p.cooldown>0 and gene["reproduction_cost"]>1:
                p.cooldown+=int((gene["reproduction_cost"]-1)*2)
            if p.biomass<=0.035:
                hydro.network.nodes[p.patch].move(p.species,"detritus",p.biomass,"genetic_selection_death")
                self.life.counts["deaths"]+=1
                self.selection_deaths+=1
                self.life._event("plant_death",p,p.biomass)
                del self.genes[p.identity]
            else:survivors.append(p)
        self.life.individuals=survivors
        self.audit()
        return self.summary()

    def summary(self):
        counts={s:[self.genes[p.identity] for p in self.life.individuals if p.species==s] for s in PRODUCERS}
        return {"tick":self.life.hydro.network.ticks,"alive":len(self.life.individuals),
                "births":self.life.counts["births"],"deaths":self.life.counts["deaths"],
                "mutations":self.mutations,"selection_deaths":self.selection_deaths,
                "mean_genes":{s:({g:round(sum(p[g] for p in entries)/len(entries),6) for g in GENES}
                                   if entries else None) for s,entries in counts.items()},
                "total_biomass":round(self.life.hydro.network.biomass(),8),
                "total_water":round(self.life.hydro.total_water(),8)}

    def snapshot(self):
        return json.dumps({"schema":SCHEMA,"life":self.life.snapshot(),
                           "genes":self.genes,"rng_state":repr(self.rng.getstate()),
                           "mutation_probability":self.mutation_probability,
                           "mutations":self.mutations,
                           "selection_deaths":self.selection_deaths},
                          sort_keys=True,separators=(",",":"))

    @classmethod
    def restore(cls,payload):
        import ast
        d=json.loads(payload)
        if d.get("schema")!=SCHEMA:raise ValueError("schema")
        obj=object.__new__(cls)
        obj.life=PlantLifecycle.restore(d["life"])
        obj.genes=d["genes"]
        obj.mutation_probability=d["mutation_probability"]
        obj.mutations=d["mutations"]
        obj.selection_deaths=d["selection_deaths"]
        obj.rng=random.Random()
        state=ast.literal_eval(d["rng_state"])
        obj.rng.setstate(state)
        obj.audit()
        return obj

def experiment(seeds=(11,23,37),ticks=350):
    cases=[]
    for seed in seeds:
        for scenario,rates in {
            "normal":{"rain_rate":0.14,"evaporation_rate":0.035},
            "drought":{"rain_rate":0.0,"evaporation_rate":0.09},
            "wet":{"rain_rate":0.5,"evaporation_rate":0.015}}.items():
            model=GeneticPlants(seed=seed)
            for _ in range(ticks):model.tick(**rates)
            cases.append({"seed":seed,"scenario":scenario,"final":model.summary()})
    return {"schema":"osixbay.genesis.gple.plant-genetics-experiment.v1",
            "status":"experimental_not_canonical",
            "cases":cases,"ticks":ticks,
            "limitations":["Genes are artificial numerical traits, not molecular DNA",
                           "Reproduction still splits parental tissue; no propagules or dispersal",
                           "Growth efficiency currently scales stress cost, not direct photosynthesis",
                           "No individual plant water allocation, real-world climate or Godot assets"]}
