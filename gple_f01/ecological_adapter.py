"""F01 ecological adapter, experimental and offline only.

Uses original PR88 World/Organism/Parameters and RNG. Adds local water,
temperature, humidity and finite food pools. Does NOT replace original engine.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import json
import math
from biome_search import load_f01, synthetic_map, HABITATS

BIOME_FOOD={"alien_forest":("biofilm","soft_biomass"),
            "wet_shore":("biofilm","microfauna"),
            "mineral_outcrop":("biofilm",)}
DEFAULTS={
    "alien_forest":(18.0,0.78,0.10,0.85),
    "wet_shore":(20.0,0.90,0.35,0.96),
    "mineral_outcrop":(25.0,0.34,0.00,0.42)
}
@dataclass
class Environment:
    biome: str
    playable: bool
    water_depth: float
    humidity: float
    temperature: float
    capacity: float
    regrowth: float
    food: float
    danger: float
    water_access: bool

class EcoF01:
    """Deterministic experimental proxy with World authoritative tick semantics."""
    def __init__(self,f01,variant,seed=11,width=12,mask=None,labels=None,water_access=True):
        if mask is None or labels is None:
            mask,labels=synthetic_map(seed,variant,width=width)
        if len(mask)!=len(labels) or not mask or any(len(a)!=len(b) for a,b in zip(mask,labels)):
            raise ValueError("incompatible map")
        self.f01=f01
        self.world=f01.World(mask,seed=seed)
        self.env=[]
        self.drinking=bool(water_access)
        for y,row in enumerate(mask):
            er=[]
            for x,playable in enumerate(row):
                biome=labels[y][x]
                if biome not in DEFAULTS:raise ValueError("unknown biome")
                temp,humid,water,resource=DEFAULTS[biome]
                capacity=variant["food_capacity"]*resource if playable else 0.0
                er.append(Environment(biome,bool(playable),water,humid,temp,capacity,
                                      variant["regrowth"]*resource if playable else 0.0,
                                      capacity,min(1.0,variant["hazard"]),bool(water_access and water>0)))
            self.env.append(er)
        self.hydration={}
        self.events={"births":0,"deaths":0,"eaten":0.0,"grown":0.0,"hydration_deaths":0}
        self._assert_invariants()

    def spawn(self,n=8):
        points=[(x,y) for y,row in enumerate(self.env) for x,c in enumerate(row) if c.playable]
        if not points:raise ValueError("no available spawn cells")
        if n<1 or n>len(points) or n>self.world.parameters.max_population:raise ValueError("spawn out of bounds")
        for x,y in points[:n]:
            creature=self.world.add_organism(x,y)
            self.hydration[creature.identity]=1.0

    def _assert_invariants(self):
        p=self.world.parameters
        ids=[a.identity for a in self.world.organisms]
        if len(ids)!=len(set(ids)):raise ValueError("duplicate IDs")
        if set(ids)!=set(self.hydration):raise ValueError("hydration/organism state mismatch")
        if len(ids)>p.max_population:raise ValueError("population cap")
        for a in self.world.organisms:
            if not 0<=a.x<self.world.width or not 0<=a.y<self.world.height:
                raise ValueError("out of bounds")
            if not self.env[a.y][a.x].playable or not 0<a.energy<=p.energy_cap:
                raise ValueError("invalid organism state")
            if not 0<=self.hydration[a.identity]<=1:raise ValueError("hydration bounds")
        for row in self.env:
            for c in row:
                if not all(math.isfinite(v) for v in (c.food,c.capacity,c.regrowth,c.temperature,c.humidity,c.water_depth)):
                    raise ValueError("nonfinite eco data")
                if not 0<=c.food<=c.capacity or c.regrowth<0:raise ValueError("resource conservation")

    def _adjacent(self,a):
        points=[(a.x,a.y),(a.x+1,a.y),(a.x-1,a.y),(a.x,a.y+1),(a.x,a.y-1)]
        return [(x,y) for x,y in points if 0<=x<self.world.width and 0<=y<self.world.height
                and self.env[y][x].playable]

    def step(self):
        p=self.world.parameters
        born=[]; survivors=[]; deaths=0
        for a in sorted(self.world.organisms,key=lambda v:v.identity):
            a.age+=1
            a.cooldown=max(0,a.cooldown-1)
            e=self.env[a.y][a.x]
            climate_stress=max(0,abs(e.temperature-20.0)-6.0)*0.045 + max(0,0.42-e.humidity)*0.20
            a.energy-=p.basal_cost+climate_stress
            hydration=self.hydration[a.identity]-0.022-0.024*(1-e.humidity)
            if e.water_access:
                hydration=min(1.0,hydration+0.16)
            hydration=max(0.0,hydration)
            self.hydration[a.identity]=hydration
            if hydration<=0:
                deaths+=1;self.events["hydration_deaths"]+=1;continue
            if a.energy<=0 or a.age>=p.max_age:
                deaths+=1;continue
            near=self._adjacent(a)
            if e.danger>0.5:
                x,y=min(near,key=lambda q:(self.env[q[1]][q[0]].danger,-self.env[q[1]][q[0]].food,q[1],q[0]))
                a.last_action="flee"
            elif hydration<0.5 and self.drinking:
                x,y=max(near,key=lambda q:(int(self.env[q[1]][q[0]].water_access),
                                            self.env[q[1]][q[0]].food,-q[1],-q[0]))
                a.last_action="seek_water"
            elif a.energy<a.threshold:
                x,y=max(near,key=lambda q:(self.env[q[1]][q[0]].food,-q[1],-q[0]))
                a.last_action="forage"
            else:
                x,y=a.x,a.y;a.last_action="rest"
            if (x,y)!=(a.x,a.y):
                a.energy-=p.movement_cost
                a.x,a.y=x,y
            target=self.env[a.y][a.x]
            if target.water_access and self.drinking:
                self.hydration[a.identity]=min(1.0,self.hydration[a.identity]+0.18)
            if a.energy<=0:
                deaths+=1;continue
            if a.last_action in ("forage","seek_water"):
                eaten=min(p.food_per_tick,target.food)
                target.food-=eaten
                a.energy=min(p.energy_cap,a.energy+eaten*p.food_energy*a.efficiency)
                self.events["eaten"]+=eaten
            if a.energy>=p.birth_threshold and a.cooldown==0 and self.hydration[a.identity]>=0.65 and (
                    len(self.world.organisms)-deaths+len(born)<p.max_population):
                a.energy-=p.child_energy+p.birth_cost
                a.cooldown=p.cooldown;a.last_action="reproduce"
                threshold=min(18,max(2,a.threshold+self.world.random()-0.5))
                efficiency=min(1.5,max(0.5,a.efficiency+(self.world.random()-0.5)*0.1))
                child=self.f01.Organism(self.world.next_id,a.x,a.y,p.child_energy,
                                         threshold=threshold,efficiency=efficiency)
                self.world.next_id+=1
                born.append(child)
                self.hydration[child.identity]=0.80
            survivors.append(a)
        self.world.organisms=survivors+born
        self.hydration={a.identity:self.hydration[a.identity] for a in self.world.organisms}
        self.events["births"]+=len(born);self.events["deaths"]+=deaths
        for row in self.env:
            for c in row:
                if not c.playable:continue
                gain=min(c.regrowth,c.capacity-c.food)
                c.food+=gain;self.events["grown"]+=gain
        self.world.ticks+=1
        self._assert_invariants()
        return {"tick":self.world.ticks,"alive":len(self.world.organisms),
                "born":len(born),"died":deaths}

    def snapshot(self):
        return json.dumps({"schema":"gple.eco-f01.experimental.v1",
                           "world":self.world.snapshot(),"env":[[asdict(c) for c in row] for row in self.env],
                           "hydration":self.hydration,"events":self.events,"drinking":self.drinking},
                          sort_keys=True,separators=(",",":"))

    @classmethod
    def from_snapshot(cls,f01,source):
        d=json.loads(source)
        if d.get("schema")!="gple.eco-f01.experimental.v1":raise ValueError("invalid adapter snapshot")
        instance=object.__new__(cls)
        instance.f01=f01
        instance.world=f01.World.from_snapshot(d["world"])
        instance.env=[[Environment(**c) for c in row] for row in d["env"]]
        if len(instance.env)!=instance.world.height or any(len(row)!=instance.world.width for row in instance.env):
            raise ValueError("bad ecological snapshot dimensions")
        instance.hydration={int(k):v for k,v in d["hydration"].items()}
        instance.events=d["events"]
        instance.drinking=d["drinking"]
        instance._assert_invariants()
        return instance

def trial(original,variant,seed=11,ticks=120,water_access=True):
    if not 1<=ticks<=10000:raise ValueError("invalid ticks")
    f01=load_f01(original)
    eco=EcoF01(f01,variant,seed=seed,water_access=water_access)
    eco.spawn(8)
    peak=8
    for _ in range(ticks):
        result=eco.step()
        peak=max(peak,result["alive"])
    return {"seed":seed,"alive":len(eco.world.organisms),
            "peak":peak,"max_population":eco.world.parameters.max_population,
            "births":eco.events["births"],"deaths":eco.events["deaths"],
            "hydration_deaths":eco.events["hydration_deaths"],
            "consumed":round(eco.events["eaten"],5),
            "regrown":round(eco.events["grown"],5),
            "remaining_food":round(sum(c.food for row in eco.env for c in row),5)}

def compare(original,variants,seeds=(11,23,37,53,71),ticks=120):
    out=[]
    for variant in variants:
        runs=[trial(original,variant,seed,ticks) for seed in seeds]
        out.append({"candidate":variant["id"],"trials":runs,
                    "extinction_rate":sum(v["alive"]==0 for v in runs)/len(runs),
                    "mean_survivors":round(sum(v["alive"] for v in runs)/len(runs),3),
                    "cap_hit_rate":sum(v["peak"]>=v["max_population"] for v in runs)/len(runs)})
    return {"schema":"osixbay.gple.ecological-comparison.v1",
            "status":"synthetic_parameter_experiment_only",
            "source_world_mask_imported":False,
            "biome_physiology":"experimental proxy, not approved F01 biology",
            "caveats":["Original F01 rules preserved as source reference but adapter changes tick physiology",
                       "No canonical real terrain, chemistry, stage-based life cycle or material chemistry"],
            "results":out}
