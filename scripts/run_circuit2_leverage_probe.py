"""Dev only (seeds >= 100): does the choice of procedure change what the engine learns?"""
import sys, random, statistics, time
sys.path.insert(0, '.')
from genesis import circuit_tasks as t, circuit_engine as e, circuit_procedure as cp

def improved_tried(engine, tasks, budget, solutions, procedure, tried, generation):
    found = e.proposals(engine, solutions); flags = e.composed_flags(engine, solutions)
    ranked = []
    for comp, sup in found:
        pr, adm, _ = cp.run(procedure, cp.traits_of(sup, comp.arity, len(comp.steps), flags.get(comp.key, False)))
        if adm: ranked.append((-pr, comp.key, comp))
    ranked.sort(key=lambda x: x[:2])
    before = e.measure(solutions); best = None
    for i, (_, _, comp) in enumerate(ranked[:tried]):
        wider = e.Engine(engine.components + [e.Component(f"g{generation}c{i}", comp.arity, comp.steps)])
        cand = e.refitted(wider, e.attempt(wider, tasks, budget), e.SEED_PROCEDURE)
        sol = e.attempt(cand, tasks, budget); after = e.measure(sol)
        if (after[0], -after[1]) > (before[0], -before[1]) and (best is None or (after[0], -after[1]) > best[0]):
            best = ((after[0], -after[1]), cand, sol)
    return (best[1], best[2], len(found), len(ranked)) if best else (engine, solutions, len(found), len(ranked))

def lineage(learn, held, budget, procedure, tried, gens):
    eng = e.Engine(); sol = e.attempt(eng, learn, budget); props = []
    for g in range(1, gens + 1):
        eng, sol, nf, na = improved_tried(eng, learn, budget, sol, procedure, tried, g); props.append(nf)
    return e.measure(sol)[0], e.measure(e.attempt(eng, held, budget))[0], len(eng.components), props


def main() -> int:
    for max_in, budget, tried in ((4, 16384, 2), (4, 16384, 3), (4, 65536, 2)):
        for seed in (100, 101, 102):
            learn = [x for x in t.circuit2_suite(t.LEARN, seed) if x.inputs <= max_in]; held = t.circuit2_suite(t.HELD_OUT, seed)
            t0 = time.time()
            res = [lineage(learn, held, budget, cp.seed_procedure(), tried, 6)]
            rng = random.Random(f"dev|{seed}")
            for _ in range(10):
                p = cp.seed_procedure()
                for _ in range(3): p = cp.mutate(p, rng)
                res.append(lineage(learn, held, budget, p, tried, 6))
            held_scores = [r[1] for r in res]
            print(f"max_in={max_in} budget={budget} tried={tried} seed={seed} learn={len(learn)} held={len(held)} | seed_proc held={res[0][1]} lib={res[0][2]} props={res[0][3]} | mutants held={held_scores[1:]} | {round(time.time()-t0)}s", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
