"""FAUNA-02 reference simulator; synthetic non-canonical habitat, stdlib only."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json

MASK = (1 << 64) - 1

@dataclass(frozen=True)
class Parameters:
    capacity: float = 4.0
    regrowth: float = 0.15
    food_per_tick: float = 1.2
    food_energy: float = 2.5
    basal_cost: float = 0.55
    movement_cost: float = 0.2
    birth_threshold: float = 13.0
    child_energy: float = 4.0
    birth_cost: float = 1.0
    energy_cap: float = 20.0
    max_age: int = 120
    max_population: int = 50
    cooldown: int = 6

    def __post_init__(self):
        if self.capacity <= 0 or not 0 <= self.regrowth <= self.capacity:
            raise ValueError("invalid resource bounds")
        if self.food_per_tick <= 0 or self.food_energy <= 0:
            raise ValueError("invalid food configuration")
        if self.basal_cost <= 0 or self.movement_cost < 0:
            raise ValueError("invalid metabolism")
        if not 0 < self.child_energy < self.birth_threshold <= self.energy_cap:
            raise ValueError("invalid reproduction threshold")
        if self.birth_cost < 0 or self.child_energy + self.birth_cost >= self.birth_threshold:
            raise ValueError("invalid birth cost")
        if self.max_age <= 0 or self.max_population <= 0 or self.cooldown < 0:
            raise ValueError("invalid population bounds")

@dataclass
class Cell:
    suitable: bool
    food: float
    danger: float = 0.0

@dataclass
class Organism:
    identity: int
    x: int
    y: int
    energy: float = 9.0
    age: int = 0
    cooldown: int = 0
    threshold: float = 14.0
    efficiency: float = 1.0
    last_action: str = "rest"

class World:
    """One authoritative local grid, not the deployed Cloudflare world."""

    def __init__(self, habitat: list[list[bool]], seed: int = 1,
                 parameters: Parameters | None = None):
        if not habitat or not habitat[0] or any(len(row) != len(habitat[0]) for row in habitat):
            raise ValueError("habitat must be rectangular and nonempty")
        if not isinstance(seed, int):
            raise TypeError("seed must be int")
        self.width, self.height = len(habitat[0]), len(habitat)
        self.parameters = parameters or Parameters()
        self.cells = [[Cell(bool(v), self.parameters.capacity if v else 0.0)
                       for v in row] for row in habitat]
        self.organisms: list[Organism] = []
        self.next_id, self.ticks, self.rng_state = 1, 0, seed & MASK

    def random(self) -> float:
        self.rng_state = (self.rng_state * 6364136223846793005 + 1442695040888963407) & MASK
        return (self.rng_state >> 11) / float(1 << 53)

    def add_organism(self, x: int, y: int, energy: float = 9.0,
                     threshold: float = 14.0, efficiency: float = 1.0):
        if not (0 <= x < self.width and 0 <= y < self.height and self.cells[y][x].suitable):
            raise ValueError("unsuitable habitat")
        if not (0 < energy <= self.parameters.energy_cap and 2 <= threshold <= 18 and
                0.5 <= efficiency <= 1.5):
            raise ValueError("invalid organism parameters")
        if len(self.organisms) >= self.parameters.max_population:
            raise ValueError("population full")
        animal = Organism(self.next_id, x, y, energy, threshold=threshold, efficiency=efficiency)
        self.next_id += 1
        self.organisms.append(animal)
        return animal

    def neighbors(self, a: Organism):
        points = [(a.x, a.y), (a.x + 1, a.y), (a.x - 1, a.y),
                  (a.x, a.y + 1), (a.x, a.y - 1)]
        return [(x, y) for x, y in points if 0 <= x < self.width and
                0 <= y < self.height and self.cells[y][x].suitable]

    def step(self):
        p, births, survivors, deaths = self.parameters, [], [], 0
        for a in sorted(self.organisms, key=lambda unit: unit.identity):
            a.age += 1
            a.cooldown = max(0, a.cooldown - 1)
            if not self.cells[a.y][a.x].suitable:
                deaths += 1
                continue
            a.energy = max(0.0, a.energy - p.basal_cost)
            if a.energy <= 0 or a.age >= p.max_age:
                deaths += 1
                continue
            nearby = self.neighbors(a)
            if self.cells[a.y][a.x].danger > 0.5:
                x, y = min(nearby, key=lambda xy: (
                    self.cells[xy[1]][xy[0]].danger,
                    -self.cells[xy[1]][xy[0]].food, xy[1], xy[0]))
                a.last_action = "flee"
                if (x, y) != (a.x, a.y):
                    a.energy = max(0.0, a.energy - p.movement_cost)
                    a.x, a.y = x, y
            elif a.energy < a.threshold:
                a.last_action = "forage"
                x, y = max(nearby, key=lambda xy: (
                    self.cells[xy[1]][xy[0]].food, -xy[1], -xy[0]))
                if (x, y) != (a.x, a.y):
                    a.energy = max(0.0, a.energy - p.movement_cost)
                    a.x, a.y = x, y
                if a.energy <= 0:
                    deaths += 1
                    continue
                cell = self.cells[a.y][a.x]
                eaten = min(p.food_per_tick, cell.food)
                cell.food = max(0.0, cell.food - eaten)
                a.energy = min(p.energy_cap, a.energy + eaten * p.food_energy * a.efficiency)
            else:
                a.last_action = "rest"
            if a.energy <= 0:
                deaths += 1
                continue
            if a.energy >= p.birth_threshold and a.cooldown == 0 and (
                    len(self.organisms) - deaths + len(births) < p.max_population):
                a.energy -= p.child_energy + p.birth_cost
                a.cooldown = p.cooldown
                a.last_action = "reproduce"
                threshold = min(18.0, max(2.0, a.threshold + self.random() - 0.5))
                efficiency = min(1.5, max(0.5, a.efficiency + (self.random() - 0.5) * 0.1))
                births.append(Organism(self.next_id, a.x, a.y, p.child_energy,
                                       threshold=threshold, efficiency=efficiency))
                self.next_id += 1
            survivors.append(a)
        self.organisms = (survivors + births)[:p.max_population]
        for row in self.cells:
            for cell in row:
                if cell.suitable:
                    cell.food = min(p.capacity, cell.food + p.regrowth)
                else:
                    cell.food = 0.0
        self.ticks += 1
        return {"tick": self.ticks, "alive": len(self.organisms),
                "born": max(0, len(self.organisms) - len(survivors)), "died": deaths}

    def snapshot(self):
        return json.dumps({
            "version": 1, "width": self.width, "height": self.height,
            "parameters": asdict(self.parameters),
            "cells": [[asdict(c) for c in row] for row in self.cells],
            "organisms": [asdict(a) for a in self.organisms],
            "next_id": self.next_id, "ticks": self.ticks,
            "rng_state": str(self.rng_state),
        }, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_snapshot(cls, source: str):
        d = json.loads(source)
        if d.get("version") != 1:
            raise ValueError("unsupported snapshot")
        world = cls([[c["suitable"] for c in row] for row in d["cells"]],
                    seed=int(d["rng_state"]), parameters=Parameters(**d["parameters"]))
        if (world.width, world.height) != (d["width"], d["height"]):
            raise ValueError("invalid snapshot dimensions")
        world.cells = [[Cell(**c) for c in row] for row in d["cells"]]
        world.organisms = [Organism(**a) for a in d["organisms"]]
        world.next_id, world.ticks = d["next_id"], d["ticks"]
        return world

def demonstration(seed: int = 13, ticks: int = 80):
    habitat = [[(x + y) % 7 != 0 for x in range(8)] for y in range(8)]
    world = World(habitat, seed=seed)
    world.add_organism(3, 3)
    world.add_organism(4, 2)
    tally = {"born": 0, "died": 0}
    for _ in range(ticks):
        result = world.step()
        tally["born"] += result["born"]
        tally["died"] += result["died"]
    return {"seed": seed, "ticks": world.ticks, "alive": len(world.organisms),
            **tally, "remaining_food": round(sum(c.food for row in world.cells for c in row), 5)}

if __name__ == "__main__":
    print(json.dumps(demonstration(), indent=2, sort_keys=True))
