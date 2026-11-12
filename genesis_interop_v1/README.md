# DM-091 — OSIXBAY Genesis intermodule contract (proposal v1)

**Status:** offline draft, not canonical. No runtime integration, merge, deploy, or live World modification.

## Purpose
Allow GPLE, GLPE, World Engine and Godot client teams to develop independently without silently inventing world geography, creature identities or resource stocks.

## Envelope
Every message uses a stable schema `osixbay.genesis.interop.v1`, `world_id`, `world_version`, deterministic `seed`, monotonically managed integer `tick` (ordering must be enforced by the authoritative integrator), `provenance` and `kind`.

- **Snapshots** have unique `patches`, `entities`, finite nonnegative `stocks`, a `transform` that is `null` for lab fixtures.
- **Events** have unique `event_id` and `idempotency_key`; deduplication and monotonic tick ordering must be implemented in World Engine, not claimed by this stateless validator.
- **Positions** use metres with Godot XZ horizontal / Y vertical and are forbidden in synthetic fixtures. A real export needs a versioned source scene, nonempty scene hash, origin and cell size. The validator does **not** authenticate the hash or prove provenance; this requires an authorized export.
- **Resource units** remain explicitly `abstract_mass` or `abstract_water`. They are not calories, kilograms or litres.
- **Communication** exposes channel, utterance ID and recipient perception only. No omniscient translation is allowed.
- **Authority:** client messages cannot claim `authoritative_world`. The current validator checks shape and declared provenance only; authentication, permissions, transaction processing and snapshot provenance remain future gates.

## Ownership
| Producer | Consumer | Authority |
| --- | --- | --- |
| World Engine | GPLE + Godot | patch IDs, terrain/biomes, stock, simulation tick, persistence |
| GPLE | World Engine + Godot | proposed organism updates/events; no independent resource minting |
| GLPE | AI + Godot | perceived messages, learner memory; no hidden canonical meaning |
| Godot | presentation only | cameras, animations, UI; no world stock writes |

## Next integration gates
1. Compare this contract with existing `gple_f01/scene_contract_p0.py` and canonical source `genesis/fauna01` without breaking the existing scene schema.
2. Prove snapshot/event identity and idempotency in tests against World Engine adapter.
3. Verify real S03 coordinate transform and irregular playable mask from actual Godot export. Synthetic fixture coordinates must never be treated as real.
4. Add rollback, ownership, permissions and replay validation before integrating.
5. Review with Andrea; the current document is **a proposal**, not authorization to merge or deploy.

Run offline tests: `python -m unittest discover -s genesis_interop_v1 -p 'test_*.py' -v`
