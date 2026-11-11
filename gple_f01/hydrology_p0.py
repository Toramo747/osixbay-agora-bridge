"""Experimental CLOSED water cycle for the 3 synthetic ECO-P0 patches.

Separate surface, groundwater and atmospheric water, all in arbitrary water
stock units. No real hydrology/terrain, atmospheric transport, or water chemistry.
Rain, evaporation, infiltration and discharge are internal transfers only.
"""
import json
import math
from multi_patch_p0 import PatchNetwork, NODES, PROFILES, EDGES, finite_nonnegative

SCHEMA="osixbay.genesis.gple.hydrology-p0.v1"
WEIGHTS={"forest":0.30,"shore":0.50,"rock":0.20}

class Hydrology:
    def __init__(self,seed=11,connections=EDGES):
        self.network=PatchNetwork(seed=seed,connections=connections)
        self.groundwater={name:0.0 for name in NODES}
        self.atmosphere=0.0
        self.initial_water=self.total_water()
        self.events={"evaporated":0.0,"rainfall":0.0,
                     "infiltrated":0.0,"discharged":0.0,"ledger_ticks":0}
        self.audit()

    def total_water(self):
        return sum(self.network.water.values())+sum(self.groundwater.values())+self.atmosphere

    def audit(self):
        if set(self.groundwater)!=set(NODES) or not finite_nonnegative(self.atmosphere):
            raise ValueError("invalid hydrology reservoirs")
        if any(not finite_nonnegative(v) for v in self.groundwater.values()):
            raise ValueError("invalid groundwater")
        if not math.isclose(self.total_water(),self.initial_water,rel_tol=1e-11,abs_tol=1e-8):
            raise ValueError("global water mass violated")
        self.network.audit()

    def _retarget_network_water_ledger(self):
        # PatchNetwork only owns surface reservoirs; its per-tick audit is updated
        # explicitly when water crosses to groundwater/atmosphere.
        self.network.water_initial=sum(self.network.water.values())

    def tick(self,*,rain_rate=0.14,evaporation_rate=0.035,
             infiltration_rate=0.025,discharge_rate=0.018,
             override_consumers=None):
        rates=(rain_rate,evaporation_rate,infiltration_rate,discharge_rate)
        if any(not isinstance(v,(int,float)) or isinstance(v,bool)
               or not math.isfinite(v) or not 0<=v<=1 for v in rates):
            raise ValueError("invalid hydrology rates")
        # 1) surface evaporation: local temperature is an experimental multiplier.
        for name in NODES:
            temp_factor=max(0.2,min(2.0,1+(PROFILES[name]["temperature"]-20)/20))
            surface=self.network.water[name]
            amount=surface*evaporation_rate*temp_factor
            self.network.water[name]-=amount
            self.atmosphere+=amount
            self.events["evaporated"]+=amount
        # 2) soil infiltration, bounded by currently available surface water.
        for name in NODES:
            amount=self.network.water[name]*infiltration_rate
            self.network.water[name]-=amount
            self.groundwater[name]+=amount
            self.events["infiltrated"]+=amount
        # 3) groundwater discharge to the same patch surface.
        for name in NODES:
            amount=self.groundwater[name]*discharge_rate
            self.groundwater[name]-=amount
            self.network.water[name]+=amount
            self.events["discharged"]+=amount
        # 4) precipitation: distributed from the finite atmospheric reservoir.
        rain=self.atmosphere*rain_rate
        self.atmosphere-=rain
        for name in NODES:
            self.network.water[name]+=rain*WEIGHTS[name]
        self.events["rainfall"]+=rain
        self._retarget_network_water_ledger()
        # 5) in-patch biology and conservative surface water lateral exchange.
        self.network.tick(override_consumers=override_consumers)
        self.events["ledger_ticks"]+=1
        self.audit()
        return self.summary()

    def summary(self):
        return {"tick":self.network.ticks,"total_water":round(self.total_water(),8),
                "surface":{k:round(v,8) for k,v in self.network.water.items()},
                "groundwater":{k:round(v,8) for k,v in self.groundwater.items()},
                "atmosphere":round(self.atmosphere,8),
                "biomass_total":round(self.network.biomass(),8),
                "ledger_ticks":self.events["ledger_ticks"]}

    def snapshot(self):
        return json.dumps({"schema":SCHEMA,"network":self.network.snapshot(),
                           "groundwater":self.groundwater,"atmosphere":self.atmosphere,
                           "initial_water":self.initial_water,"events":self.events},
                          sort_keys=True,separators=(",",":"))

    @classmethod
    def restore(cls,payload):
        d=json.loads(payload)
        if d.get("schema")!=SCHEMA:raise ValueError("snapshot schema")
        obj=object.__new__(cls)
        obj.network=PatchNetwork.restore(d["network"])
        obj.groundwater=d["groundwater"]
        obj.atmosphere=d["atmosphere"]
        obj.initial_water=d["initial_water"]
        obj.events=d["events"]
        if set(obj.events)!={"evaporated","rainfall","infiltrated","discharged","ledger_ticks"}:
            raise ValueError("snapshot event fields")
        if not isinstance(obj.events["ledger_ticks"],int) or obj.events["ledger_ticks"]!=obj.network.ticks:
            raise ValueError("tick ledger")
        for key in ("evaporated","rainfall","infiltrated","discharged"):
            if not finite_nonnegative(obj.events[key]):raise ValueError("bad event ledger")
        if not finite_nonnegative(obj.initial_water):raise ValueError("initial water")
        obj.audit()
        return obj

def experiment(seeds=(11,23,37),ticks=600):
    if not seeds or len(seeds)>20 or not 1<=ticks<=5000:raise ValueError("budget")
    configs={
        "cyclic":{"rain_rate":0.14,"evaporation_rate":0.035},
        "drought":{"rain_rate":0.0,"evaporation_rate":0.07},
        "wet":{"rain_rate":0.4,"evaporation_rate":0.018},
    }
    cases=[]
    for seed in seeds:
        for case,rates in configs.items():
            hyd=Hydrology(seed=seed)
            checkpoints=[]
            for tick in range(1,ticks+1):
                hyd.tick(**rates)
                if tick in (1,ticks//2,ticks):
                    checkpoints.append(hyd.summary())
            cases.append({"seed":seed,"scenario":case,
                          "summary":hyd.summary(),"checkpoints":checkpoints,
                          "events":{k:round(v,7) for k,v in hyd.events.items()}})
    return {"schema":"osixbay.genesis.gple.hydrology-experiment.v1",
            "status":"synthetic_water_proxies_not_physical_hydrology",
            "ticks":ticks,"cases":cases,
            "limitations":["No external precipitation; rain comes from finite atmosphere",
                           "No oceans, aquifers, runoff elevation model or evapotranspiration",
                           "Water stocks are abstract units, not liters",
                           "F01 drinking does not subtract from stock",
                           "No real Godot terrain or World Engine integration"]}
