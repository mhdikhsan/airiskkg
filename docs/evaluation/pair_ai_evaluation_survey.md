# PAIR-AI Workbench — Evaluation Survey

A user-study instrument for evaluating the PAIR-AI Architecture Workbench (design-time
AI risk assessment). It has two administrations around a single hands-on session:

- **Pre-survey** — background + how participants assess AI risk *today* + baseline familiarity.
- **Post-survey** — perceived **usefulness**, **accuracy** of the candidate findings, usability,
  trust, and a direct comparison against the participant's current practice.

Anchored to established scales (TAM for usefulness, SUS for usability) so results are
benchmarkable, with tool-specific items grounded in the actual Workbench workflow
(describe → annotate → run → read candidate findings).

> **Item codes** (e.g. `PU1`, `ACC3`) are stable analysis handles — keep them if you port
> this into Google Forms / Qualtrics / LimeSurvey. Items marked **[Core]** are the minimum
> viable instrument; **[Optional]** items add rigor but lengthen the session.

> **One framing rule the survey must respect** (same rule the tool respects): every PAIR-AI
> output is a **candidate** risk — a *structural disposition*, not a confirmed failure. Accuracy
> items below therefore ask whether a candidate finding **applies to this architecture**, never
> whether the tool "found a real bug." Please keep this wording if you edit them.

---

## 0. Administration

| | |
| --- | --- |
| **Design** | Within-subjects, pre/post around one session. No control group required; add one if comparing PAIR-AI vs. the participant's usual method on the same system. |
| **Session length** | ~45–60 min: 5 min pre-survey · 5 min intro · 20–30 min hands-on task · 10–15 min post-survey. |
| **Scale** | 5-point Likert throughout — **1 = Strongly disagree … 5 = Strongly agree** (SUS keeps its native 5-point). "N/A — didn't use / didn't notice" allowed on every Likert item; exclude N/A from means. |
| **Recording** | Screen + think-aloud is recommended but optional; the per-finding protocol (§3.2) is far richer with it. |
| **Anonymity** | Responses are anonymous; only aggregate results are reported. |

### Consent (show first)

> You are invited to help evaluate PAIR-AI, a research tool for design-time AI risk assessment.
> Participation is voluntary, takes about one hour, and you may stop at any time. Responses are
> anonymous and used only in aggregate for research on the tool. There are no right or wrong
> answers — we are evaluating the tool, not you. Proceeding indicates your consent.
>
> ☐ I have read the above and consent to participate.

---

## 1. Part A — Participant background *(pre-session)*

**BG1. [Core] Which best describes your primary role?**
- ☐ AI/ML engineer or data scientist
- ☐ Software architect / engineer
- ☐ Security engineer / red-teamer
- ☐ Risk, compliance, or AI-governance professional
- ☐ Researcher / academic
- ☐ Product manager
- ☐ Student
- ☐ Other: ______

**BG2. [Core] Years of hands-on experience building or shipping AI/ML systems.**
- ☐ None · ☐ <1 · ☐ 1–3 · ☐ 4–6 · ☐ 7+

**BG3. [Core] Years of experience doing security or risk assessment (of any kind of system).**
- ☐ None · ☐ <1 · ☐ 1–3 · ☐ 4–6 · ☐ 7+

**BG4. [Core] How much have you worked with LLM applications specifically (RAG, chatbots, agents, fine-tuning)?**
- ☐ Never · ☐ Tried a few · ☐ Built prototypes · ☐ Shipped to production · ☐ Build them regularly

**BG5. [Core] Familiarity with knowledge graphs / RDF / Turtle / SPARQL.**
*(The Workbench represents architectures as a Turtle graph; this contextualizes the ease-of-use results.)*
- ☐ None · ☐ Heard of them · ☐ Can read them · ☐ Can author them · ☐ Expert

**BG6. [Optional] How do you most often see AI system architectures documented in your work?**
- ☐ Not documented / in people's heads · ☐ Diagrams (slides, whiteboard, draw.io) · ☐ Code / IaC only
- ☐ Formal models (BPMN, UML, ontologies) · ☐ Other: ______

---

## 2. Part B — Current risk-assessment practice & familiarity *(pre-session, before seeing the tool)*

> Purpose: capture how you assess AI risk **today** and your **baseline familiarity**, so we can
> compare against your experience with PAIR-AI afterwards. Answer for your current practice.

### 2.1 Current practice

**CP1. [Core] Do you currently perform risk assessments for AI/ML systems?**
- ☐ Never · ☐ Rarely (ad hoc) · ☐ Occasionally · ☐ Regularly · ☐ It's a core part of my job

**CP2. [Core] At which stage(s) do you (or your team) assess AI risk? *(select all)***
- ☐ Design / architecture stage (before building)
- ☐ Pre-deployment review
- ☐ Post-deployment / in production
- ☐ Continuously / as part of CI
- ☐ We don't have a defined stage
- ☐ N/A

**CP3. [Core] What do you use today to assess AI risk? *(select all)***
- ☐ Nothing formal / gut feel / ad-hoc review
- ☐ Spreadsheets or a risk register
- ☐ Generic threat modeling (STRIDE, LINDDUN, attack trees)
- ☐ OWASP Top 10 for LLM Applications
- ☐ MIT AI Risk Repository
- ☐ IBM AI Risk Atlas
- ☐ NIST AI RMF
- ☐ ISO/IEC 23894 or ISO/IEC 42001
- ☐ EU AI Act obligations / conformity checks
- ☐ An internal/company framework or checklist
- ☐ External auditors / consultants
- ☐ Automated tooling (name it): ______
- ☐ Other: ______

**CP4. [Core] How is the assessment mostly carried out?**
- ☐ Fully manual (expert review) · ☐ Manual with checklists · ☐ Mix of manual + tooling
- ☐ Mostly automated · ☐ N/A

**CP5. [Optional] Roughly how long does a typical AI risk assessment take end-to-end?**
- ☐ <1 hour · ☐ A few hours · ☐ 1–2 days · ☐ About a week · ☐ Weeks or more · ☐ N/A

**CP6. [Core] Biggest pain points in how you assess AI risk today. *(select up to 3)***
- ☐ Too time-consuming / manual
- ☐ Requires scarce expertise
- ☐ Inconsistent / depends who does it
- ☐ Hard to know what risks even apply
- ☐ Hard to connect risks to concrete architecture
- ☐ Hard to keep up with new LLM-specific risks
- ☐ Findings aren't actionable (no clear mitigations)
- ☐ No good tooling exists
- ☐ Other: ______

**CP7. [Optional, open] In 1–2 sentences, describe how you would assess the risk of a new
LLM/RAG system today, if asked right now.**
> ______________________________________________

### 2.2 Baseline familiarity *(1 = Not at all familiar … 5 = Very familiar)*

| Code | Item | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- | --- |
| **FAM1 [Core]** | AI/LLM-specific security & safety risks in general | ☐ | ☐ | ☐ | ☐ | ☐ |
| **FAM2 [Core]** | OWASP Top 10 for LLM Applications | ☐ | ☐ | ☐ | ☐ | ☐ |
| **FAM3 [Core]** | MIT AI Risk Repository | ☐ | ☐ | ☐ | ☐ | ☐ |
| **FAM4 [Core]** | IBM AI Risk Atlas | ☐ | ☐ | ☐ | ☐ | ☐ |
| **FAM5 [Core]** | Reasoning about risk from an *architecture / design*, before any code runs | ☐ | ☐ | ☐ | ☐ | ☐ |
| **FAM6 [Optional]** | Mapping identified risks to concrete mitigations/controls | ☐ | ☐ | ☐ | ☐ | ☐ |

**FAM7. [Core] Right now, how confident are you that you could list the main risks of an
LLM/RAG architecture just by looking at its design?**
- ☐ Not at all · ☐ Slightly · ☐ Moderately · ☐ Very · ☐ Completely

**EXP1. [Optional, open] Before you try it: what would make a design-time AI-risk tool actually
useful to you? What would make you distrust or abandon it?**
> ______________________________________________

---

## 3. Part C — Post-session evaluation

> Administer **after** the hands-on task. The task (facilitator sets this up, see §5) should have
> the participant: load or build an architecture, annotate it with roles, run the assessment, and
> read the resulting candidate findings (mechanism, evidence, taxonomy links, suggested mitigations).

### 3.1 Perceived usefulness *(TAM-adapted; 1 = Strongly disagree … 5 = Strongly agree)*

| Code | Item | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- | --- |
| **PU1 [Core]** | Using PAIR-AI would improve the quality of my AI risk assessments. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **PU2 [Core]** | PAIR-AI helped surface risks I might otherwise have missed. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **PU3 [Core]** | PAIR-AI would make my risk assessment faster. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **PU4 [Core]** | The findings were relevant to the system I assessed. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **PU5 [Core]** | The suggested mitigations/controls were useful and actionable. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **PU6 [Optional]** | The taxonomy links (OWASP / MIT / IBM) added value to a finding. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **PU7 [Optional]** | The "risk mechanism" explanation helped me understand *why* a risk applies. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **PU8 [Optional]** | Highlighting the evidence elements in the diagram helped me judge each finding. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **PU9 [Core]** | I would use PAIR-AI in my real workflow. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **PU10 [Core]** | I would recommend PAIR-AI to a colleague. | ☐ | ☐ | ☐ | ☐ | ☐ |

### 3.2 Accuracy & quality of the findings

> **Framing reminder:** PAIR-AI outputs **candidate** risks — structural dispositions, not
> confirmed failures. So "accurate" here means the candidate **applies to the architecture you
> assessed** and its evidence/mechanism are right; and "missed" means a risk that *does* apply but
> was not raised. A candidate that doesn't apply is a **false alarm for this architecture**, not
> proof the tool is wrong in general.

**Aggregate accuracy items** *(1 = Strongly disagree … 5 = Strongly agree)*

| Code | Item | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- | --- |
| **ACC1 [Core]** | Overall, the candidate findings correctly reflect risks that apply to this architecture. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **ACC2 [Core]** | PAIR-AI captured the risks I consider **most important** for this system. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **ACC3 [Core]** | Few or none of the findings were false alarms (did not apply to this architecture). | ☐ | ☐ | ☐ | ☐ | ☐ |
| **ACC4 [Core]** | The **evidence** elements shown for each finding were the right ones. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **ACC5 [Optional]** | The **risk mechanism** stated for each finding was technically correct. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **ACC6 [Optional]** | The mapping of findings to OWASP/MIT/IBM taxonomy entries was appropriate. | ☐ | ☐ | ☐ | ☐ | ☐ |

**ACC7. [Core] How did the *number* of findings feel for this system?**
- ☐ Far too few · ☐ Slightly too few · ☐ About right · ☐ Slightly too many · ☐ Far too many (noise/fatigue)

**ACC8. [Core] Were there risks you believe apply to this architecture that PAIR-AI did **not**
raise? List them.** *(This is your perceived-recall signal.)*
> ______________________________________________

**ACC9. [Optional] Was there a finding you disagreed with (didn't apply, wrong evidence, or wrong
mechanism)? Which, and why?**
> ______________________________________________

#### Per-finding protocol *(Optional but high-value — enables a perceived precision/recall estimate)*

> For each candidate finding shown in the session, have the participant rate it. Pre-fill the
> **Finding** column from the participant's actual run. Precision-style scoring in §6.

| # | Finding (label + OWASP category) | Applies to this architecture? | Evidence correct? | Mitigations useful? |
| --- | --- | --- | --- | --- |
| 1 | ______ | ☐ Yes ☐ Partly ☐ No ☐ Unsure | ☐ Yes ☐ Partly ☐ No | ☐ Yes ☐ Partly ☐ No |
| 2 | ______ | ☐ Yes ☐ Partly ☐ No ☐ Unsure | ☐ Yes ☐ Partly ☐ No | ☐ Yes ☐ Partly ☐ No |
| 3 | ______ | ☐ Yes ☐ Partly ☐ No ☐ Unsure | ☐ Yes ☐ Partly ☐ No | ☐ Yes ☐ Partly ☐ No |
| … | ______ | ☐ Yes ☐ Partly ☐ No ☐ Unsure | ☐ Yes ☐ Partly ☐ No | ☐ Yes ☐ Partly ☐ No |

### 3.3 Candidate-framing comprehension *(a core claim of the tool — test whether it lands)*

**CF1. [Core] In your own words, what does a PAIR-AI "finding" tell you about the system?**
> ______________________________________________

**CF2. [Core] Which statement best matches your understanding of a finding? *(single choice — comprehension check)***
- ☐ A confirmed vulnerability that definitely exists in the system
- ☐ A risk the *architecture is predisposed to*, to be reviewed — may be mitigated by something not in the model *(intended)*
- ☐ A guarantee the system will fail this way
- ☐ A recommendation to add a specific tool/library
- ☐ Not sure

**CF3. [Core] The distinction "candidate risk, not confirmed failure" was communicated clearly by
the tool.** *(1 = Strongly disagree … 5 = Strongly agree)* → ☐1 ☐2 ☐3 ☐4 ☐5

**CF4. [Optional] An empty result would mean my system is safe.** *(reverse-scored — agreement here
indicates a misconception; the correct answer is Disagree.)* → ☐1 ☐2 ☐3 ☐4 ☐5

### 3.4 Trust & calibration *(1 = Strongly disagree … 5 = Strongly agree)*

| Code | Item | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- | --- |
| **TR1 [Core]** | I trust the findings enough to act on them (review/triage). | ☐ | ☐ | ☐ | ☐ | ☐ |
| **TR2 [Core]** | The findings were at the right level of detail (not too shallow, not overwhelming). | ☐ | ☐ | ☐ | ☐ | ☐ |
| **TR3 [Optional]** | I could tell, for each finding, what I would need to check next. | ☐ | ☐ | ☐ | ☐ | ☐ |

### 3.5 Usability — System Usability Scale (SUS) *(Optional but standard; 1 = Strongly disagree … 5 = Strongly agree)*

> Standard 10-item SUS. Odd items positive, even items negative — keep the alternation; it's part
> of the validated instrument. Scoring in §6.

| Code | Item | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- | --- |
| **SUS1** | I think I would like to use PAIR-AI frequently. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **SUS2** | I found PAIR-AI unnecessarily complex. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **SUS3** | I thought PAIR-AI was easy to use. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **SUS4** | I would need the support of a technical person to use PAIR-AI. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **SUS5** | I found the various functions in PAIR-AI well integrated. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **SUS6** | I thought there was too much inconsistency in PAIR-AI. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **SUS7** | I imagine most people would learn to use PAIR-AI very quickly. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **SUS8** | I found PAIR-AI very cumbersome to use. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **SUS9** | I felt very confident using PAIR-AI. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **SUS10** | I needed to learn a lot before I could get going with PAIR-AI. | ☐ | ☐ | ☐ | ☐ | ☐ |

**Tool-specific ease items** *(the workflow's known friction points; 1 = Strongly disagree … 5 = Strongly agree)*

| Code | Item | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- | --- |
| **EU1 [Core]** | Describing / editing the architecture (Turtle editor ↔ diagram) was easy. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **EU2 [Core]** | **Annotating elements with roles** (the step that makes a graph assessable) was clear. | ☐ | ☐ | ☐ | ☐ | ☐ |
| **EU3 [Core]** | Reading and navigating the findings was easy. | ☐ | ☐ | ☐ | ☐ | ☐ |

### 3.6 Comparison to current practice *(ties back to Part B)*

**CMP1. [Core] Compared with how you assess AI risk today, PAIR-AI is:**
- ☐ Much worse · ☐ Somewhat worse · ☐ About the same · ☐ Somewhat better · ☐ Much better · ☐ Can't compare

**CMP2. [Core] PAIR-AI surfaces risks that my current process would likely miss.**
*(1 = Strongly disagree … 5 = Strongly agree)* → ☐1 ☐2 ☐3 ☐4 ☐5

**CMP3. [Optional] Where would PAIR-AI best fit in your workflow? *(select all)***
- ☐ Early design reviews · ☐ Pre-deployment gate · ☐ Security/threat-modeling sessions
- ☐ Governance / compliance evidence · ☐ Teaching / onboarding · ☐ Nowhere yet · ☐ Other: ______

### 3.7 Open feedback

**OF1. [Core] What was the single most **valuable** thing about PAIR-AI?**
> ______________________________________________

**OF2. [Core] What was the most **confusing or frustrating** thing?**
> ______________________________________________

**OF3. [Optional] The annotation step (assigning roles) was worth the effort for the findings it
produced. Agree? Why / why not?**
> ______________________________________________

**OF4. [Optional] What one change would most increase your trust in, or use of, PAIR-AI?**
> ______________________________________________

**OF5. [Optional] Anything else?**
> ______________________________________________

---

## 4. Optional post-session knowledge item *(only if the study measures learning)*

**KN1. Having used PAIR-AI, how confident are you now that you could list the main risks of an
LLM/RAG architecture from its design?** *(compare against FAM7 for a pre/post shift)*
- ☐ Not at all · ☐ Slightly · ☐ Moderately · ☐ Very · ☐ Completely

---

## 5. Facilitator note — the hands-on task *(not shown to participant as a survey item)*

Keep the task identical across participants so accuracy/precision data is comparable. Suggested
script (≈20–30 min), using bundled examples so findings are known ground truth:

1. **Warm-up (known-good):** Load example → `onyx_danswer` → **Run assessment**. Walk through one
   finding: mechanism, evidence highlight, taxonomy, mitigations. *(Teaches the finding anatomy.)*
2. **Core task (annotation):** Load `beam_export_graph_rag` (structure only, **0 findings** until
   annotated) → open **Annotate** → assign roles → **Apply** → **Run assessment**. Expected: 3
   candidate findings (prompt injection / sensitive data / vector-embedding weakness).
3. **Judgement:** For each finding, participant fills the per-finding table (§3.2) and notes any
   missed risks (ACC8).

Record: time-to-first-finding, number of role-assignment errors, whether they reached the expected
findings unaided, and any think-aloud confusion points.

---

## 6. Analysis plan / scoring key

**Scales (report mean, SD, and % top-2-box "4–5"):**
- **Perceived Usefulness** = mean(PU1–PU10). Intention subscore = mean(PU9, PU10).
- **Accuracy** = mean(ACC1, ACC2, ACC3, ACC4[, ACC5, ACC6]). Note ACC3 is already positively
  phrased (few false alarms) — no reversal needed.
- **Trust** = mean(TR1–TR3).
- **Ease (tool-specific)** = mean(EU1–EU3).

**SUS score (0–100):** for odd items subtract 1 from the response; for even items subtract the
response from 5; sum the 10 adjusted scores (0–40) and multiply by 2.5. Benchmarks: ≥68 = above
average; ≥80 ≈ "A" / strong. Report the SUS score, not raw item means.

**Perceived precision (from §3.2 per-finding table):**
`precision ≈ (#Applies=Yes + 0.5·#Partly) / (total findings rated)`. Report per participant and
pooled. "No/Unsure" ratings are your candidate-false-alarm set — inspect them qualitatively
(is it a tool gap, an annotation error, or a genuine architecture-specific non-applicability?).

**Perceived recall (qualitative):** count distinct valid missed-risk types from ACC8, cross-checked
by the facilitator against what the motif library *could* have raised. Distinguish "tool has no
motif for this" from "motif exists but didn't fire" — the second is a bug signal.

**Comprehension:** CF2 correct-answer rate (target: the intended option). CF4 is reverse-scored —
high agreement flags a "silence = safe" misconception to fix in the UI copy. Report CF2/CF4 as the
**candidate-framing comprehension** result — it directly tests the tool's central design claim.

**Pre/post shift (if used):** FAM7 → KN1 paired change (Wilcoxon signed-rank for small N).

**Segmenting:** cross-tabulate PU/ACC/SUS by BG5 (RDF familiarity) and CP1 (assessment frequency)
— e.g., does the Turtle representation depress usability for RDF-novices? Is perceived usefulness
higher for those who assess risk regularly, or for novices who lean on it more?

**Qualitative:** open-text (CP6/CP7, ACC8/ACC9, OF1–OF5) — thematic-code into
*value*, *friction*, *missed-risk*, *trust*, *fit* buckets; surface the top recurring items.

---

## 7. Trimmed "quick" version (≈10 min total)

If session time is tight, administer only the **[Core]** items. Minimum viable set:
- Pre: BG1–BG5, CP1–CP3, CP6, FAM1–FAM5, FAM7.
- Post: PU1–PU5 + PU9–PU10, ACC1–ACC4 + ACC7–ACC8, CF2–CF3, TR1–TR2, EU1–EU3, CMP1–CMP2, OF1–OF2.

---

*Instrument v1 · aligns with PAIR-AI candidate-risk framing (see `docs/user_guide.md` and
`docs/reference/PAIR-AI_glossary_v1.2.md`). Scales adapted from the Technology Acceptance Model
(Davis, 1989) and the System Usability Scale (Brooke, 1996).*
