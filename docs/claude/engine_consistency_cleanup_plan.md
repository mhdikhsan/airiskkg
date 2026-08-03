# AI-RKG Engine Consistency Cleanup — Analysis & Plan

Status: **PROPOSED — awaiting sign-off** (no changes implemented yet).
Scope: motif library, risk pattern library, SPARQL implementations, role/category
vocabulary, example graphs. Root cause under repair: the libraries, queries, and
examples were LLM-assisted-curated in separate passes, so identifiers and
semantics drifted between layers (hallucinated URIs, invented roles, declarative
metadata that does not match executable behavior).

Method: every finding below comes from a **mechanical cross-reference audit**
(scripted, reproducible — to become `python/tests/test_library_consistency.py`
in Phase 0) plus an **empirical firing matrix** (assessment run on the three
examples), not from eyeballing. Verified 2026-07-16 on
`feature/characterization-layer`.

---

## 1. Empirical baseline (what actually fires today)

| | onyx_danswer | uc6 | verba |
|---|---|---|---|
| **Motif matches** | DirectPrompting, Reranker, Embeddings, VectorIR, QueryRewriting | Reranker, VectorIR, QueryRewriting | VectorIR, Embeddings |
| **RAG motif** | ✗ | ✗ | ✗ |
| prompt-injection | 3 | 3 | 2 |
| vector-embedding-weakness | 3 | 2 | 2 |
| sensitive-data-retrieval | 1 | 1 | 1 |
| supply-chain | 3 | 0 | **0 (test fails)** |
| data-model-poisoning | 1 | 0 | 1 |
| improper-output-handling | 1 | 0 | 0 |
| unbounded-consumption | 0 | 1 | 0 |
| system-prompt-leakage | 0 | **0 (uc6 tags a SystemPrompt!)** | 0 |
| excessive-agency | 0 (cannot ever fire) | 0 | 0 |
| direct-prompting-w/o-grounding | 0 (correctly suppressed — grounded) | 0 | 0 |

Headline problems the matrix exposes:

- **The flagship RAG motif matches nothing**, including onyx (a real RAG
  system). All four of its legs (embed / retrieve / prompt-construct /
  generate) hold in onyx *individually*; the conjunction fails because the
  motif requires the retrieval step's direct output to feed prompt
  construction, and onyx inserts a reranking step in between. The motif is
  over-rigid to pipeline variants, not wrong in spirit.
- **excessive-agency can never fire for anyone**: its positive match requires
  roles (`pair:ToolInvocationStep`, `pair:StateChangingStep`) that are not
  declared anywhere and not offered by the UI role picker.
- **verba supply-chain test failure** (known debt #1): `verba:GeneratorModel`
  plays ExternalModel/PretrainedModel but is bound by no motif match; the
  query only fires for match-bound elements. Deeper cause: the risk pattern
  is *declared* to anchor to FineTuning / ModelLoad / ModelInImage /
  TrainingToServing motifs — **none of which have an implementation** — so
  the query free-rides on arbitrary matches instead.
- **uc6's SystemPrompt annotation is wasted**: leakage query requires the
  system prompt / generation step / output to be bound in *some* motif match,
  but uc6's matches (Reranker/VectorIR/QueryRewriting) bind none of them.

## 2. Defect classes (from the audit)

### 2.1 Hallucinated / drifted URIs in queries (hard bugs)

| # | Where | Wrong URI | Correct/declared counterpart | Effect |
|---|---|---|---|---|
| 1 | `risk_unbounded_consumption.rq` | `pat:DirectPrompting_GenerationStepNode`, `pat:DirectPrompting_AnswerNode` | emitted nodes are `pat:DP_GenerationStepNode`, `pat:DP_AnswerNode` | whole DirectPrompting branch silently dead |
| 2 | `risk_supply_chain.rq` | `pat:ModelArtifactRole`, `pat:ServingImageRole` | `pair:ModelArtifact`, `pair:ServingImage` | two external-resource classes never detected |
| 3 | `risk_improper_output_handling.rq` | `pat:OutputGuardrailStepRole` | `pair:OutputGuardrailStep` | guardrail branch of the control check dead |
| 4 | `match_embeddings.rq` | `pat:VectorIndexRole` | `pair:VectorIndex` | UNION branch dead (matches survive via VectorStore branch only) |

### 2.2 Roles used but never declared (vocabulary gaps)

Positive-match roles (undeclared ⇒ rule is **dead code**, and the UI picker
cannot offer them, so no user can ever activate it):

- `pair:ToolInvocationStep`, `pair:StateChangingStep` (excessive-agency)
- `pair:ExternalDependency`, `pair:ThirdPartyPackage` (supply-chain VALUES)
- `pair:SystemPrompt` (leakage query + uc6 example both use it — they agree
  with each other; only the central vocabulary lags)
- `pair:ExternalModel`, `pair:ExternalProviderCredential` (supply-chain VALUES
  + onyx/verba examples — same situation)

`FILTER NOT EXISTS` control roles (undeclared ⇒ the "control is absent" check
is **unfalsifiable** — the pattern can never be silenced by modeling the
control):

- `pair:RateLimitControlStep` (unbounded-consumption)
- `pair:OutputValidationStep` (improper-output-handling)

### 2.3 Declarative metadata ≠ executable behavior (ODP ↔ OQP drift)

- **EmbeddingsMotif**: ODP declares `Embedding_ModelNode` and expects roles
  EmbeddingModel/EmbeddingVector; the query binds no model node and checks
  neither role (vector accepted via VectorStore role instead).
- **QueryRewritingMotif**: ODP expects FoundationLLM; query accepts any
  GenerativeModel. ODP declares `QueryRewrite_OriginalQueryNode`; never bound.
- **RerankerMotif**: ODP expects UserInput / RetrievedCandidateSet /
  RerankedContext; query uses RetrievedContext for both candidate set and
  output, plain Model for the model, binds no query node.
- **RAG motif**: ODP declares `RAG_EmbeddingModelNode` and
  `RAG_PromptTemplateNode`; query binds neither (emits `RAG_PromptNode`).
- 9 of 11 risk patterns have only the inverse link (`motif
  pair:hasRiskPattern rp`), no `rp pair:hasMotif motif`; two have only the
  forward link. No consumer breaks today (queries hardcode motif URIs), but
  the knowledge graph is inconsistent for any future consumer.

### 2.4 Rule-R2 leak (known debt #2)

`match_embeddings.rq` reads `pair:containsDataCategory` (`FILTER NOT EXISTS …
pair:PromptInstruction`) inside a **motif** query. Root cause: the chunking
step in that motif has *no structural constraint at all* (any step that
`use`s something and `produce`s something an embedding step consumes), and
the facet filter papers over the resulting false positives. The R2-clean fix
is a structural constraint (role on the chunking step or its output), not a
facet read.

### 2.5 Declared-but-inert knowledge

- 17 of 23 motifs (the MLOps/Boxology set) have no OQP — *known and
  acceptable* (ODP-only library entries), but 4 of them are the declared
  anchors of the supply-chain and poisoning risk patterns, which makes those
  anchors dead metadata (see 2.1/verba).
- `MisinformationFromWeakGroundingRiskPattern` has **no implementation and no
  motif** and is a near-duplicate of `DirectPromptingWithoutGroundingRiskPattern`
  (same OWASP anchor, mechanism, condition, controls).
- Dead declared roles (referenced by nothing): ControlStep (parent — keep),
  EvalDataset, EvaluatedOutput, GuardrailModel, VectorRepresentation.
- uc6 uses `pair:ProductInformation` as a data category minted in the *core*
  namespace without declaring it (should be a use-case-local concept with
  `pair:subDataCategoryOf pair:Information`).

### 2.6 What is NOT broken (audit came back clean)

All `implementationPath`s resolve; no orphan `.rq` files; all
`implementsMotif`/`implementsRiskPattern` targets exist; **every taxonomy link
(OWASP/Atlas/MIT/mitctrl) resolves** — no hallucinated taxonomy entries; all
conditions are attached and all attached conditions declared; match queries
emit only declared pattern nodes.

---

## 3. Fix plan (phased; one labeled commit per phase)

### Phase 0 — Permanent consistency net (no semantic change)

Turn the audit into `python/tests/test_library_consistency.py`:
every role/category/pattern-node/motif/risk-pattern URI used in any query,
library file, or example must be declared; every `bindsPatternNode` referenced
by a risk query must be emitted by some match query; every implementationPath
resolves; every taxonomy link resolves. This is the regression net that makes
LLM-assisted curation safe going forward — a hallucinated URI becomes a test
failure, not a silent dead rule.

### Phase 1 — Vocabulary repairs (fills gaps; firing changes expected and individually diffed)

1. Declare the missing role family in `pair_ai_pattern.ttl`:
   `ExternalDependency` (parent, under ResourceRole) with children
   `ExternalModel`, `ThirdPartyPackage`, `ExternalProviderCredential`;
   `SystemPrompt` (under PromptTemplate); control-step roles
   `RateLimitControlStep`, `OutputValidationStep`, `ToolInvocationStep`,
   `StateChangingStep` (under ControlStep/ProcessingStep as appropriate).
   Rationale: queries and examples already agree on these URIs; only the
   vocabulary lags. Declaring them also makes them pickable in the workbench.
2. Fix the four wrong-namespace URIs (2.1 #2–4) to their declared
   counterparts.
3. Fix the dead pattern-node URIs (2.1 #1) `pat:DirectPrompting_*` →
   `pat:DP_*`.
4. Add the missing `pair:hasMotif` / `pair:hasRiskPattern` pairs so both
   directions are asserted consistently.
5. uc6: re-mint `pair:ProductInformation` as a use-case-local concept with a
   declaration and hierarchy edge.

Verification: firing matrix before/after; every delta explained line by line
(e.g. #2 can only *add* supply-chain evidence for ModelArtifact/ServingImage
elements — currently none exist in examples, so expected delta is zero; #3
may add unbounded-consumption findings on onyx's DirectPrompting match —
that is the rule working as documented for the first time).

### Phase 2 — R2 leak fix in match_embeddings (semantic, needs explicit OK)

Replace the facet filter with a structural constraint:
`?chunkingStep pair:playsRole/pair:subRoleOf* pair:ChunkingStep` (roles
already exist and onyx already tags them; alternatively constrain the source
to SourceDocument). Then delete the `containsDataCategory` FILTER. Verify:
Embeddings match set unchanged on all three examples (onyx tags
ChunkingStep; verba needs checking — if verba's chunking step lacks the
role, that is an example annotation fix, not a query relaxation).

### Phase 3 — Supply-chain redesign (fixes the verba test; needs explicit OK)

Introduce a real, small `ExternalDependencyMotif` (one element playing a
role `subRoleOf* pair:ExternalDependency`, used by some step) with its own
match query, and re-anchor `SupplyChainCompromiseRiskPattern` to it. The
risk query then keys on that motif's own matches instead of free-riding on
arbitrary other matches. Effects: verba's GeneratorModel gets match-bound →
test passes; findings become properly evidence-anchored; the dead anchors to
unimplemented MLOps motifs stay as *additional* declared anchors (they gain
meaning if those motifs ever get OQPs). PretrainedModel stays in the VALUES
list (declared, used by onyx/verba).

### Phase 4 — ODP ↔ OQP reconciliation (mostly descriptive)

For Embeddings / QueryRewriting / Reranker / RAG: correct the **ODP
declarations** to describe what the OQP actually matches (the OQP behavior is
the de-facto motif semantics that produced all validated results so far).
Where the ODP captured genuine intent the OQP lost (e.g. Reranker's
RetrievedCandidateSet vs RetrievedContext), flag per-case in the commit for
your review rather than silently changing either side.

### Phase 5 — Decisions needed from you (each blocks one item only)

- **D1 — RAG motif**: relax it so realistic pipelines match? Proposal:
  make the retrieval→prompt leg path-tolerant (allow an intervening
  reranking/aggregation step: `beam:produce/^beam:use` chain of length ≤2 or a
  property path over produce/use), and make the query-embedding leg optional.
  This is the highest-value semantic change (flagship motif currently dead)
  but changes match sets everywhere → your call on the exact loosening.
- **D2 — MisinformationFromWeakGrounding**: merge into
  DirectPromptingWithoutGrounding (deprecate alias), or keep as an
  unimplemented umbrella awaiting a RAG-grounding OQP? Recommendation: keep +
  document as awaiting-OQP, since D1 would give it a real motif to anchor to.
- **D3 — match-anchoring philosophy**: system-prompt-leakage (and improper
  output handling) under-fire because they require generation-path elements
  to be match-bound. Options: (a) keep strict anchoring, accept that graphs
  without a generation-binding motif match get no generation findings
  (pushes value onto D1); (b) drop the match requirement for these two
  (findings anchored on structure alone). Recommendation: (a) + D1.
- **D4 — dead roles** (EvalDataset, EvaluatedOutput, GuardrailModel,
  VectorRepresentation): keep for the unimplemented motif set, or prune?
  Recommendation: keep, annotate each with a note naming the motif that will
  use it.

## 4. Execution rules

- `v1/` untouched. Branch stays `feature/characterization-layer`.
- Candidate framing preserved in all labels/comments.
- Per CLAUDE.md: Phases 2, 3, and every D-item are motif/risk-query semantic
  changes — **none are implemented without your explicit OK**. Phase 0 and
  most of Phase 1 are mechanical; Phase 1 items whose firing matrix delta is
  non-zero are called out per item in the commit message.
- After every phase: RDFLib parse of all TTL, pyshacl, full pytest, firing
  matrix diff on all three examples, explained in the commit.
