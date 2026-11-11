"""DM-087 experimental microfauna individuals on conservative patch stocks.

Microfauna FoodWeb stock remains authoritative. Individuals share its biomass.
Birth splits a parent, movement transfers material only on network edges,
death transfers material to detritus. No positions or Godot animation.
"""
from dataclasses import dataclass,asdict
import json,math
from propagules_p0 import PropaguleWorld
from multi_patch_p0 import NODES

SCHEMA="osixbay.genesis.gple.microfauna-individuals.v1"
MAX_PER_PATCH=40
MIN_MASS=.018

@dataclass
class Micro:
    identity:str
    patch:str
    age:int
    mass:float
    cooldown:int=0

class MicroWorld:
    def __init__(self,seed=11,connections=None):
        self.world=PropaguleWorld(seed=seed,connections=connections)
        self.micro=[]
        self.next_id=1
        self.births=0;self.deaths=0;self.moves=0
        for patch in NODES:self._new(patch,2.0,age=5)
        self.audit()

    def _new(self,patch,mass,age=0):
        pid=f"m{self.next_id:07d}";self.next_id+=1
        self.micro.append(Micro(pid,patch,age,mass))
        return pid

    def _web(self,patch):
        return self.world.genetic.life.hydro.network.nodes[patch]

    def audit(self):
        self.world.audit()
        ids=[m.identity for m in self.micro]
        if len(set(ids))!=len(ids):raise ValueError("duplicate micro IDs")
        for m in self.micro:
            if m.patch not in NODES or not isinstance(m.age,int) or m.age<0 or not isinstance(m.cooldown,int) or m.cooldown<0 or not math.isfinite(m.mass) or m.mass<=0:
                raise ValueError("invalid micro")
        for patch in NODES:
            group=[m for m in self.micro if m.patch==patch]
            if len(group)>MAX_PER_PATCH:raise ValueError("overcrowding")
            if not math.isclose(sum(m.mass for m in group),self._web(patch).state.microfauna,rel_tol=1e-10,abs_tol=1e-7):
                raise ValueError("micro stock mismatch")

    def _move(self,m,dest):
        net=self.world.genetic.life.hydro.network
        if tuple(sorted((m.patch,dest))) not in net.connections:raise ValueError("unlinked movement")
        src=self._web(m.patch);dst=self._web(dest)
        if src.state.microfauna+1e-9<m.mass:raise ValueError("insufficient source")
        src.state.microfauna-=m.mass;dst.state.microfauna+=m.mass
        src.initial_total-=m.mass;dst.initial_total+=m.mass
        m.patch=dest
        self.moves+=1

    def tick(self,**kwargs):
        self.world.tick(**kwargs)
        net=self.world.genetic.life.hydro.network
        rng=self.world.genetic.rng
        # Existing foodweb eats biofilm and turns over microfauna. Reconcile
        # the resulting aggregate stock before assigning individual events.
        for patch in NODES:
            group=[m for m in self.micro if m.patch==patch]
            stock=self._web(patch).state.microfauna
            total=sum(m.mass for m in group)
            if not group:
                if stock>0:self._web(patch).move("microfauna","detritus",stock,"unowned_micro_decay")
            else:
                for m in group:m.mass*=stock/total
        kept=[]
        for m in sorted(self.micro,key=lambda x:x.identity):
            m.age+=1;m.cooldown=max(0,m.cooldown-1)
            if m.age>=110 or m.mass<MIN_MASS:
                self._web(m.patch).move("microfauna","detritus",m.mass,"micro_death")
                self.deaths+=1
                continue
            kept.append(m)
        self.micro=kept
        # Movement is conservative, limited to explicit edges and patch capacity.
        for m in sorted(list(self.micro),key=lambda x:x.identity):
            if rng.random()>=.035:continue
            options=sorted(b if a==m.patch else a for a,b in net.connections if m.patch in (a,b))
            options=[p for p in options if sum(x.patch==p for x in self.micro)<MAX_PER_PATCH]
            if options:self._move(m,options[rng.randrange(len(options))])
        # Birth only redistributes parent material; no ex-nihilo microfauna.
        newborn=[]
        for m in sorted(self.micro,key=lambda x:x.identity):
            occupancy=sum(x.patch==m.patch for x in self.micro+newborn)
            if m.age>=6 and m.cooldown==0 and m.mass>=1.5 and occupancy<MAX_PER_PATCH:
                child_mass=m.mass*.23
                m.mass-=child_mass;m.cooldown=16
                pid=f"m{self.next_id:07d}";self.next_id+=1
                newborn.append(Micro(pid,m.patch,0,child_mass))
                self.births+=1
        self.micro.extend(newborn)
        self.audit()
        return self.summary()

    def summary(self):
        return {"tick":self.world.genetic.life.hydro.network.ticks,
                "individuals":len(self.micro),"births":self.births,
                "deaths":self.deaths,"moves":self.moves,
                "by_patch":{p:sum(m.patch==p for m in self.micro) for p in NODES},
                "biomass":round(self.world.total_biomass(),8),
                "water":round(self.world.genetic.life.hydro.total_water(),8)}

    def snapshot(self):
        return json.dumps({"schema":SCHEMA,"world":self.world.snapshot(),
                           "micro":[asdict(m) for m in self.micro],
                           "next_id":self.next_id,"births":self.births,
                           "deaths":self.deaths,"moves":self.moves},
                          sort_keys=True,separators=(",",":"))

    @classmethod
    def restore(cls,payload):
        d=json.loads(payload)
        if d.get("schema")!=SCHEMA:raise ValueError("schema")
        x=object.__new__(cls)
        x.world=PropaguleWorld.restore(d["world"])
        x.micro=[Micro(**m) for m in d["micro"]]
        x.next_id=d["next_id"];x.births=d["births"]
        x.deaths=d["deaths"];x.moves=d["moves"]
        if any(not isinstance(n,int) or n<0 for n in (x.next_id,x.births,x.deaths,x.moves)):raise ValueError("counters")
        x.audit()
        return x

def experiment(seeds=(11,23,37),ticks=240):
    if not seeds or len(seeds)>20 or not 1<=ticks<=5000:raise ValueError("budget")
    cases=[]
    for seed in seeds:
        for name,rates in {"normal":{"rain_rate":.14},"drought":{"rain_rate":0,"evaporation_rate":.09}}.items():
            w=MicroWorld(seed=seed)
            for _ in range(ticks):w.tick(**rates)
            cases.append({"seed":seed,"scenario":name,"final":w.summary()})
    return {"schema":"osixbay.genesis.gple.microfauna-experiment.v1","ticks":ticks,
            "status":"synthetic_not_canonical","cases":cases,
            "limitations":["Microfauna is aggregate material allocated to individuals",
                           "No per-organism position, energy, genome or animation",
                           "Foodweb already consumes biofilm and F01 proxy; no double feeding",
                           "Age, reproduction and migration are arbitrary placeholders"]}
