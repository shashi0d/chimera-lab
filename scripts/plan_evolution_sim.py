"""Plan-level evolution demo: random trait arrangements on every possible host,
scored on possibility (hard gate), survival (function audit), realism and identity.
Simplified animal facts, hand-entered for the demo; not the engine's data."""
import random, itertools, statistics, sys, json

ANIMALS = {
 "axolotl":  dict(habitat="water", mass=0.2, cls="amphibian",
   parts={"head":"broad axolotl head, suction feeder", "breathing":"external gills",
          "cover":"soft moist skin", "limbs":"short paddling legs", "tail":"finned swimming tail"},
   signature=["breathing","head","tail"]),
 "pangolin": dict(habitat="land", mass=4.5, cls="mammal",
   parts={"head":"long pangolin snout, ant-eating tongue", "breathing":"lungs",
          "cover":"overlapping keratin scales", "limbs":"clawed digging legs", "tail":"scaled grasping tail"},
   signature=["cover","head","limbs"]),
 "eagle":    dict(habitat="air", mass=5.0, cls="bird",
   parts={"head":"hooked eagle beak", "breathing":"bird lungs and air sacs",
          "cover":"feathers", "limbs":"wings", "tail":"fan of tail feathers"},
   signature=["limbs","head","cover"]),
}
SLOTS = ["head","breathing","cover","limbs","tail"]

# what each part does in each habitat (1 = works, 0.5 = weak, 0 = fails)
JOB = {
 ("external gills","water"):1, ("external gills","land"):0, ("external gills","air"):0,
 ("lungs","water"):0.5, ("lungs","land"):1, ("lungs","air"):1,
 ("bird lungs and air sacs","water"):0.5, ("bird lungs and air sacs","land"):1, ("bird lungs and air sacs","air"):1,
 ("finned swimming tail","water"):1, ("finned swimming tail","land"):0.3, ("finned swimming tail","air"):0,
 ("scaled grasping tail","water"):0.5, ("scaled grasping tail","land"):1, ("scaled grasping tail","air"):0.3,
 ("fan of tail feathers","water"):0.2, ("fan of tail feathers","land"):0.5, ("fan of tail feathers","air"):1,
 ("short paddling legs","water"):1, ("short paddling legs","land"):0.6, ("short paddling legs","air"):0,
 ("clawed digging legs","water"):0.5, ("clawed digging legs","land"):1, ("clawed digging legs","air"):0,
 ("wings","water"):0, ("wings","land"):0.3, ("wings","air"):1,
 ("overlapping keratin scales","water"):0.8, ("overlapping keratin scales","land"):1, ("overlapping keratin scales","air"):0.2,
 ("soft moist skin","water"):1, ("soft moist skin","land"):0.3, ("soft moist skin","air"):0.2,
 ("feathers","water"):0.3, ("feathers","land"):0.8, ("feathers","air"):1,
 ("broad axolotl head, suction feeder","water"):1, ("broad axolotl head, suction feeder","land"):0.4, ("broad axolotl head, suction feeder","air"):0.2,
 ("long pangolin snout, ant-eating tongue","water"):0.2, ("long pangolin snout, ant-eating tongue","land"):1, ("long pangolin snout, ant-eating tongue","air"):0.3,
 ("hooked eagle beak","water"):0.4, ("hooked eagle beak","land"):0.8, ("hooked eagle beak","air"):1,
}

def parts_of(g):  return {s: ANIMALS[g[s]]["parts"][s] for s in SLOTS}

def possible(g, parents):
    """Hard gate: host owns body frame; gills never on a non-water creature (RC-R9-03);
    wings only from a bird host or as a declared license; flight above ~40 kg not modeled here."""
    hab = ANIMALS[g["host"]]["habitat"]
    p = parts_of(g)
    if p["breathing"] == "external gills" and hab != "water": return False
    if hab == "air" and g["limbs"] != g["host"]: return False      # a flyer keeps its own wings
    return True

def survival(g):
    hab = ANIMALS[g["host"]]["habitat"]; p = parts_of(g)
    return statistics.mean(JOB[(p[s], hab)] for s in SLOTS)

def realism(g, parents, budget=0):
    """Every part needs a job (RC-R9-12); parts below 0.5 in the habitat count as licenses."""
    hab = ANIMALS[g["host"]]["habitat"]; p = parts_of(g)
    weak = sum(1 for s in SLOTS if JOB[(p[s], hab)] < 0.5)
    over = max(0, weak - budget)
    return max(0.0, 1 - 0.35 * over)

def identity(g, parents):
    """Weakest parent's share of its own signature parts that are visible."""
    shares = []
    for a in parents:
        sig = ANIMALS[a]["signature"]
        shares.append(sum(1 for s in sig if g[s] == a) / len(sig))
    return min(shares)

W = dict(survival=0.4, realism=0.3, identity=0.3)
def fitness(g, parents):
    return _base_fitness(g, parents)

def _base_fitness(g, parents):
    if not possible(g, parents): return 0.0
    return W["survival"]*survival(g) + W["realism"]*realism(g, parents) + W["identity"]*identity(g, parents)

def random_genome(parents, rng):
    g = {"host": rng.choice(parents)}
    for s in SLOTS: g[s] = rng.choice(parents)
    return g

def mutate(g, parents, rng, rate=0.25):
    g = dict(g)
    for k in ["host"] + SLOTS:
        if rng.random() < rate: g[k] = rng.choice(parents)
    return g

def crossover(a, b, rng):
    return {k: (a[k] if rng.random() < 0.5 else b[k]) for k in a}

def evolve(parents, seed, pop=24, gens=15):
    rng = random.Random(seed)
    P = [random_genome(parents, rng) for _ in range(pop)]
    for _ in range(gens):
        P.sort(key=lambda g: fitness(g, parents), reverse=True)
        elite = P[:6]
        kids = [mutate(crossover(rng.choice(elite), rng.choice(elite), rng), parents, rng) for _ in range(pop-6)]
        P = elite + kids
    P.sort(key=lambda g: fitness(g, parents), reverse=True)
    return P[0]

def describe(g):
    return f"host={g['host']}; " + ", ".join(f"{s}:{ANIMALS[g[s]]['parts'][s]}" for s in SLOTS)

def exhaustive(parents):
    keys = ["host"] + SLOTS
    best = {}
    for combo in itertools.product(parents, repeat=len(keys)):
        g = dict(zip(keys, combo)); f = fitness(g, parents)
        h = g["host"]
        if f > best.get(h, (-1, None))[0]: best[h] = (f, g)
    return best

if __name__ == "__main__":
    for parents in (["axolotl","pangolin"], ["axolotl","pangolin","eagle"]):
        print("="*90); print("PARENTS:", " x ".join(parents))
        best = exhaustive(parents)
        for h,(f,g) in sorted(best.items(), key=lambda x:-x[1][0]):
            print(f"  best with host {h:9s} fitness {f:.3f}  surv {survival(g):.2f} real {realism(g,parents):.2f} ident {identity(g,parents):.2f}")
            print("     ", describe(g))
        wins = {}
        for seed in range(30):
            w = evolve(parents, seed); wins[w["host"]] = wins.get(w["host"],0)+1
        print("  GA winner host over 30 random runs:", wins)
    # old rule for comparison
    print("="*90)
    print("Old rule (equal structure -> heavier wins): host = pangolin (4.5 kg > 0.2 kg)")

def fitness_floor(g, parents):
    """Same score, but every parent must keep at least one signature part (hard floor)."""
    for a in parents:
        if not any(g[s] == a for s in ANIMALS[a]["signature"]): return 0.0
    return _base_fitness(g, parents)

if __name__ == "__main__":
    print("="*90); print("WITH IDENTITY FLOOR (each parent keeps >= 1 signature part)")
    globals()["fitness"] = fitness_floor  # swap scorer
    for parents in (["axolotl","pangolin"], ["axolotl","pangolin","eagle"]):
        best = exhaustive(parents)
        print("PARENTS:", " x ".join(parents))
        for h,(f,g) in sorted(best.items(), key=lambda x:-x[1][0]):
            print(f"  host {h:9s} fitness {f:.3f}  surv {survival(g):.2f} real {realism(g,parents):.2f} ident {identity(g,parents):.2f}")
            print("     ", describe(g))
