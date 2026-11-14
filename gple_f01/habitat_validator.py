"""Fail-closed validator for an exported real F01 habitat. Not a map generator."""
import json
import math
import sys

BIOMES={"alien_forest","wet_shore","mineral_outcrop"}
REQUIRED={"playable","suitable_for_f01","traversable","biome","substrate","water_depth_m",
          "resources","resource_capacity","resource_regrowth","danger","shelter",
          "temperature","humidity"}

def validate(data):
    if not isinstance(data,dict) or data.get("schema")!="osixbay.genesis.gple.f01.habitat-export.v1":
        raise ValueError("invalid schema")
    for key in ("zone_id","world_version","source_scene","source_commit"):
        if not isinstance(data.get(key),str) or not data[key].strip():
            raise ValueError("missing source: "+key)
    scale=data.get("grid_resolution_m")
    if not isinstance(scale,(int,float)) or isinstance(scale,bool) or not math.isfinite(scale) or scale<=0:
        raise ValueError("invalid scale")
    origin=data.get("origin_world")
    if not isinstance(origin,list) or len(origin) not in (2,3) or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in origin):
        raise ValueError("invalid origin")
    cells=data.get("cells")
    if not isinstance(cells,list) or not cells or not isinstance(cells[0],list) or not cells[0]:
        raise ValueError("no cells")
    width=len(cells[0])
    if len(cells)>4096 or width>4096:raise ValueError("oversized")
    viable=0
    for row in cells:
        if not isinstance(row,list) or len(row)!=width:raise ValueError("ragged grid")
        for c in row:
            if not isinstance(c,dict) or not REQUIRED.issubset(c):raise ValueError("incomplete cell")
            if c["biome"] not in BIOMES:raise ValueError("unknown biome")
            for k in ("playable","suitable_for_f01","traversable","shelter"):
                if not isinstance(c[k],bool):raise ValueError("bad boolean")
            if not isinstance(c["substrate"],str) or not c["substrate"]:raise ValueError("no substrate")
            for k in ("temperature","humidity","water_depth_m","danger"):
                v=c[k]
                if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError("bad environment")
            if not 0<=c["humidity"]<=1 or not 0<=c["danger"]<=1 or c["water_depth_m"]<0:
                raise ValueError("bad environmental range")
            d,e,g=(c[k] for k in ("resources","resource_capacity","resource_regrowth"))
            if not all(isinstance(x,dict) for x in (d,e,g)) or set(d)!=set(e) or set(d)!=set(g):
                raise ValueError("resource mismatch")
            for resource,value in d.items():
                if not isinstance(resource,str) or not resource:raise ValueError("resource name")
                for n in (value,e[resource],g[resource]):
                    if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or n<0:
                        raise ValueError("resource value")
                if value>e[resource]:raise ValueError("capacity exceeded")
            viable+=bool(c["playable"] and c["suitable_for_f01"] and c["traversable"])
    if not viable:raise ValueError("no suitable habitat")
    return {"zone_id":data["zone_id"],"world_version":data["world_version"],
            "width":width,"height":len(cells),"viable_cells":viable}

if __name__=="__main__":
    from pathlib import Path
    print(json.dumps(validate(json.loads(Path(sys.argv[1]).read_text())),indent=2))
