"""OSIXBAY Genesis GPLE/F01: deterministic, dependency-free fauna laboratory.
Six specialist modules are explicit policies, not autonomous LLM processes.
No network, no publishing, no external writes beyond optional --out.
"""
from __future__ import annotations
import argparse
import json
import math
import random
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class Creature:
    cid: int
    x: int
    y: int
    energy: float = 65.0
    age: int = 0
    generation: int = 0
    speed: float = 1.0
    efficiency: float = 1.0
    caution: float = 0.5
    experience: float = 0.0

class Biology:
    @staticmethod
    def tick(c):
        c.age += 1
        c.energy -= (0.42 + 0.10 * c.speed) / c.efficiency
        return c.energy > 0 and c.age < 400

class Perception:
    @staticmethod
    def adjacent(x, y, size):
        return [(a,b) for a,b in ((x+1,y),(x-1,y),(x,y+1),(x,y-1),(x,y))
                if 0 <= a < size and 0 <= b < size]

class Behaviour:
    @staticmethod
    def choose(c, food, size, rng):
        cells = Perception.adjacent(c.x,c.y,size)
        # Utility: visible food first; learned bias to exploit promising locations.
        weights = [food[y][x] * (1 + c.experience * 0.3)
                   - 0.10 * (abs(x-c.x)+abs(y-c.y)) for x,y in cells]
        best = max(weights)
        choices = [xy for xy,score in zip(cells,weights) if score == best]
        return rng.choice(choices)

class Learning:
    @staticmethod
    def reward(c, eaten):
        # Bounded reward-dependent individual adaptation; not yet reinforcement learning.
        c.experience = max(0.0, min(1.0, 0.94 * c.experience + 0.06 * (1.0 if eaten > 0 else 0.0)))

class Reproduction:
    @staticmethod
    def offspring(parent, cid, rng):
        def mutate(v, lo, hi):
            return max(lo, min(hi, v + rng.uniform(-0.08, 0.08)))
        return Creature(cid=cid, x=parent.x, y=parent.y, energy=25.0,
                        generation=parent.generation+1,
                        speed=mutate(parent.speed, 0.7, 1.3),
                        efficiency=mutate(parent.efficiency, 0.7, 1.3),
                        caution=mutate(parent.caution, 0.0, 1.0))

class Ecology:
    @staticmethod
    def regrow(food, rng, capacity):
        for row in food:
            for i, value in enumerate(row):
                if value < capacity and rng.random() < 0.18:
                    row[i] += 1

class Validation:
    @staticmethod
    def check(creatures, food, size, capacity):
        ids = [c.cid for c in creatures]
        assert len(ids) == len(set(ids)), "duplicate creature id"
        assert all(0 <= c.x < size and 0 <= c.y < size for c in creatures)
        assert all(math.isfinite(c.energy) and c.energy > 0 for c in creatures)
        assert all(0 <= v <= capacity for row in food for v in row)

def simulate(seed=42, ticks=250, size=24, initial=18, max_population=300):
    if min(ticks, size, initial, max_population) < 1 or initial > max_population:
        raise ValueError("invalid simulation dimensions")
    if size > 128 or ticks > 100000 or max_population > 10000:
        raise ValueError("simulation safety cap exceeded")
    rng = random.Random(seed)
    capacity = 5
    food = [[rng.randrange(capacity + 1) for _ in range(size)] for _ in range(size)]
    creatures = [Creature(i, rng.randrange(size), rng.randrange(size)) for i in range(initial)]
    next_id, births, deaths, consumed = initial, 0, 0, 0
    timeline = []
    for tick in range(ticks):
        rng.shuffle(creatures)
        survivors, newborns = [], []
        for c in creatures:
            if not Biology.tick(c):
                deaths += 1
                continue
            c.x, c.y = Behaviour.choose(c, food, size, rng)
            eaten = min(2, food[c.y][c.x])
            food[c.y][c.x] -= eaten
            c.energy = min(100.0, c.energy + 7.0 * eaten * c.efficiency)
            consumed += eaten
            Learning.reward(c, eaten)
            if (c.age >= 25 and c.energy >= 85 and
                len(survivors) + len(newborns) + len(creatures) < max_population):
                c.energy -= 30.0
                newborns.append(Reproduction.offspring(c, next_id, rng))
                next_id += 1
                births += 1
            survivors.append(c)
        creatures = survivors + newborns
        Ecology.regrow(food, rng, capacity)
        Validation.check(creatures, food, size, capacity)
        if tick % 10 == 0 or tick == ticks-1:
            timeline.append({"tick":tick+1,"population":len(creatures),
                             "food":sum(map(sum,food)),"births":births,"deaths":deaths})
    return {"schema":"gple.f01.metrics.v1","seed":seed,"ticks":ticks,"size":size,
            "initial_population":initial,"final_population":len(creatures),
            "births":births,"deaths":deaths,"food_consumed":consumed,
            "max_generation":max((c.generation for c in creatures),default=0),
            "mean_energy":round(sum(c.energy for c in creatures)/len(creatures),3) if creatures else 0,
            "timeline":timeline}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed",type=int,default=42)
    p.add_argument("--ticks",type=int,default=250)
    p.add_argument("--size",type=int,default=24)
    p.add_argument("--initial",type=int,default=18)
    p.add_argument("--max-population",type=int,default=300)
    p.add_argument("--out",default="")
    args = p.parse_args()
    result = simulate(args.seed,args.ticks,args.size,args.initial,args.max_population)
    serialized = json.dumps(result,indent=2,sort_keys=True)
    if args.out:
        Path(args.out).parent.mkdir(parents=True,exist_ok=True)
        Path(args.out).write_text(serialized+"\n",encoding="utf-8")
    print(serialized)

if __name__ == "__main__":
    main()
