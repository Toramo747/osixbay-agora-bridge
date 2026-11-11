"""Minimal closed-material F01 food web, ONE SYNTHETIC PATCH.

All material is in abstract equal-mass units; solar energy is external but
physical biochemistry, breathing and water stocks are not yet modeled.
This does not modify the original PR88 F01 simulator.
"""
from dataclasses import dataclass,asdict
import json
import math
import random

FIELDS=("nutrients","producer_a","producer_b","fruit_a","fruit_b","biofilm",
        "microfauna","detritus","f01_reserve")
PRODUCERS=("producer_a","producer_b")
@dataclass
class State:
    nutrients:float=60.0
    producer_a:float=8.0
    producer_b:float=8.0
    fruit_a:float=0.0
    fruit_b:float=0.0
    biofilm:float=4.0
    microfauna:float=2.0
    detritus:float=8.0
    f01_reserve:float=0.0

class FoodWeb:
    def __init__(self,seed=1,state=None):
        if not isinstance(seed,int):raise ValueError("bad seed")
        self.rng=random.Random(seed)
        self.growth_bias=0.85+0.3*self.rng.random() # seed-specific, bounded synthetic productivity
        self.state=state if state is not None else State()
        self.ticks=0
        self.events=[]
        self.validate()
        self.initial_total=self.total()

    def total(self):
        return sum(getattr(self.state,k) for k in FIELDS)

    def validate(self):
        for key in FIELDS:
            v=getattr(self.state,key)
            if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v<0:
                raise ValueError("bad material stock: "+key)

    def move(self,source,target,amount,event):
        if source not in FIELDS or target not in FIELDS or source==target:
            raise ValueError("invalid transfer")
        if not isinstance(amount,(float,int)) or not math.isfinite(amount) or amount<0:
            raise ValueError("invalid amount")
        v=min(getattr(self.state,source),amount)
        if v:
            setattr(self.state,source,max(0,getattr(self.state,source)-v))
            setattr(self.state,target,getattr(self.state,target)+v)
            self.events.append({"tick":self.ticks,"event":event,"source":source,
                                "target":target,"quantity":round(v,8)})
        return v

    def tick(self,*,water=1.0,light=1.0,temperature=20.0,consumers=1):
        if not (isinstance(water,(int,float)) and isinstance(light,(int,float))
                and isinstance(temperature,(int,float))
                and all(math.isfinite(x) for x in (water,light,temperature))
                and 0<=water<=1 and 0<=light<=1
                and isinstance(consumers,int) and 0<=consumers<=100):
            raise ValueError("invalid environment")
        self.ticks+=1
        # These are PROPOSED rates, not validated physiology. No genesis ex nihilo:
        # growth draws from nutrient stock; the light/water factors only limit rate.
        suitability=max(0,1-abs(temperature-20)/20)
        for name,rate in (("producer_a",0.33),("producer_b",0.24),("biofilm",0.18)):
            self.move("nutrients",name,rate*water*light*suitability*self.growth_bias,"growth_"+name)
        for name,fruit in (("producer_a","fruit_a"),("producer_b","fruit_b")):
            self.move(name,fruit,getattr(self.state,name)*0.055,"fruiting_"+name)
        self.move("biofilm","microfauna",min(0.16,self.state.microfauna*0.05+0.03),"microfauna_feed")
        self.move("microfauna","detritus",self.state.microfauna*0.018,"microfauna_turnover")
        self.move("producer_a","detritus",self.state.producer_a*0.012,"producer_a_turnover")
        self.move("producer_b","detritus",self.state.producer_b*0.012,"producer_b_turnover")
        for i in range(consumers):
            # No material is consumed if stock is zero; food enters proxy F01 reserves.
            options=("fruit_a","fruit_b","biofilm","microfauna")
            available=[k for k in options if getattr(self.state,k)>0]
            if not available:break
            selected=max(available,key=lambda k:(getattr(self.state,k),-options.index(k)))
            self.move(selected,"f01_reserve",0.14,"f01_consumption")
        # Return fraction of reserve to detritus, distinct from organism energy.
        self.move("f01_reserve","detritus",self.state.f01_reserve*0.035,"f01_waste_proxy")
        self.move("detritus","nutrients",min(0.24,self.state.detritus*0.025),"decomposition")
        self.validate()
        if not math.isclose(self.total(),self.initial_total,rel_tol=1e-11,abs_tol=1e-8):
            raise AssertionError("total material changed")
        return self.summary()

    def summary(self):
        return {"tick":self.ticks,"material_total":round(self.total(),8),
                "stocks":{k:round(getattr(self.state,k),8) for k in FIELDS},
                "event_count":len(self.events)}

    def snapshot(self):
        return json.dumps({"schema":"osixbay.gple.f01.foodweb.p0.v1","ticks":self.ticks,
                           "state":asdict(self.state),"initial_total":self.initial_total,
                           "growth_bias":self.growth_bias,"events":self.events},
                          sort_keys=True,separators=(",",":"))

    @classmethod
    def restore(cls,snapshot):
        data=json.loads(snapshot)
        if data.get("schema")!="osixbay.gple.f01.foodweb.p0.v1":raise ValueError("bad schema")
        obj=cls(seed=1,state=State(**data["state"]))
        obj.ticks=data["ticks"]
        obj.initial_total=data["initial_total"]
        obj.events=data["events"]
        bias=data.get("growth_bias")
        if not isinstance(bias,(float,int)) or not math.isfinite(bias) or not 0.85<=bias<=1.15:
            raise ValueError("invalid growth bias")
        obj.growth_bias=bias
        if not math.isclose(obj.total(),obj.initial_total,abs_tol=1e-8):
            raise ValueError("invalid material ledger")
        return obj

def experiment(seeds=(11,23,37),ticks=300):
    if not seeds or len(seeds)>20 or not 1<=ticks<=5000:raise ValueError("budget")
    scenarios={"normal":{"water":1.0,"light":1.0,"consumers":2},
               "drought":{"water":0.0,"light":1.0,"consumers":2},
               "darkness":{"water":1.0,"light":0.0,"consumers":2},
               "no_f01":{"water":1.0,"light":1.0,"consumers":0}}
    results=[]
    for name,kwargs in scenarios.items():
        for seed in seeds:
            world=FoodWeb(seed=seed)
            for _ in range(ticks):world.tick(**kwargs)
            results.append({"scenario":name,"seed":seed,"result":world.summary()})
    return {"schema":"osixbay.gple.f01.foodweb-experiment.v1",
            "status":"synthetic_foodweb_only_no_game_assets",
            "ticks":ticks,"runs":len(results),"results":results,
            "limitations":["Stocks are abstract material mass, not calories",
                           "No actual Godot plants/fruits/skins/meshes",
                           "Producers use external light but no physical biochemistry",
                           "F01 energy, reproduction and diet NOT linked to these proxy stocks",
                           "Only one synthetic ecological patch"]}
