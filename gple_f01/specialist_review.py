"""Specialist review of synthetic biome hypotheses (deterministic expert-system checks).
Roles: biology, ecology, genetics, behaviour, climate, validation.
Not six deployed LLM agents and not a scientific guarantee.
"""
import json
from pathlib import Path

ROLES=("biology","ecology","genetics","behaviour","climate","validation")

def review(report):
    if report.get("schema")!="osixbay.gple.f01.generated-biome-hypotheses.v1":
        raise ValueError("unsupported candidate report")
    proposal=report["top_proposal"]
    c=proposal
    total=sum(c["biome_mix"])
    reviews={
        "biology":{"status":"needs_empirical_data","findings":["F01 diet, water chemistry and temperature tolerance remain unapproved"]},
        "ecology":{"status":"conditional","findings":[
            "Resource regeneration and food capacity are hypothetical, not measured in Godot",
            "Missing trophic web and physical material/energy conservation"]},
        "genetics":{"status":"not_measured","findings":[
            "Original F01 has two inherited traits; environment search does not measure heritable adaptation or speciation"]},
        "behaviour":{"status":"limited","findings":[
            "Behaviour is forage/rest/flee with local perception; no memory or RL adaptation"]},
        "climate":{"status":"blocked","findings":[
            "Original F01 does not model temperature, humidity, salinity or seasonal hydrology"]},
        "validation":{"status":"no_go_real_world","findings":[
            "A real playable mask, resources and coordinate transform must be imported before Godot integration",
            "High population can be a simulator cap artefact, not a sustainable ecosystem"]}
    }
    if not 0.999<=total<=1.001: raise ValueError("invalid biome fractions")
    if not 0<=c["hazard"]<=1 or not 0<=c["regrowth"]<=1 or c["food_capacity"]<=0:
        raise ValueError("invalid environmental parameters")
    return {"schema":"osixbay.gple.f01.specialist-review.v1","candidate":c["id"],
            "reviewers":reviews,"approved_for_godot":False,
            "approved_for_world_engine":False,"real_biome_claim":False}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    data=json.loads(Path(args.input).read_text())
    result=review(data)
    Path(args.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"candidate":result["candidate"],"reviewers":len(result["reviewers"]),"approved":False}))
