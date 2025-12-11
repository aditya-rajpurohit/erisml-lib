"""
Example: Clinical triage ethics demo.

This script constructs a few EthicalFacts instances representing candidate
allocations of a scarce clinical resource, runs multiple ethics modules
over them, and uses the governance layer to select an option.

Run with:

    python -m erisml.examples.triage_ethics_demo

(assuming erisml is installed or the repo root is on PYTHONPATH)
"""

from __future__ import annotations

from typing import Dict, List

from erisml.ethics import (
    EthicalFacts,
    Consequences,
    RightsAndDuties,
    JusticeAndFairness,
    AutonomyAndAgency,
    ProceduralAndLegitimacy,
    EpistemicStatus,
    GovernanceConfig,
    select_option,
)
from erisml.ethics.judgement import EthicalJudgement
from erisml.ethics.modules.base import BaseEthicsModule
from erisml.ethics.modules.triage_em import CaseStudy1TriageEM


class RightsFirstEM(BaseEthicsModule):
    """
    Simple "rights-first" module.

    - If rights or explicit rules are violated, forbid the option.
    - Otherwise, assign a high but fixed score (0.8) and a simple rationale.

    This EM is deliberately minimal: the goal is to show how multiple EMs
    can disagree or align, not to encode a full deontic theory.
    """

    em_name: str = "rights_first_compliance"
    stakeholder: str = "patients_and_public"

    def evaluate(self, facts: EthicalFacts):
        rd = facts.rights_and_duties
        reasons: List[str] = []
        metadata: Dict[str, object] = {
            "violates_rights": rd.violates_rights,
            "violates_explicit_rule": rd.violates_explicit_rule,
        }

        if rd.violates_rights or rd.violates_explicit_rule:
            reasons.append(
                "Forbid: option violates rights and/or explicit rules, "
                "which take precedence over other considerations."
            )
            if rd.violates_rights:
                reasons.append("• violates_rights = True")
            if rd.violates_explicit_rule:
                reasons.append("• violates_explicit_rule = True")
            verdict = "forbid"
            score = 0.0
        else:
            reasons.append(
                "Rights and explicit rules are respected; no deontic veto "
                "from this module."
            )
            verdict = "prefer"
            score = 0.8  # fixed high score when rights are respected

        return verdict, score, reasons, metadata


def make_demo_options() -> Dict[str, EthicalFacts]:
    """
    Construct a few hard-coded EthicalFacts options for demonstration.

    These are intentionally simple and synthetic.
    """
    options: Dict[str, EthicalFacts] = {}

    # Option A: High benefit, high urgency, respects rights, prioritizes disadvantaged.
    options["allocate_to_patient_A"] = EthicalFacts(
        option_id="allocate_to_patient_A",
        consequences=Consequences(
            expected_benefit=0.9,
            expected_harm=0.2,
            urgency=0.9,
            affected_count=1,
        ),
        rights_and_duties=RightsAndDuties(
            violates_rights=False,
            has_valid_consent=True,
            violates_explicit_rule=False,
            role_duty_conflict=False,
        ),
        justice_and_fairness=JusticeAndFairness(
            discriminates_on_protected_attr=False,
            prioritizes_most_disadvantaged=True,
            distributive_pattern="maximin",
            exploits_vulnerable_population=False,
            exacerbates_power_imbalance=False,
        ),
        autonomy_and_agency=AutonomyAndAgency(
            has_meaningful_choice=True,
            coercion_or_undue_influence=False,
            can_withdraw_without_penalty=True,
            manipulative_design_present=False,
        ),
        procedural_and_legitimacy=ProceduralAndLegitimacy(
            followed_approved_procedure=True,
            stakeholders_consulted=True,
            decision_explainable_to_public=True,
            contestation_available=True,
        ),
        epistemic_status=EpistemicStatus(
            uncertainty_level=0.3,
            evidence_quality="high",
            novel_situation_flag=False,
        ),
        tags=["demo", "triage", "patient_A"],
    )

    # Option B: Moderate benefit, low urgency, but also prioritizes disadvantaged.
    options["allocate_to_patient_B"] = EthicalFacts(
        option_id="allocate_to_patient_B",
        consequences=Consequences(
            expected_benefit=0.7,
            expected_harm=0.2,
            urgency=0.5,
            affected_count=1,
        ),
        rights_and_duties=RightsAndDuties(
            violates_rights=False,
            has_valid_consent=True,
            violates_explicit_rule=False,
            role_duty_conflict=False,
        ),
        justice_and_fairness=JusticeAndFairness(
            discriminates_on_protected_attr=False,
            prioritizes_most_disadvantaged=True,
            distributive_pattern="maximin",
            exploits_vulnerable_population=False,
            exacerbates_power_imbalance=False,
        ),
        autonomy_and_agency=AutonomyAndAgency(
            has_meaningful_choice=True,
            coercion_or_undue_influence=False,
            can_withdraw_without_penalty=True,
            manipulative_design_present=False,
        ),
        procedural_and_legitimacy=ProceduralAndLegitimacy(
            followed_approved_procedure=True,
            stakeholders_consulted=False,
            decision_explainable_to_public=True,
            contestation_available=True,
        ),
        epistemic_status=EpistemicStatus(
            uncertainty_level=0.2,
            evidence_quality="medium",
            novel_situation_flag=False,
        ),
        tags=["demo", "triage", "patient_B"],
    )

    # Option C: Looks good on benefit/urgency, but violates an explicit rule.
    options["allocate_to_patient_C"] = EthicalFacts(
        option_id="allocate_to_patient_C",
        consequences=Consequences(
            expected_benefit=0.85,
            expected_harm=0.25,
            urgency=0.8,
            affected_count=1,
        ),
        rights_and_duties=RightsAndDuties(
            violates_rights=False,
            has_valid_consent=False,
            violates_explicit_rule=True,  # this triggers forbids
            role_duty_conflict=True,
        ),
        justice_and_fairness=JusticeAndFairness(
            discriminates_on_protected_attr=False,
            prioritizes_most_disadvantaged=False,
            distributive_pattern="utilitarian",
            exploits_vulnerable_population=False,
            exacerbates_power_imbalance=False,
        ),
        autonomy_and_agency=AutonomyAndAgency(
            has_meaningful_choice=False,
            coercion_or_undue_influence=True,
            can_withdraw_without_penalty=False,
            manipulative_design_present=True,
        ),
        procedural_and_legitimacy=ProceduralAndLegitimacy(
            followed_approved_procedure=False,
            stakeholders_consulted=False,
            decision_explainable_to_public=False,
            contestation_available=False,
        ),
        epistemic_status=EpistemicStatus(
            uncertainty_level=0.6,
            evidence_quality="low",
            novel_situation_flag=True,
        ),
        tags=["demo", "triage", "patient_C"],
    )

    return options


def main() -> None:
    # 1. Build demo options.
    options = make_demo_options()

    # 2. Instantiate EMs.
    triage_em = CaseStudy1TriageEM()
    rights_em = RightsFirstEM()

    ems = [triage_em, rights_em]

    # 3. Collect judgements per option.
    judgements_by_option: Dict[str, List[EthicalJudgement]] = {}

    for option_id, facts in options.items():
        judgements: List[EthicalJudgement] = []
        for em in ems:
            j = em.judge(facts)
            judgements.append(j)
        judgements_by_option[option_id] = judgements

    # 4. Define a simple governance config.
    cfg = GovernanceConfig(
        # equal stakeholder weights (both EMs use "patients_and_public")
        stakeholder_weights={},
        # give rights-first EM a bit more weight, but both matter
        em_weights={
            "rights_first_compliance": 1.5,
            "case_study_1_triage": 1.0,
        },
        veto_ems=["rights_first_compliance"],  # rights EM has veto power
        min_score_threshold=0.0,
        require_non_forbidden=True,
        tie_breaker="first",
    )

    # 5. Use governance to select an option.
    outcome = select_option(
        judgements_by_option=judgements_by_option,
        cfg=cfg,
        candidate_ids=list(options.keys()),
        baseline_option_id=None,
    )

    # 6. Pretty-print results.
    print("\n=== Triage Ethics Demo ===\n")
    print("Candidate options:")
    for opt_id in options:
        print(f"  - {opt_id}")
    print()

    for opt_id, judgements in judgements_by_option.items():
        print(f"--- Option: {opt_id} ---")
        for j in judgements:
            print(
                f"[EM={j.em_name:<24}] verdict={j.verdict:<14} score={j.normative_score:.3f}"
            )
            for r in j.reasons:
                print(f"    - {r}")
        agg = outcome.aggregated_judgements[opt_id]
        print(
            f"[AGG governance] verdict={agg.verdict:<14} score={agg.normative_score:.3f}"
        )
        for r in agg.reasons:
            print(f"    * {r}")
        print()

    print("=== Governance Outcome ===")
    print(f"Selected option: {outcome.selected_option_id!r}")
    print(f"Ranked options: {outcome.ranked_options}")
    print(f"Forbidden options: {outcome.forbidden_options}")
    print("Rationale:")
    print(f"  {outcome.rationale}")
    print()


if __name__ == "__main__":
    main()
