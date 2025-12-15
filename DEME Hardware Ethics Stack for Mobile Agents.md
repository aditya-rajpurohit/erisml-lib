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
  - safety / consequences  
  - rights & duties  
  - fairness / equity  
  - autonomy & privacy  
  - societal & environmental impact  
  - procedural legitimacy  
  - epistemic status  

- **Ethics Modules (EMs)**  
  Pluggable components that consume `EthicalFacts` and emit an `EthicalJudgement`:

        EthicalJudgement(
            option_id: str,
            em_name: str,
            stakeholder: str,
            verdict: Literal["strongly_prefer", "prefer", "neutral", "avoid", "forbid"],
            normative_score: float,  # [0, 1]
            reasons: List[str],
            metadata: Dict[str, Any],
        )

- **DEME Profiles (e.g., DEMEProfileV03)**  
  Stakeholder- and context-specific profiles that encode:

  - **dimension weights**  
    safety, autonomy, fairness, privacy, environment, rule-following, priority for vulnerable, trust;

  - **principlism weights**  
    beneficence, non-maleficence, autonomy, justice;

  - **lexical layers**  
    e.g., rights-first, welfare, justice/commons;

  - **hard vetoes**  
    critical “never do” categories;

  - override and resolution modes.

- **Governance Layer**  
  A resolution function that:

  - aggregates EM outputs under a given profile,  
  - enforces lexical priorities,  
  - produces a `DecisionOutcome` and an auditable rationale.

### 1.2 ErisML Library

`erisml-lib` provides:

- types and schemas for `EthicalFacts`, `EthicalJudgement`, and `DecisionOutcome`;
- governance/aggregation logic;
- example EMs (e.g., `CaseStudy1TriageEM`);
- interop modules (JSON schema, serialization, profile adapters);
- tests and demos.

DEME is the **ethics layer**, not the whole system. It plugs into agents, planners, and controllers that handle perception and control.

---

## 2. Design Requirements for Mobile Agents

### 2.1 Timing Bands for “Ethical Decisions”

Real-world mobile agents (robots, vessels, vehicles) operate across several timescales:

1. **Reflex band** (≲ 1–5 ms)  
   Safety-critical constraints:

   - don’t cross this distance/speed envelope;  
   - don’t enter a hard exclusion zone;  
   - don’t execute a maneuver that obviously violates agreed safety rules.

   Needs: **deterministic, low-latency checks** co-located with control loops.

2. **Tactical band** (tens of ms)  
   Local path and maneuver selection:

   - which of these three trajectories best balances safety, comfort, environment?

   Needs: fast evaluation of a small set of options each cycle.

3. **Strategic band** (hundreds of ms to seconds+)  
   High-level decisions:

   - which mission goal to prioritize?  
   - whether to accept a task under current risk conditions?  
   - what policy updates or governance changes to apply?

   Can involve LLMs, humans, remote HPC, etc.

Ethical reasoning must be present in **all three bands**, but **bands 1 and 2 cannot depend on slow components**.

### 2.2 Key Requirements

- **R1: Latency-first EM path**  
  There must be a path from “current state + candidate action” to “ethical verdict” that runs within the control loop budget.

- **R2: DEME compatibility**  
  The low-latency path must be derived from the same DEME profiles and EM semantics as the slower, richer software stack.

- **R3: Agent flexibility**  
  Agents must be able to:

  - self-police via EM services (low-/mid-risk deployments);  
  - rely on optional higher-order enforcement agents (Cop, Internal Affairs) in higher-risk or regulated deployments.

- **R4: Auditability**  
  Even hardware-accelerated EM evaluations must be loggable and explainable at some level:

  - Why did the EM forbid this option?  
  - Which veto category was triggered?

---

## 3. Zynq-7020 as a DEME EM Hardware Accelerator

### 3.1 Role

The **Zynq-7020** SoC serves as a **DEME EM hardware service**:

- It is **not** the “cop” or final enforcement authority.
- It is a **low-latency, deterministic Ethics Module accelerator** that:

  - ingests compact encodings derived from `EthicalFacts` (an `EthicsFrame`);  
  - runs a distilled set of DEME rules and weights;  
  - emits EM-style scores and flags fast enough to be used directly in control loops.

### 3.2 Inputs and Outputs

**Input** (conceptual `EthicsFrame`):

- `option_id` (or small integer ID)  
- safety signals: distance, relative speed, risk band etc.  
- rights/zone flags: protected area, consent flags, legal constraints  
- fairness/protected-group bits (if applicable)  
- environment signals: emissions mode, noise constraints  
- priority_for_vulnerable bits: presence of vulnerable humans/animals  
- profile selector bits: which DEME profile slice to use  

These fields are:

- compact bitfields / fixed-width integers;  
- precomputed upstream from `EthicalFacts` by software running on the host or PS core.

**Output**:

- **Scalar score(s)** (0–1 or discrete buckets):

  - overall normative score under a compiled subset of DEME weights;  
  - optionally per-dimension scores.

- **Flags**:

  - `hard_violation_flags` (which hardware veto categories fired);  
  - `risk_band` (e.g., low / medium / high);  
  - `profile_slice_id` used.

### 3.3 Implementation Sketch

- **PL (FPGA fabric)**

  - Combinational logic for simple hard vetoes:  

    - `if distance < d_min and closing_speed > v_thresh ⇒ HARD_SAFETY_VIOLATION`  
    - `if protected_zone_flag and action == ENTER ⇒ HARD_RIGHTS_VIOLATION`.

  - Pipelined arithmetic for score computation:

    - weighted sum or lexicographic aggregation on a small set of signals.

  - Latency measured in microseconds, fully bounded.

- **PS (ARM cores)**

  - Runs a lightweight service that:

    - receives `EthicsFrame` requests (via SPI, UART, Ethernet, shared memory, etc.);  
    - feeds them to the PL;  
    - returns EM-style outputs to callers (agents, Cop, etc.);  
    - optionally logs a compressed trace.

- **Configuration**

  - DEME profiles on the host side are compiled into:

    - PL configuration (weights, thresholds, mode bits);  
    - PS-side lookup tables and metadata.

The net result is **callable EM hardware** that adheres to DEME semantics at high speed.

---

## 4. Agents and Optional Nano Enforcement Pod

### 4.1 Self-Policing Agents (Baseline)

In the **baseline deployment**, there is **no dedicated Cop agent**. Instead:

- Each agent that can issue actions (planner, controller, high-level behavior agent) must:

  1. Construct `EthicalFacts` (or at least the subset needed for band 1/2).  
  2. Call software EMs where time permits.  
  3. Call the **Zynq EM accelerator** for a fast judgement.  
  4. Apply DEME aggregation rules locally.  
  5. Respect the results:

     - never execute an action with any hardware hard-violation flag set;  
     - avoid actions below a configured normative score threshold.

- The DEME contract is enforced via:

  - design and code review;  
  - tests and simulation;  
  - runtime checks and monitoring.

This mode is appropriate for:

- lower-risk robots and mobile agents (e.g., domestic robots in test environments);  
- simulation and digital twin setups;  
- early field trials with human oversight.

### 4.2 Optional Jetson Nano DEME Enforcement Pod

For **higher-risk** or **more complex multi-agent** deployments, we can add a **Jetson Nano DEME Enforcement Pod**.

The Nano is a small embedded Linux system with modest CPU and GPU resources. It is well-suited to:

- hosting **oversight and coordination agents**;  
- acting as a **DEME-aware supervisory node**.

Two main agents run on Nano:

1. **Primary Enforcement Agent (PEA)** – optional “Cop”  
2. **Oversight / Internal Affairs Agent (OIA)** – optional “cop for the cop”

#### 4.2.1 Primary Enforcement Agent (PEA)

**Role**

- Sits in the **decision path** for selected actions or subsystems.  
- Calls the same DEME EM stack as other agents (including the Zynq hardware EM).  
- Enforces allow/forbid/escalate decisions at a system boundary.

**Responsibilities**

- Receive candidate actions from one or more agents.  
- For each candidate:

  - build or fetch `EthicalFacts`;  
  - query software EMs on host / AGI-HPC when time allows;  
  - query **Zynq EM hardware** for band 1/2 checks;  
  - aggregate EM outputs using the active DEME profile.

- Decide:

  - allow → action passes through;  
  - forbid → block / override;  
  - escalate → require human or additional analysis.

- Log all decisions and EM inputs/outputs for audit.

PEA is a **deployment choice**:

- In some deployments, agents self-police with “best-effort” and logs.  
- In others, PEA becomes a **choke point** for safety-critical commands.

#### 4.2.2 Oversight / Internal Affairs Agent (OIA)

**Role**

- Monitors PEA, EM outputs, and long-term decision patterns.  
- Looks for **bias, drift, gaming, or governance capture**.

**Responsibilities**

- Analyze decision logs from PEA and self-policing agents.  
- Track:

  - frequencies of vetoes and near-veto decisions;  
  - which stakeholders are impacted by avoid/forbid decisions;  
  - changes in patterns after DEME profile updates.

- Assess PEA:

  - Are there systematic mismatches between PEA decisions and DEME profile intent?  
  - Are certain veto flags being ignored in practice?

- Produce:

  - periodic governance reports;  
  - alerts on anomalies;  
  - recommendations for DEME profile changes or deployment mode (for example, switch from self-policing to mandatory PEA for domain X).

OIA coordinates with human governance bodies (internal ethics boards, LF AAIF initiatives, etc.).

### 4.3 Risk-Tiered Deployment Profiles

Deployment modes:

- **Tier 0 – Simulation / Lab**

  - Self-policing agents.  
  - Zynq EM hardware optional or simulated.  
  - Nano pod optional.

- **Tier 1 – Low/Moderate-Risk Field Deployment**

  - Zynq EM hardware in the loop.  
  - Agents self-police; they must call EMs and respect hardware vetoes.  
  - Nano pod optional or used purely for offline analysis.

- **Tier 2 – High-Risk / Regulated Deployment**

  - Zynq EM hardware required.  
  - PEA on Nano required in the command path for designated action classes.  
  - OIA performs ongoing oversight.  
  - DEME profiles and deployment mode changes subject to formal governance processes.

In all tiers, **Zynq remains the latency-first EM accelerator**; what changes is how much centralized enforcement and oversight is layered above.

---

## 5. Real-Time EM Path for a Mobile Agent

### 5.1 Control Cycle Sketch

At each control tick (e.g., every 10 ms):

1. **Perception / State Estimation**

   - Sensors → world model update (pose, obstacles, human locations, zones).

2. **Candidate Action / Trajectory Proposal**

   - Local planner proposes a velocity command or short-horizon trajectory.

3. **Ethics Encoding**

   - A small `EthicsFrame` is constructed from:

     - distance / velocity / risk band;  
     - flags for protected zones or no-go areas;  
     - presence of vulnerable entities;  
     - relevant DEME profile bits.

4. **Zynq EM Evaluation**

   - `EthicsFrame` is sent to the EM accelerator.  
   - Within a bounded time (e.g., tens of microseconds), Zynq returns:

     - `hard_violation_flags`;  
     - `normative_score_hw`.

5. **Local Decision**

   - If `hard_violation_flags` is non-empty:

     - discard or modify the candidate action.

   - Otherwise:

     - optionally combine `normative_score_hw` with software EM scores;  
     - decide whether to execute, adjust, or re-plan within the 10 ms budget.

This path is **purely local**, requiring no network and no heavy compute. It is sufficient to avoid obviously unethical maneuvers at control-loop timescales.

### 5.2 Integration with PEA

If PEA is present:

- It subscribes to summarized decision events (option, Zynq EM outputs, final action).  
- It may intervene in certain high-risk transitions (mode changes, entering sensitive zones).  
- It enforces additional policies on top of the local EM checks.

PEA does **not** replace the Zynq EM in the loop; it wraps and coordinates it.

---

## 6. Interoperability and APIs

### 6.1 Zynq EM Service API (Conceptual)

A simple service for agents and PEA:

- **Request: `EvalEthicsFrame`**

  - `frame_id`  
  - `option_id`  
  - `profile_id`  
  - `encoded_ethics_frame` (fixed-width bytes)

- **Response: `EvalEthicsFrameResult`**

  - `frame_id`  
  - `option_id`  
  - `profile_id`  
  - `normative_score_hw` (float or fixed-point)  
  - `hard_violation_flags` (bitfield)  
  - `metadata` (for example, risk band)

This may be exposed as:

- a local C API on PS;  
- a lightweight RPC over UART/SPI/PCIe;  
- or an MCP tool that wraps lower-level transport.

### 6.2 Nano PEA/OIA APIs

On Nano, we expose services such as:

- `demesvc.pea_review_decision(decision_id)` – re-evaluate a specific decision using Zynq EM plus slower EM/LLM methods offline.  
- `demesvc.oia_report(time_window)` – generate an oversight summary.  
- `demesvc.get_risk_tier()` / `demesvc.set_risk_tier()` – manage deployment mode (Tier 0/1/2).

Nano does **not** need to run DEME/ErisML’s full stack in the critical path; it mainly orchestrates, analyzes, and, when configured, enforces.

---

## 7. Implementation Sketch in `erisml-lib`

To support this architecture in the codebase:

1. **Hardware EM Interface Module**

   - `src/erisml/ethics/domain/hw_em_client.py`  
   - Provides an API for:

     - constructing `EthicsFrame` from `EthicalFacts`;  
     - calling the Zynq EM service;  
     - mapping results back into an `EthicalJudgement`-like structure.

2. **Profile-to-Hardware Compiler**

   - `src/erisml/ethics/interop/hw_profile_compile.py`  
   - Given a `DEMEProfileV0x`, produces:

     - PL configuration (bitstreams/parameters);  
     - PS-side configuration tables.

3. **PEA/OIA Stubs**

   - `src/erisml/ethics/enforcement/pea.py`  
   - `src/erisml/ethics/enforcement/oia.py`  

   Provide reference implementations that:

   - consume decision logs (`EthicalFacts` + `DecisionOutcome`);  
   - use `hw_em_client` as needed;  
   - can be instantiated on Nano or other supervisory nodes.

4. **Examples and Tests**

   - Extend the triage demo to:

     - simulate a hardware EM path;  
     - show how an agent can self-police using the EM API;  
     - demonstrate a simple PEA wrapper.

---

## 8. Discussion and Future Work

### 8.1 Benefits

- **Latency-first ethics**  
  Ethical checks move into the same timing budget as control logic, shrinking the gap between declared values and real-world behavior.

- **Separation of concerns**  
  DEME profiles and EMs remain the **source of ethical semantics**; Zynq is a **derived, safety-critical implementation** of a subset.

- **Risk-tiered deployment**  
  The same EM and DEME infrastructure supports:

  - self-policing agents;  
  - optional centralized enforcement;  
  - optional oversight, depending on context and regulation.

- **Hardware/software co-design**  
  Profiles can be incrementally compiled into more expressive hardware EMs as experience grows.

### 8.2 Limitations

- **Distillation gap**  
  Not all of DEME’s richness can fit into a tiny `EthicsFrame` and FPGA logic. There is always a gap between the full ethical worldview and the reflex/tactical subset.

- **Specification risk**  
  Hardware EM logic is only as good as the mapping from `EthicalFacts` and the profile compiler. Bugs or omissions there can create dangerous blind spots.

- **Oversight complexity**  
  Adding PEA and OIA can improve robustness but also adds complexity. Good tooling and visualization are needed so that humans can still understand what is happening.

### 8.3 Future Work

- Better **profile compilation** strategies (automatically extracting safe approximations of complex EM behavior).  
- Formal **verification** of hardware EM pipelines against DEME profile constraints.  
- Richer **telemetry and visualization** for EM and PEA/OIA behavior, to support governance boards and community review.  
- Reference **open hardware designs** for DEME EM accelerators based on Zynq-7020, other FPGAs, or ASICs.

---

## 9. Conclusion

For mobile AI agents operating in the physical world, ethics cannot be a slow, advisory overlay. It has to run at **control-loop speed**.

The architecture outlined here makes that concrete:

- A **Zynq-7020 EM accelerator** provides a **latency-first execution path** for a distilled subset of DEME rules and vetoes, derived from the same profiles and EM semantics used in the broader ErisML/DEME stack.
- **Agents can self-police** by calling this EM service directly, ensuring that every action checks in with a fast ethics oracle before it touches the physical world.
- For high-risk deployments, an **optional Jetson Nano enforcement pod** can host a **Primary Enforcement Agent** and an **Internal Affairs agent**, providing additional enforcement and oversight over the same EM substrate.

This keeps DEME’s core promise intact:

> **Ethics is modular, democratically governed, and technologically grounded — all the way down to the control cycles of the robot.**
