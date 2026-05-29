from __future__ import annotations

import random
from typing import Any


ScenarioRound = dict[str, str]


def _rounds(public: list[str], analytical: list[str], intelligence: list[str]) -> dict[int, ScenarioRound]:
    out: dict[int, ScenarioRound] = {}
    for idx in range(6):
        out[idx + 1] = {
            "public": public[idx],
            "analytical": analytical[idx],
            "intelligence": intelligence[idx],
        }
    return out


SCENARIOS: dict[str, dict[int, ScenarioRound]] = {
    "A": _rounds(
        public=[
            "Valdoria and Norheim exchange sharp diplomatic statements.",
            "Border patrol movements are reported by local media.",
            "Regional mediators call for restraint while tensions persist.",
            "A military spokesperson announces defensive readiness measures.",
            "International observers note rising uncertainty in the corridor.",
            "Outcome bulletin issued after market close.",
        ],
        analytical=[
            "Trade logistics are slowing and public communication has hardened.",
            "Coordination channels remain open, but confidence is fragile.",
            "Incident reports are clustered near high-friction zones.",
            "Public language from both sides is less conciliatory than earlier.",
            "Signals remain mixed, with pressure concentrated around security topics.",
            "Post-outcome commentary for archive records.",
        ],
        intelligence=[
            "Internal brief indicates rapid response units are on heightened notice.",
            "Confidential contacts describe elevated readiness in command structures.",
            "A restricted memo references contingency activation discussions.",
            "Analysts flag unusual synchronization in logistical planning.",
            "Classified chatter suggests decision windows are narrowing.",
            "Outcome intelligence addendum archived for admin review.",
        ],
    ),
    "B": _rounds(
        public=[
            "Valdoria and Norheim reopen a diplomatic working group.",
            "Humanitarian corridors are discussed in a joint statement.",
            "State media from both countries reduces inflammatory tone.",
            "Regional partners host a closed-door de-escalation forum.",
            "A ceasefire draft framework is circulated informally.",
            "Outcome bulletin issued after market close.",
        ],
        analytical=[
            "Negotiation signals appear durable but operational frictions remain.",
            "Cross-border incidents are lower than recent baseline chatter.",
            "Political messaging is more consistent with compromise incentives.",
            "Stakeholders report progress on procedural confidence-building steps.",
            "Residual risk persists in contested districts despite calmer rhetoric.",
            "Post-outcome commentary for archive records.",
        ],
        intelligence=[
            "Private cables indicate both leadership teams are prioritizing de-escalation.",
            "Internal notes suggest military planners received stand-down guidance.",
            "Restricted observers report fewer high-alert deployments.",
            "Classified assessments emphasize political costs of renewed escalation.",
            "Secure channels report broad support for maintaining current calm.",
            "Outcome intelligence addendum archived for admin review.",
        ],
    ),
    "C": _rounds(
        public=[
            "No major geopolitical developments are confirmed today.",
            "Routine diplomatic updates continue without notable shifts.",
            "Public commentary remains balanced across major outlets.",
            "Officials repeat prior positions with limited new detail.",
            "International monitors report a stable information environment.",
            "Outcome bulletin issued after market close.",
        ],
        analytical=[
            "Public data streams are broadly neutral with low directional signal.",
            "Observed events are consistent with ordinary background volatility.",
            "No clear leading indicator dominates the current evidence set.",
            "Short-horizon interpretation remains sensitive to small shocks.",
            "Assessment confidence is moderate due to signal symmetry.",
            "Post-outcome commentary for archive records.",
        ],
        intelligence=[
            "Internal traffic does not indicate a decisive strategic pivot.",
            "Confidential intercepts are heterogeneous and hard to rank.",
            "Restricted briefs emphasize uncertainty rather than trend certainty.",
            "Operational reports show routine movement patterns.",
            "Classified updates continue to support a balanced view.",
            "Outcome intelligence addendum archived for admin review.",
        ],
    ),
    "D": _rounds(
        public=[
            "Valdoria announces a limited security consultation with allies.",
            "Norheim responds with a formal protest and call for talks.",
            "A maritime inspection incident draws international attention.",
            "Emergency envoys travel to the region for direct consultations.",
            "Both governments issue statements warning against miscalculation.",
            "Outcome bulletin issued after market close.",
        ],
        analytical=[
            "The consultation signal increases strategic salience of near-term decisions.",
            "Escalation and dialogue channels are both active, raising variance.",
            "Event sequencing suggests heightened sensitivity to tactical incidents.",
            "External mediation may dampen immediate escalation pressure.",
            "Current evidence indicates a compressed but still uncertain decision path.",
            "Post-outcome commentary for archive records.",
        ],
        intelligence=[
            "Secure reports indicate selective mobilization near critical assets.",
            "Private interlocutors mention unresolved command-level disagreements.",
            "Restricted analysis flags elevated risk from signaling misreads.",
            "Sensitive communications show competing factions shaping policy timing.",
            "Classified monitoring points to fragile deterrence stability.",
            "Outcome intelligence addendum archived for admin review.",
        ],
    ),
}


HEADLINE = "Will Valdoria enter armed conflict with Norheim within 12 months of the Karvač incident?"

PRIMING_POOLS: dict[str, dict] = {
    "A": {
        "headline": HEADLINE,
        "slots": {
            "wire": {
                "tier": "public", "lean": "yes",
                "candidates": [
                    {"name": "Continental Wire Service", "text": "Valdoria moves armored units toward the Karvač corridor as diplomatic talks stall."},
                    {"name": "Continental Wire Service", "text": "Norheim recalls its ambassador as border incidents multiply."},
                    {"name": "Continental Wire Service", "text": "Valdorian forces conduct unannounced live-fire exercises near the contested boundary."},
                ],
            },
            "social": {
                "tier": "public", "lean": "yes",
                "candidates": [
                    {"name": "@frontline_obs", "text": "Locals near the border report troop movements not seen since the last crisis."},
                    {"name": "@valdoria_watch", "text": "Videos circulating show military convoys heading east — unverified but widespread."},
                    {"name": "@conflict_tracker", "text": "#KarvacCrisis trending in both capitals as border tensions sharpen."},
                ],
            },
            "official": {
                "tier": "public", "lean": "no",
                "candidates": [
                    {"name": "Valdorian Foreign Ministry", "text": "We remain committed to a diplomatic resolution and call for de-escalation."},
                    {"name": "Joint Communiqué", "text": "Both sides reaffirm they will keep back-channel talks open."},
                    {"name": "State Department", "text": "Both parties have agreed to a 72-hour cooling period pending further consultations."},
                ],
            },
            "tabloid": {
                "tier": "public", "lean": "yes",
                "candidates": [
                    {"name": "The Daily Klaxon", "text": "'WAR FOOTING' — leaked photos purport to show troops massing overnight near Karvač."},
                    {"name": "Karvač Chronicle", "text": "Editorial: analysts warn the point of no return is fast approaching."},
                    {"name": "Evening Standard Extra", "text": "Valdoria has crossed a threshold, senior analysts tell this paper."},
                ],
            },
            "analyst": {
                "tier": "analytical", "lean": "yes",
                "candidates": [
                    {"name": "Meridian Risk Advisory", "text": "Probability of kinetic exchange elevated — recent logistical shifts are consistent with pre-conflict deployments."},
                    {"name": "Stratford Group", "text": "This type of deployment historically precedes escalation in 70% of comparable cases."},
                    {"name": "Regional Security Quarterly", "text": "Command-level decisions appear to be outpacing diplomatic channels by a significant margin."},
                ],
            },
            "markets": {
                "tier": "analytical", "lean": "yes",
                "candidates": [
                    {"name": "Prediction Exchange Digest", "text": "Conflict probability trading at 74% — up 18 points over 48 hours."},
                    {"name": "Regional Insurance Markets", "text": "Premiums for regional assets have tripled; markets pricing a sustained conflict risk spike."},
                    {"name": "Sovereign Debt Monitor", "text": "Valdorian bond spreads widening at rates consistent with pre-conflict periods in comparable crises."},
                ],
            },
            "intel": {
                "tier": "intelligence", "lean": "yes",
                "candidates": [
                    {"name": "Restricted Assessment", "text": "Internal brief indicates rapid-response units are on heightened notice with compressed authorization chains."},
                    {"name": "Classified Contact", "text": "Confidential sources describe elevated readiness in senior command structures."},
                    {"name": "Eyes-Only Memo", "text": "Decision timelines appear to have compressed from weeks to days according to two independent assessments."},
                ],
            },
            "field": {
                "tier": "intelligence", "lean": "yes",
                "candidates": [
                    {"name": "Field Report Alpha", "text": "Forward supply depots receiving logistics at above-maintenance surge levels."},
                    {"name": "Ground Source Kilo", "text": "Officers in theater describe current posture as operational rather than defensive."},
                    {"name": "Asset Report Sierra", "text": "Troop rotations have shifted from scheduled to surge cadence at three monitored sites."},
                ],
            },
        },
    },
    "B": {
        "headline": HEADLINE,
        "slots": {
            "wire": {
                "tier": "public", "lean": "no",
                "candidates": [
                    {"name": "Continental Wire Service", "text": "Valdoria and Norheim announce a joint de-escalation working group meeting this week."},
                    {"name": "Continental Wire Service", "text": "Both governments confirm diplomatic back-channels remain active and productive."},
                    {"name": "Continental Wire Service", "text": "Troop withdrawal confirmed from contested zone pending further talks."},
                ],
            },
            "social": {
                "tier": "public", "lean": "no",
                "candidates": [
                    {"name": "@peace_monitor", "text": "Civil society groups in both capitals holding joint peace vigils — turnout higher than expected."},
                    {"name": "@norheim_news", "text": "Footage of soldiers returning to barracks circulates widely; cautious public optimism emerging."},
                    {"name": "@valdoria_updates", "text": "Bilateral cultural exchange event proceeds uninterrupted — widely read as a symbolic signal."},
                ],
            },
            "official": {
                "tier": "public", "lean": "no",
                "candidates": [
                    {"name": "Joint Communiqué", "text": "Both states reaffirm commitment to the Karvač Framework Agreement and renounce unilateral action."},
                    {"name": "Valdorian Prime Minister", "text": "Military options are not on the table at this time; we seek a negotiated outcome."},
                    {"name": "State Department", "text": "Mediators report substantial progress in overnight sessions; a framework draft is circulating."},
                ],
            },
            "tabloid": {
                "tier": "public", "lean": "yes",
                "candidates": [
                    {"name": "The Daily Klaxon", "text": "Don't be fooled — critics say de-escalation diplomacy is cover for quiet rearmament."},
                    {"name": "Evening Dispatch", "text": "Hardliners in both capitals warn the de-escalation deal will collapse within days."},
                    {"name": "Karvač Chronicle", "text": "Border communities remain unconvinced as military equipment stays in place despite talks."},
                ],
            },
            "analyst": {
                "tier": "analytical", "lean": "no",
                "candidates": [
                    {"name": "Meridian Risk Advisory", "text": "Both governments face strong domestic incentives to avoid escalation this quarter."},
                    {"name": "Stratford Group", "text": "Diplomatic sequencing is consistent with durable settlement patterns observed in prior crises."},
                    {"name": "Regional Security Quarterly", "text": "Leadership transitions in both capitals favour compromise over confrontation at this juncture."},
                ],
            },
            "markets": {
                "tier": "analytical", "lean": "no",
                "candidates": [
                    {"name": "Prediction Exchange Digest", "text": "Conflict probability at 22% — down 12 points since framework talks resumed."},
                    {"name": "Regional Insurance Markets", "text": "Travel insurance rates for the region have normalised; markets pricing a stable short-term outlook."},
                    {"name": "Sovereign Debt Monitor", "text": "Sovereign bond spreads for both nations compressing toward pre-tension levels."},
                ],
            },
            "intel": {
                "tier": "intelligence", "lean": "no",
                "candidates": [
                    {"name": "Restricted Assessment", "text": "Private cables indicate both leadership teams are internally prioritising de-escalation."},
                    {"name": "Classified Contact", "text": "Internal notes suggest military planners have received stand-down guidance at the operational level."},
                    {"name": "Eyes-Only Memo", "text": "Political costs of renewed escalation assessed as prohibitive by senior advisers in both capitals."},
                ],
            },
            "field": {
                "tier": "intelligence", "lean": "no",
                "candidates": [
                    {"name": "Field Report Alpha", "text": "Fewer high-alert deployments observed at three independently monitored forward positions."},
                    {"name": "Ground Source Kilo", "text": "Forward command posts are returning to standard peacetime staffing levels."},
                    {"name": "Asset Report Sierra", "text": "Logistical draw-down at border positions is consistent with stand-down orders."},
                ],
            },
        },
    },
    "C": {
        "headline": HEADLINE,
        "slots": {
            "wire": {
                "tier": "public", "lean": "yes",
                "candidates": [
                    {"name": "Continental Wire Service", "text": "Border patrol activity elevated following an overnight incident in the disputed corridor."},
                    {"name": "Continental Wire Service", "text": "Valdoria lodges a formal protest over an alleged airspace incursion near Karvač."},
                    {"name": "Continental Wire Service", "text": "Joint commission talks suspended pending clarification of latest incident reports."},
                ],
            },
            "social": {
                "tier": "public", "lean": "no",
                "candidates": [
                    {"name": "@conflict_tracker", "text": "Market indicators and diplomatic signals pointing in opposite directions — genuinely mixed picture."},
                    {"name": "@norheim_news", "text": "Officials call for calm amid contradictory reports; public reaction subdued."},
                    {"name": "@valdoria_watch", "text": "Observers split on whether latest moves are defensive posturing or something more serious."},
                ],
            },
            "official": {
                "tier": "public", "lean": "no",
                "candidates": [
                    {"name": "Joint Statement", "text": "Both foreign ministries call for de-escalation and confirm consultations are ongoing."},
                    {"name": "Karvač Oversight Commission", "text": "Situation remains sensitive but manageable; we urge restraint from all parties."},
                    {"name": "Joint Statement", "text": "Neither party has initiated military action; talks will continue through existing channels."},
                ],
            },
            "tabloid": {
                "tier": "public", "lean": "yes",
                "candidates": [
                    {"name": "The Daily Klaxon", "text": "'Edge of the knife' — the situation could tip either way within days, analysts warn."},
                    {"name": "Karvač Chronicle", "text": "Experts divided as pressure mounts on both governments to show resolve."},
                    {"name": "Evening Dispatch", "text": "No one knows — deep uncertainty grips the region as signals remain contradictory."},
                ],
            },
            "analyst": {
                "tier": "analytical", "lean": "neutral",
                "candidates": [
                    {"name": "Meridian Risk Advisory", "text": "Probability remains near 50% — available evidence is insufficient to shift the prior meaningfully."},
                    {"name": "Stratford Group", "text": "Current indicators are consistent with either resolution or escalation; no dominant signal."},
                    {"name": "Regional Security Quarterly", "text": "Balanced risk assessment — monitoring closely without a directional call at this stage."},
                ],
            },
            "markets": {
                "tier": "analytical", "lean": "neutral",
                "candidates": [
                    {"name": "Prediction Exchange Digest", "text": "Conflict probability trading in a narrow 45–55% band this week — genuine uncertainty priced in."},
                    {"name": "Regional Insurance Markets", "text": "Market-implied volatility elevated but without directional bias; uncertainty priced symmetrically."},
                    {"name": "Sovereign Debt Monitor", "text": "No sustained directional move in regional risk assets; implied probability near parity."},
                ],
            },
            "intel": {
                "tier": "intelligence", "lean": "neutral",
                "candidates": [
                    {"name": "Restricted Assessment", "text": "Internal traffic does not indicate a decisive strategic pivot in either direction at this time."},
                    {"name": "Classified Contact", "text": "Confidential intercepts are heterogeneous — no dominant signal trend is detectable."},
                    {"name": "Eyes-Only Memo", "text": "Restricted briefs emphasise uncertainty; senior analysts disagree on direction."},
                ],
            },
            "field": {
                "tier": "intelligence", "lean": "neutral",
                "candidates": [
                    {"name": "Field Report Alpha", "text": "Routine movement patterns observed at all monitored positions; no anomalous concentrations."},
                    {"name": "Ground Source Kilo", "text": "Equipment levels at monitored sites unchanged from the prior week."},
                    {"name": "Asset Report Sierra", "text": "Standard rotation schedules maintained — no surge indicators detected."},
                ],
            },
        },
    },
    "D": {
        "headline": HEADLINE,
        "slots": {
            "wire": {
                "tier": "public", "lean": "yes",
                "candidates": [
                    {"name": "Continental Wire Service", "text": "Valdoria announces new security consultations, citing a 'changed threat environment.'"},
                    {"name": "Continental Wire Service", "text": "Naval patrol frequency increased in the disputed maritime zone without prior notice."},
                    {"name": "Continental Wire Service", "text": "Valdoria signals readiness to escalate if provocations continue, foreign ministry says."},
                ],
            },
            "social": {
                "tier": "public", "lean": "yes",
                "candidates": [
                    {"name": "@frontline_obs", "text": "Unconfirmed reports of a troop build-up shared widely — difficult to verify but significant traction."},
                    {"name": "@valdoria_watch", "text": "Public mood hardening; support for a firm stance growing in latest informal polling."},
                    {"name": "@conflict_tracker", "text": "Social media in both nations trending hawkish despite official statements urging calm."},
                ],
            },
            "official": {
                "tier": "public", "lean": "no",
                "candidates": [
                    {"name": "Norheim Foreign Ministry", "text": "A diplomatic resolution remains achievable and is our strong preference."},
                    {"name": "Valdorian Spokesperson", "text": "Security consultations are precautionary and should not be read as provocative."},
                    {"name": "Regional Mediator", "text": "Both parties remain in contact — the diplomatic window has not closed."},
                ],
            },
            "tabloid": {
                "tier": "public", "lean": "yes",
                "candidates": [
                    {"name": "The Daily Klaxon", "text": "'War drums' — analysts warn the window for diplomacy is narrowing fast."},
                    {"name": "Karvač Chronicle", "text": "Officials privately brace for the worst even as public statements soften tensions."},
                    {"name": "Evening Dispatch", "text": "'Powder keg' — latest security moves draw international alarm and emergency consultations."},
                ],
            },
            "analyst": {
                "tier": "analytical", "lean": "yes",
                "candidates": [
                    {"name": "Meridian Risk Advisory", "text": "Conflict probability updated upward — security consultations historically precede escalation."},
                    {"name": "Stratford Group", "text": "Despite diplomatic statements, operational indicators lean toward confrontation."},
                    {"name": "Regional Security Quarterly", "text": "Compressed decision timelines materially increase accidental escalation risk."},
                ],
            },
            "markets": {
                "tier": "analytical", "lean": "yes",
                "candidates": [
                    {"name": "Prediction Exchange Digest", "text": "Conflict probability at 63%, up 8 points since the security consultation announcement."},
                    {"name": "Regional Insurance Markets", "text": "Equity markets showing risk-off movement; geopolitical premium being priced in."},
                    {"name": "Intelligence-Linked Exchanges", "text": "Prediction markets citing operational signals are trading at 65%."},
                ],
            },
            "intel": {
                "tier": "intelligence", "lean": "yes",
                "candidates": [
                    {"name": "Restricted Assessment", "text": "Selective mobilisation observed near critical strategic assets in the Karvač region."},
                    {"name": "Classified Contact", "text": "Private interlocutors mention unresolved command-level disagreements on timing."},
                    {"name": "Eyes-Only Memo", "text": "Deterrence stability described as 'fragile' by two independent classified assessments."},
                ],
            },
            "field": {
                "tier": "intelligence", "lean": "yes",
                "candidates": [
                    {"name": "Field Report Alpha", "text": "Logistics tempo at two forward positions elevated above maintenance baseline."},
                    {"name": "Ground Source Kilo", "text": "Officers describe current planning horizon as weeks, not months."},
                    {"name": "Asset Report Sierra", "text": "Equipment pre-positioning observed at sites associated with rapid deployment capability."},
                ],
            },
        },
    },
}

_SLOT_ORDER = ("wire", "social", "official", "tabloid", "analyst", "markets", "intel", "field")


def build_priming_bulletin(scenario_id: str, rng: random.Random) -> dict[str, Any]:
    pool = PRIMING_POOLS[scenario_id]
    sources = []
    for source_type in _SLOT_ORDER:
        slot = pool["slots"][source_type]
        candidate = rng.choice(slot["candidates"])
        sources.append({
            "source_type": source_type,
            "name": candidate["name"],
            "tier": slot["tier"],
            "lean": slot["lean"],
            "text": candidate["text"],
        })
    return {"headline": pool["headline"], "sources": sources}


def get_priming_bulletin(scenario_id: str, role_tier: str, stage: int, seed: str) -> dict[str, Any]:
    if scenario_id not in PRIMING_POOLS:
        raise ValueError(f"Unknown scenario_id={scenario_id!r}")
    rng = random.Random(seed)
    bulletin = build_priming_bulletin(scenario_id, rng)
    if stage == 1 or role_tier == "uninformed":
        bulletin["sources"] = [s for s in bulletin["sources"] if s["tier"] == "public"]
    elif role_tier == "informed":
        pass
    else:
        raise ValueError(f"Unknown role_tier={role_tier!r}")
    return bulletin


def get_bulletin(scenario_id: str, round_number: int, role_tier: str, stage: int) -> dict[str, Any]:
    if scenario_id not in SCENARIOS:
        raise ValueError(f"Unknown scenario_id={scenario_id}")
    if round_number not in SCENARIOS[scenario_id]:
        raise ValueError(f"Unknown round_number={round_number}")
    bullet = SCENARIOS[scenario_id][round_number]

    if stage == 1:
        return {"public": bullet["public"], "analytical": None, "intelligence": None}

    if role_tier == "uninformed":
        return {"public": bullet["public"], "analytical": None, "intelligence": None}
    if role_tier == "informed":
        return {
            "public": bullet["public"],
            "analytical": bullet["analytical"],
            "intelligence": bullet["intelligence"],
        }
    raise ValueError(f"Unknown role_tier={role_tier}")
