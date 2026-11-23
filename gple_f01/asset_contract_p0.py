"""Offline asset/event manifest schema for the Genesis 2.5D ECO-P0 candidates.

A manifest is a specification, not a GLB/skin/rig/animation. All paths remain
None until actual files are inspected. F01 original design remains unmodified.
"""
import json
import math

KINDS={"producer","microfauna","reference_fauna"}
STAGES={"seed","juvenile","adult","senescent","bud"}
EVENTS={"biomass_growth","fruit_created","fruit_consumed","biofilm_grazed",
        "microfauna_grazed","organism_spawned","organism_dead","organism_moved"}
SPECIES=(
  ("PROD-A","Laminofora","producer",["seed","juvenile","adult","senescent"],
   ["biomass_growth","fruit_created","fruit_consumed","organism_dead"]),
  ("PROD-B","Nodulessa","producer",["seed","juvenile","adult","senescent"],
   ["biomass_growth","fruit_created","fruit_consumed","organism_dead"]),
  ("MICRO-01","MICRO-01","microfauna",["juvenile","adult"],
   ["organism_spawned","organism_moved","biofilm_grazed","organism_dead"]),
  ("F01","F01","reference_fauna",["bud","juvenile","adult","senescent"],
   ["organism_spawned","organism_moved","fruit_consumed","microfauna_grazed","organism_dead"])
)

def manifest():
    return {"schema":"osixbay.genesis.eco-p0.asset-manifest.v1",
      "status":"design_only_all_assets_missing",
      "target":"Godot 2.5D; axes X,Z ground; Y height; meters",
      "species":[{
        "species_id":sid,"name":name,"kind":kind,"approval":"candidate",
        "biological_source":"F01 original PR88" if sid=="F01" else "Atlante biologico ECO-P0 v0.1",
        "reference_art_status":"concept_only_not_runtime",
        "source_blend_path":None,"glb_path":None,"texture_paths":[],
        "animation_paths":[],"collision_path":None,
        "lifecycle_stages":stages,"events":ev,"lod_assets":{"near":None,"mid":None,"far":None},
        "scale_m_verified":False,"art_approved":False,"bio_approved":False,
        "resource_stock_binding":("fruit_a" if sid=="PROD-A" else
                                  "fruit_b" if sid=="PROD-B" else
                                  "microfauna" if sid=="MICRO-01" else None)
      } for sid,name,kind,stages,ev in SPECIES],
      "runtime_scene_verified":False,
      "actual_godot_build_verified":False}

def validate_manifest(data):
    if data.get("schema")!="osixbay.genesis.eco-p0.asset-manifest.v1":raise ValueError("schema")
    entries=data.get("species")
    if not isinstance(entries,list) or len(entries)!=4:raise ValueError("species count")
    ids=set()
    for item in entries:
        sid=item.get("species_id")
        if sid in ids or sid not in {v[0] for v in SPECIES}:raise ValueError("species identity")
        ids.add(sid)
        if item.get("kind") not in KINDS:raise ValueError("kind")
        if item.get("approval") not in {"candidate","review","approved"}:raise ValueError("approval")
        if not set(item.get("lifecycle_stages",[]))<=STAGES:raise ValueError("stages")
        if not set(item.get("events",[]))<=EVENTS:raise ValueError("events")
        lod=item.get("lod_assets")
        if not isinstance(lod,dict) or set(lod)!={"near","mid","far"}:raise ValueError("lod keys")
        for key in ("source_blend_path","glb_path","collision_path"):
            v=item.get(key)
            if v is not None and (not isinstance(v,str) or not v.strip()):raise ValueError("bad asset path")
        if not isinstance(item.get("texture_paths"),list) or not isinstance(item.get("animation_paths"),list):
            raise ValueError("asset arrays")
        for val in list(lod.values())+item["texture_paths"]+item["animation_paths"]:
            if val is not None and (not isinstance(val,str) or not val.strip()):raise ValueError("bad asset reference")
        if item.get("art_approved") is not True and item.get("glb_path") is not None:
            # Valid path alone never implies approval; this just prevents accidental gate promotion.
            pass
        if not item.get("scale_m_verified") and item.get("approval")=="approved":
            raise ValueError("cannot approve unverified scale")
    if ids!={v[0] for v in SPECIES}:raise ValueError("missing entry")
    for k in ("runtime_scene_verified","actual_godot_build_verified"):
        if not isinstance(data.get(k),bool):raise ValueError("gate flag")
    return True

def validate_event(event, world_version):
    if not isinstance(event,dict) or event.get("event") not in EVENTS:raise ValueError("event type")
    if not isinstance(event.get("tick"),int) or event["tick"]<0:raise ValueError("tick")
    if not isinstance(event.get("entity_id"),str) or not event["entity_id"]:raise ValueError("entity")
    if event.get("species_id") not in {v[0] for v in SPECIES}:raise ValueError("species")
    if event.get("world_version")!=world_version:raise ValueError("stale event")
    if not isinstance(event.get("cell_id"),str) or not event["cell_id"]:raise ValueError("cell")
    before,after=event.get("quantity_before"),event.get("quantity_after")
    if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v<0 for v in (before,after)):
        raise ValueError("stock")
    if event["event"] in {"fruit_consumed","biofilm_grazed","microfauna_grazed"} and after>before:
        raise ValueError("consumption increased stock")
    if event["event"] in {"fruit_created","biomass_growth"} and after<before:
        raise ValueError("growth reduced stock")
    return {"entity_id":event["entity_id"],"tick":event["tick"],"visual_delta":round(after-before,7)}

if __name__=="__main__":
    data=manifest()
    validate_manifest(data)
    print(json.dumps(data,indent=2,sort_keys=True))
