# Priming Bulletin per Market

## Context

The platform runs a 4-market prediction-market experiment on a single binary
question ("Will Valdoria enter armed conflict with Norheim…"). Each market maps
to a scenario (C/A/B/D) with a fixed underlying `true_probability`
(C=0.50, A=0.75, B=0.25, D=0.65 — see `server/roles.py:87`).

Today the only narrative content is the per-**round** 3-tier `BulletinPayload`
(`public`/`analytical`/`intelligence`) authored in `server/scenarios.py` and
emitted in `round_started`. There is **nothing shown at the moment a market
opens**, and there is no concept of *multiple distinct information sources*.

The goal is a **priming bulletin** shown once at the **start of each market** to
prime participants. It presents a *range of differing information sources*
(news wire, social sentiment, official statement, independent analyst, polling/
markets, classified intel, field report) whose mix is **deliberately noisy but
leans, proportional to the market's `true_probability`, toward the correct YES/NO
direction** — so it carries genuine information without being a giveaway.

Per the user's decisions:
- **Combine** "new market-start element" + "extend the format" — a richer
  multi-source structure delivered at market open (the currently-unused
  `market_started` path), keeping the per-round bulletins intact.
- **Tier-gated** — same gating as `get_bulletin`: stage 1 and uninformed see
  public sources only; informed see all tiers.
- **Proportional lean** — YES:NO source ratio tracks `true_probability`, always
  with ≥1 contrarian source.
- **Wide variety per probability** *(user feedback)* — do not ship one fixed
  bulletin per scenario. Maintain a **pool of source variants** per probability
  level and draw a fresh mix per session/market, so different runs see different
  bulletins while the proportional lean is preserved.
- **Full-stack** — content + payload + server wiring + frontend display.

YES = conflict/escalation, NO = de-escalation/calm.

## Source format

A priming bulletin is a `headline` (the standing market question, restated) plus
a list of **sources**. Each source:

| field         | meaning                                                        |
|---------------|----------------------------------------------------------------|
| `source_type` | machine key: `wire` / `social` / `official` / `tabloid` / `analyst` / `markets` / `intel` / `field` |
| `name`        | display name, e.g. "Continental Wire Service", "@frontline_obs" |
| `tier`        | `public` / `analytical` / `intelligence` (drives gating + accent)|
| `lean`        | `yes` / `no` / `neutral` (drives the proportional mix; used in tests, not shown verbatim) |
| `text`        | one-to-two sentence frozen prose, same voice as existing `SCENARIOS` |

**Eight** archetype slots per bulletin *(public count raised 3 → 4 per user
feedback)*: 4 public (`wire`, `social`, `official`, `tabloid`), 2 analytical
(`analyst`, `markets`), 2 intelligence (`intel`, `field`).

### Variant pools (wide range per probability)

Instead of a single authored bulletin, each `(scenario, slot)` has a **pool of
candidate lines** tagged with a `lean`. At market start a deterministic draw
(seeded `"{session_id}:{market_id}:priming"`, same pattern as
`_draw_market_truth` in `orchestrator.py:476`) selects one line per slot. The
draw is constrained so the resulting YES:NO:neutral composition lands in the
target band for that probability (below) and always includes ≥1 contrarian
source. Determinism keeps it reproducible for analysis/tests; the pool is large
enough that different sessions/markets get visibly different mixes.

### Lean composition bands (the draw targets these per visibility level)

Bands hold both within the public-only subset (what uninformed see) and across
the full set (what informed see), each with a mandatory contrarian.

| Scenario | p    | public (4 slots) target | full (8 slots) target  |
|----------|------|-------------------------|------------------------|
| C (mkt1) | 0.50 | ~2 yes / ~2 no          | balanced, ±1           |
| A        | 0.75 | 3 yes / 1 no            | ~6 yes / 1 no / 1 neu  |
| B        | 0.25 | 1 yes / 3 no            | ~1 yes / 6 no / 1 neu  |
| D        | 0.65 | 3 yes / 1 no (noisier)  | ~5 yes / 3 no (noisy)  |

(D is intentionally noisier — matches its "high variance" narrative.)

### Representative pool lines (full pools authored at implementation)

Scenario A, `wire` slot (lean YES) candidates:
- "Continental Wire: Valdoria moves armored units toward the Karvač corridor as talks stall."
- "Wire desk: Norheim recalls its ambassador as border incidents multiply."

Scenario A, `official` slot (contrarian NO) candidates:
- "Valdorian Foreign Ministry: 'We remain committed to a diplomatic resolution.'"
- "Joint communiqué reaffirms both sides will keep back-channel talks open."

Scenario A, `tabloid` slot (new public source, lean YES) candidate:
- "The Daily Klaxon: 'WAR FOOTING' — leaked photos show troops massing overnight."

Each scenario provides pools for all 8 slots with several lines apiece, tagged
by lean and matching the de-escalation (B) / neutral (C) / mixed (D) narratives
already established in `SCENARIOS`.

## Backend changes

### `server/scenarios.py`
- Add a `PRIMING_POOLS: dict[str, dict]` keyed by `scenario_id` (A/B/C/D). Each
  holds a `headline` plus, per slot (`wire`/`social`/`official`/`tabloid`/
  `analyst`/`markets`/`intel`/`field`), a list of candidate
  `{name, lean, text}` lines (with the slot's fixed `tier`).
- Add `build_priming_bulletin(scenario_id, rng) -> dict`: for each slot, pick a
  candidate from its pool via `rng` subject to the scenario's composition band
  (above) and the ≥1-contrarian rule; returns
  `{"headline": ..., "sources": [ {source_type, name, tier, lean, text}, ...8 ]}`.
- Add `get_priming_bulletin(scenario_id, role_tier, stage, seed) -> dict` that
  builds the full bulletin from a seeded `random.Random(seed)` then applies the
  same gating as `get_bulletin` (`scenarios.py:128`):
  - validate `scenario_id`;
  - if `stage == 1` or `role_tier == "uninformed"` → keep only `public`-tier
    sources;
  - if `role_tier == "informed"` → keep all sources;
  - else `raise ValueError`.
  - Same `seed` (e.g. `f"{session_id}:{market_id}:priming"`) yields the same
    bulletin across all participants in a market and across reconnects.

### `server/events.py`
- Add `PrimingSourcePayload(BaseModel)`: `source_type, name, tier, lean, text`
  (all `str`; `tier`/`lean` as `Literal`s matching `BulletinPayload` style at
  `events.py:8`).
- Add `PrimingBulletinPayload(BaseModel)`: `headline: str`,
  `sources: list[PrimingSourcePayload]`.
- Add `priming: PrimingBulletinPayload` to `MarketStartedEvent`
  (`events.py:19`).

### `server/server.py`
- Build the seed once per market as `f"{session_id}:{market.id}:priming"` so the
  same drawn bulletin is reused everywhere for that market.
- `start_market` (`server.py:398`): in the per-role loop, call
  `get_priming_bulletin(market.scenario_id, role.role_tier, market.stage, seed)`
  and pass it as `priming=` on the `MarketStartedEvent` (`server.py:404`). Import
  the new helper alongside `get_bulletin` (`server.py:38`).
- `_build_state` (the dict returned at `server.py:317`, served by `/state`):
  add `"priming": get_priming_bulletin(market.scenario_id, role.role_tier,
  market.stage, f"{session_id}:{market.id}:priming")` when `market` and `role`
  exist (reuse the existing `market`/`role`/`bulletin` guard at `server.py:298`).
  This is the key wiring — `/state` is what the lobby polls and TradingView
  loads, so the priming bulletin (identical for the market thanks to the seed)
  survives navigation and reconnects with no extra socket handler strictly
  required.

## Frontend changes

### `client/src/types/events.ts`
- Add `PrimingSource` and `PrimingBulletin` interfaces mirroring the payloads.
- Add `priming` to the `market_started` payload shape (`events.ts:82`) and add
  `priming: PrimingBulletin | null` to `ParticipantState` (`events.ts:60`).

### `client/src/views/TradingView.tsx`
- Add a `MarketBriefing` presentational component rendering the priming
  `sources` as a stacked list of source cards, reusing the `IntelPanel` accent
  convention (`TradingView.tsx:22`) — accent/icon by `tier`
  (Eye/Shield/Lock as already imported, `TradingView.tsx:17`), with the
  `source_type`/`name` as the label and `text` as the body.
- Show it prominently when `state.phase === "market_open"` and no round is
  active yet (the pre-trading window the lobby lands in), and keep it rendered —
  collapsed/secondary — above the per-round `IntelPanel`s at
  `TradingView.tsx:527` once rounds begin, so priming context persists for the
  market.
- Carry `priming` through `onStateSync` (`TradingView.tsx:261`) and add a
  `market_started` socket handler (subscribe near `TradingView.tsx:277`) that
  stores `payload.priming` into state — so the briefing appears immediately on
  market open even between `/state` polls.

## Tests

Add `tests/test_priming_bulletin.py` (integration-style, matching existing
suite):
- All four scenarios present in `PRIMING_POOLS`; every slot has ≥2 candidate
  lines (so variety is real), and a built bulletin has exactly 8 sources with
  tier counts 4/2/2.
- `get_priming_bulletin` gating: `stage==1` and `uninformed` → only `public`
  sources (4); `informed` → all 8; bad `role_tier`/`scenario_id` → `ValueError`.
- Determinism: same `seed` → identical bulletin; differing seeds → at least some
  differing source lines across a sweep of seeds (proves the "wide range").
- Proportional lean: across a sweep of seeds, each scenario's YES-vs-NO counts
  stay within its composition band (and ≥1 contrarian always present), asserted
  off the `lean` field — checked for both the public subset and full set.

## Verification

1. `pytest -k priming -v` and full `pytest` — all green (35+ existing + new).
2. `npm --prefix client run build` succeeds (TS types compile).
3. Manual smoke (`./scripts/run_local_smoke.sh` plus a live run):
   - start backend + `npm run dev`, create a session, join as a participant;
   - `POST /admin/sessions/{id}/markets` (market 1 = scenario C) → confirm the
     participant lands on `/trade` in `market_open` and sees the balanced
     briefing with **public sources only** (stage-1 symmetric baseline);
   - advance to a later market with an informed role → confirm all 8 sources
     show and the YES/NO lean visibly tracks the scenario (A skews escalation,
     B skews calm);
   - create a second session and confirm the same scenario yields a visibly
     different source mix (variety), while the lean direction is unchanged.