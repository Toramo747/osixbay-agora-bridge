"""DM-089: bounded multi-seed, multi-phase ECO-P0 endurance experiment.

This reports testable synthetic outcomes, NOT ecological plausibility or
a working Godot habitat. Biomass and water are separate closed proxy ledgers.
No organisms are spawned to "recover" an extinct species. A drought recovery
phase is merely a change in how EXISTING atmospheric water is redistributed.
"""
import argparse
import json
import math
import statistics
import time
import tracemalloc
from f01_feeding_bridge_p0 import F01Feeding
from multi_patch_p0 import NODES

SCHEMA="osixbay.genesis.gple.ecology-stress.dm089.v1"
SCENARIOS=("baseline","drought_recovery","wet","no_water_extinction")
DEFAULT_SEEDS=(11,23,37)
NORMAL={"rain_rate":0.14,"evaporation_rate":0.035}
DROUGHT={"rain_rate":0.0,"evaporation_rate":0.09}
REHYDRATE={"rain_rate":0.65,"evaporation_rate":0.015}
WET={"rain_rate":0.50,"evaporation_rate":0.015}
ZERO={"rain_rate":0.0,"evaporation_rate":0.0,
      "infiltration_rate":0.0,"discharge_rate":0.0}

def _require(ok,detail):
    if not ok:
        raise ValueError(detail)

def _run_args(seed,ticks,scenario):
    _require(isinstance(seed,int) and not isinstance(seed,bool) and 0<=seed<=1000000,"invalid seed")
    _require(isinstance(ticks,int) and not isinstance(ticks,bool) and 24<=ticks<=1200,"invalid ticks")
    _require(scenario in SCENARIOS,"invalid scenario")

def _waterless_initial_condition(sim):
    """A separate ZERO-water initial world; no injection/removal mid-run."""
    hydro=sim.eco.world.genetic.life.hydro
    _require(hydro.network.ticks==0,"waterless only at tick zero")
    for patch in NODES:
        hydro.network.water[patch]=0.0
        hydro.groundwater[patch]=0.0
        hydro.f01_tissue_water[patch]=0.0
        for species in hydro.producer_water[patch]:
            hydro.producer_water[patch][species]=0.0
    hydro.atmosphere=0.0
    hydro.initial_water=0.0
    hydro.network.water_initial=0.0
    sim.audit()

def _rates(scenario,i,ticks):
    if scenario=="baseline": return NORMAL
    if scenario=="wet": return WET
    if scenario=="no_water_extinction": return ZERO
    # Three phases: baseline, drought, return to closed-cycle rainfall.
    if i<ticks//3:return NORMAL
    if i<(2*ticks)//3:return DROUGHT
    return REHYDRATE

def _metrics(sim):
    sim.audit()
    eco=sim.eco
    world=eco.world
    genetic=world.genetic
    hydro=genetic.life.hydro
    living=[p for p,a in sim.f01.items() if a["alive"]]
    deaths={reason:sum(a["death_reason"]==reason for a in sim.f01.values())
            for reason in ("thirst","starvation")}
    return {
      "tick":hydro.network.ticks,
      "f01_alive":len(living),
      "f01_alive_by_patch":{p:sim.f01[p]["alive"] for p in NODES},
      "f01_deaths":deaths,
      "f01_cumulative_meals":round(sum(a["consumed"] for a in sim.f01.values()),7),
      "f01_cumulative_drinking":round(sum(a["water_consumed"] for a in sim.f01.values()),7),
      "plants_alive":len(genetic.life.individuals),
      "plant_births":genetic.life.counts["births"],
      "plant_deaths":genetic.life.counts["deaths"],
      "propagules_dormant":len(world.seeds),
      "propagules_created":world.created,
      "propagules_germinated":world.germinated,
      "propagules_expired":world.expired,
      "microfauna_alive":len(eco.micro),
      "microfauna_births":eco.births,
      "microfauna_deaths":eco.deaths,
      "microfauna_moves":eco.moves,
      "biomass":round(world.total_biomass(),7),
      "water":round(hydro.total_water(),7),
      "water_surface":round(sum(hydro.network.water.values()),7),
      "water_ground":round(sum(hydro.groundwater.values()),7),
      "water_atmosphere":round(hydro.atmosphere,7)
    }

def run_case(seed=11,ticks=180,scenario="baseline",profile=False,check_replay=True):
    _run_args(seed,ticks,scenario)
    _require(type(profile) is bool and type(check_replay) is bool,"boolean flags")
    sim=F01Feeding(seed=seed)
    if scenario=="no_water_extinction":
        _waterless_initial_condition(sim)
    before=_metrics(sim)
    checkpoints={"0":before}
    sample_at={1,ticks//3,(2*ticks)//3,ticks}
    per_tick_ms=[]
    replica=None
    for i in range(ticks):
        start=time.perf_counter_ns()
        sim.tick(**_rates(scenario,i,ticks))
        elapsed=(time.perf_counter_ns()-start)/1_000_000
        per_tick_ms.append(elapsed)
        if i+1 in sample_at:
            checkpoints[str(i+1)]=_metrics(sim)
        if check_replay and i+1==ticks//2:
            replica=F01Feeding.restore(sim.snapshot())
        elif replica is not None:
            replica.tick(**_rates(scenario,i,ticks))
        _require(math.isclose(sim.eco.world.total_biomass(),before["biomass"],abs_tol=1e-6),
                 "biomass created/deleted")
        _require(math.isclose(sim.eco.world.genetic.life.hydro.total_water(),before["water"],abs_tol=1e-6),
                 "water created/deleted")
    after=_metrics(sim)
    if replica is not None:
        _require(replica.snapshot()==sim.snapshot(),"snapshot replay divergence")
    timings=sorted(per_tick_ms)
    result={
       "seed":seed,"scenario":scenario,"ticks":ticks,
       "starting":before,"ending":after,"checkpoints":checkpoints,
       "replay_exact":bool(check_replay),
       "biomass_conserved":True,"water_conserved":True,
       "elapsed_ms":round(sum(per_tick_ms),4),
       "tick_ms_mean":round(statistics.fmean(per_tick_ms),5),
       "tick_ms_p95":round(timings[math.ceil(len(timings)*.95)-1],5),
       "tick_ms_max":round(timings[-1],5)
    }
    if profile:
        # profile measures heap allocations, not physical RSS or in-game FPS.
        result["host_profiling_note"]="Python wall-clock only; not Godot or target hardware"
    return result

def experiment(seeds=DEFAULT_SEEDS,ticks=180,scenarios=SCENARIOS,profile=False):
    _require(isinstance(seeds,(tuple,list)) and 1<=len(seeds)<=8
             and len(set(seeds))==len(seeds),"seed list")
    _require(isinstance(scenarios,(tuple,list)) and 1<=len(scenarios)<=4
             and len(set(scenarios))==len(scenarios),"scenario list")
    for seed in seeds:_run_args(seed,ticks,"baseline")
    for scenario in scenarios:_require(scenario in SCENARIOS,"scenario list entry")
    cases=[]
    for seed in seeds:
        for scenario in scenarios:
            if profile:
                tracemalloc.start()
            try:
                case=run_case(seed,ticks,scenario,profile=profile)
                if profile:
                    _,peak=tracemalloc.get_traced_memory()
                    case["python_traced_heap_peak_mb"]=round(peak/(1024*1024),4)
            finally:
                if profile:
                    tracemalloc.stop()
            cases.append(case)
    return {
        "schema":SCHEMA,
        "status":"synthetic_offline_not_canonical",
        "seeds":list(seeds),"ticks":ticks,"scenarios":list(scenarios),
        "cases":cases,
        "aggregate":{
            "runs":len(cases),
            "all_replay_exact":all(x["replay_exact"] for x in cases),
            "all_conserved":all(x["biomass_conserved"] and x["water_conserved"] for x in cases),
            "f01_extinct_runs":sum(x["ending"]["f01_alive"]==0 for x in cases),
            "microfauna_extinct_runs":sum(x["ending"]["microfauna_alive"]==0 for x in cases),
            "producer_extinct_runs":sum(x["ending"]["plants_alive"]==0 for x in cases),
        },
        "limitations":[
          "Synthetic three-patch stocks; no authoritative terrain, coordinates or Godot simulation",
          "Three F01 proxies only: not the original F01 behavior, no F01 reproduction",
          "F01 extinction is irreversible in this laboratory: weather recovery cannot respawn organisms",
          "The no-water extinction scenario starts from a different zero-water initial world",
          "F01 energy proxy and organism reproduction are not biologically calibrated",
          "Biomass is abstract mass, water is abstract stock, solar energy external",
          "Scenario rainfall redistributes closed atmospheric water; no external precipitation",
          "Long-term event history grows with ticks; real CPU/GPU budgets require separate profiling",
          "Timed values are runner-dependent; not Windows client FPS or target server throughput"
        ]
    }

def _cli():
    parser=argparse.ArgumentParser(description="OSIXBAY ECO-P0 multi-seed stress, no deployments")
    parser.add_argument("--seeds",default="11,23,37")
    parser.add_argument("--ticks",type=int,default=180)
    parser.add_argument("--profile",action="store_true")
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    seeds=tuple(int(x) for x in args.seeds.split(","))
    result=experiment(seeds=seeds,ticks=args.ticks,profile=args.profile)
    with open(args.out,"w",encoding="utf-8") as f:
        json.dump(result,f,indent=2,sort_keys=True)
        f.write("\n")
    print(json.dumps({"schema":SCHEMA,"runs":result["aggregate"]["runs"],
          "ticks":result["ticks"],"all_conserved":result["aggregate"]["all_conserved"],
          "all_replay_exact":result["aggregate"]["all_replay_exact"],
          "f01_extinct_runs":result["aggregate"]["f01_extinct_runs"]},sort_keys=True))

if __name__=="__main__":_cli()
