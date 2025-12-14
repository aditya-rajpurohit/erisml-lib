# DEME Hardware Ethics Stack for Mobile Agents  
### Zynq-7020 Latency-First EM Accelerator with Optional Jetson Nano Oversight

**Status:** Draft  
**Version:** 0.2  
**Date:** 2025-12-13  
**Authors:** _TBD_  

---

## Abstract

Democratically governed Ethical Modules (DEME) and the ErisML library define a programmable architecture for ethics in autonomous systems: structured `EthicalFacts`, pluggable Ethics Modules (EMs), democratic profiles (DEMEProfileV0x), and a governance layer that aggregates EM outputs into system decisions.

For **mobile AI agents in the physical world**, ethical decisions must be made at **control-loop timescales**. A robot cannot wait hundreds of milliseconds for a cloud LLM to decide whether to stop for a pedestrian or avoid an obstacle. Ethics needs a **low-latency execution path**, not just a high-level policy layer.

This document describes a hardware/software stack where:

1. A **Zynq-7020 FPGA SoC** acts as a **latency-first DEME EM accelerator**:
   - It ingests compact `EthicsFrame`s derived from `EthicalFacts`.
   - It evaluates a distilled subset of DEME rules and weights in **tightly bounded time**.
   - It returns EM-style scores and flags fast enough to sit **inside real-time control loops**.

2. **Agents can self-police** by calling this EM service directly:
   - In **low- and medium-risk deployments**, planners and controllers integrate the Zynq EM accelerator into their own decision loops and enforce DEME contracts themselves.

3. An **optional Jetson Nano “DEME Enforcement Pod”** can be added for higher-risk contexts:
   - A **Primary Enforcement Agent (PEA)** – a “cop” – that supervises decisions from multiple agents, calling the same EM hardware service and enforcing allow/forbid/escalate.
   - An **Oversight / Internal Affairs Agent (OIA)** that monitors the PEA, EM outcomes, and long-term patterns for bias, drift, or gaming.

The key design principle is:

> **Ethical constraints must be computable within the control loop’s timing budget.**  
> DEME EMs therefore need a **hardware-accelerated path**, with optional higher-level enforcement and oversight layered above.

---

## 1. DEME and ErisML in Brief

### 1.1 DEME Concepts

DEME builds on ErisML and introduces:

- **EthicalFacts**  
  A structured representation of ethically relevant features for a candidate action or plan, including:
  - safety / consequences,
  - rights & duties,
  - fairness / equity,
  - autonomy & privacy,
  - societal & environmental impact,
  - procedural legitimacy,
  - epistemic status.

- **Ethics Modules (EMs)**  
  Pluggable components that consume `EthicalFacts` and emit:

  ```python
  EthicalJudgement(
      option_id: str,
      em_name: str,
      stakeholder: str,
      verdict: Literal["strongly_prefer", "prefer", "neutral", "avoid", "forbid"],
      normative_score: float,  # [0, 1]
      reasons: List[str],
      metadata: Dict[str, Any],
  )
