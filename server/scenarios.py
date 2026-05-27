from __future__ import annotations

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
    if role_tier == "semi_informed":
        return {"public": bullet["public"], "analytical": bullet["analytical"], "intelligence": None}
    if role_tier == "insider":
        return {
            "public": bullet["public"],
            "analytical": bullet["analytical"],
            "intelligence": bullet["intelligence"],
        }
    raise ValueError(f"Unknown role_tier={role_tier}")

