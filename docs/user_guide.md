# PAIR-AI Workbench: User Guide

A hands-on guide to the PAIR-AI workbench: what it is, how to use each level of it,
and a worked example of annotating an architecture graph so the assessment can match
it.

> This is a living document, so edit freely. Screenshots are left out on purpose so
> it stays easy to update as the UI evolves.

---

## 1. What this application is

**PAIR-AI is pattern-based risk assessment for AI systems.** Instead of running the
system, you describe it: its architecture as a graph, and optionally the business
process that runs it. PAIR-AI tells you which risks the *structure* predisposes it
to. That works before the system is built and as an audit of one already running.
Either way you are assessing a description, never a live system. It works with two
core concepts.

### Motif

A **motif** is *the recurring solution structure of a design, stated as a small typed graph of pattern roles joined by flow relations*, in the same vocabulary your architecture is modelled in. For example: *"a retrieval step that uses a knowledge source and
produces retrieved context"*, or *"a generation step that puts the user's input to a
generative model and produces output the user sees"*.

**A motif is not an architecture design pattern.** A design pattern is prescriptive,
something you apply while designing. A motif is descriptive, something recognised in
a design afterwards, and it sits *below* design-pattern level: one design pattern
(RAG, say) induces several motifs, and one motif (vector retrieval) turns up in
several design patterns. Architecture design patterns are **not modelled** in the
ontology; motifs and AI risk patterns are.

Three properties carry the definition:

- **A configuration, not an element.** A motif constrains several elements *together
  with the relations between them*. One annotated element is never a motif, because
  risk attaches to the interaction, not the part.
- **Over roles, not implementations.** A motif's nodes are constrained by pattern
  roles and BEAM classes, never by implementation-specific labels. That is what lets
  one motif match systems that look nothing alike.
- **Structure only.** A motif reads roles and flow relations and
  **no facet**. A motif matching your graph just means your system has that shape.

**Type and instance:** the motif is the type; a **motif match** is its instantiation,
mapping the motif's abstract nodes onto concrete elements of your graph. The
[Library](#23-the-library) lists every motif in the current knowledge base.

### Candidate risk finding

When a motif match *also* satisfies the **applicability conditions** of an **AI risk
pattern** (the right context, data categories, or the *absence* of a control), PAIR-AI
emits a **candidate risk finding**. Each finding carries:

- the **risk mechanism** (why the structure enables the risk),
- the **evidence** elements from your graph,
- **taxonomy** links (OWASP LLM and Agentic Top 10, IBM AI Risk Atlas, MIT AI Risk
  Repository, NIST AI 600-1, the ML risks of Zhang et al. (2022), the Eticas AI Risk
  Taxonomy), and
- **suggested controls**.

**Every output is a *candidate* risk: a structural disposition, never a confirmed
failure.** A finding means *"this shape is known to enable this risk unless something
outside the graph prevents it."* It is a prompt for review, not a verdict. Formally,
PAIR-AI reasons under the Open World Assumption, and a "no control found" check is
closed-world over *the graph you submitted only*.

### How it works, end to end

1. **You describe the architecture** as a graph of BEAM elements: *resources*
   (`beam:Data`, `beam:StatisticalModel`, `beam:SemanticModel`, `beam:Symbol`) and
   *processes* (`beam:Transform`, `beam:Infer`, `beam:Train`, `beam:Generate`,
   `beam:Process`), joined by `beam:use` and `beam:produce`. The graph is bipartite:
   a step reaches another step only through a resource one produces and the other
   uses.
2. **You annotate** each element with **one or more roles** (e.g. `FoundationLLM`,
   `RetrievedContext`, `GuardrailStep`) and, where relevant, **data categories**.
   Structure says *what shape* the system is; roles say *what each part means*.
3. **Motifs match the structure:** the roles and the flow.
4. **AI risk patterns interpret the matches** and emit candidate risk findings when
   their applicability conditions hold.

---

## 2. Using the application

The workbench is a web app. Open the URL your team provides, or run it locally
(see the [README](../README.md#quick-start)). The server writes nothing to disk from
the UI: every assessment runs in memory, and the History tab lives in your browser.

### 2.1 The layout

```text
┌────────────────────────────── header toolbar ─────────────────────────────┐
│ PAIR-AI  Library │ Load example  Open  Clear │ Validate  Run assessment │… │
├──────────────────────────┬─────────────────────────────────────────────────┤
│                          │  Process · Architecture · Risk                  │
│  LEFT: Turtle editor     │  the canvas for the level you picked            │
│  (folds away)            ├─────────────────────────────────────────────────┤
│                          │  bottom drawer: Findings, Architectural motifs, │
│                          │  Data flow, Annotate, Input contract, Process,  │
│                          │  History                                        │
└──────────────────────────┴─────────────────────────────────────────────────┘
```

The editor and the canvas are **two views of the same Turtle document and stay in
sync both ways**. Type Turtle and the diagram redraws; draw, connect or rename on the
canvas and the Turtle updates.

The workbench opens on the [Library](#23-the-library). On an empty canvas it asks
what you are describing, a business process or an AI architecture, and starts you on
that level. Once there is content, the **Process / Architecture / Risk** switch above
the canvas moves between levels, and an edit never moves you off the level you chose.

### 2.2 Header toolbar

| Control | What it does |
| --- | --- |
| **PAIR-AI** | Start over. |
| **Library** | Browse the AI risk patterns, motifs and terms the knowledge base holds. |
| **Load example** | Load a graph. Bundled: `customer_support` (the starter scene), `support_chatbot` (that chatbot alone) and `simple_graph_rag` (a small, fully annotated graph RAG). Local graphs are listed under their own heading; see [Your own graphs](#29-your-own-graphs). |
| **Open** | Upload a `.ttl` or `.nt` file. A Tool4Boxology export is recognised by its content and normalised to BEAM on load. |
| **Clear** | Empty both the code and the diagram, after asking. |
| **Validate** | Check the graph against the SHACL input contracts and the annotation guidance. Results land in the **Input contract** tab. |
| **Run assessment** | Match the motifs, propagate derived facts and raise candidate findings. |
| **Overview** | A one-page view of the business context and what was found in it, for people who are not editing the graph. |
| **Export** | Download the assessment as an RDF knowledge graph (Turtle, JSON-LD or N-Triples) with a PROV record of the run. |

**Starter** sits at the top of the editor pane and loads the
[starter scene](#28-the-starter-scene) from any level.

### 2.3 The Library

The Library is the front door. It is generated from the loaded knowledge base, so it
always shows what the assessment can actually do. It has three tabs:

- **Risks** lists every AI risk pattern, shelved by the kind of system it applies to.
  A risk page gives the mechanism and the conditions that raise it, what it may lead
  to, suggested controls, and the motifs curated for it.
- **Architectural motifs** draws each motif from its own declaration and shows the
  risks it carries.
- **Terms** lists every role and data category with its definition and the structures
  that read it.

You can work backwards from a risk: open it, press **Add to canvas** on one of its
motifs, and the motif arrives with the context the risk needs. Run the assessment and
the risk is raised on what you added.

The motifs listed on a risk page are the structures the library curates for it. A few
risk queries read roles on any motif match, so a run can name a motif that is not
listed there. The [catalogue](reference/catalogue.md) says which queries do.

### 2.4 The Process level

A BPMN canvas for the business process. The palette above it draws pools and lanes,
activities, events, gateways, data objects and stores, and text annotations. Dragging
a connector from one shape to another picks the right kind of flow from what it joins.

- **Name the AI system.** An activity can refine one system. The blue **AI system**
  chip on the box opens that architecture and outlines the steps the activity names.
  The pencil opens the activity's editor.
- **Say what the data is.** Click a data box to set its name, its shape (document or
  store), its classification, and whether each step reads it, writes it or both. What
  the analyst states here reaches the architecture through a bridge and is never
  copied as a facet.
- **Carry data across.** A data box can be added to the architecture from its panel
  ("Add to the … architecture"), and the page offers this when data joins an activity
  that refines a system.

One document can hold several process models, picked beside the palette.

### 2.5 The Architecture level

A Boxology canvas for the AI system, with two trays that fold from their headers:

- **Elements** holds Data, Symbol, Model, Transform, Infer, Train and Generate. Drag
  one onto the canvas, or click it to drop it in the centre.
- **Architectural motifs** holds the motif catalogue, shelved by family and
  searchable. Clicking a motif opens a card with its drawing and the risks it
  carries, and **Add to canvas** adds its elements already wired and annotated.
  Dragging it adds it directly.

The system bar above the canvas shows the systems in the document, and **+ system**
adds one. An element always belongs to a system, and a frame can be dragged to move
everything it holds.

- **Connect** by dragging from a node's **▸** port onto another node. The kind of edge
  follows from its ends: **uses** when a step reads a resource, **produces** when a
  step writes one. A step-to-step or data-to-data connection is refused, because the
  graph is bipartite.
- **Edit or delete** by clicking a node. Its popup holds **Label**, **Name (id)**,
  **Type**, **Roles** and **Data categories**, then **Apply** or **Delete**. The
  **Delete** or **Backspace** key removes the selected node too.
- **Roles** are picked from a menu that opens on role categories and fits the element
  first, with the rest one click away. The menu shows each role's workbench name, such
  as *Retrieve* for `RetrievalStep`.
- **Zoom and fit** with the controls at the corner of the canvas.

### 2.6 The Risk level

The run on one diagram, in the notation of risk storming: each concern sits above the
elements it concerns, **stated risks are solid and derived ones dashed**. Findings are
grouped into concerns, so the same weakness reached by nested motifs appears once.

Here a team states its own risks and attaches them to elements or activities, records
consequences, impacts, controls and priorities, and triages each candidate (for
example **Confirmed**, **Mitigated** or **Accepted**, with the reason and who decided).
Severity is never computed; it is a judgement recorded with who made it.

**Hide the run** keeps machine findings off the diagram while the team states risks
first, because seeing them early anchors the room. A scope narrows what the review
looks at and never changes what is detected.

### 2.7 Reading the results

**Run assessment** fills the drawer.

| Tab | What it shows |
| --- | --- |
| **Findings** | Each candidate concern. Selecting one highlights its evidence on the canvas. |
| **Architectural motifs** | The motifs that matched. Repeated matches collapse to one row with a **×N** count. A match alone is not a finding. |
| **Data flow** | Data categories the engine derived by following the flow, and the route each one took. |
| **Annotate** | Every element with its role and data category pickers. **Apply annotations** writes them into the Turtle. |
| **Input contract** | Violations and warnings from the SHACL shapes, including annotations that cannot match anything. |
| **Process** | The business activities in the submitted process. |
| **History** | Past assessments in this browser, and what moved between them. |

Where a control has a registered rewrite for a finding, **Apply to this finding**
inserts the step it suggests, bound to the elements the finding cites, and assesses
again. Adding a control's motif is another route. Either way, the amended design is
assessed afresh, because a control can bring risks of its own.

**Possible risks** sit dashed below the findings. They help a drawing that says less
than a motif does: an element tagged with a coarser role, left untagged, or missing.
Each one lists what the diagram would have to say to raise it. **Apply** it only if
that is true of your system. Possible risks never change what is detected.

Findings are candidates. An empty result does not mean "safe". It means nothing
matched, which often signals that the graph still needs **roles** (see §3).

### 2.8 The starter scene

**Starter** loads a customer support scene, the same one the tutorial uses. A customer
sends a question; the shop's chatbot answers it; when it is not confident, it escalates
to a support agent, who reviews the draft, checks the customer records, updates the
knowledge base and sends the reply. Every conversation is logged.

| Part | What is in it |
| --- | --- |
| Process (`customer_support`) | Two pools, *Customer* and *Shop support*, with the lanes *Chatbot* and *Support agent*; a message start event, an XOR on confidence that merges again before *Log conversation*; three message flows; two data stores, *Knowledge base* (read by the chatbot, written by the agent) and *Customer records* (read by the agent, written by *Log conversation*). |
| Join | *Answer question* is refined by the *Support chatbot* system and names the three steps that carry it out. *Question*, *Knowledge base* and *Draft answer* name the architecture elements they are. |
| Architecture (`support_chatbot`) | A RAG chatbot: *Find passages* retrieves from the knowledge base, *Build prompt* combines the question, the passages and the answering instructions, and *Generate answer* calls a hosted LLM. |

Running the assessment on the whole scene raises six candidate concerns. Each one is a
structural candidate for the team to discuss, not a confirmed defect.

| Concern | Why it is raised |
| --- | --- |
| Prompt injection (through the passages) | A public question shapes what is retrieved, and the passages reach the model with no input screen in between. |
| Prompt injection (through the prompt) | The same question is also written into the prompt itself, which is a second path to the model. |
| Misinformation from weak grounding | The model produces the answer, and no verification or evaluation step over what it produced is represented. |
| Protected data to an external model | The process marks the question as personal data, and the prompt carrying it is sent to a hosted model. |
| Sensitive information disclosure | Personal data reaches an answer the customer sees, with no redaction or output screen on the way out. |
| Supply chain compromise | The generation step uses an external model, so the answer depends on a component the shop does not build. |

Two things to notice in the tutorial:

- **The architecture alone raises a different set.** Without the process, nothing says
  the question is personal, so the two personal-data concerns are not raised, and
  *Improper output handling* is.
- **The agent's review clears *Improper output handling*,** because a human task after
  *Answer question* reads the draft answer. It clears it for the whole activity,
  although confident answers take the *yes* branch and skip the review. The library
  reads "a review follows on some path", not "on every path". That makes it a good
  thing to discuss when triaging.

### 2.9 Your own graphs

`ontology/example_local/` is yours. Drop any `.ttl` in it and the workbench offers it in
**Load example** under its own heading, so you can always tell your graphs from the ones
the project ships.

Nothing there can be published by accident:

| | |
| --- | --- |
| **git** | Every file in the folder is gitignored, so `git add .` cannot stage one. Only the folder's `README.md` is tracked. |
| **Docker image** | `.dockerignore` is an allow-list, and it excludes the folder explicitly. |
| **Deployed server** | A WSGI server (gunicorn, the Docker image) never lists or serves the folder, whatever is on its disk. Only `cli serve` offers it, because that is by definition a local run. Pass `--no-local-examples` to turn it off there too. |

`python/tests/test_private_examples.py` enforces these, so a change that would start
leaking fails the suite rather than a review.

---

## 3. Annotation guide (worked example)

**Why annotation matters:** motifs match on *roles*, not on BEAM types alone. A graph
with the right shape but no roles produces **zero findings**. Graphs imported from
Tool4Boxology are exactly that: they carry structure (types and flow edges) and **no
pattern roles**. Annotation is the step that makes such a graph assessable.

The graph here is a GraphRAG event-information chatbot.

> **The finished result** of this walkthrough, with every role filled in, is bundled
> as **`ontology/example/simple_graph_rag.ttl`**, so you can compare your annotation
> against it. To follow along from a blank slate, load `simple_graph_rag` and delete
> its `pair:playsRole` and `pair:containsDataCategory` lines in the editor, or open
> `external/tool4boxology/sample_export.nt`, a real Tool4Boxology export that arrives
> with structure and no roles at all.

### Step 1: load it and look

**Load example → simple_graph_rag**, then strip the role triples as above.

You will see a RAG pipeline: a `beam:System`, resources and processes wired with
`beam:use` and `beam:produce`. It is structurally sound, but **Run assessment** now
finds **nothing**, because no element has a role.

### Step 2: open the Annotate tab

Bottom drawer → **Annotate**. Every element is listed with a **Roles** picker and a
**Data categories** picker. Both take several values. The count on the tab shows how
many elements are still untagged, and selecting a row highlights that element in the
diagram. You can also tag an element from its popup on the canvas.

### Step 3: assign roles

Pick one or more roles per element. Some elements genuinely play several, such as an
LLM that is both `FoundationLLM` and `GenerativeModel`. The picker shows each role's
workbench name, given in brackets below where it differs from the identifier. The
[Library](#23-the-library)'s **Terms** tab and the
[catalogue](reference/catalogue.md) define all of them.

| Need | Roles |
| --- | --- |
| User-facing I/O | `UserInput`, `PublicUserInput`, `UserFacingOutput`, `PublicUserFacingOutput` |
| Knowledge and retrieval | `KnowledgeSource`, `VectorStore`, `RetrievedContext`, `RetrievedResult`, `SourceDocument` |
| Models | `FoundationLLM`, `GenerativeModel`, `EmbeddingModel`, `JudgeModel` |
| Steps | `RetrievalStep` (Retrieve), `PromptConstructionStep` (Construct prompt), `GenerationStep` (Generate), `EmbeddingStep` (Embed) |
| Controls | `GuardrailStep` (Apply guardrail), `InputGuardrailStep` (Screen input), `OutputGuardrailStep` (Screen output), `OutputValidationStep` (Validate output), `RateLimitControlStep` (Limit rate) |

For a first result, assign at minimum:

| Element | Role | Data category |
| --- | --- | --- |
| Natural Language Question | `PublicUserInput` | |
| Event ID | `UserInput` | |
| KG Querying (Retrieval) | `RetrievalStep` | |
| Event KG | `KnowledgeSource` | Sensitive Information |
| Event KG Subgraph on Event ID | `RetrievedResult` | Sensitive Information |
| LLM | `GenerativeModel` | |
| LLM Prompting (Generation) | `GenerationStep` | |
| Event Summary | `UserFacingOutput` | |

### Step 4: apply

Click **Apply annotations**. This writes `pair:playsRole` and
`pair:containsDataCategory` triples into the editor graph, and the Turtle on the left
grows, e.g.:

```turtle
<…/Component/kg_subgraph>
    a beam:Data ;
    rdfs:label "Event KG Subgraph on Event ID" ;
    pair:playsRole pair:RetrievedResult ;
    pair:containsDataCategory pair:SensitiveInformation .
```

Re-applying replaces an element's existing roles with exactly what is selected, so you
can iterate freely.

### Step 5: assess again

Click **Run assessment**. With those roles the *Information Retrieval* motif matches and
**Findings** shows **2 candidate findings**: prompt injection and sensitive information
disclosure, each with evidence, taxonomy links and suggested controls.

The finished `simple_graph_rag` graph tags every element and raises 7 findings, because
more roles let more motifs match. Comparing the two is a good way to see what each
annotation buys.

### Annotating by hand (alternative)

Roles are just triples, so you can write them directly in the editor:

```turtle
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .

ex:MyLLM        a beam:StatisticalModel ; pair:playsRole pair:FoundationLLM .
ex:GenerateStep a beam:Generate ;         pair:playsRole pair:GenerationStep .
ex:Context      a beam:Data ;             pair:playsRole pair:RetrievedContext ;
                                          pair:containsDataCategory pair:UntrustedContent .
```

The diagram and the Annotate tab pick these up immediately.

---

## 4. Reference

The vocabulary the assessment knows changes with the library, so this guide does not
copy it. Two places always match the loaded knowledge base:

- **The [Library](#23-the-library) in the workbench**, for reading and for adding a
  structure to the canvas.
- **[catalogue.md](reference/catalogue.md)**, generated from the graph: every motif,
  AI risk pattern, role, data category and annotation guidance shape.

How AI risk patterns reach controls is in
[risk_control_linkage.md](reference/risk_control_linkage.md), and the terminology and
modelling rules are in the [glossary](reference/PAIR-AI_glossary_v1_4.md).

---

## Quick reference

| I want to… | Do this |
| --- | --- |
| Try it fast | **Load example → simple_graph_rag**, then **Run assessment** |
| See what the library holds | **Library** in the header |
| Start from a risk | **Library** → open a risk → **Add to canvas** on a motif → **Run assessment** |
| Import a structure-only graph | **Open** a `.ttl`, or a Tool4Boxology export, then annotate |
| Make a graph matchable | **Annotate** tab → assign roles → **Apply annotations** |
| Check my graph is well formed | **Validate** → read the **Input contract** tab |
| See why a finding was raised | Select it in **Findings** to highlight its evidence |
| See which motifs matched | **Run assessment** → **Architectural motifs** tab |
| Scaffold a motif fast | **Architectural motifs** tray → click a motif → **Add to canvas** |
| Run a risk workshop | **Risk** level → **Hide the run** while the team states risks |
| Start from scratch | **Starter**, or **Clear** and build with the palette |
| Keep a graph off GitHub | Put it in `ontology/example_local/`, which is gitignored and never in a built image |
