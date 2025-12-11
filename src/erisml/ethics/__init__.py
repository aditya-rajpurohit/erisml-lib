"""
erisml.ethics
=============

Public API for the ErisML ethics subsystem.

This package exposes:

- Core data structures for ethically relevant summaries:
  * EthicalFacts
  * Consequences
  * RightsAndDuties
  * JusticeAndFairness
  * AutonomyAndAgency
  * PrivacyAndDataGovernance
  * SocietalAndEnvironmental
  * VirtueAndCare
  * ProceduralAndLegitimacy
  * EpistemicStatus

- Judgements and module interfaces:
  * Verdict
  * EthicalJudgement
  * EthicsModule

- Democratic governance:
  * GovernanceConfig
  * DecisionOutcome
  * aggregate_judgements
  * select_option
"""

from .facts import (
    EthicalFacts,
    Consequences,
    RightsAndDuties,
    JusticeAndFairness,
    AutonomyAndAgency,
    PrivacyAndDataGovernance,
    SocietalAndEnvironmental,
    VirtueAndCare,
    ProceduralAndLegitimacy,
    EpistemicStatus,
)

from .judgement import (
    Verdict,
    EthicalJudgement,
)

from .modules.base import (
    EthicsModule,
)

from .governance.config import (
    GovernanceConfig,
)

from .governance.aggregation import (
    DecisionOutcome,
    aggregate_judgements,
    select_option,
)

__all__ = [
    # Facts & ethical dimensions
    "EthicalFacts",
    "Consequences",
    "RightsAndDuties",
    "JusticeAndFairness",
    "AutonomyAndAgency",
    "PrivacyAndDataGovernance",
    "SocietalAndEnvironmental",
    "VirtueAndCare",
    "ProceduralAndLegitimacy",
    "EpistemicStatus",
    # Judgements & verdicts
    "Verdict",
    "EthicalJudgement",
    # Modules
    "EthicsModule",
    # Governance
    "GovernanceConfig",
    "DecisionOutcome",
    "aggregate_judgements",
    "select_option",
]
