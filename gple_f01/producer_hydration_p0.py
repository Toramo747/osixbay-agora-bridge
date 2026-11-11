"""Experimental water uptake and transpiration for PROD-A / PROD-B.

Offline 3-patch synthetic abstraction. Conserves water across surface, soil,
atmosphere and producer tissue (all arbitrary units). Producer hydration limits
only biomass growth, not fruiting from existing biomass.
"""
import json
import math
from hydrology_p0 import Hydrology
from multi_patch_p0 import PatchNetwork, NODES, PROFILES, finite_nonnegative

SCHEMA="osixbay.genesis.gple.producer-hydration.v1"
PLANTS=("producer_a","producer_b")

class ProducerHydrology(Hydrology):
    def __init__(self,seed=11,connections=None,dry_start=False):
        self.producer_water={name:{p:0.0 for p in PLANTS} for name in NODES}
        self.uptake_total=0.0
        self.transpiration_total=0.0
        if connections is None:
            super().__init__(seed=seed)
        else:
            super().__init__(seed=seed,connections=connections)
        if dry_start:
            self.network.water={name:0.0 for name in NODES}
            self.network.water_initial=0.0
            self.initial_water=0.0
        self.audit()

    def total_water(self):
        return super().total_water()+sum(v for water in self.producer_water.values() for v in water.values())

    def audit(self):
        if set(self.producer_water)!=set(NODES) or any(
                set(stocks)!=set(PLANTS) or any(not finite_nonnegative(v) for v in stocks.values())
                for stocks in self.producer_water.values()):
            raise ValueError("invalid producer hydration stocks")
        if not finite_nonnegative(self.uptake_total) or not finite_nonnegative(self.transpiration_total):
            raise ValueError("invalid hydration ledger")
        super().audit()

    def tick(self,*,rain_rate=0.14,evaporation_rate=0.035,
             infiltration_rate=0.025,discharge_rate=0.018,
             override_consumers=None):
        rates=(rain_rate,evaporation_rate,infiltration_rate,discharge_rate)
        if any(not isinstance(v,(int,float)) or isinstance(v,bool)
               or not math.isfinite(v) or not 0<=v<=1 for v in rates):
            raise ValueError("invalid rates")
        hydration={}
        for name in NODES:
            state=self.network.nodes[name].state
            # Saturation requirement is experimental; shares water fairly if scarce.
            demand={p:0.02+0.015*getattr(state,p) for p in PLANTS}
            capacity={p:0.2+0.04*getattr(state,p) for p in PLANTS}
            desired={p:min(demand[p],max(0.0,capacity[p]-self.producer_water[name][p])) for p in PLANTS}
            total_desired=sum(desired.values())
            supply=self.network.water[name]
            proportion=min(1.0,supply/total_desired) if total_desired else 0.0
            for p in PLANTS:
                amount=desired[p]*proportion
                self.network.water[name]-=amount
                self.producer_water[name][p]+=amount
                self.uptake_total+=amount
            # Existing stores can buffer drought, but are NOT a perpetual source.
            hydration[name]=min(1.0,min(
                self.producer_water[name][p]/demand[p] for p in PLANTS))
        # Explicitly transfer water inventory out of PatchNetwork before base
        # hydrology ticks. It still conserves the whole water system via total_water.
        self.network.water_initial=sum(self.network.water.values())
        super().tick(rain_rate=rain_rate,evaporation_rate=evaporation_rate,
                     infiltration_rate=infiltration_rate,discharge_rate=discharge_rate,
                     override_consumers=override_consumers,
                     producer_water_by_patch=hydration)
        # Return tissue water to atmosphere: actual flow, not deletion.
        for name in NODES:
            for p in PLANTS:
                amount=self.producer_water[name][p]*0.18
                self.producer_water[name][p]-=amount
                self.atmosphere+=amount
                self.transpiration_total+=amount
        self.audit()
        return self.summary()

    def summary(self):
        out=super().summary()
        out["producer_water"]={name:{p:round(x,8) for p,x in stocks.items()}
                               for name,stocks in self.producer_water.items()}
        out["uptake_total"]=round(self.uptake_total,8)
        out["transpiration_total"]=round(self.transpiration_total,8)
        return out

    def snapshot(self):
        return json.dumps({
            "schema":SCHEMA,
            "network":self.network.snapshot(),
            "groundwater":self.groundwater,"atmosphere":self.atmosphere,
            "initial_water":self.initial_water,"events":self.events,
            "producer_water":self.producer_water,
            "uptake_total":self.uptake_total,
            "transpiration_total":self.transpiration_total,
        },sort_keys=True,separators=(",",":"))

    @classmethod
    def restore(cls,payload):
        d=json.loads(payload)
        if d.get("schema")!=SCHEMA:raise ValueError("schema")
        obj=object.__new__(cls)
        obj.network=PatchNetwork.restore(d["network"])
        obj.groundwater=d["groundwater"]
        obj.atmosphere=d["atmosphere"]
        obj.initial_water=d["initial_water"]
        obj.events=d["events"]
        obj.producer_water=d["producer_water"]
        obj.uptake_total=d["uptake_total"]
        obj.transpiration_total=d["transpiration_total"]
        if (not isinstance(obj.events.get("ledger_ticks"),int)
                or obj.events["ledger_ticks"]!=obj.network.ticks):
            raise ValueError("tick mismatch")
        obj.audit()
        return obj

def experiment(seeds=(11,23,37),ticks=400):
    if not seeds or len(seeds)>20 or not 1<=ticks<=5000:raise ValueError("budget")
    settings={
        "baseline":{"rain_rate":0.14,"evaporation_rate":0.035},
        "drought":{"rain_rate":0.0,"evaporation_rate":0.09},
        "wet":{"rain_rate":0.5,"evaporation_rate":0.015},
    }
    result=[]
    for seed in seeds:
        for name,rates in settings.items():
            x=ProducerHydrology(seed=seed)
            start=x.summary()
            for _ in range(ticks):x.tick(**rates)
            result.append({"scenario":name,"seed":seed,"initial":start,
                           "final":x.summary()})
    return {
        "schema":"osixbay.genesis.gple.producer-water-experiment.v1",
        "status":"synthetic_only_not_canonical",
        "ticks":ticks,"cases":result,
        "limitations":["Arbitrary water stock units, not liters",
                       "Plant requirements not experimentally validated",
                       "Only biomass growth is gated: fruiting can continue on existing biomass",
                       "No F01 drinking, biology or Godot integration",
                       "No root geometry, real soil or rainfall forcing"]}
