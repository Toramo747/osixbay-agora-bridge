"""Offline Godot-facing scene snapshot contract, versioned and validated.

No engine dependency. Position is deliberately absent until a terrain-to-patch
coordinate mapping is approved; clients must not invent world coordinates.
"""
import json,math
from f01_feeding_bridge_p0 import F01Feeding
from multi_patch_p0 import NODES

SCHEMA="osixbay.genesis.demo-ecology-scene.v1"
SPECIES={"producer_a":"laminofora","producer_b":"nodulessa"}

def export_scene(sim):
    if not isinstance(sim,F01Feeding):raise TypeError("sim")
    sim.audit()
    world=sim.eco.world
    plants=[{"id":p.identity,"type":"plant","species":SPECIES[p.species],
             "patch":p.patch,"age":p.age,"biomass":round(p.biomass,8),
             "genome":world.genetic.genes[p.identity]}
            for p in world.genetic.life.individuals]
    propagules=[{"id":s.identity,"type":"propagule","species":SPECIES[s.species],
                 "patch":s.patch,"age":s.age,"biomass":round(s.biomass,8),
                 "parent_id":s.parent_id} for s in world.seeds]
    micro=[{"id":m.identity,"type":"microfauna","species":"micro-01",
            "patch":m.patch,"age":m.age,"biomass":round(m.mass,8)}
           for m in sim.eco.micro]
    f01=[{"id":a["identity"],"type":"f01","species":"f01",
          "patch":p,"energy":round(a["energy"],8),"starvation_ticks":a["starvation_ticks"]}
         for p,a in sim.f01.items()]
    entities=sorted(plants+propagules+micro+f01,key=lambda e:e["id"])
    payload={"schema":SCHEMA,"tick":world.genetic.life.hydro.network.ticks,
             "units":"abstract_mass_not_real_world","patches":list(NODES),
             "entities":entities,"rendering":{"positions":"not_provided",
             "mapping_required":"patch_to_world_coordinates",
             "models_required":["laminofora","nodulessa","micro-01","f01"]}}
    validate_scene(payload)
    return payload

def validate_scene(payload):
    if payload.get("schema")!=SCHEMA or payload.get("patches")!=list(NODES):
        raise ValueError("schema/patches")
    if not isinstance(payload.get("tick"),int) or payload["tick"]<0:raise ValueError("tick")
    entities=payload.get("entities")
    if not isinstance(entities,list) or len(entities)>10000:raise ValueError("entities")
    ids=set()
    for e in entities:
        if not isinstance(e,dict) or not isinstance(e.get("id"),str) or not e["id"] or e["id"] in ids:
            raise ValueError("duplicate/invalid entity")
        ids.add(e["id"])
        if e.get("patch") not in NODES or e.get("type") not in ("plant","propagule","microfauna","f01"):
            raise ValueError("entity")
        if "position" in e:raise ValueError("unverified coordinates")
        for field in ("biomass","energy"):
            if field in e and (not isinstance(e[field],(int,float)) or not math.isfinite(e[field]) or e[field]<0):
                raise ValueError("invalid "+field)
    return True

def demo(seed=11,ticks=35):
    sim=F01Feeding(seed=seed)
    for _ in range(ticks):sim.tick()
    return json.dumps(export_scene(sim),indent=2,sort_keys=True)
