"""Agent-based predator/prey island used by the ecosystem Shorts.

Rabbits wander, eat grass and breed when well fed; they run from foxes they can see. Foxes chase the
nearest rabbit they can see, breed when well fed and starve when they can't eat. Grass regrows. Nothing
is scripted: booms, crashes and extinctions come out of these rules.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

ISLAND_R = 460.0
GRID = 40  # grass cells across the island's bounding square
TICKS_PER_YEAR = 30


@dataclass
class Params:
    rabbit_speed: float = 2.2
    rabbit_burn: float = 0.012
    rabbit_bite: float = 0.35  # grass taken per meal
    rabbit_gain: float = 0.5  # energy per unit of grass
    rabbit_breed: float = 1.3
    rabbit_flee: float = 80.0
    rabbit_max_age: int = 900
    fox_speed: float = 2.7
    fox_burn: float = 0.011
    fox_gain: float = 0.55
    fox_breed: float = 1.7
    fox_sense: float = 170.0
    fox_catch: float = 11.0
    fox_max_age: int = 1500
    grass_regrow: float = 0.004


@dataclass
class World:
    rng: np.random.Generator
    p: Params
    rab: dict = field(default_factory=dict)  # pos (n,2), head (n,), energy (n,), age (n,)
    fox: dict = field(default_factory=dict)
    grass: np.ndarray = None
    mask: np.ndarray = None
    tick: int = 0
    next_id: int = 0
    catch_log: list = field(default_factory=list)  # this tick's catches: (fox id, rabbit id, position)
    death_log: list = field(default_factory=list)  # this tick's other deaths: (kind, id, cause, position)

    def ids(self, n):
        out = np.arange(self.next_id, self.next_id + n)
        self.next_id += n
        return out


def _spawn(rng, n, energy, r=ISLAND_R * 0.85):
    a = rng.uniform(0, 2 * math.pi, n)
    rr = r * np.sqrt(rng.uniform(0, 1, n))
    return {
        "pos": np.stack([rr * np.cos(a), rr * np.sin(a)], 1),
        "head": rng.uniform(0, 2 * math.pi, n),
        "energy": np.full(n, energy) * rng.uniform(0.8, 1.2, n),
        "age": rng.integers(0, 200, n),
    }


def _cat(a, b):
    return {k: np.concatenate([a[k], b[k]]) for k in a}


def _keep(a, m):
    return {k: v[m] for k, v in a.items()}


def add_foxes(w: World, n: int, energy=1.2):
    """Drop n foxes onto the island (used to add the predators after the rabbits have settled)."""
    f = _spawn(w.rng, n, energy, r=ISLAND_R * 0.6)
    f["id"] = w.ids(n)
    w.fox = _cat(w.fox, f) if len(w.fox.get("pos", [])) else f


def new_world(seed, rabbits=100, foxes=10, p: Params | None = None):
    rng = np.random.default_rng(seed)
    w = World(rng, p or Params())
    c = (np.arange(GRID) + 0.5) / GRID * 2 * ISLAND_R - ISLAND_R
    X, Y = np.meshgrid(c, c)
    w.mask = np.hypot(X, Y) < ISLAND_R
    w.grass = np.where(w.mask, rng.uniform(0.5, 1.0, (GRID, GRID)), 0.0)
    w.rab = _spawn(rng, rabbits, 1.0)
    w.rab["id"] = w.ids(rabbits)
    w.fox = _spawn(rng, foxes, 1.2)
    w.fox["id"] = w.ids(foxes)
    return w


def _cell(pos):
    ij = ((pos + ISLAND_R) / (2 * ISLAND_R) * GRID).astype(int)
    return np.clip(ij, 0, GRID - 1)


def _move(pos, head, speed, rng):
    pos += np.stack([np.cos(head), np.sin(head)], 1) * speed
    d = np.hypot(pos[:, 0], pos[:, 1])
    out = d > ISLAND_R - 6
    if out.any():  # turn back towards the middle at the shore
        pos[out] *= ((ISLAND_R - 6) / d[out])[:, None]
        head[out] = np.arctan2(-pos[out, 1], -pos[out, 0]) + rng.normal(0, 0.6, out.sum())


def step(w: World):
    """Advance one tick. Returns (births_rabbit, births_fox, catches [positions])."""
    p, rng = w.p, w.rng
    R, F = w.rab, w.fox
    w.catch_log, w.death_log = [], []
    nr, nf = len(R["pos"]), len(F["pos"])
    catches = []

    # rabbits: wander, flee visible foxes
    R["head"] += rng.normal(0, 0.35, nr)
    if nr and nf:
        dv = R["pos"][:, None, :] - F["pos"][None, :, :]
        dist = np.hypot(dv[..., 0], dv[..., 1])
        j = dist.argmin(1)
        near = dist[np.arange(nr), j] < p.rabbit_flee
        away = dv[np.arange(nr), j]
        R["head"][near] = np.arctan2(away[near, 1], away[near, 0]) + rng.normal(0, 0.3, near.sum())
    _move(R["pos"], R["head"], p.rabbit_speed, rng)

    # foxes: chase the nearest visible rabbit, else wander
    F["head"] += rng.normal(0, 0.3, nf)
    if nr and nf:
        dv = R["pos"][None, :, :] - F["pos"][:, None, :]
        dist = np.hypot(dv[..., 0], dv[..., 1])
        k = dist.argmin(1)
        dmin = dist[np.arange(nf), k]
        see = dmin < p.fox_sense
        to = dv[np.arange(nf), k]
        F["head"][see] = np.arctan2(to[see, 1], to[see, 0])
        _move(F["pos"], F["head"], p.fox_speed, rng)
        # catches (each rabbit eaten at most once)
        dv = R["pos"][None, :, :] - F["pos"][:, None, :]
        dist = np.hypot(dv[..., 0], dv[..., 1])
        eaten = np.zeros(nr, bool)
        for fi in np.nonzero(dist.min(1) < p.fox_catch)[0]:
            ri = dist[fi].argmin()
            if not eaten[ri] and dist[fi, ri] < p.fox_catch:
                eaten[ri] = True
                F["energy"][fi] += p.fox_gain
                catches.append(R["pos"][ri].copy())
                w.catch_log.append((int(F["id"][fi]), int(R["id"][ri]), R["pos"][ri].copy()))
        R = _keep(R, ~eaten)
    else:
        _move(F["pos"], F["head"], p.fox_speed, rng)

    # rabbits eat grass
    nr = len(R["pos"])
    if nr:
        ij = _cell(R["pos"])
        for n in rng.permutation(nr):
            i, j = ij[n, 1], ij[n, 0]
            g = w.grass[i, j]
            if g > 0.15:
                bite = min(g, p.rabbit_bite)
                w.grass[i, j] -= bite
                R["energy"][n] += bite * p.rabbit_gain
    w.grass = np.where(w.mask, np.minimum(1.0, w.grass + p.grass_regrow), 0.0)

    # metabolism, ageing, death
    R["energy"] -= p.rabbit_burn
    F["energy"] -= p.fox_burn
    R["age"] += 1
    F["age"] += 1
    for kind, A, max_age in (("rabbit", R, p.rabbit_max_age), ("fox", F, p.fox_max_age)):
        for i in np.nonzero((A["energy"] <= 0) | (A["age"] >= max_age))[0]:
            w.death_log.append((kind, int(A["id"][i]), "starved" if A["energy"][i] <= 0 else "old age", A["pos"][i].copy()))
    R = _keep(R, (R["energy"] > 0) & (R["age"] < p.rabbit_max_age))
    F = _keep(F, (F["energy"] > 0) & (F["age"] < p.fox_max_age))

    # breeding: split energy with a child next to the parent
    def breed(A, thr):
        m = A["energy"] > thr
        if not m.any():
            return A, 0
        A["energy"][m] /= 2
        kid = {k: v[m].copy() for k, v in A.items()}
        kid["pos"] += rng.normal(0, 6, kid["pos"].shape)
        kid["head"] = rng.uniform(0, 2 * math.pi, m.sum())
        kid["age"][:] = 0
        kid["id"] = w.ids(int(m.sum()))
        return _cat(A, kid), int(m.sum())

    R, br = breed(R, p.rabbit_breed)
    F, bf = breed(F, p.fox_breed)
    w.rab, w.fox = R, F
    w.tick += 1
    return br, bf, catches


def run(seed, years=100, **kw):
    """Run headless; returns the population history and the tick of the first extinction (or None)."""
    w = new_world(seed, **kw)
    hist, ext = [], None
    for _ in range(years * TICKS_PER_YEAR):
        step(w)
        nr, nf = len(w.rab["pos"]), len(w.fox["pos"])
        hist.append((nr, nf))
        if ext is None and (nr == 0 or nf == 0):
            ext = w.tick
            break
    return np.array(hist), ext
