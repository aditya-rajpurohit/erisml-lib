"""
Case Study 1: Clinical triage ethics module(s).

This module provides a reference implementation of an ethics-only triage
module for allocating scarce clinical resources (e.g., ICU beds).

It operates *only* on EthicalFacts and returns an EthicalJudgement. All
clinical, legal, and statistical complexity is upstream in the construction
of EthicalFacts.

Version: 0.2 (EthicalDomains update)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from ..facts import EthicalFacts
from ..judgement import Verdict
from .base import BaseEthicsModule


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp x into [lo, hi]."""
    return lo if x < lo else hi if x > hi else x


@dataclass
class CaseStudy1TriageEM(BaseEthicsModule):
    """
    Ethics-only triage module for Case Study 1 (clinical resource allocation).

    This module:

    - Enforces hard deontic constraints on rights and explicit rules.
    - Computes a composite normative score based on:

        * expected benefit (w_benefit),
        * (1 - expected harm) (w_harm),
        * urgency (w_urgency),
        * priority for the most disadvantaged (w_disadvantaged),
        * autonomy and agency (w_autonomy),
        * procedural legitimacy (w_procedural).

    - Penalizes options that discriminate on protected attributes or exploit
      vulnerable populations.
    - Down-weights options under high epistemic uncertainty.

    All inputs come from EthicalFacts; there is no direct access to ICD codes,
    vitals, or other raw domain artifacts.
    """

    em_name: str = "case_study_1_triage"
    stakeholder: str = "patients_and_public"

    # Weights over ethical dimensions (sum does not need to be 1.0).
    w_benefit: float = 0.30
    w_harm: float = 0.20
    w_urgency: float = 0.20
    w_disadvantaged: float = 0.15
    w_autonomy: float = 0.10
    w_procedural: float = 0.05

    # Penalties and uncertainty handling.
    fairness_penalty: float = 0.0  # set to e.g. 0.4 to strongly penalize unfair options
    exploitation_penalty: float = 0.4
    discrimination_penalty: float = 0.5
    power_imbalance_penalty: float = 0.3

    max_uncertainty_penalty: float = 0.4
    """
    At uncertainty_level = 1.0, the final score is multiplied by (1 - max_uncertainty_penalty).
    At uncertainty_level = 0.0, there is no penalty.
    """

    def evaluate(
        self,
        facts: EthicalFacts,
    ) -> Tuple[Verdict, float, List[str], Dict[str, object]]:
        """
        Core normative logic.

        Returns:
            (verdict, normative_score, reasons, metadata)
        """
        reasons: List[str] = []
        meta: Dict[str, object] = {}

        # --- 1. Hard deontic constraints: rights & explicit rules ---

        rd = facts.rights_and_duties

        if rd.violates_rights or rd.violates_explicit_rule:
            verdict: Verdict = "forbid"
            score = 0.0

            reasons.append(
                "Option is forbidden because it violates fundamental rights "
                "and/or explicit rules or regulations."
            )
            if rd.violates_rights:
                reasons.append("• violates_rights = True")
            if rd.violates_explicit_rule:
                reasons.append("• violates_explicit_rule = True")

            meta.update(
                {
                    "hard_constraint_triggered": True,
                    "violates_rights": rd.violates_rights,
                    "violates_explicit_rule": rd.violates_explicit_rule,
                    "has_valid_consent": rd.has_valid_consent,
                    "role_duty_conflict": rd.role_duty_conflict,
                }
            )
            return verdict, score, reasons, meta

        # Not forbidden at this stage.
        meta["hard_constraint_triggered"] = False
        meta["violates_rights"] = rd.violates_rights
        meta["violates_explicit_rule"] = rd.violates_explicit_rule
        meta["has_valid_consent"] = rd.has_valid_consent
        meta["role_duty_conflict"] = rd.role_duty_conflict

        # --- 2. Dimension-wise scores (0–1 proxies) ---

        cons = facts.consequences
        jf = facts.justice_and_fairness
        auto = facts.autonomy_and_agency
        proc = facts.procedural_and_legitimacy
        epistemic = facts.epistemic_status

        # Consequences: benefit and (inverse) harm.
        benefit_score = _clamp(cons.expected_benefit)
        harm_score = _clamp(1.0 - cons.expected_harm)
        urgency_score = _clamp(cons.urgency)

        # Justice & fairness: base score.
        # Default neutral if no explicit priority for disadvantaged.
        disadvantaged_score = 0.5
        if jf.prioritizes_most_disadvantaged:
            disadvantaged_score = 1.0

        # Fairness penalties will be applied later for discrimination/exploitation.
        discriminates = jf.discriminates_on_protected_attr
        exploits = jf.exploits_vulnerable_population
        worsens_power = jf.exacerbates_power_imbalance

        # Autonomy & agency.
        autonomy_score = 0.5  # default neutral
        if auto is not None:
            autonomy_score = 1.0

            if auto.coercion_or_undue_influence:
                autonomy_score -= 0.4
                reasons.append("Autonomy concern: coercion_or_undue_influence=True.")
            if auto.manipulative_design_present:
                autonomy_score -= 0.3
                reasons.append("Autonomy concern: manipulative_design_present=True.")
            if not auto.has_meaningful_choice:
                autonomy_score -= 0.4
                reasons.append("Autonomy concern: has_meaningful_choice=False.")
            if not auto.can_withdraw_without_penalty:
                autonomy_score -= 0.3
                reasons.append("Autonomy concern: can_withdraw_without_penalty=False.")

            autonomy_score = _clamp(autonomy_score)

        # Procedural legitimacy.
        procedural_score = 0.5  # neutral default
        if proc is not None:
            procedural_score = 0.0
            if proc.followed_approved_procedure:
                procedural_score += 0.4
            if proc.stakeholders_consulted:
                procedural_score += 0.2
            if proc.decision_explainable_to_public:
                procedural_score += 0.2
            if proc.contestation_available:
                procedural_score += 0.2
            procedural_score = _clamp(procedural_score)

        # --- 3. Aggregate base normative score via weighted average ---

        weights = {
            "benefit": self.w_benefit,
            "harm": self.w_harm,
            "urgency": self.w_urgency,
            "disadvantaged": self.w_disadvantaged,
            "autonomy": self.w_autonomy,
            "procedural": self.w_procedural,
        }

        dimension_scores = {
            "benefit": benefit_score,
            "harm": harm_score,
            "urgency": urgency_score,
            "disadvantaged": disadvantaged_score,
            "autonomy": autonomy_score,
            "procedural": procedural_score,
        }

        weighted_sum = 0.0
        total_weight = 0.0
        for name, w in weights.items():
            s = dimension_scores[name]
            weighted_sum += w * s
            total_weight += w

        base_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        base_score = _clamp(base_score)

        # --- 4. Apply fairness / exploitation penalties ---

        penalty = 0.0
        fairness_flags: List[str] = []

        if discriminates:
            penalty += self.discrimination_penalty
            fairness_flags.append("discriminates_on_protected_attr=True")
        if exploits:
            penalty += self.exploitation_penalty
            fairness_flags.append("exploits_vulnerable_population=True")
        if worsens_power:
            penalty += self.power_imbalance_penalty
            fairness_flags.append("exacerbates_power_imbalance=True")

        if penalty > 0:
            reasons.append("Fairness concern(s) detected: " + ", ".join(fairness_flags))

        fairness_penalty_applied = _clamp(penalty, 0.0, 0.9)
        score_after_fairness = base_score * (1.0 - fairness_penalty_applied)

        # --- 5. Apply epistemic uncertainty penalty (if available) ---

        final_score = score_after_fairness
        if epistemic is not None:
            unc = _clamp(epistemic.uncertainty_level)
            # Linear penalty: more uncertainty → lower score.
            unc_factor = 1.0 - self.max_uncertainty_penalty * unc
            final_score *= unc_factor
            meta["uncertainty_level"] = epistemic.uncertainty_level
            meta["uncertainty_factor"] = unc_factor
            if unc > 0.5:
                reasons.append(
                    f"High epistemic uncertainty (uncertainty_level={unc:.2f}) "
                    "reduces confidence in this option."
                )
        else:
            meta["uncertainty_level"] = None
            meta["uncertainty_factor"] = 1.0

        final_score = _clamp(final_score)

        # --- 6. Map final_score to verdict ---

        if final_score >= 0.8:
            verdict = "strongly_prefer"
        elif final_score >= 0.6:
            verdict = "prefer"
        elif final_score >= 0.4:
            verdict = "neutral"
        elif final_score >= 0.2:
            verdict = "avoid"
        else:
            verdict = "avoid"  # low scores are discouraged

        # --- 7. Build reasons & metadata summaries ---

        reasons.insert(
            0,
            (
                "Composite triage judgement based on benefit, harm, urgency, "
                "priority for the disadvantaged, autonomy, and procedural legitimacy."
            ),
        )

        meta.update(
            {
                "dimension_scores": dimension_scores,
                "base_score": base_score,
                "fairness_penalty_applied": fairness_penalty_applied,
                "score_after_fairness": score_after_fairness,
                "final_score": final_score,
                "fairness_flags": fairness_flags,
                "weights": weights,
            }
        )

        return verdict, final_score, reasons, meta


__all__ = [
    "CaseStudy1TriageEM",
]
