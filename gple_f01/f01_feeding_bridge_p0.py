"""DM-088 conservative F01 feeding bridge over the existing foodweb.

The existing FoodWeb already transfers food into f01_reserve. This bridge
observes that transfer and attributes it to an individual F01 proxy; it does
NOT execute a second feeding transfer. Energy is a bounded derived indicator,
not an independently conserved mass store.
"""
import json,math
from microfauna_p0 import MicroWorld
from multi_patch_p0 import NODES

SCHEMA="osixbay.genesis.gple.f01-feeding-bridge.v1"
FOOD=("fruit_a","fruit_b","biofilm","microfauna")
class F01Feeding:
    def __init__(self,seed=11):
        self.eco=MicroWorld(seed=seed)
        self.f01={p:{"identity":"f01-"+p,"energy":.5,"consumed":0.0,"starvation_ticks":0} for p in NODES}
        self.audit()

    def audit(self):
        self.eco.audit()
        for p,a in self.f01.items():
            if p not in NODES or not 0<=a["energy"]<=1 or a["consumed"]<0 or a["starvation_ticks"]<0:
                raise ValueError("invalid F01 proxy")

    def tick(self,**kwargs):
        net=self.eco.world.genetic.life.hydro.network
        offsets={p:len(net.nodes[p].events) for p in NODES}
        self.eco.tick(**kwargs)
        meals={}
        for p in NODES:
            events=net.nodes[p].events[offsets[p]:]
            food=[e for e in events if e["event"]=="f01_consumption" and e["source"] in FOOD and e["target"]=="f01_reserve"]
            quantity=sum(e["quantity"] for e in food)
            actor=self.f01[p]
            actor["consumed"]+=quantity
            actor["energy"]=max(0,min(1,actor["energy"]-.025+quantity*.12))
            actor["starvation_ticks"]=0 if quantity>0 else actor["starvation_ticks"]+1
            meals[p]={"food":{k:round(sum(e["quantity"] for e in food if e["source"]==k),8) for k in FOOD},
                      "consumed":round(quantity,8),"energy":round(actor["energy"],6),
                      "starvation_ticks":actor["starvation_ticks"]}
        self.audit()
        return {"tick":net.ticks,"meals":meals,"biomass":round(self.eco.world.total_biomass(),8)}

    def snapshot(self):
        return json.dumps({"schema":SCHEMA,"eco":self.eco.snapshot(),"f01":self.f01},
                          sort_keys=True,separators=(",",":"))

    @classmethod
    def restore(cls,payload):
        d=json.loads(payload)
        if d.get("schema")!=SCHEMA:raise ValueError("schema")
        x=object.__new__(cls)
        x.eco=MicroWorld.restore(d["eco"])
        x.f01=d["f01"]
        if set(x.f01)!=set(NODES):raise ValueError("F01 patches")
        x.audit()
        return x
