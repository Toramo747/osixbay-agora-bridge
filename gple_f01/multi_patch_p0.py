"""Synthetic connected eco-patches, offline only, no Godot/world deployment.

Conserves abstract biomass globally and a separate proxy water inventory. 
Three linked zones; producers, biofilm, microfauna and nutrient transport.
"""
from dataclasses import asdict
import json
import math
from foodweb_p0 import FoodWeb, State, FIELDS

SCHEMA="osixbay.genesis.gple.ecopatches.v1"
NODES=("forest","shore","rock")
EDGES=(("forest","shore"),("shore","rock"))
PROFILES={
 "forest":{"water":18.0,"light":0.68,"temperature":18.0,"consumers":2},
 "shore":{"water":36.0,"light":0.92,"temperature":20.0,"consumers":3},
 "rock":{"water":6.0,"light":0.95,"temperature":25.0,"consumers":1}
}
def finite_nonnegative(n):
    return isinstance(n,(int,float)) and not isinstance(n,bool) and math.isfinite(n) and n>=0

class PatchNetwork:
    def __init__(self,seed=11,connections=EDGES):
        if not isinstance(seed,int):raise ValueError("seed")
        self.nodes={name:FoodWeb(seed=seed+i*107) for i,name in enumerate(NODES)}
        self.water={n:float(PROFILES[n]["water"]) for n in NODES}
        self.connections=self._validate_connections(connections)
        self.ticks=0
        self.biomass_initial=self.biomass()
        self.water_initial=sum(self.water.values())
        self.flux_events=0
        self.audit()

    @staticmethod
    def _validate_connections(edges):
        if not isinstance(edges,(list,tuple)):raise ValueError("edges")
        result=[]
        for edge in edges:
            if len(edge)!=2 or edge[0] not in NODES or edge[1] not in NODES or edge[0]==edge[1]:
                raise ValueError("bad edge")
            pair=tuple(sorted(edge))
            if pair in result:raise ValueError("duplicate edge")
            result.append(pair)
        return tuple(sorted(result))

    def biomass(self):
        return sum(w.total() for w in self.nodes.values())

    def audit(self):
        for w in self.nodes.values():w.validate()
        if set(self.water)!=set(NODES) or any(not finite_nonnegative(v) for v in self.water.values()):
            raise ValueError("invalid water")
        if not math.isclose(self.biomass(),self.biomass_initial,abs_tol=1e-7,rel_tol=1e-11):
            raise ValueError("biomass imbalance")
        if not math.isclose(sum(self.water.values()),self.water_initial,abs_tol=1e-9,rel_tol=1e-11):
            raise ValueError("water imbalance")

    def _transfer(self,a,b,field,amount):
        if not finite_nonnegative(amount):raise ValueError("flux")
        if field=="water":
            stocks=self.water
        else:
            if field not in ("nutrients","microfauna"):raise ValueError("transport stock")
            stocks=None
        if stocks is not None:
            value=min(stocks[a],amount)
            stocks[a]-=value;stocks[b]+=value
        else:
            value=min(getattr(self.nodes[a].state,field),amount)
            setattr(self.nodes[a].state,field,getattr(self.nodes[a].state,field)-value)
            setattr(self.nodes[b].state,field,getattr(self.nodes[b].state,field)+value)
            # Each FoodWeb audits local conservation; cross-patch exchange updates
            # its accounting baseline, without changing global biomass.
            self.nodes[a].initial_total-=value
            self.nodes[b].initial_total+=value
        if value>0:self.flux_events+=1

    def tick(self,*,override_consumers=None):
        if override_consumers is not None and (not isinstance(override_consumers,int) or not 0<=override_consumers<=20):
            raise ValueError("consumers")
        # Environmental water is a finite proxy stock. Plant metabolism does not
        # consume it yet; there is no rain/evaporation or chemical conservation model.
        for name in NODES:
            profile=PROFILES[name]
            moisture=min(1.0,self.water[name]/(2*profile["water"]))
            self.nodes[name].tick(
                water=moisture, light=profile["light"],
                temperature=profile["temperature"],
                consumers=profile["consumers"] if override_consumers is None else override_consumers)
        # Synchronous gradients: freeze initial values before edge transfers,
        # aggregate signed deltas and then apply conservatively.
        for field,rate in (("water",0.035),("nutrients",0.012),("microfauna",0.009)):
            before={n:self.water[n] if field=="water" else getattr(self.nodes[n].state,field) for n in NODES}
            wants=[]
            for a,b in self.connections:
                gradient=before[a]-before[b]
                if gradient:
                    src,dst=(a,b) if gradient>0 else (b,a)
                    wants.append((src,dst,abs(gradient)*rate))
            outgoing={n:0.0 for n in NODES}
            for src,dst,val in wants:outgoing[src]+=val
            for src,dst,val in wants:
                available=before[src]
                scale=min(1.0,available/outgoing[src]) if outgoing[src]>0 else 0
                self._transfer(src,dst,field,val*scale)
        self.ticks+=1
        self.audit()
        return self.summary()

    def summary(self):
        return {"tick":self.ticks,
                "total_biomass":round(self.biomass(),7),
                "total_water":round(sum(self.water.values()),7),
                "flux_events":self.flux_events,
                "patches":{name:{"water":round(self.water[name],7),
                                 "stocks":self.nodes[name].summary()["stocks"]}
                           for name in NODES}}

    def snapshot(self):
        return json.dumps({"schema":SCHEMA,"ticks":self.ticks,
                           "biomass_initial":self.biomass_initial,
                           "water_initial":self.water_initial,
                           "flux_events":self.flux_events,
                           "water":self.water,"connections":self.connections,
                           "nodes":{n:self.nodes[n].snapshot() for n in NODES}},
                          sort_keys=True,separators=(",",":"))

    @classmethod
    def restore(cls,payload):
        d=json.loads(payload)
        if d.get("schema")!=SCHEMA:raise ValueError("schema")
        x=cls(seed=11,connections=d["connections"])
        if set(d["nodes"])!=set(NODES):raise ValueError("nodes")
        x.nodes={name:FoodWeb.restore(d["nodes"][name]) for name in NODES}
        x.water=d["water"]
        x.ticks=d["ticks"]
        x.biomass_initial=d["biomass_initial"]
        x.water_initial=d["water_initial"]
        x.flux_events=d["flux_events"]
        if not isinstance(x.ticks,int) or x.ticks<0 or not isinstance(x.flux_events,int) or x.flux_events<0:
            raise ValueError("counters")
        x.audit()
        return x

def experiment(seeds=(11,23,37),ticks=500):
    if not seeds or len(seeds)>20 or not 1<=ticks<=5000:raise ValueError("budget")
    cases=[]
    scenarios={"linked":EDGES,"isolated":()}
    for seed in seeds:
        for scenario,links in scenarios.items():
            x=PatchNetwork(seed=seed,connections=links)
            start=x.summary()
            for _ in range(ticks):x.tick()
            cases.append({"seed":seed,"scenario":scenario,
                          "initial":start,"final":x.summary()})
    return {"schema":"osixbay.genesis.gple.ecopatches-experiment.v1",
            "status":"synthetic_connected_patches_not_real_biomes",
            "ticks":ticks,"cases":cases,
            "limitations":["No real Godot masks, elevation or local hydrology",
                           "Water is finite proxy redistributed, not consumed or replenished",
                           "Biomass units are abstract and do not measure calories",
                           "Microfauna stock transported, no individual organism movement",
                           "F01 consumption proxy not integrated with F01 energy/reproduction",
                           "No material chemistry, gas exchange or climate dynamics"]}
