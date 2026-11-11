# Genesis — GPLE / Fauna F01 (P0)
Isolated experiment: **no Agora resident messages, no Cloudflare deploy, no production changes**.

## Modules / specialist agents
1. Biology: lifespan, energy, metabolism.
2. Behaviour: local perception, resource-seeking utility policy.
3. Learning: bounded, reward-dependent adaptation (**not RL yet**).
4. Reproduction: asexual baseline, heredity and bounded mutations (**not sexual reproduction yet**).
5. Ecology: resource consumption and regrowth.
6. Validation: invariants, reproducible experiments and metrics.

The coordinator is the deterministic Python simulation loop. These are logical algorithmic specialists, **not six independent LLMs**, and no background autonomy is claimed.

## Run (CPU, Python 3.10+)
```sh
python gple_f01/sim.py --seed 42 --ticks 250 --out f01-metrics.json
python -m unittest discover -s gple_f01 -p 'test_*.py' -v
```

## Kaggle execution
The manual GitHub Actions workflow `.github/workflows/gple-f01-kaggle.yml` supports CPU smoke-test and optional Kaggle notebook submission. It has **no cron**. The existing Agora Kaggle residents remain disabled. For Kaggle, set existing repository secrets KAGGLE_USERNAME and KAGGLE_API_TOKEN (or KAGGLE_KEY); the workflow uses a dedicated kernel ID `<username>/osixbay-gple-f01-lab`, and requires an explicit workflow input.

Kaggle execution must be confirmed by notebook status, not by successful submission alone. Generated output is `/kaggle/working/f01-metrics.json`. Do not enable GPU for this CPU baseline. The notebook is private; avoid entering real secrets in code or logs.

## Acceptance criteria and known limitations
- Replay with same seed produces identical metrics.
- Food, coordinates, population, energy remain bounded.
- Births, deaths, generations and consumption are tracked.
- F01 anatomy, canonical species properties, habitat geometry and actual game contracts still need to be mapped from authoritative Genesis documents before calling it F01 biologically accurate.
- No neural learning, sexual mating, predator/prey, diseases, age stages, or Godot integration yet.
- First gate: validate baseline across multiple seeds and measure extinction vs population explosion. Never claim an evolution result solely from a single simulation.
