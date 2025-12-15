# DEME Hardware Ethics Stack for Mobile Agents  
### Zynq-7020 Latency-First EM Accelerator with Optional Jetson Nano Oversight

**Status:** Draft  
**Version:** 0.3  
**Date:** 2025-12-13  
**Authors:** _TBD_  

---

## Abstract

Democratically governed Ethical Modules (DEME) and the ErisML library define a programmable architecture for ethics in autonomous systems: structured `EthicalFacts`, pluggable Ethics Modules (EMs), democratic profiles (DEMEProfileV0x), and a governance layer that aggregates EM outputs into system decisions.

For **mobile AI agents in the physical world**, ethical decisions must be made at **control-loop timescales**. A robot cannot wait hundreds of milliseconds for a cloud LLM to decide whether to stop for a pedestrian or avoid an obstacle. Ethics needs a **low-latency execution path**, not just a high-level policy layer.

This document describes a hardware/software stack where:

1. A **Zynq-7020 FPGA SoC** acts as a **latency-first DEME EM accelerator**:
   - It ingests compact `EthicsFrame`s derived from `EthicalFacts`.
   - It evaluates a distilled subset of DEME rules and weights in **tightly bounded time** (<50μs typical, <200μs worst-case).
   - It returns EM-style scores and flags fast enough to sit **inside real-time control loops**.

2. **Agents can self-police** by calling this EM service directly:
   - In **low- and medium-risk deployments**, planners and controllers integrate the Zynq EM accelerator into their own decision loops and enforce DEME contracts themselves.

3. An **optional Jetson Nano "DEME Enforcement Pod"** can be added for higher-risk contexts:
   - A **Primary Enforcement Agent (PEA)** that supervises decisions from multiple agents, calling the same EM hardware service and enforcing allow/forbid/escalate.
   - An **Oversight / Internal Affairs Agent (OIA)** that monitors the PEA, EM outcomes, and long-term patterns for bias, drift, or gaming.

The key design principle is:

> **Ethical constraints must be computable within the control loop's timing budget.**  
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
    critical "never do" categories;

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

### 2.1 Timing Bands for "Ethical Decisions"

Real-world mobile agents (robots, vessels, vehicles) operate across several timescales:

1. **Reflex band** (≤ 1–5 ms)  
   Safety-critical constraints:

   - don't cross this distance/speed envelope;  
   - don't enter a hard exclusion zone;  
   - don't execute a maneuver that obviously violates agreed safety rules.

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
  There must be a path from "current state + candidate action" to "ethical verdict" that runs within the control loop budget.
  
  - **Target latency**: <50μs for typical HW EM evaluation
  - **Worst-case guarantee**: <200μs (including communication overhead)
  - **Budget allocation**: ≤1% of 10ms control cycle

- **R2: DEME compatibility**  
  The low-latency path must be derived from the same DEME profiles and EM semantics as the slower, richer software stack.

- **R3: Agent flexibility**  
  Agents must be able to:

  - self-police via EM services (low-/mid-risk deployments);  
  - rely on optional higher-order enforcement agents (PEA, OIA) in higher-risk or regulated deployments.

- **R4: Auditability**  
  Even hardware-accelerated EM evaluations must be loggable and explainable:

  - Why did the EM forbid this option?  
  - Which veto category was triggered?
  - Hardware determinism enables reproducible debugging.

### 2.3 Comparison of Ethical Reasoning Approaches

| Approach | Latency | Expressiveness | Hardware Required | Deployment Complexity | Certification Potential |
|----------|---------|----------------|-------------------|----------------------|------------------------|
| Cloud LLM | 100-500ms | Very High | None | Low | Very Low |
| Local LLM | 50-200ms | High | High-end GPU | Medium | Low |
| Software EM | 1-10ms | Medium | Standard CPU | Low | Medium |
| **Zynq HW EM** | **<0.05ms** | **Low-Medium** | **FPGA SoC** | **High** | **High** |

The hardware EM approach trades expressiveness for deterministic timing and certification potential—critical for safety-critical mobile agents.

---

## 3. Zynq-7020 as a DEME EM Hardware Accelerator

### 3.1 Role

The **Zynq-7020** SoC serves as a **DEME EM hardware service**:

- It is **not** the "cop" or final enforcement authority.
- It is a **low-latency, deterministic Ethics Module accelerator** that:

  - ingests compact encodings derived from `EthicalFacts` (an `EthicsFrame`);  
  - runs a distilled set of DEME rules and weights;  
  - emits EM-style scores and flags fast enough to be used directly in control loops.

### 3.2 EthicsFrame Specification

#### 3.2.1 Conceptual Fields

An `EthicsFrame` is a compact encoding of ethically relevant features:

- `option_id` (or small integer ID)  
- **Safety signals**: distance, relative speed, risk band, collision probability
- **Rights/zone flags**: protected area, consent flags, legal constraints  
- **Fairness/protected-group bits**: presence of protected classes (if applicable)
- **Environment signals**: emissions mode, noise constraints  
- **Vulnerable entity flags**: presence of children, elderly, disabled persons, animals
- **Profile selector bits**: which DEME profile slice to use  

#### 3.2.2 Concrete Encoding (64-bit baseline)

```
EthicsFrame (64 bits):
┌─────────────────────────────────────────────────────────────────┐
│ Bits 0-7:   distance_band (8 levels, 0=<1m, 7=>50m)             │
│ Bits 8-15:  relative_speed (signed, -128 to +127, scaled 0.1m/s)│
│ Bits 16-19: zone_flags                                           │
│             [16]: protected_zone (e.g., school, hospital)        │
│             [17]: consent_required                               │
│             [18]: legal_constraint_active                        │
│             [19]: sensitive_area (privacy concern)               │
│ Bits 20-23: vulnerable_presence                                  │
│             [20]: child_present                                  │
│             [21]: elderly_present                                │
│             [22]: disabled_present                               │
│             [23]: animal_present                                 │
│ Bits 24-27: risk_band (4 levels: 0=minimal, 3=critical)         │
│ Bits 28-31: profile_slice_id (16 profile variants)              │
│ Bits 32-47: action_type (16-bit action classifier)              │
│ Bits 48-63: option_id (unique identifier for this option)       │
└─────────────────────────────────────────────────────────────────┘

Extensions (optional 128-bit or 256-bit frames):
- Environmental impact metrics (emissions, noise levels)
- Fairness dimensions (equity scores, protected class interactions)
- Epistemic uncertainty markers
```

**Design rationale**:
- Bitfields enable fast combinational logic in FPGA fabric
- Fixed-width integers eliminate variable parsing overhead
- Pre-computation on host/PS cores converts rich `EthicalFacts` to this compact form
- Extension path allows adding dimensions without breaking existing logic

#### 3.2.3 Example Encoding

**Scenario**: Delivery robot approaching pedestrian crosswalk

```
Option A (continue at 1.5 m/s):
  distance_band = 0x02  (4-6 meters)
  relative_speed = 0x0F  (+1.5 m/s toward pedestrian)
  zone_flags = 0x0 (no special zones)
  vulnerable_presence = 0x1 (child detected)
  risk_band = 0x2 (moderate)
  profile_slice_id = 0x0 (urban pedestrian profile)
  action_type = 0x0010 (continue motion)
  option_id = 0x0001

Encoded: 0x0001 0010 0020 0001 000F 0002
```

### 3.3 Hardware Outputs

**Output Structure**:

```
EthicsEvaluation (96 bits):
┌─────────────────────────────────────────────────────────────────┐
│ normative_score_hw: 16-bit fixed-point [0.0, 1.0]               │
│ hard_violation_flags: 16-bit field (see below)                   │
│ risk_assessment: 8-bit aggregate risk score                      │
│ dimension_scores: 6×8-bit per-dimension scores (optional)        │
│ profile_slice_id: 8-bit echo of input profile                    │
│ metadata: 24-bit reserved/diagnostic                             │
└─────────────────────────────────────────────────────────────────┘
```

**Hard Violation Flags** (16-bit field):

| Bit | Flag Name | Trigger Condition |
|-----|-----------|-------------------|
| 0 | `HARD_SAFETY_COLLISION` | Imminent collision (distance < d_min AND closing_speed > v_thresh) |
| 1 | `HARD_RIGHTS_ZONE` | Entering protected zone without consent flag |
| 2 | `HARD_LEGAL_CONSTRAINT` | Action violates legal boundary or regulation |
| 3 | `HARD_VULNERABLE_RISK` | Risk_band ≥ 2 AND vulnerable_presence != 0 |
| 4 | `HARD_ENVIRONMENT_BREACH` | Exceeds emissions or noise limits |
| 5 | `HARD_CONSENT_VIOLATION` | Consent_required flag set but not granted |
| 6 | `HARD_PRIVACY_BREACH` | Sensitive area + recording/surveillance action |
| 7 | `HARD_AUTONOMY_OVERRIDE` | Attempting override without authorization |
| 8-15 | Reserved | Future ethical categories |

**Any non-zero hard_violation_flags value** → action is **FORBIDDEN** by hardware EM.

### 3.4 Implementation Architecture

#### 3.4.1 Programmable Logic (PL)

- **Combinational Logic Path** (ultra-fast, ~10ns):
  
  - Hard veto evaluators:
    ```verilog
    // Example: Safety collision veto
    assign HARD_SAFETY_COLLISION = 
      (distance_band < DIST_MIN) && 
      (relative_speed > SPEED_THRESH) &&
      (risk_band >= 2);
    ```
  
  - Simple threshold checks for each violation category
  - Runs in parallel, all vetoes evaluated simultaneously

- **Pipelined Arithmetic Path** (medium-fast, ~100ns):
  
  - Weighted sum computation for normative_score:
    ```
    score = w_safety × safety_component +
            w_rights × rights_component +
            w_fairness × fairness_component + ...
    ```
  
  - 3-5 stage pipeline using DSP48 slices
  - 16-bit fixed-point arithmetic (Q0.16 format)
  - Lexicographic layer evaluation (priority-ordered)

- **Resource Estimates** (Zynq-7020):
  - LUTs: ~5,000 (of 53,200 available) — 10% utilization
  - FFs: ~3,000 (of 106,400 available) — 3% utilization
  - DSP48s: 8-12 (of 220 available) — 5% utilization
  - Block RAM: 50KB (of 630KB available) — 8% utilization

#### 3.4.2 Processing System (PS)

The ARM Cortex-A9 cores (dual-core @ 866 MHz) run a lightweight service:

- **EM Service Daemon**:
  - Receives `EthicsFrame` requests via:
    - **Shared memory** (baseline, <1μs overhead) using AXI HP ports
    - SPI/UART (backup, ~10μs overhead)
    - Ethernet (remote agents, ~100μs overhead)
  
  - Coordinates PL evaluation pipeline
  - Returns `EthicsEvaluation` results
  - Maintains compressed decision log (ring buffer)

- **Configuration Manager**:
  - Loads DEME profile parameters into PL registers
  - Manages profile switching (hot-swap between 16 preloaded profiles)
  - Handles updates from governance system

- **Diagnostics & Telemetry**:
  - Watchdog monitoring of PL health
  - Latency histogram tracking
  - Anomaly detection (unexpected veto patterns)

#### 3.4.3 Latency Budget Breakdown

**Typical path** (Option A: shared memory interface):

```
1. Host writes EthicsFrame to shared memory:         ~0.5 μs
2. PS reads from memory, validates format:           ~2 μs
3. PS writes to PL input registers:                  ~0.5 μs
4. PL combinational veto check:                      ~0.01 μs
5. PL pipelined score computation (5 stages):        ~5 μs
6. PS reads PL output registers:                     ~0.5 μs
7. PS writes result to shared memory:                ~0.5 μs
8. Host reads result:                                ~0.5 μs
────────────────────────────────────────────────────────────
   Total (typical):                                  ~10 μs
```

**Worst-case path** (contention, cache misses, profile switch):

```
- Additional cache miss overhead:                   +20 μs
- Profile parameter reload:                         +50 μs
- PL pipeline flush/refill:                         +10 μs
- PS interrupt latency:                             +30 μs
────────────────────────────────────────────────────────────
   Total (worst-case):                              ~120 μs
```

**Safety margin**: Specify <200μs guarantee (includes 40% margin over worst-case).

### 3.5 Multi-Agent Resource Management

When multiple agents share a single Zynq EM accelerator:

#### 3.5.1 Priority Queueing

- **3 priority levels**:
  1. **Critical** (safety-related, band 1 decisions) — preempts others
  2. **Normal** (tactical, band 2 decisions) — round-robin
  3. **Background** (strategic, band 3 decisions) — lowest priority

- **Queue limits**:
  - Critical: 4 slots (prevents overflow from single aggressive agent)
  - Normal: 16 slots
  - Background: 32 slots, tail-drop on overflow

#### 3.5.2 Isolation & Fair Sharing

- **Per-agent token bucket**:
  - 100 EM evaluations/second baseline rate
  - Burst allowance: 20 evaluations
  - Prevents single agent from monopolizing EM service

- **Starvation prevention**:
  - Normal and background requests age up to critical after 5ms wait
  - Ensures no agent is blocked indefinitely

#### 3.5.3 Fault Isolation

- **Malformed requests**:
  - Invalid `EthicsFrame` format → return error, don't crash
  - Log offending agent ID, rate-limit future requests

- **DOS protection**:
  - Per-agent request counting
  - Temporary suspension (100ms) after 200 requests in 1 second
  - Alert OIA on repeated violations

---

## 4. Profile Compiler: From DEME Profiles to Hardware

### 4.1 The Compilation Challenge

**Problem**: DEME profiles are rich, multi-dimensional, and potentially LLM-augmented. The Zynq EM hardware requires simple, fixed-point arithmetic and combinational logic.

**Goal**: Automatically extract a **safe, conservative approximation** of a DEME profile that:
- Captures all hard vetoes with zero false negatives
- Approximates normative scores with acceptable error (±0.05)
- Fits within FPGA resource constraints

### 4.2 Compilation Approach (Phase 1: Rule-Based Extraction)

**Step 1: Hard Veto Extraction**

For each `hard_veto` category in the DEME profile:
1. Identify the trigger conditions (logical predicates over `EthicalFacts`)
2. Map predicates to `EthicsFrame` bitfields
3. Generate Verilog combinational logic
4. Conservative bias: If uncertain, include the veto (false positives acceptable for hard vetoes)

**Example**:
```python
# DEME Profile (Python)
hard_vetoes = {
    "imminent_collision": lambda facts: 
        facts.distance < 2.0 and facts.relative_speed > 1.0,
}

# Compiled to Verilog
assign HARD_SAFETY_COLLISION = 
    (distance_band <= 1) && (relative_speed > 10);
// Note: conservative threshold (distance_band 1 = <2m)
```

**Step 2: Weight Quantization**

For normative score computation:
1. Extract dimension weights from DEME profile
2. Normalize to sum = 1.0
3. Quantize to 16-bit fixed-point: `w_i = round(w_float × 65536)`
4. Verify quantization error: `Σ |w_float - (w_fixed / 65536)| < 0.01`

**Step 3: Scoring Function Approximation**

For complex scoring functions:
1. Sample the function over input space (10,000 random `EthicalFacts`)
2. Fit piecewise-linear approximation or lookup table
3. Implement in PL using BRAM-based LUT or arithmetic units
4. Validate approximation error on held-out test set

### 4.3 Validation & Certification

**Validation Pipeline**:

1. **Semantic Equivalence Testing**:
   - Generate 100,000 random `EthicalFacts`
   - Evaluate with software EM and hardware EM
   - Assert: All hard vetoes match (100% recall required)
   - Assert: Score RMSE < 0.05

2. **Edge Case Testing**:
   - Boundary values (distance = 0, max speed, etc.)
   - Simultaneous veto triggers
   - Profile transitions

3. **Formal Verification** (future work):
   - Use tools like SymbiYosys to prove veto logic correctness
   - Prove latency bounds on PL pipeline

### 4.4 Update Mechanism

**Deployment Pipeline**:

```
1. DEME governance board approves profile update
2. Profile compiler generates new PL bitstream + PS config
3. Simulation testing in digital twin environment
4. Sign bitstream with cryptographic key
5. OTA update to field-deployed Zynq units (controlled rollout)
6. Agents automatically reload new profile_slice_id
7. OIA monitors for unexpected behavior changes
```

**Update frequency**: Monthly for minor tweaks, quarterly for major changes.

**Version skew handling**: Agents tag requests with expected profile version; mismatches trigger warnings but don't block (use closest available profile).

---

## 5. Agents and Optional Nano Enforcement Pod

### 5.1 Self-Policing Agents (Baseline)

In the **baseline deployment**, there is **no dedicated PEA**. Instead:

- Each agent that can issue actions (planner, controller, behavior tree) must:

  1. Construct `EthicalFacts` from perception and world model
  2. Call software EMs where time permits (band 2-3)
  3. Derive `EthicsFrame` and call **Zynq EM accelerator** (band 1-2)
  4. Apply DEME aggregation rules locally
  5. Respect the results:

     - **NEVER** execute an action with any `hard_violation_flags` set
     - Avoid actions with `normative_score_hw < 0.4` (configurable threshold)

- The DEME contract is enforced via:

  - Design patterns and code review
  - Runtime assertions and watchdogs
  - Automated testing and simulation

This mode is appropriate for:

- Lower-risk robots (domestic assistants, warehouse logistics)
- Simulation and digital twin environments
- Early field trials with human supervision

### 5.2 Optional Jetson Nano DEME Enforcement Pod

For **higher-risk** or **multi-agent** deployments, add a **Jetson Nano DEME Enforcement Pod**.

The Nano (4GB model, ~10W TDP) provides:
- Quad-core ARM A57 CPU for coordination
- 128-core Maxwell GPU for optional ML oversight
- Ethernet connectivity to supervised agents
- Runs Ubuntu + ROS2 + DEME enforcement stack

Two agents run on Nano:

1. **Primary Enforcement Agent (PEA)** — "the cop"
2. **Oversight / Internal Affairs Agent (OIA)** — "cop for the cop"

#### 5.2.1 Primary Enforcement Agent (PEA)

**Role**: Gatekeeper for safety-critical commands

**Operating Modes**:

- **Advisory mode** (Tier 1):
  - Monitors agent decisions passively
  - Logs mismatches between agent choice and PEA recommendation
  - Alerts OIA on systematic deviations

- **Enforcement mode** (Tier 2):
  - Sits **in command path** for designated action classes
  - Can block or override agent decisions
  - Requires explicit approval for high-risk actions

**Decision Process**:

For each candidate action:
1. Receive action proposal from agent (including `EthicalFacts`)
2. Call Zynq EM hardware (same service agents use)
3. Optionally call software EMs for richer analysis (if time allows)
4. Aggregate using active DEME profile
5. Decision logic:

```python
if any hard_violation_flags:
    return FORBID("Hardware veto: " + violated_categories)

if normative_score < enforcement_threshold:  # e.g., 0.5
    if action_class in HIGH_RISK_CLASSES:
        return ESCALATE("Requires human review")
    else:
        return FORBID("Below normative threshold")

if agent_decision != pea_recommendation:
    log_mismatch()
    if enforcement_mode:
        return OVERRIDE(pea_recommendation)
    else:
        return ALLOW(agent_decision, flag="advisory_mismatch")

return ALLOW(agent_decision)
```

**Graceful Degradation**:
- If PEA is unavailable, agents revert to self-policing with Zynq EM
- PEA failure triggers alert to human operators
- Agents enter "safe mode" (conservative thresholds) until PEA recovers

#### 5.2.2 Oversight / Internal Affairs Agent (OIA)

**Role**: Meta-level monitor ensuring system health

**Monitoring Dimensions**:

1. **Bias Detection**:
   - Track veto/forbid rates by demographic proxies
   - Statistical tests for disparate impact
   - Alert if veto rate for vulnerable_present actions drops unexpectedly

2. **Drift Detection**:
   - Compare current decision patterns to historical baselines
   - Detect sudden changes in score distributions
   - Flag potential sensor miscalibration or EM parameter drift

3. **Gaming Detection**:
   - Look for agents systematically manipulating `EthicsFrame` inputs
   - Detect abnormal patterns (e.g., all actions scored exactly 0.50)
   - Cross-validate agent-reported `EthicalFacts` against independent sensors

4. **PEA Health**:
   - Verify PEA is calling Zynq EM for all required actions
   - Check PEA is respecting hard_violation_flags (not overriding vetoes)
   - Measure PEA decision latency and availability

**Reporting & Escalation**:

- **Daily summaries**: Decision counts, veto statistics, anomaly scores
- **Weekly governance reports**: Trend analysis, profile effectiveness metrics
- **Real-time alerts**: Critical anomalies (e.g., PEA bypassing vetoes)
- **Quarterly deep dives**: Bias audits, long-term drift analysis

**Access Requirements**:
- Read-only access to all agent and PEA decision logs
- Independent sensor feeds for ground truth validation
- Encrypted communication with governance board

### 5.3 Risk-Tiered Deployment Profiles

| Tier | Use Case | Zynq EM | Self-Policing | PEA | OIA | Governance |
|------|----------|---------|---------------|-----|-----|------------|
| **0: Lab** | Simulation, development | Optional | Yes | No | No | Informal |
| **1: Low-Risk Field** | Domestic robots, controlled environments | Required | Yes | Advisory | Optional | Quarterly review |
| **2: High-Risk Field** | Public spaces, regulated industries | Required | Yes | Enforcement | Required | Monthly review + incident response |

**Tier Transition Criteria**:

- **0→1**: Pass simulation test suite, human oversight available
- **1→2**: 1000+ hours field operation without incidents, risk assessment
- **2→1**: Systematic safety issues, or environment becomes lower-risk
- **Emergency shutdown**: Any critical safety incident → return to Tier 0

---

## 6. Real-Time EM Integration

### 6.1 Control Cycle Example (10ms loop)

**Scenario**: Delivery robot navigation in urban environment

```
t=0ms:    Perception completes
          └─ LIDAR: pedestrian at 5m, crossing trajectory
          └─ Camera: child detected (vulnerable_presence flag)

t=1ms:    Planner generates 3 candidate trajectories
          ├─ Option A: Continue 1.5 m/s
          ├─ Option B: Slow to 0.5 m/s
          └─ Option C: Emergency stop

t=2ms:    Build EthicsFrames for each option
          ├─ Option A: distance_band=2, speed=+15, vulnerable=0x1
          ├─ Option B: distance_band=2, speed=+5, vulnerable=0x1
          └─ Option C: distance_band=2, speed=0, vulnerable=0x1

t=2.05ms: Send 3 frames to Zynq EM (parallel evaluation)

t=2.15ms: Zynq returns results (10μs each)
          ├─ Option A: HARD_VULNERABLE_RISK flag SET, score=0.12
          │           → FORBIDDEN
          ├─ Option B: no flags, score=0.67
          │           → ACCEPTABLE
          └─ Option C: no flags, score=0.94
                      → PREFERRED

t=3ms:    Local aggregation applies DEME profile
          └─ Select Option C (highest score, no vetoes)

t=3.5ms:  Command sent to controller: "decelerate to stop"

t=4ms:    Controller executes motion command

t=10ms:   Next control cycle begins
          └─ New perception, replanning, repeat
```

**Latency Budget**:
- Perception: 1ms
- Planning: 1ms
- **Ethics check: 1.15ms** (includes Zynq EM call)
- Aggregation: 0.5ms
- Control: 1ms
- Slack: 5.35ms

**Key insight**: Ethics is **1.15ms out of 10ms** — only 11.5% of cycle time.

### 6.2 Integration with PEA (Tier 2 Mode)

When PEA enforcement is active:

```
t=3ms:    Agent completes local ethics check (selects Option C)

t=3.1ms:  Agent sends proposal to PEA:
          "Intend to execute Option C (emergency stop)"
          + Full EthicalFacts
          + Zynq EM results

t=3.2ms:  PEA evaluates:
          ├─ Calls Zynq EM independently (verification)
          ├─ Results match agent's call → good
          └─ normative_score=0.94 > threshold → approve

t=3.5ms:  PEA returns ALLOW

t=3.6ms:  Agent executes command

t=10ms:   Cycle complete
```

**PEA overhead**: +0.5ms (still within 10ms budget)

**Failure handling**: If PEA doesn't respond within 1ms, agent proceeds with local decision (logged as "PEA timeout").

### 6.3 Power and Thermal Considerations

**Power Budget Analysis**:

| Component | Typical Power | Peak Power | Notes |
|-----------|---------------|------------|-------|
| Zynq-7020 SoC | 2-3W | 5W | PL utilization dependent |
| Jetson Nano 4GB | 5-10W | 15W | GPU idle in enforcement mode |
| **Total Pod** | **7-13W** | **20W** | Excludes cooling |

**Mobile Agent Impact**:
- Typical mobile robot: 100-500W total power budget
- DEME pod: 2-4% of total power
- Runtime impact: ~10 minutes per hour of operation (for 200Wh battery)

**Thermal Management**:
- Passive cooling sufficient for Zynq at <3W average
- Jetson requires small heatsink + fan at >10W
- Compact form factor: 10cm × 10cm × 5cm enclosure feasible

**Power Optimization Strategies**:
- Clock-gate unused PL blocks (saves ~20%)
- Jetson CPU-only mode when GPU not needed (saves ~3W)
- Sleep Zynq PS cores during idle periods (saves ~1W)
- Wake-on-request via GPIO interrupt

---

## 7. Interoperability and APIs

### 7.1 Zynq EM Service API

**Transport Layer**: Shared memory (baseline) with fallback to SPI/Ethernet

**Request Message** (`EvalEthicsFrame`):

```c
struct EthicsFrameRequest {
    uint32_t frame_id;          // Unique request identifier
    uint32_t option_id;         // Which candidate action
    uint8_t  profile_id;        // Which DEME profile slice
    uint8_t  priority;          // 0=background, 1=normal, 2=critical
    uint64_t ethics_frame;      // The encoded frame (see Section 3.2.2)
    uint32_t timestamp_us;      // Request timestamp (microseconds)
} __attribute__((packed));
```

**Response Message** (`EthicsEvaluation`):

```c
struct EthicsFrameResponse {
    uint32_t frame_id;              // Echo of request
    uint32_t option_id;             // Echo of option
    uint16_t normative_score;       // Fixed-point [0, 65535] = [0.0, 1.0]
    uint16_t hard_violation_flags;  // Bitfield (see Section 3.3)
    uint8_t  risk_assessment;       // Aggregate risk [0, 255]
    uint8_t  dimension_scores[6];   // Per-dimension optional
    uint8_t  profile_id;            // Echo of profile used
    uint8_t  reserved;
    uint32_t latency_us;            // Measured eval time
    uint32_t timestamp_us;          // Response timestamp
} __attribute__((packed));
```

**Error Codes**:
- `0x00`: Success
- `0x01`: Invalid frame format
- `0x02`: Unknown profile_id
- `0x03`: Queue full (rate limit)
- `0xFF`: Internal error

**C API Example**:

```c
#include "zynq_em_client.h"

// Initialize connection to Zynq EM service
em_handle_t em = zynq_em_init("/dev/mem", SHM_BASE_ADDR);

// Build ethics frame
uint64_t frame = build_ethics_frame(
    .distance_band = 2,
    .relative_speed = 15,
    .vulnerable_presence = 0x1,  // child present
    .risk_band = 2,
    .profile_id = 0
);

// Evaluate
EthicsFrameRequest req = {
    .frame_id = get_next_frame_id(),
    .option_id = 1,
    .profile_id = 0,
    .priority = PRIORITY_CRITICAL,
    .ethics_frame = frame,
    .timestamp_us = get_timestamp_us()
};

EthicsFrameResponse resp;
int result = zynq_em_eval(em, &req, &resp, TIMEOUT_200US);

if (result == 0 && resp.hard_violation_flags == 0) {
    // Safe to proceed
    float score = resp.normative_score / 65535.0;
    execute_action_if_acceptable(option_id, score);
} else {
    // Forbidden or error
    log_veto(option_id, resp.hard_violation_flags);
    replan();
}
```

**Python API** (via `erisml-lib`):

```python
from erisml.ethics.hw_em_client import ZynqEMClient

em_client = ZynqEMClient(device="/dev/mem", base_addr=0x43C00000)

# Convert EthicalFacts to EthicsFrame
ethics_frame = em_client.build_frame(
    distance=5.0,
    relative_speed=1.5,
    vulnerable_entities=["child"],
    profile_name="urban_pedestrian"
)

# Evaluate
result = em_client.evaluate(
    option_id="continue_forward",
    frame=ethics_frame,
    priority="critical"
)

if result.is_forbidden():
    print(f"Action forbidden: {result.violation_reasons}")
else:
    print(f"Score: {result.normative_score:.3f}")
```

### 7.2 Nano PEA/OIA APIs

**PEA Service** (REST API on Nano):

```
POST /pea/evaluate
{
    "agent_id": "robot_007",
    "decision_id": "dec_12345",
    "action": {
        "type": "navigate",
        "parameters": {...}
    },
    "ethical_facts": {...},
    "agent_em_result": {
        "normative_score": 0.94,
        "hard_violations": []
    }
}

Response:
{
    "decision": "ALLOW" | "FORBID" | "ESCALATE",
    "pea_score": 0.94,
    "rationale": "...",
    "required_actions": []
}
```

**OIA Service**:

```python
from erisml.ethics.enforcement import OIAClient

oia = OIAClient(nano_address="192.168.1.100:8080")

# Request oversight report
report = oia.generate_report(
    time_window="last_7_days",
    focus_areas=["bias", "drift", "pea_health"]
)

print(report.summary)
# "7 days, 45,203 decisions analyzed.
#  No significant bias detected.
#  Minor drift in safety scores (-0.02 avg).
#  PEA availability: 99.7%."

# Get real-time alerts
for alert in oia.stream_alerts():
    if alert.severity == "CRITICAL":
        notify_human_operators(alert)
```

---

## 8. Implementation Roadmap in `erisml-lib`

### 8.1 New Modules

**1. Hardware EM Client** (`src/erisml/ethics/hw_em_client.py`)

```python
class ZynqEMClient:
    def build_frame(self, ethical_facts: EthicalFacts, 
                   profile: str) -> EthicsFrame
    def evaluate(self, option_id: str, frame: EthicsFrame,
                priority: str) -> EthicsEvaluation
    def batch_evaluate(self, frames: List[EthicsFrame]) -> List[EthicsEvaluation]
```

**2. Profile Compiler** (`src/erisml/ethics/interop/hw_profile_compiler.py`)

```python
class DEMEProfileCompiler:
    def compile_to_hardware(self, profile: DEMEProfileV03) -> HardwareConfig
    def validate_compilation(self, profile: DEMEProfileV03, 
                           hw_config: HardwareConfig) -> ValidationReport
    def generate_verilog(self, hw_config: HardwareConfig) -> str
```

**3. PEA Agent** (`src/erisml/ethics/enforcement/pea.py`)

```python
class PrimaryEnforcementAgent:
    def __init__(self, em_client: ZynqEMClient, mode: EnforcementMode)
    def evaluate_decision(self, decision: AgentDecision) -> Verdict
    def get_statistics(self) -> PEAStatistics
```

**4. OIA Agent** (`src/erisml/ethics/enforcement/oia.py`)

```python
class OversightAgent:
    def analyze_decision_log(self, log: DecisionLog) -> OversightReport
    def detect_bias(self, decisions: List[Decision]) -> BiasReport
    def detect_drift(self, recent: DecisionLog, baseline: DecisionLog) -> DriftReport
    def monitor_pea(self, pea: PrimaryEnforcementAgent) -> PEAHealthReport
```

### 8.2 Extended Examples

**Example 1**: Self-policing delivery robot (Tier 1)

```python
# examples/delivery_robot_self_policing.py
from erisml.ethics.hw_em_client import ZynqEMClient
from erisml.ethics.domain import EthicalFacts
from erisml.ethics.governance import resolve_decision

em = ZynqEMClient.connect()
profile = load_deme_profile("urban_delivery")

while robot.is_operating():
    # Perception
    state = robot.get_world_state()
    
    # Planning
    candidates = planner.generate_trajectories(state)
    
    # Ethics evaluation
    for candidate in candidates:
        facts = build_ethical_facts(state, candidate)
        hw_result = em.evaluate(candidate.id, facts, profile)
        
        if hw_result.is_forbidden():
            candidates.remove(candidate)
            log_veto(candidate, hw_result.violations)
    
    # Aggregation & selection
    if candidates:
        best = resolve_decision(candidates, profile)
        robot.execute(best)
    else:
        robot.emergency_stop("All options vetoed")
```

**Example 2**: Warehouse robot with PEA oversight (Tier 2)

```python
# examples/warehouse_robot_with_pea.py
from erisml.ethics.enforcement import PEAClient

pea = PEAClient(nano_address="192.168.1.100")
em = ZynqEMClient.connect()

while robot.is_operating():
    state = robot.get_world_state()
    action = planner.plan_next_action(state)
    
    # Local ethics check
    facts = build_ethical_facts(state, action)
    local_result = em.evaluate(action.id, facts, "warehouse_safety")
    
    # PEA enforcement
    if action.risk_level == "HIGH":
        pea_verdict = pea.evaluate_decision(
            agent_id="warehouse_bot_03",
            action=action,
            facts=facts,
            local_em_result=local_result
        )
        
        if pea_verdict.decision == "FORBID":
            log_override(action, pea_verdict.rationale)
            continue
        elif pea_verdict.decision == "ESCALATE":
            await_human_approval(action)
    
    robot.execute(action)
```

### 8.3 Testing Infrastructure

**Hardware-in-Loop Simulator**:

```python
# tests/test_hw_em_simulator.py
class ZynqEMSimulator:
    """Simulates Zynq EM hardware for testing without actual FPGA"""
    
    def __init__(self, profile: DEMEProfileV03):
        self.compiled_rules = compile_profile(profile)
    
    def evaluate(self, frame: EthicsFrame) -> EthicsEvaluation:
        # Simulate PL combinational logic
        violations = self._check_hard_vetoes(frame)
        
        # Simulate PL pipelined arithmetic
        score = self._compute_score(frame)
        
        # Add simulated latency
        time.sleep(0.00001)  # 10μs
        
        return EthicsEvaluation(
            normative_score=score,
            hard_violation_flags=violations,
            latency_us=10
        )
```

**Validation Test Suite**:

```python
def test_hw_sw_equivalence():
    """Verify hardware and software EMs produce equivalent results"""
    
    profile = load_test_profile()
    sw_em = SoftwareEM(profile)
    hw_em = ZynqEMSimulator(profile)
    
    # Generate 10,000 random scenarios
    test_cases = generate_random_ethical_facts(n=10000)
    
    for facts in test_cases:
        sw_result = sw_em.evaluate(facts)
        hw_frame = build_frame(facts)
        hw_result = hw_em.evaluate(hw_frame)
        
        # Hard vetoes must match exactly
        assert sw_result.is_forbidden() == hw_result.is_forbidden()
        
        # Scores must be close
        assert abs(sw_result.score - hw_result.score) < 0.05
```

---

## 9. Failure Modes and Mitigations

### 9.1 Hardware Failures

| Failure Mode | Symptom | Detection | Mitigation | Recovery |
|--------------|---------|-----------|------------|----------|
| **Zynq EM Crash** | No response within timeout | Watchdog timer (500μs) | Agent enters safe-stop mode | Automatic reboot, diagnostic log |
| **PL Corruption** | Incorrect outputs, inconsistent results | Self-test on each evaluation | Disable HW EM, fall back to SW | Reconfigure bitstream |
| **Shared Memory Fault** | Read/write errors | Parity checks, CRC | Switch to SPI transport | OS-level memory scrubbing |
| **Power Loss** | System shutdown | Voltage monitoring | Graceful shutdown, log flush | Resume with last known good profile |

### 9.2 Logical Failures

| Failure Mode | Symptom | Detection | Mitigation | Recovery |
|--------------|---------|-----------|------------|----------|
| **False Negative** (missed violation) | Unsafe action not flagged | Post-hoc OIA analysis, incident review | Conservative thresholds, redundancy | Update profile, recompile |
| **False Positive** (over-conservative) | Safe actions blocked, mission failure | High forbid rate (>20%), user complaints | Lower thresholds, expand exceptions | Profile tuning, A/B testing |
| **Distillation Error** | HW EM diverges from SW EM intent | Validation test suite failures | Don't deploy, fix compiler | Improve compiler, add test cases |
| **Profile Version Skew** | Agent expects v2.1, Zynq has v2.0 | Version mismatch in logs | Use closest match with warning | Coordinate profile updates across fleet |

### 9.3 Security & Adversarial Failures

| Failure Mode | Symptom | Detection | Mitigation | Recovery |
|--------------|---------|-----------|------------|----------|
| **Input Manipulation** | Agent sends false `EthicsFrame` data | OIA cross-validation with independent sensors | Rate-limit offending agent, alert OIA | Incident investigation, agent audit |
| **DOS Attack** | One agent floods EM service | Queue saturation, latency spike | Per-agent token bucket, temporary suspension | Block offending agent |
| **Profile Tampering** | Unauthorized profile update | Cryptographic signature verification | Reject unsigned updates | Restore last signed profile, audit access |
| **PEA Bypass** | Agent executes without PEA approval | OIA monitors command logs | Automatic agent shutdown | Disciplinary action, code review |

### 9.4 Graceful Degradation Strategy

**Degradation Levels**:

1. **Normal Operation**: Zynq HW EM + Software EM + PEA + OIA all active
2. **Degraded (HW Failure)**: Software EM only, increased latency (5-10ms), continue operation
3. **Degraded (PEA Failure)**: Self-policing with Zynq HW EM, alert humans
4. **Safe Mode**: Minimal operations only (return to base, no new tasks)
5. **Emergency Stop**: Complete shutdown if no reliable ethics path available

**Transition Logic**:

```python
def determine_operating_mode():
    if zynq_em.is_healthy() and pea.is_healthy() and oia.is_healthy():
        return NORMAL
    elif zynq_em.is_healthy() and not pea.is_healthy():
        alert_operators("PEA failure, self-policing mode")
        return DEGRADED_NO_PEA
    elif not zynq_em.is_healthy() and sw_em.is_healthy():
        alert_operators("HW EM failure, SW EM fallback")
        return DEGRADED_SW_ONLY
    elif not sw_em.is_healthy():
        alert_operators("All EM paths failed, safe mode")
        return SAFE_MODE
    else:
        alert_operators("CRITICAL: No ethics path available")
        return EMERGENCY_STOP
```

---

## 10. Discussion and Future Work

### 10.1 Benefits

**1. Latency-First Ethics**  
Ethical checks move into the same timing budget as control logic (≤200μs), closing the gap between declared values and real-world behavior. This enables ethics in the reflex band (1-5ms) where safety-critical decisions occur.

**2. Separation of Concerns**  
DEME profiles remain the **source of ethical truth**; Zynq hardware is a **derived, safety-critical implementation**. This preserves democratic governance while enabling real-time execution.

**3. Risk-Tiered Deployment**  
The same infrastructure supports self-policing agents (Tier 1), centralized enforcement (Tier 2), and oversight (OIA), matching deployment complexity to actual risk level.

**4. Auditability Through Determinism**  
Hardware execution is bit-reproducible, making debugging and incident analysis vastly easier than probabilistic LLM-based ethics. Every decision can be replayed exactly.

**5. Certification Pathway**  
Bounded latency, formal verification potential, and separation from ML components create a path toward safety certification (e.g., IEC 61508, ISO 26262).

**6. Cognitive Realism**  
The reflex/tactical/strategic split mirrors human moral psychology: fast intuitive responses (System 1) backed by slower deliberation (System 2). Hardware EM provides the fast path.

### 10.2 Limitations

**1. Distillation Gap**  
Not all DEME richness fits in compact `EthicsFrame` and FPGA logic. Complex stakeholder reasoning, probabilistic deliberation, and context-dependent nuance require the full software stack.

**Mitigation**: Use hardware EM for hard constraints and safety-critical reflexes; escalate ambiguous cases to software EMs or PEA.

**2. Specification Risk**  
Hardware EM is only as good as the profile compiler. Bugs in compilation create dangerous blind spots that may not be caught until deployment.

**Mitigation**: Extensive validation testing, formal verification (future work), conservative bias in hard vetoes.

**3. Update Latency**  
Propagating governance decisions to deployed hardware takes days/weeks (bitstream compilation, testing, rollout), creating democratic lag.

**Mitigation**: Over-the-air updates, staged rollouts, version tolerance.

**4. Resource Constraints**  
FPGA logic is finite (~5K LUTs for baseline); adding dimensions or complexity may require larger/more expensive FPGAs.

**Mitigation**: Profile prioritization (implement most critical rules first), multi-stage evaluation (fast vetoes + slower scoring).

**5. Oversight Complexity**  
PEA + OIA add 15-20W power, cost, and failure modes. Not all deployments can afford this overhead.

**Mitigation**: Tier 0/1 deployments skip enforcement pod; scale up only when risk justifies it.

### 10.3 Future Work

**Near-Term (6-12 months)**:

1. **Reference Implementation**:
   - Complete Zynq-7020 bitstream for baseline `EthicsFrame`
   - C/Python client libraries
   - Hardware-in-loop simulator for testing

2. **Profile Compiler V1**:
   - Rule-based extraction from `DEMEProfileV03`
   - Validation test suite (10K+ scenarios)
   - Compilation time: <5 minutes per profile

3. **Field Trial**:
   - Deploy on 5-10 warehouse robots (Tier 1)
   - Measure latency, false positive/negative rates
   - OIA monitoring for 90 days

**Medium-Term (1-2 years)**:

4. **Advanced Profile Compilation**:
   - Neural network distillation for complex scoring functions
   - Formal verification of hard veto logic using SymbiYosys
   - Automatic optimization for FPGA resource usage

5. **Richer Telemetry**:
   - Real-time visualization dashboard for OIA
   - Explainable AI techniques for hardware EM decisions
   - Integration with governance board workflows

6. **Hardware Variants**:
   - Low-power version (Zynq-7010, <1W)
   - High-performance version (Zynq Ultrascale+, 100K+ LUTs)
   - ASIC study for volume production

**Long-Term (2-5 years)**:

7. **Standardization**:
   - Propose `EthicsFrame` format as open standard
   - Collaborate with robotics/automotive industry on common EM interfaces
   - Contribute to ISO/IEC safety standard development

8. **Federated DEME**:
   - Multi-stakeholder profiles with cryptographic guarantees
   - Blockchain-based governance audit trails
   - Cross-organizational OIA coordination

9. **Adaptive Hardware EMs**:
   - Runtime reconfiguration based on context
   - Partial FPGA reconfiguration for dynamic profile switching
   - Self-tuning thresholds via reinforcement learning (with human oversight)

---

## 11. Related Work

### 11.1 AI Ethics Frameworks

- **IEEE P7000 Series**: Model process for addressing ethical concerns [1]
- **EU AI Act**: Risk-based regulatory framework for AI systems [2]
- **Principled AI**: Microsoft's responsible AI principles [3]
- **Constitutional AI**: Anthropic's approach to AI alignment [4]

DEME distinguishes itself through **democratic governance** and **hardware acceleration** for real-time constraints.

### 11.2 Robot Safety & Verification

- **Runtime Verification for Robotics**: Leucker & Schallhart's RV framework [5]
- **Simplex Architecture**: Sha et al.'s approach to safety-critical control [6]
- **Formal Methods in Robotics**: Survey by Luckcuck et al. [7]

This work extends these by making **ethics** (not just safety) a verified real-time constraint.

### 11.3 Hardware Acceleration for AI

- **FPGA Neural Network Accelerators**: Survey by Guo et al. [8]
- **Embedded AI Ethics**: Limited prior work; most ethics systems are cloud-based

**Gap addressed**: Prior work accelerates perception/planning, not ethical reasoning itself.

### 11.4 Democratic AI Governance

- **Participatory AI Design**: Kalluri et al. on community engagement [9]
- **Linux Foundation AAIF**: Industry collaboration on AI ethics frameworks [10]
- **Fairlearn**: Microsoft's toolkit for algorithmic fairness [11]

DEME provides **technical infrastructure** for these governance models to execute at machine speed.

---

## 12. Conclusion

For mobile AI agents operating in the physical world, ethics cannot be a slow, advisory overlay disconnected from real-time control. It must run at **control-loop speed** to be meaningful.

The architecture outlined here makes that concrete:

1. A **Zynq-7020 FPGA-based EM accelerator** provides a **latency-first execution path** (<200μs worst-case) for distilled DEME rules and hard vetoes, derived from democratically governed profiles.

2. **Agents can self-police** (Tier 1) by calling this EM service directly, ensuring every action is checked against ethical constraints before touching the physical world.

3. For high-risk deployments (Tier 2), an **optional Jetson Nano enforcement pod** provides:
   - **Primary Enforcement Agent (PEA)**: Centralized gatekeeper for safety-critical commands
   - **Oversight Agent (OIA)**: Meta-level monitor for bias, drift, and gaming

4. A **profile compiler** translates rich DEME governance into hardware-executable logic, maintaining democratic control while enabling microsecond-scale decisions.

This keeps DEME's core promise intact:

> **Ethics is modular, democratically governed, and technologically grounded—all the way down to the control cycles of the robot.**

By providing both the low-latency infrastructure (hardware EM) and the governance framework (PEA/OIA, democratic profiles), we enable mobile AI agents to be both **fast** and **ethical**—not as a trade-off, but as a unified system property.

The path forward requires:
- Building and validating the reference Zynq implementation
- Deploying in real-world field trials
- Iterating on the profile compilation process
- Engaging with standards bodies and the broader AI ethics community

We invite collaboration from robotics engineers, FPGA developers, ethicists, and governance researchers to refine and deploy this architecture.

---

## 13. References

[1] IEEE Standards Association. (2021). IEEE 7000-2021 - Model Process for Addressing Ethical Concerns.

[2] European Commission. (2024). Regulation on Artificial Intelligence (AI Act).

[3] Aether Committee. (2018). Microsoft AI Principles.

[4] Bai et al. (2022). "Constitutional AI: Harmlessness from AI Feedback." Anthropic.

[5] Leucker, M., & Schallhart, C. (2009). "A brief account of runtime verification." Journal of Logic and Algebraic Programming.

[6] Sha, L. et al. (1999). "The Simplex Architecture for Safe Online Control System Upgrades." American Control Conference.

[7] Luckcuck, M. et al. (2019). "Formal Specification and Verification of Autonomous Robotic Systems: A Survey." ACM Computing Surveys.

[8] Guo, K. et al. (2019). "A Survey of FPGA-Based Neural Network Accelerators." ACM Transactions on Reconfigurable Technology and Systems.

[9] Kalluri, P. et al. (2023). "Participatory Approaches to Machine Learning." CSCW.

[10] Linux Foundation. (2024). AI Accountability and Integrity Framework (AAIF).

[11] Bird, S. et al. (2020). "Fairlearn: A toolkit for assessing and improving fairness in AI." Microsoft Research.

---

## Appendix A: Glossary

- **DEME**: Democratically governed Ethical Modules for autonomous systems
- **EM**: Ethics Module, a pluggable component that evaluates ethical dimensions
- **EthicalFacts**: Structured representation of ethically relevant features
- **EthicsFrame**: Compact, hardware-friendly encoding of EthicalFacts
- **PEA**: Primary Enforcement Agent, centralized ethics gatekeeper
- **OIA**: Oversight / Internal Affairs Agent, meta-level monitor
- **Hard Veto**: Absolute prohibition enforced by hardware EM
- **Normative Score**: [0, 1] scalar representing ethical acceptability
- **Reflex Band**: 1-5ms timescale for safety-critical decisions
- **Tactical Band**: Tens of milliseconds for local planning
- **Strategic Band**: Seconds+ for high-level deliberation

---

## Appendix B: Hardware Bill of Materials

**Minimal Deployment (Tier 1: Self-Policing)**:

| Component | Part Number | Qty | Unit Cost | Purpose |
|-----------|-------------|-----|-----------|---------|
| Zynq-7020 SoC | XC7Z020-CLG484 | 1 | $150 | EM accelerator |
| DDR3 RAM | MT41K256M16 | 2 | $15 | PS memory |
| Flash Storage | MT29F4G | 1 | $10 | Boot + config |
| Power Supply | TPS65086100 | 1 | $8 | Multi-rail power |
| PCB | Custom 6-layer | 1 | $50 | Integration |
| **Total** | | | **~$250** | |

**Full Deployment (Tier 2: with Enforcement Pod)**:

| Component | Part Number | Qty | Unit Cost | Purpose |
|-----------|-------------|-----|-----------|---------|
| Above components | | 1 | $250 | EM accelerator |
| Jetson Nano 4GB | 945-13450-0000-100 | 1 | $130 | PEA/OIA host |
| Storage (NVMe) | Samsung 970 EVO 128GB | 1 | $40 | Decision logs |
| Ethernet Switch | Microsemi VSC7512 | 1 | $25 | Agent connectivity |
| Enclosure | Custom CNC | 1 | $80 | Rugged housing |
| **Total** | | | **~$525** | |

**Note**: Prices are approximate (2024 USD, volume 100+). Full system includes cooling, cables, and integration labor (~$200 additional).

---

---

## Appendix C: Detailed Case Study - Autonomous Delivery Robot

### C.1 Scenario Description

**Context**: Urban delivery robot operating in mixed pedestrian/vehicle environment during evening rush hour.

**Robot Specifications**:
- Platform: 4-wheeled differential drive, 80cm × 60cm × 100cm
- Sensors: 360° LIDAR, 4× RGB cameras, IMU, GPS
- Compute: Jetson Xavier NX (main controller) + Zynq-7020 (EM accelerator)
- Max speed: 2.0 m/s, typical cruise: 1.2 m/s
- Deployment tier: Tier 1 (self-policing with hardware EM)

**Mission**: Deliver package from restaurant to residential address, 800m route.

### C.2 Critical Decision Point: Crosswalk Encounter

**Timestamp**: 2025-12-13 18:47:23.450 UTC  
**Location**: Intersection of Main St & 2nd Ave (crosswalk)  
**Mission phase**: En route (450m completed, 350m remaining)

**Perceptual State** (t=0ms):
```
LIDAR detections:
  - Object 1: Adult pedestrian, 8.2m ahead, stationary at curb
  - Object 2: Child (estimated age 6-8), 5.1m ahead, moving toward crosswalk (0.8 m/s)
  - Object 3: Cyclist, 15m ahead, crossing perpendicular

Camera inference:
  - Child detected with 0.94 confidence
  - Crosswalk painted lines visible
  - Traffic signal: pedestrian WALK active

World model:
  - Robot position: 37.7749°N, 122.4194°W
  - Heading: 045° (northeast)
  - Current velocity: 1.2 m/s
  - Zone classification: PROTECTED_PEDESTRIAN_ZONE (school nearby)
```

### C.3 Planning and Option Generation (t=1ms)

**Local planner** generates 5 candidate trajectories:

**Option A: Continue Current Speed**
- Maintain 1.2 m/s for next 3 seconds
- Path: straight through crosswalk
- Time to crosswalk: 4.25 seconds
- Predicted child position at that time: in crosswalk (collision risk)

**Option B: Slow to Cautious Speed**
- Decelerate to 0.4 m/s over 1 second
- Maintain reduced speed through crosswalk
- Time to crosswalk: 12.75 seconds
- Predicted child position: crossed or returned to curb

**Option C: Stop Before Crosswalk**
- Full deceleration, stop at 1m before crosswalk edge
- Stopping distance: 2.5m (at current speed)
- Resume when crosswalk clear

**Option D: Navigate Around (Left)**
- Swerve 1.5m left, bypass crosswalk on street side
- Requires entering vehicle lane briefly
- Violates local traffic rules (robot must use sidewalk/crosswalk)

**Option E: Navigate Around (Right)**
- Swerve 1.5m right onto grass verge
- Avoids crosswalk entirely
- Potential private property violation, terrain uncertainty

### C.4 Ethical Facts Construction (t=1.5ms)

For each option, build `EthicalFacts`:

**EthicalFacts for Option A** (continue):
```python
EthicalFacts(
    option_id="opt_a_continue",
    
    # Safety dimension
    collision_risk=0.72,  # HIGH - child trajectory intersects
    injury_severity_potential=0.85,  # Child victim
    stopping_distance_margin=-0.3,  # NEGATIVE - cannot stop in time
    
    # Rights dimension
    pedestrian_right_of_way=True,  # Child has legal right in crosswalk
    protected_zone_active=True,  # School zone, enhanced protections
    
    # Vulnerable populations
    child_present=True,
    child_age_estimate=7,
    vulnerable_entity_count=1,
    
    # Legal/procedural
    traffic_law_compliance=False,  # Failure to yield
    zone_restrictions_compliance=True,
    
    # Environmental
    noise_impact=0.0,  # Electric motor
    emissions_impact=0.0,
    
    # Mission/efficiency
    mission_completion_probability=0.95,
    time_to_goal_impact=0.0,  # No delay
    
    # Epistemic
    perception_confidence=0.94,
    prediction_confidence=0.78,
    planning_uncertainty=0.15
)
```

**EthicalFacts for Option C** (stop):
```python
EthicalFacts(
    option_id="opt_c_stop",
    
    # Safety dimension
    collision_risk=0.02,  # VERY LOW
    injury_severity_potential=0.05,
    stopping_distance_margin=1.5,  # 1.5m safety buffer
    
    # Rights dimension
    pedestrian_right_of_way=True,
    protected_zone_active=True,
    
    # Vulnerable populations
    child_present=True,
    child_age_estimate=7,
    vulnerable_entity_count=1,
    
    # Legal/procedural
    traffic_law_compliance=True,  # Yields as required
    zone_restrictions_compliance=True,
    
    # Environmental
    noise_impact=0.0,
    emissions_impact=0.0,
    
    # Mission/efficiency
    mission_completion_probability=0.92,  # Slight delay
    time_to_goal_impact=15.0,  # +15 seconds
    
    # Epistemic
    perception_confidence=0.94,
    prediction_confidence=0.95,  # Stopping is predictable
    planning_uncertainty=0.05
)
```

### C.5 EthicsFrame Encoding (t=2.0ms)

Convert to hardware-compatible format:

**Option A → EthicsFrame**:
```
distance_band = 0x02         # 4-6m range
relative_speed = 0x0C        # +1.2 m/s (closing)
zone_flags = 0x5             # [0001 0101] = protected_zone + legal_constraint
vulnerable_presence = 0x1    # [0001] = child_present
risk_band = 0x3              # CRITICAL (highest)
profile_slice_id = 0x1       # "urban_pedestrian_priority"
action_type = 0x0010         # CONTINUE_MOTION
option_id = 0x0001

Encoded (hex): 0x0001 0010 0135 030C 0002
```

**Option C → EthicsFrame**:
```
distance_band = 0x02         # 4-6m range
relative_speed = 0x00        # 0 m/s (stopping)
zone_flags = 0x5             # protected_zone + legal_constraint
vulnerable_presence = 0x1    # child_present
risk_band = 0x1              # LOW (stopping is safe)
profile_slice_id = 0x1       # "urban_pedestrian_priority"
action_type = 0x0020         # EMERGENCY_STOP
option_id = 0x0003

Encoded (hex): 0x0003 0020 0115 0100 0002
```

### C.6 Zynq Hardware EM Evaluation (t=2.05ms - 2.15ms)

**Zynq PL evaluates both frames in parallel (10μs each)**:

**Option A Evaluation**:

*Combinational veto checks* (5ns):
```verilog
// Check 1: Imminent collision with vulnerable entity
collision_veto = (distance_band <= 0x02) &&    // <6m
                 (relative_speed > 0x05) &&     // >0.5 m/s closing
                 (vulnerable_presence != 0) &&   // vulnerable present
                 (risk_band >= 0x02);            // moderate+ risk
// Result: TRUE → HARD_VULNERABLE_RISK flag SET

// Check 2: Rights violation
rights_veto = (zone_flags & 0x01) &&            // protected zone
              (action_type == 0x0010) &&         // continue motion
              (collision_veto == TRUE);          // and collision risk
// Result: TRUE → HARD_RIGHTS_ZONE flag SET
```

*Pipelined score computation* (100ns):
```
Pipeline stage 1: Load profile weights
  w_safety = 0.40 (40%)
  w_rights = 0.25 (25%)
  w_welfare = 0.20 (20%)
  w_mission = 0.15 (15%)

Pipeline stage 2: Compute dimension scores
  safety_score = f_safety(distance_band, relative_speed, risk_band)
               = (0x02 / 0x07) * (1.0 - (0x0C / 0xFF)) * (1.0 - 0x03/0x03)
               ≈ 0.28 * 0.95 * 0.0
               ≈ 0.0
  
  rights_score = f_rights(zone_flags, vulnerable_presence)
               = (collision_with_right_of_way) ? 0.0 : 1.0
               = 0.0
  
  welfare_score = f_welfare(vulnerable_presence, injury_potential)
                = 0.15  # Very low (child endangered)

Pipeline stage 3: Weighted sum
  normative_score = 0.40 * 0.0 + 0.25 * 0.0 + 0.20 * 0.15 + 0.15 * 1.0
                  = 0.0 + 0.0 + 0.03 + 0.15
                  = 0.18
  
  normative_score_hw = 0.18 * 65535 = 11796 (0x2E14)

Pipeline stage 4: Apply lexical overrides
  # Profile specifies: "rights violations override utility"
  if (rights_veto == TRUE):
      normative_score_hw = min(normative_score_hw, 0.15 * 65535)
  # Result: 0.18 → 0.15 (capped)

Pipeline stage 5: Output assembly
  Result: 0x2710 (0.15 in fixed-point)
```

**Option A Result**:
```
EthicsEvaluation {
    normative_score_hw: 0x2710 (0.15),
    hard_violation_flags: 0x0009,  // COLLISION + RIGHTS_ZONE
    risk_assessment: 0xE0 (224/255 = critical),
    dimension_scores: [0, 0, 38, 255, ...],
    latency_us: 10
}
→ VERDICT: FORBIDDEN (hard violations present)
```

**Option C Evaluation** (parallel):

*Combinational veto checks*:
```verilog
// All veto conditions FALSE
collision_veto = FALSE   // stopping, no collision
rights_veto = FALSE      // yielding properly
legal_veto = FALSE       // compliant
```

*Score computation*:
```
safety_score = 0.95      # Stopping is safe
rights_score = 1.0       # Respecting right-of-way
welfare_score = 0.90     # Protecting child
mission_score = 0.85     # Minor delay acceptable

normative_score = 0.40*0.95 + 0.25*1.0 + 0.20*0.90 + 0.15*0.85
                = 0.38 + 0.25 + 0.18 + 0.13
                = 0.94

normative_score_hw = 0.94 * 65535 = 61603 (0xF0A3)
```

**Option C Result**:
```
EthicsEvaluation {
    normative_score_hw: 0xF0A3 (0.94),
    hard_violation_flags: 0x0000,  // No violations
    risk_assessment: 0x10 (16/255 = low),
    dimension_scores: [242, 255, 230, 217, ...],
    latency_us: 9
}
→ VERDICT: STRONGLY_PREFER
```

### C.7 Local Decision Aggregation (t=2.2ms - 3.0ms)

**Agent's decision logic**:

```python
results = {
    'opt_a': hw_em_result_a,  # score=0.15, FORBIDDEN
    'opt_b': hw_em_result_b,  # score=0.68, ACCEPTABLE
    'opt_c': hw_em_result_c,  # score=0.94, PREFERRED
    'opt_d': hw_em_result_d,  # score=0.35, legal_violation
    'opt_e': hw_em_result_e,  # score=0.42, property_violation
}

# Filter out forbidden options
viable = [opt for opt in results 
          if results[opt].hard_violation_flags == 0]
# viable = ['opt_b', 'opt_c']

# Apply DEME profile aggregation
profile = load_profile("urban_pedestrian_priority_v2.1")

# Lexical layers (checked in order):
# Layer 1: Rights and safety hard constraints (already filtered)
# Layer 2: Maximize welfare for vulnerable populations
# Layer 3: Mission efficiency

best_option = max(viable, key=lambda o: results[o].normative_score_hw)
# best_option = 'opt_c' (score 0.94 > opt_b score 0.68)

selected_action = options['opt_c']  # STOP
```

**Decision metadata logged**:
```json
{
    "timestamp_us": 1702492043452200,
    "decision_id": "dec_2025-12-13_18:47:23.452_001",
    "agent_id": "delivery_robot_007",
    "mission_id": "delivery_20251213_1845_abc123",
    
    "options_evaluated": 5,
    "options_forbidden": 3,
    "selected_option": "opt_c_stop",
    
    "hw_em_latency_us": 10,
    "total_ethics_latency_ms": 0.8,
    
    "rationale": [
        "Option A forbidden: HARD_VULNERABLE_RISK (child in path)",
        "Option A forbidden: HARD_RIGHTS_ZONE (pedestrian right-of-way)",
        "Option D forbidden: HARD_LEGAL_CONSTRAINT (traffic rules)",
        "Option E forbidden: HARD_RIGHTS_ZONE (property boundary)",
        "Option C selected: highest normative score (0.94), protects child"
    ],
    
    "profile_used": "urban_pedestrian_priority_v2.1",
    "profile_weights": {
        "safety": 0.40,
        "rights": 0.25,
        "welfare": 0.20,
        "mission": 0.15
    }
}
```

### C.8 Action Execution (t=3.5ms - 1000ms)

**Controller receives command**: "Emergency stop, maintain stop until crosswalk clear"

**Execution timeline**:
```
t=3.5ms:   Begin deceleration (-2.4 m/s²)
t=500ms:   Velocity reaches 0 m/s
t=520ms:   Robot stopped, 1.8m before crosswalk edge
t=2.5s:    Child crosses safely
t=4.0s:    Crosswalk clear, traffic signal changes
t=4.2s:    Resume motion at 0.6 m/s (cautious re-start)
t=10.0s:   Return to cruise speed 1.2 m/s
```

**Mission impact**: +15 seconds total delay (acceptable within tolerance)

### C.9 Post-Decision Analysis

**Scenario Outcome**: ✓ SUCCESS
- Child safety protected (zero risk of collision)
- Legal compliance maintained
- Rights respected (yielded to pedestrian)
- Mission completed with acceptable delay
- No human intervention required

**Counterfactual**: What if hardware EM was unavailable?

Using software EM only (10ms latency):
```
t=0ms:     Perception completes
t=1ms:     Planning completes
t=2ms:     Begin software EM evaluation
t=12ms:    Software EM completes → NEXT CONTROL CYCLE
           Robot has traveled additional 1.2cm during ethics check
           Still safe, but tighter margins
```

**Alternative**: If agent had ignored EM and selected Option A:
- Collision probability: 72%
- Estimated injury: Serious (child victim)
- Legal liability: Traffic violation + negligence
- Public trust: Severely damaged
- Regulatory response: Likely suspension of operations

**Hardware EM Value**: The <1ms ethics check enabled safe decision within control loop, maintaining predictable robot behavior.

### C.10 OIA Monitoring Insights

**Pattern detected** (after 30 days of operation):

```
OIA Report: Crosswalk Scenarios
================================
Total crosswalk encounters: 1,247
Emergency stops triggered: 89 (7.1%)
Slow-downs triggered: 412 (33.0%)
Continue-as-is (safe): 746 (59.8%)

Vulnerable entities involved:
  - Children: 45 cases (all resulted in stop or slow)
  - Elderly: 28 cases (all resulted in stop or slow)
  - Mobility aids: 16 cases (all resulted in stop)
  
False positive rate: 0.8%
  (8 stops where pedestrian was not actually crossing)
  
False negative rate: 0.0%
  (No cases of failing to stop when required)
  
Hardware EM performance:
  - Average latency: 11.2μs
  - Max latency observed: 47μs (well under 200μs spec)
  - No hardware faults detected
  - Veto flags accuracy: 100% (verified against post-hoc analysis)

Recommendation: Current profile tuning is excellent.
  Consider minor adjustment to reduce false positives
  (8 cases) while maintaining zero false negatives.
```

---

## Appendix D: Frequently Asked Questions

### D.1 Technical Questions

**Q: Why FPGA instead of ASIC?**

A: FPGAs offer crucial advantages for ethics:
- **Reconfigurability**: DEME profiles evolve through democratic governance; FPGAs can be updated in-field without hardware replacement
- **Transparency**: FPGA bitstreams are auditable; ASICs are black boxes
- **Development speed**: Iterate and validate designs faster
- **Volume economics**: For <100K units/year, FPGA NRE costs are lower than ASIC

ASICs become attractive at >500K units/year or for ultra-low-power applications (<0.5W).

**Q: Can the hardware EM be formally verified?**

A: Partially. We can formally verify:
- ✓ Combinational veto logic (using SymbiYosys or similar)
- ✓ Latency bounds (worst-case timing analysis)
- ✓ Arithmetic overflow/underflow conditions
- ✗ Semantic correctness of profile compilation (requires human judgment)
- ✗ Real-world appropriateness of weights (empirical validation needed)

Hardware verification proves "the EM does what the specification says," but not "the specification captures the right ethics."

**Q: What happens if LIDAR/camera fails?**

A: Sensor failures are detected by perception layer:
- Missing/corrupt sensor data → perception confidence drops
- Low confidence propagates to `EthicsFrame` (risk_band increases)
- Hardware EM becomes more conservative (lower scores, more vetoes)
- Agent enters degraded mode: slow down, increase safety margins, alert operators
- If all perception fails: emergency stop, refuse to move

Ethics system assumes sensor data is best-effort; it doesn't create false certainty.

**Q: How do you prevent "ethics washing" (claiming ethical behavior without substance)?**

A: Multiple mechanisms:
1. **Open specification**: This document and EthicsFrame format are public
2. **Auditable logs**: Every decision logged with EM outputs
3. **OIA monitoring**: Independent oversight detects gaming
4. **Third-party verification**: OIA logs can be audited by external ethics boards
5. **Democratic governance**: Stakeholders can propose profile changes
6. **Cryptographic signing**: Profile updates must be signed by governance authority

An agent claiming "DEME compliance" can be challenged: "Show us your decision logs and profile version."

### D.2 Ethical & Policy Questions

**Q: Who decides what goes into DEME profiles?**

A: The governance model is multi-stakeholder:
- **Default profiles**: Developed by DEME consortium (ethicists, engineers, community representatives)
- **Domain-specific profiles**: Customized by industry working groups (e.g., warehouse robotics, delivery, eldercare)
- **Local adaptations**: Regional/cultural adjustments via democratic process
- **Updates**: Propose → discuss → vote → implement cycle
- **Oversight**: Independent ethics boards review for bias and fairness

Governance framework draws on:
- IEEE P7000 participatory design
- AAIF multi-stakeholder model
- EU AI Act transparency requirements

**Q: What if stakeholders disagree?**

A: DEME profiles support multiple resolution modes:
- **Lexical priority**: Safety/rights first, then optimize welfare/efficiency
- **Weighted voting**: Stakeholder weights reflect power/vulnerability
- **Escalation**: Ambiguous cases punt to human review
- **A/B deployment**: Test alternative profiles in controlled settings
- **Minority protections**: Vetoes for fundamental rights violations

No governance system pleases everyone, but transparency enables contestation and improvement.

**Q: Can companies override DEME profiles for competitive advantage?**

A: Technical and policy barriers:
- **Cryptographic enforcement**: Profile updates require governance-board signatures
- **Regulatory mandates**: High-risk deployments (Tier 2) may require approved profiles
- **Public transparency**: Agents must disclose profile version
- **Liability incentives**: Using aggressive profiles increases legal risk
- **Reputation costs**: Public trust depends on ethical behavior

That said, enforcement requires vigilance. OIA monitors for deviations; regulatory audits check compliance.

**Q: Is this "ethics as compliance" (just following rules)?**

A: Yes and no. The hardware EM path is necessarily rule-based (latency constraints), but:
- **Rules derive from values**: DEME profiles encode principled positions, not arbitrary rules
- **Layered reasoning**: Fast reflexes (HW EM) → tactical deliberation (SW EM) → strategic reflection (LLM/human)
- **Continuous learning**: OIA feedback improves profiles over time
- **Epistemic humility**: System flags uncertainty, escalates hard cases

Ethics is rules + judgment + values. Hardware handles rules; software and humans handle judgment.

**Q: What about trolley-problem scenarios?**

A: Classic dilemma: "Swerve to avoid 5 people but hit 1, or stay course and hit 5?"

DEME's approach:
1. **Prevention**: Design systems to avoid such situations (better sensing, speed limits, exclusion zones)
2. **Lexical priorities**: Never deliberately harm (no "actively choosing to kill")
3. **Minimal harm**: If unavoidable, minimize total harm while respecting rights
4. **Transparency**: Log decisions, accept accountability
5. **Democracy**: Society decides priority ordering through profile governance

In practice: Most "trolley problems" are edge cases; focus on preventing the 99.9% of normal collisions first.

### D.3 Deployment Questions

**Q: What's the minimum viable deployment?**

A: Tier 1 (self-policing):
- 1× Zynq-7020 EM accelerator ($250 hardware)
- Integration with existing robot controller (1-2 person-months software work)
- Load baseline DEME profile
- Test in simulation + controlled environment (2-4 weeks)
- Deploy with human oversight (initial 100 hours)

Total: ~$5K-10K per robot for hardware + integration + testing.

**Q: Can this work for drones/aerial robots?**

A: Yes, with adaptations:
- **Weight**: Zynq+power budget adds ~150g (acceptable for mid-size drones)
- **Latency**: Even more critical (drones can't "stop and think" mid-air)
- **EthicsFrame**: Add altitude, airspace restrictions, failure recovery modes
- **Profiles**: Different stakeholders (airspace authorities, ground public, privacy concerns)

Aerial robotics is an excellent use case—arguably more urgent than ground robots due to safety risks.

**Q: What about very low-power robots (toy-scale)?**

A: Zynq-7020 is overkill. Alternatives:
- **Zynq-7010**: Smaller FPGA, 1-2W power, $100
- **Software-only EM**: If control loops are >50ms, pure software works
- **Cloud offload**: For non-safety-critical decisions (not recommended for safety)