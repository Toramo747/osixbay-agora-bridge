"""Offline Genesis F01 2.5D world/visual contract.

Godot renders in 3D; ecological simulation is cell-based. Neither camera nor LOD
controls authoritative survival, reproduction, hydration, resource stock or tick.
This validates real exports fail-closed; synthetic tests are explicitly marked.
"""
from __future__ import annotations

import math
from habitat_validator import validate as validate_ecology

SCHEMA="osixbay.genesis.gple.f01.habitat-export.v1"
RENDER_SCHEMA="osixbay.genesis.godot25d.f01.visual-frame.v1"
MAX_SLOPE_DEG=35.0 # experimental mobility limit, not canonical biology
MAX_WADE_M=0.45    # experimental mobility limit, not canonical biology
RENDER_MODES=("management","exploration")
LOD_NAMES=("near","mid","far","culled")

def _finite_number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def validate_25d_export(export):
    """Original habitat contract plus elevation/slope and explicit source provenance."""
    baseline=validate_ecology(export)
    cells=export["cells"]
    if not isinstance(export.get("coordinate_system"),dict):
        raise ValueError("missing Godot coordinate system")
    axes=export["coordinate_system"]
    if axes.get("horizontal")!=["x","z"] or axes.get("vertical")!="y" or axes.get("units")!="meters":
        raise ValueError("unknown coordinate axes or units")
    if export.get("camera_mode") not in RENDER_MODES:
        raise ValueError("invalid camera mode")
    if not isinstance(export.get("playable_boundary_source"),str) or not export["playable_boundary_source"].strip():
        raise ValueError("missing real playable boundary provenance")
    for y,row in enumerate(cells):
        for x,cell in enumerate(row):
            for key in ("elevation_m","slope_deg","water_surface_y_m"):
                if not _finite_number(cell.get(key)):
                    raise ValueError("missing/bad 2.5D terrain "+key)
            if cell["slope_deg"]<0 or cell["slope_deg"]>90:
                raise ValueError("invalid slope at "+str((x,y)))
            if cell["water_depth_m"]>0 and cell["water_surface_y_m"]<cell["elevation_m"]:
                raise ValueError("water below terrain")
    return baseline

def navigable(export, x, z, *, max_slope_deg=MAX_SLOPE_DEG, max_wade_m=MAX_WADE_M):
    if not _finite_number(max_slope_deg) or not _finite_number(max_wade_m) or max_wade_m<0:
        raise ValueError("invalid locomotion settings")
    if not isinstance(x,int) or not isinstance(z,int):
        return False
    cells=export["cells"]
    if not 0<=z<len(cells) or not 0<=x<len(cells[0]):
        return False
    c=cells[z][x]
    return bool(c["playable"] and c["suitable_for_f01"] and c["traversable"]
                and c["slope_deg"]<=max_slope_deg and c["water_depth_m"]<=max_wade_m)

def position_world(export,x,z):
    """2D ecological cell to real Godot Vector3 [x,y,z]; no arbitrary height."""
    if not navigable(export,x,z):
        raise ValueError("position is outside navigable F01 area")
    scale=export["grid_resolution_m"]
    origin=export["origin_world"]
    if len(origin)!=3:
        raise ValueError("Godot origin must explicitly be [x,y,z]")
    return [round(origin[0]+(x+0.5)*scale,6),
            round(origin[1]+export["cells"][z][x]["elevation_m"],6),
            round(origin[2]+(z+0.5)*scale,6)]

def validate_step(export,from_cell,to_cell):
    """Allow at most one cardinal cell per movement; zero-distance rest supported."""
    (x,z),(nx,nz)=from_cell,to_cell
    return (navigable(export,x,z) and navigable(export,nx,nz)
            and abs(x-nx)+abs(z-nz)<=1)

def choose_lod(distance_m, *, near=15, mid=50, far=180):
    if not _finite_number(distance_m) or distance_m<0:
        raise ValueError("invalid camera distance")
    if not (0<near<mid<far):
        raise ValueError("invalid LOD thresholds")
    if distance_m<near:return "near"
    if distance_m<mid:return "mid"
    if distance_m<far:return "far"
    return "culled"

def visual_frame(export, organisms, *, camera_xyz, mode, tick, world_version):
    """Read-only render projection. No mutation of biology or resource inventory."""
    validate_25d_export(export)
    if mode not in RENDER_MODES:raise ValueError("invalid view")
    if mode!=export["camera_mode"]:raise ValueError("camera/source mode mismatch")
    if world_version!=export["world_version"]:raise ValueError("stale world version")
    if not isinstance(tick,int) or tick<0:raise ValueError("bad tick")
    if not isinstance(camera_xyz,(tuple,list)) or len(camera_xyz)!=3 or not all(_finite_number(v) for v in camera_xyz):
        raise ValueError("bad camera")
    seen=set()
    entities=[]
    for a in organisms:
        if not isinstance(a,dict) or not isinstance(a.get("entity_id"),(str,int)):
            raise ValueError("invalid entity")
        eid=a["entity_id"]
        if eid in seen:raise ValueError("duplicate entity")
        seen.add(eid)
        if a.get("species_id")!="F01":raise ValueError("unknown species")
        x,z=a.get("cell_x"),a.get("cell_z")
        pos=position_world(export,x,z)
        action=a.get("action_state")
        if action not in ("idle","forage","move","flee","alert","rest","reproduce","death","seek_water"):
            raise ValueError("unknown animation action")
        stage=a.get("lifecycle_stage")
        if stage not in ("bud","juvenile","adult","senescent"):
            raise ValueError("unknown lifecycle stage")
        dist=math.dist(camera_xyz,pos)
        lod=choose_lod(dist)
        # Rendering may hide distant actors but does not remove entities from World/GPLE.
        entities.append({"entity_id":eid,"species_id":"F01","position_world":pos,
                         "action_state":action,"lifecycle_stage":stage,"lod":lod,
                         "visible":lod!="culled","biome":export["cells"][z][x]["biome"]})
    return {"schema":RENDER_SCHEMA,"zone_id":export["zone_id"],"world_version":world_version,
            "tick":tick,"view_mode":mode,"entities":entities,"render_only":True,
            "authoritative_simulation_mutated":False}
