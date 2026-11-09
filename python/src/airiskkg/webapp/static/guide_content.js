/* The prose of the documentation, as data. Inline markup: **bold**, *italic*, `code`, [text](link). */

export const GUIDE_VERSION = "1.1.0";

export const SECTIONS = [
  { id: "tour", nav: "What is PAIR-AI", title: "What is PAIR-AI" },
  { id: "concepts", nav: "Risk and design patterns", title: "Risk and design patterns" },
  { id: "workbench", nav: "Modeling views", title: "Modeling views" },
  { id: "walkthrough", nav: "Step-by-step procedure", title: "Step-by-step procedure" },
  { id: "reading", nav: "Tool results", title: "Tool results" },
  { id: "under-the-hood", nav: "Access in knowledge graphs", title: "Access in knowledge graphs" },
  { id: "library", nav: "Library", title: "Library" },
  { id: "limits", nav: "Current features", title: "Current features" },
  { id: "glossary", nav: "Glossary", title: "Glossary" },
];

export const HOME = {
  nav: "Overview",
  kicker: "Documentation",
  title: "Pattern-based risk assessment for AI systems during system design",
  lead: "PAIR-AI represents an AI system and its business process as a knowledge graph, recognizes known structures in that graph, and raises candidate risks for review by the responsible team.",
  primary: { label: "Take the 5-minute tour", href: "#/tour" },
  secondary: [
    { label: "Browse the library", href: "#/library" },
    { label: "Open the workbench", href: "workbench" },
  ],
  search: "Search the documentation, glossary and library",
  strip: [
    { head: "Description", text: "A method and workbench that derive candidate risks from a model of an AI system." },
    { head: "Intended users", text: "System architects, students, and risk and governance teams." },
    { head: "Basis", text: "A knowledge graph of motifs and AI risk patterns linked to OWASP, IBM, MIT and other risk taxonomies." },
    { head: "Scope", text: "The method reads the represented design. Candidate risks require human triage." },
  ],
  readersHead: "Reading routes",
  readers: [
    { name: "Understanding the tool", sections: ["tour", "concepts", "limits"], text: "The purpose of the method, its main concepts and its current features." },
    { name: "Modeling", sections: ["workbench", "walkthrough", "reading"], text: "The modeling views, the procedure for a new system and the results it produces." },
    { name: "Knowledge base", sections: ["under-the-hood", "library", "glossary"], text: "The graph representation, the content of the library and the terminology." },
  ],
  flowHead: "Assessment flow",
  flow: [
    { name: "Model", question: "Who does what, and how is the system built?", output: "BPMN model or BEAM graph", step: 1 },
    { name: "Annotate", question: "What does each element represent?", output: "Roles and data categories", step: 2 },
    { name: "Run", question: "Which known risks does the structure allow?", output: "Candidate risks", step: 4 },
    { name: "Triage", question: "Which candidates apply, and what follows from them?", output: "Decisions with reasons", step: 5 },
  ],
  browseHead: "Browse by question",
  tiles: [
    { question: "What can it recognize?", count: "motifs", unit: "motifs", href: "#/library/motif", icon: "shape" },
    { question: "Which risks does it know?", count: "riskPatterns", unit: "AI risk patterns", href: "#/library/risk", icon: "alert" },
    { question: "What roles can I use?", count: "roles", unit: "roles", href: "#/library/role", icon: "tag" },
    { question: "Which controls are suggested?", count: "controls", unit: "controls", href: "#/library/control", icon: "shield" },
    { question: "Which taxonomies are linked?", count: "taxonomyEntries", unit: "taxonomy entries", href: "#/under-the-hood", icon: "link" },
    { question: "What do the terms mean?", count: "glossary", unit: "glossary terms", href: "#/glossary", icon: "book" },
  ],
  band: {
    head: "Try it on the starter scene",
    text: "The starter scene models a customer support process and the chatbot that performs it.",
    action: "Open the workbench",
    steps: ["Select **Starter**", "Select **Run assessment**", "Select a candidate risk", "Read its evidence"],
  },
};

export const DISPLAY_NAMES = { Passages: "Retrieved context", "Find passages": "Retrieve context" };

export const TOUR = {
  intro: [
    "PAIR-AI identifies risks that the structure of an AI system makes possible. An analyst models the system and the business process around it and annotates each element with a role. The method compares this model with a curated library and reports where a known risk can arise.",
    "The method applies wherever a model of the system exists, both before implementation and in the review of a system in operation. It reads the represented design and does not execute the system, observe traffic or inspect model outputs. Each result is a candidate risk that the responsible team reviews.",
  ],
  conceptsHead: "Main concepts",
  concepts: [
    { head: "Role", text: "A term that states what an element of the model represents, for example `PublicUserInput`, `RetrievalStep` or `FoundationLLM`. Matching reads roles and ignores the names given to elements." },
    { head: "Motif", text: "The recurring solution structure of a design, stated as a small graph of roles and flow relations, for example a retrieval step that uses a user query and a knowledge source and produces retrieved context. A motif is structure only." },
    { head: "Candidate risk", text: "Raised when a motif match satisfies the conditions of an AI risk pattern, for example that the input is public or that no screening step is represented." },
  ],
  quick: "**Five-minute tour.** Open the workbench, select **Starter**, then **Run assessment**. Select a candidate risk to highlight the elements it rests on. The example below explains how such a result is derived.",
  exampleHead: "Example",
  example: "The starter scene models the customer support of a shop. A customer submits a question, a chatbot answers it from the knowledge base, and a support agent reviews the draft when the confidence of the chatbot is low. The following steps show how one candidate risk is derived. The workbench names two of the elements below *Find passages* and *Passages*.",
  resultHead: "Result for starter example",
  result: "An assessment of the complete starter scene produces the candidate risks below. The process model states that the question contains personal data, so the set changes when the process model is excluded.",
  scopes: [
    { id: "full", label: "Process model and system model" },
    { id: "system", label: "System model only" },
  ],
  columns: ["Candidate risk", "Reason", "Evidence"],
  triageHead: "Triage process",
  triage: "Each candidate risk is triaged in the **Risk** view with one of the decisions below, a reason and the name of the person who decided. A decision is kept across repeated assessments for as long as the candidate is still raised.",
  decisions: [
    ["Confirmed", "The team considers the weakness real in this design."],
    ["Mitigated", "A control has been built that interrupts the weakness."],
    ["Accepted", "The risk is understood and carried, usually by an organizational process."],
    ["Not a risk", "The team examined the candidate and judged that it does not apply here."],
  ],
  decisionColumns: ["Decision", "Meaning"],
  triageExample: "**Starter scene.** The review by the support agent clears *Improper output handling* for the complete activity, although confident answers bypass the review, because the AI risk pattern tests whether a review follows on some path. The removal of a candidate risk does not establish that the risk is handled.",
};

export const STEPPER = {
  aria: "System model of the support chatbot: the customer question and the knowledge base are used by Retrieve context, which produces Retrieved context. Build prompt uses the question, the retrieved context and the answering instructions to produce a Prompt. Generate answer uses the Prompt and a hosted LLM to produce the Answer.",
  svg: `<defs><marker id="g-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#7c8698"/></marker></defs>
    <rect class="band" x="0" y="0" width="800" height="92"/>
    <text class="legend" x="20" y="22">Rounded: resource. Square: process.</text>
    <text class="note" x="20" y="44"></text>
    <g transform="translate(0,96)">
    <path class="e" data-k="q-fp" d="M140,42 L188,80"/>
    <path class="e" data-k="kb-fp" d="M140,132 L188,98"/>
    <path class="e" data-k="fp-ps" d="M320,87 L358,87"/>
    <path class="e" data-k="ps-bp" d="M490,92 L558,140"/>
    <path class="e" data-k="q-bp" d="M140,30 C330,-10 560,10 622,128"/>
    <path class="e" data-k="in-bp" d="M510,175 L558,160"/>
    <path class="e" data-k="bp-pr" d="M648,174 L650,203"/>
    <path class="e" data-k="pr-ga" d="M585,232 C480,240 400,240 300,248"/>
    <path class="e" data-k="llm-ga" d="M140,272 L198,272"/>
    <path class="e" data-k="ga-an" d="M340,277 L398,277"/>
    <g class="n res" data-k="q"><rect x="10" y="20" width="130" height="44" rx="14"/><text x="22" y="38">Customer question</text><text class="role" x="22" y="54">PublicUserInput</text></g>
    <g class="n res" data-k="kb"><rect x="10" y="110" width="130" height="44" rx="14"/><text x="22" y="128">Knowledge base</text><text class="role" x="22" y="144">KnowledgeSource</text></g>
    <g class="n proc" data-k="fp"><rect x="190" y="65" width="130" height="44"/><text x="202" y="83">Retrieve context</text><text class="role" x="202" y="99">RetrievalStep</text></g>
    <g class="n res" data-k="ps"><rect x="360" y="65" width="130" height="44" rx="14"/><text x="372" y="83">Retrieved context</text><text class="role" x="372" y="99">RetrievedContext</text></g>
    <g class="n res" data-k="in"><rect x="350" y="160" width="160" height="44" rx="14"/><text x="362" y="178">Answering instructions</text><text class="role" x="362" y="194">SystemPrompt</text></g>
    <g class="n proc" data-k="bp"><rect x="560" y="130" width="170" height="44"/><text x="572" y="148">Build prompt</text><text class="role" x="572" y="164">PromptConstructionStep</text></g>
    <g class="n res" data-k="pr"><rect x="585" y="205" width="130" height="44" rx="14"/><text x="597" y="223">Prompt</text><text class="role" x="597" y="239">PromptTemplate</text></g>
    <g class="n model" data-k="llm"><rect x="10" y="250" width="130" height="44" rx="14"/><text x="22" y="268">Hosted LLM</text><text class="role" x="22" y="284">FoundationLLM</text></g>
    <g class="n proc" data-k="ga"><rect x="200" y="250" width="140" height="44"/><text x="212" y="268">Generate answer</text><text class="role" x="212" y="284">GenerationStep</text></g>
    <g class="n res" data-k="an"><rect x="400" y="255" width="130" height="44" rx="14"/><text x="412" y="273">Answer</text><text class="role" x="412" y="289">UserFacingOutput</text></g>
    </g>`,
  steps: [
    { tab: "Model", roles: false, hi: [], flag: [], e: [], e2: [], note: [], text: "**System model.** A BEAM graph of the processes and resources of an AI system, joined by `use` and `produce`. At this stage the graph carries structure only, so no motif can match." },
    { tab: "Annotate", roles: true, hi: [], flag: [], e: [], e2: [], note: [], text: "**Role.** A term that states what an element represents. Matching reads roles and ignores element names, so an element without a role cannot take part in a match." },
    { tab: "Match a motif", roles: true, hi: ["q", "kb", "fp", "ps"], flag: [], e: ["q-fp", "kb-fp", "fp-ps"], e2: [],
      note: ["Motif match: Information Retrieval", "A retrieval process uses a user input and a knowledge source and produces retrieved context."],
      text: "**Motif match.** An occurrence of a motif in the model. It states that a structure is present and makes no claim about risk." },
    { tab: "Check conditions", roles: true, hi: ["fp", "ps", "bp", "pr", "ga"], flag: ["q"], e: ["fp-ps", "ps-bp", "bp-pr", "pr-ga", "q-fp"], e2: [],
      note: ["Condition: untrusted content enters the prompt context", "The public question is untrusted content and reaches Generate answer. No input screening step is represented."],
      text: "**Condition.** A test that an AI risk pattern applies to a motif match, such as a data category on a matched element or the absence of a represented control. Absence is evaluated over the submitted model only." },
    { tab: "Candidate risk", roles: true, hi: ["ga", "llm"], flag: ["q", "ps", "an"], e: ["llm-ga"], e2: ["ga-an"],
      note: ["Candidate risk: Prompt injection (OWASP LLM01)", "Evidence: Customer question, Retrieved context, Generate answer, Hosted LLM, Answer."],
      text: "**Candidate risk.** The result when the conditions of an AI risk pattern hold over a motif match. It is a structural disposition in the design and requires triage by the responsible team." },
  ],
};

export const RISK_REASONS = [
  { label: "Prompt injection", has: "Prompt", text: "The question is also written into the prompt, which forms a second path to the model." },
  { label: "Prompt injection", text: "A public question shapes what is retrieved, and the retrieved context reaches the model with no input screening step in between." },
  { label: "Misinformation from weak grounding", text: "The model produces the answer, and no verification or evaluation step over its output is represented." },
  { label: "Protected data to external model", text: "The process model marks the question as personal data, and the prompt carrying it is sent to a hosted model." },
  { label: "Sensitive information disclosure", text: "Personal data reaches an answer the customer sees, with no redaction or output screening step on the way out." },
  { label: "Supply chain compromise", text: "The generation step uses an external model, so every answer depends on a component the shop does not build." },
  { label: "Improper output handling", text: "The answer reaches the user with no represented validation step. In the complete scene the review by the support agent clears this candidate risk." },
];

// BEGIN STARTER FINDINGS
export const STARTER_FINDINGS = [
  {
    "label": "Improper output handling",
    "evidence": [
      "Answer",
      "Generate answer",
      "Hosted LLM"
    ],
    "scopes": [
      "system"
    ]
  },
  {
    "label": "Misinformation from weak grounding",
    "evidence": [
      "Answer",
      "Customer question",
      "Generate answer",
      "Hosted LLM",
      "Passages"
    ],
    "scopes": [
      "full",
      "system"
    ]
  },
  {
    "label": "Prompt injection",
    "evidence": [
      "Answer",
      "Customer question",
      "Generate answer",
      "Hosted LLM",
      "Passages"
    ],
    "scopes": [
      "full",
      "system"
    ]
  },
  {
    "label": "Prompt injection",
    "evidence": [
      "Answer",
      "Customer question",
      "Generate answer",
      "Hosted LLM",
      "Passages",
      "Prompt"
    ],
    "scopes": [
      "full",
      "system"
    ]
  },
  {
    "label": "Protected data to external model",
    "evidence": [
      "Generate answer",
      "Hosted LLM",
      "Prompt"
    ],
    "scopes": [
      "full"
    ]
  },
  {
    "label": "Sensitive information disclosure",
    "evidence": [
      "Answer",
      "Generate answer"
    ],
    "scopes": [
      "full"
    ]
  },
  {
    "label": "Supply chain compromise",
    "evidence": [
      "Generate answer",
      "Hosted LLM"
    ],
    "scopes": [
      "full",
      "system"
    ]
  }
];
// END STARTER FINDINGS

export const CONCEPTS = {
  intro: "PAIR-AI distinguishes the levels below. The separation allows one motif to serve several risks and one risk to be raised over several structures.",
  levels: [
    { head: "Architecture design pattern", kind: "struct", text: "A documented solution applied during design, such as retrieval-augmented generation or guardrails. PAIR-AI cites design patterns as the origin of motifs and does not model them." },
    { head: "Motif", kind: "struct", text: "The recurring solution structure of a design, stated as roles connected by `use` and `produce`. The relation to design patterns is many-to-many. A motif is structure only and makes no risk claim." },
    { head: "AI risk pattern", kind: "risk", text: "A motif combined with conditions, a mechanism, links to risk taxonomies and suggested controls. The risk claim is made at this level." },
    { head: "Candidate risk", kind: "risk", text: "One AI risk pattern holding at one place in a model, with the elements it rests on as evidence. Where several motifs reach the same weakness at the same place, they form one candidate risk." },
  ],
  howHead: "Derivation of a motif",
  how: "A motif is derived by modeling the structure that a source documents. Each participant becomes a node with an expected role and class, and each interaction becomes a `use` or `produce` edge. Where a source shows one process handing over to another, the resource exchanged between them is declared, because the graph is bipartite. Intent, applicability and consequences are omitted at this level. Consequences are stated by the AI risk pattern.",
  absence: "**Presence in motifs, absence in conditions.** Matching is monotone: a motif that matches a model also matches every extension of that model. A motif therefore asserts presence only. Absence is tested in a condition and only over the submitted model, so a candidate risk states that no control is represented in the model.",
};

export const WORKBENCH = {
  intro: "The editor and the canvas present the same Turtle document and remain synchronized in both directions. Each view addresses a different question.",
  views: [
    { id: "library", tab: "Library", image: { src: "static/guide/workbench-library.png", alt: "The Library in the workbench, showing an AI risk pattern with its motifs" }, paragraphs: [
      "**Open workbench** leads to the editor and the canvas. The **Library** button in the workbench header opens the Library at any time, and the **Documentation** button beside it returns to these pages.",
      "The Library lists each AI risk pattern with its mechanism, its possible consequences and its suggested controls, and each motif drawn from its own declaration. **Add to canvas** inserts a motif with the context that a selected risk requires.",
    ] },
    { id: "process", tab: "Process", image: { src: "static/guide/workbench-process.png", alt: "The Process canvas with the customer support process of the starter scene" }, paragraphs: [
      "A BPMN canvas for the process model: pools and lanes, events, gateways, activities, data objects and data stores. An activity names the AI system that performs it, and its chip opens the system model.",
      "Statements made from the business perspective, for example that a data object holds personal data, reach the system model through a bridge. The processes of the AI system belong to the system model.",
    ] },
    { id: "system", tab: "Architecture", image: { src: "static/guide/workbench-system.png", alt: "The Architecture canvas with the system model of the starter scene" }, paragraphs: [
      "A Boxology canvas for the system model. Processes and resources are connected with `use` and `produce`, and a process reaches another process only through a resource that one produces and the other uses.",
      "Each element receives roles and data categories from a picker that offers the applicable terms first. Motifs can be inserted from a tray, already connected and annotated. Annotation is the precondition for matching.",
    ] },
    { id: "risk", tab: "Risk", image: { src: "static/guide/workbench-risk.png", alt: "The Risk canvas with the candidate risks of the starter scene above the elements they refer to" }, paragraphs: [
      "The assessment on one diagram in the notation of risk storming: each candidate risk is placed above the elements it refers to, with stated risks drawn solid and derived ones dashed.",
      "The team states its own risks, records consequences, controls and priorities, and triages each candidate. Severity is recorded as a judgement together with its author and is never computed.",
    ] },
    { id: "further", tab: "Further functions", rows: [
      ["Findings", "The **Findings** tab groups results into candidate risks, so a weakness reached through nested motifs appears once. Selecting one highlights its evidence on the canvas."],
      ["Possible risks", "Addresses a model that states less than a motif requires, such as an element with a coarser role, without a role, or missing. Suggestions leave detection unchanged."],
      ["Controls", "**Apply to this finding** inserts the process a candidate risk suggests, bound to the elements it cites, and repeats the assessment."],
      ["Validation", "**Validate** checks the graph against the SHACL input contracts and warns when an annotation cannot match."],
      ["Import", "**Open** accepts a Tool4Boxology export, recognized by its content and normalized to BEAM. Such a graph contains structure and no roles."],
    ] },
  ],
};

export const WALKTHROUGH = {
  intro: "The procedure below applies to a new system. Each step lists the actions in the workbench and illustrates them with the starter scene.",
  starterLabel: "Starter scene",
  checkLabel: "Self-check",
  steps: [
    {
      title: "Model the process or the system", view: "Either order",
      lead: "The two models can be created in either order. Select the one to start with.",
      choices: [
        {
          label: "Model the process",
          actions: ["Select **Process** above the canvas.", "Add pools and lanes, start and end events, activities, and data stores with their read and write relations.", "Name each activity with a leading verb.", "For each activity performed by an AI system, name that system so that the **AI system** chip appears on the activity.", "Select **Validate** and resolve the entries under **Input contract**."],
          starter: "*Answer question* is refined by the *Support chatbot* system, and *Knowledge base* is a data store that the chatbot reads and the support agent writes.",
          question: "Should *Generate answer* be a task in the process model?",
          answer: "No. *Answer question* is the business activity. Retrieval, prompt construction and generation belong to the system model, which keeps the system boundary visible.",
        },
        {
          label: "Model the system",
          actions: ["Select **Architecture** above the canvas and create a system with **+ system**.", "Add processes and resources from **Elements**, or insert a structure from **Architectural motifs**.", "Connect elements from the port of a node. The connection is `use` when a process reads a resource and `produce` when a process writes one.", "Select **Validate** and confirm that each process uses and produces a resource."],
          starter: "*Retrieve context* uses the question and the knowledge base and produces the retrieved context. Data reaches the answer through *Generate answer*, which uses the hosted model.",
          question: "Can *Retrieve context* connect directly to *Build prompt*?",
          answer: "No. The graph is bipartite. *Retrieve context* produces the retrieved context, and *Build prompt* uses it. Motifs match on the resource between the two processes, so its omission can conceal a risk.",
        },
      ],
    },
    {
      title: "Annotate the elements", view: "Roles and data categories",
      actions: ["Open **Annotate** in the drawer, or select an element on the canvas.", "Assign the most specific role that fits. An element can hold several roles.", "Mark personal or sensitive data with a data category.", "Select **Apply annotations** and confirm that the count of untagged elements reaches zero."],
      starter: "*Customer question* is a `PublicUserInput`, and *Hosted LLM* carries both `FoundationLLM` and `ExternalModel`.",
      question: "A role is under consideration because it would produce a candidate risk. How should the role be chosen?",
      answer: "The role should describe the element. Selecting roles to obtain a result makes the assessment reproduce the expectations of the analyst. A concept without a suitable role is useful feedback on the role vocabulary.",
    },
    {
      title: "Record risks before the assessment", view: "Risk",
      actions: ["Select **Risk** above the canvas and use **Hide the run** while the team works.", "For each part of the system, state what could fail and where.", "Attach each stated risk to the element or activity it refers to."],
      starter: "A stated risk reads: the generated answer reaches the customer with no check against the retrieved context.",
      question: "Is \"the LLM may hallucinate\" a sufficient entry?",
      answer: "It requires a location. A risk tied to an element can be compared with a candidate risk, which is the purpose of recording it in advance.",
    },
    {
      title: "Run the assessment", view: "Findings",
      actions: ["Select **Run assessment**.", "Open **Findings** and select an entry.", "Inspect the evidence elements highlighted on the canvas and confirm that each corresponds to the intended part of the system."],
      starter: "The complete scene yields six candidate risks, listed under [Result for starter example](#/tour).",
      question: "An assessment produces no candidate risks. What does this result indicate?",
      answer: "It indicates that nothing matched. Common causes are missing or coarse roles and structures unknown to the library. **Possible risks** shows what a fuller annotation would raise.",
    },
    {
      title: "Compare and decide", view: "Risk",
      actions: ["Sort the risks into three groups: found by both, stated only by the team, and raised only by the assessment.", "Triage each candidate as **Confirmed**, **Mitigated**, **Accepted** or **Not a risk**, with a reason.", "Add risks found only by the team as stated risks."],
      starter: "The review by the support agent clears *Improper output handling*, which is a point to examine during triage.",
      question: "Why might a team identify a risk that the assessment did not raise?",
      answer: "The risk may lie outside the structure, as with the content of answers or legal terms; the model may omit the relevant part; or the library may hold no AI risk pattern for it. Each cause requires a different response.",
    },
    {
      title: "Apply controls and repeat", view: "Controls",
      actions: ["Select **Apply to this finding** on a suggested control, or model the control with the appropriate role.", "Select **Run assessment** again and compare the results.", "Select **Export** to retain the graph and the decisions."],
      starter: "An input screening process added before *Generate answer* addresses the prompt injection candidates, one path at a time.",
      question: "A candidate risk no longer appears after a control is added. Is the risk handled?",
      answer: "The model now represents the control. Whether the control operates as intended is a question for testing and operations, which lie outside the scope of PAIR-AI.",
    },
  ],
};

export const READING = {
  exampleHead: "Example candidate risk",
  intro: "The system model below shows the elements on which the candidate risk rests. The entry beneath it is the result reported for those elements.",
  riskPattern: "PromptInjectionRiskPattern",
  evidenceLabel: "Prompt injection",
  labels: { condition: "Condition", mechanism: "Mechanism", evidence: "Evidence", controls: "Suggested controls", taxonomy: "Taxonomy entries" },
  view: {
    roles: true, hi: ["ga", "llm"], flag: ["q", "ps", "an"], e: ["llm-ga", "q-fp", "fp-ps", "ps-bp", "bp-pr", "pr-ga"], e2: ["ga-an"],
    note: ["Candidate risk: Prompt injection (OWASP LLM01)", "Evidence is outlined: Customer question, Retrieved context, Generate answer, Hosted LLM, Answer."],
  },
};

export const KNOWLEDGE_GRAPHS = {
  intro: "The system model is a Turtle graph in the BEAM vocabulary, and roles are RDF triples. An assessment is a fixed sequence of SPARQL CONSTRUCT queries whose results are RDF graphs.",
  pipeline: [
    { head: "Match", text: "One CONSTRUCT per motif produces `pair:MotifMatch` nodes with node bindings." },
    { head: "Propagate", text: "Derived facts, such as data categories along flow relations, are added until a fixed point is reached." },
    { head: "Evaluate", text: "The conditions of each AI risk pattern are evaluated over its motif matches." },
    { head: "Emit", text: "A `pair:RiskFinding` with the status \"candidate\", evidence, mechanism, taxonomy entries and controls." },
  ],
  blocks: [
    { head: "Input", text: "Roles are stated as triples on the elements of the system model.", code: `csa:FindPassages a beam:Process ;
    rdfs:label "Find passages" ;
    pair:playsRole pair:RetrievalStep ;
    beam:use csa:Question, csa:KnowledgeBase ;
    beam:produce csa:Passages .

csa:Question a beam:Data ;
    pair:playsRole pair:PublicUserInput .` },
    { head: "Motif matcher", text: "The WHERE clause of the Information Retrieval motif matcher. Role hierarchies are followed with `pair:subRoleOf*`, so a `PublicUserInput` also counts as a `UserInput`.", code: `?retrievalStep a/rdfs:subClassOf* beam:Process ;
    beam:use ?query ; beam:use ?knowledgeSource ;
    beam:produce ?retrievedContext ;
    pair:playsRole/pair:subRoleOf* pair:RetrievalStep .
?query            pair:playsRole/pair:subRoleOf* pair:UserInput .
?knowledgeSource  pair:playsRole/pair:subRoleOf* pair:KnowledgeSource .
?retrievedContext pair:playsRole/pair:subRoleOf* pair:RetrievedContext .` },
    { head: "Output", text: "A candidate risk is a node that can be queried.", code: `?riskFinding a pair:RiskFinding ;
    pair:findingStatus "candidate" ;
    pair:generatedByRiskPattern pat:PromptInjectionRiskPattern ;
    pair:generatedFromMatch ?match ;
    pair:hasEvidence ?untrustedContent, ?generationStep ;
    pair:hasCandidateRiskTaxonomyEntry ?riskTaxonomyEntry ;
    pair:hasSuggestedControl ?suggestedControl .` },
  ],
  properties: [
    { head: "Reproducibility", text: "The same graph yields the same results. `airiskkg kb-version --json` prints a fingerprint of the knowledge base that can be stored with each result." },
    { head: "Open-world reading", text: "The graph is read under the open-world assumption. The closed check for a represented control ranges only over the submitted graph." },
    { head: "Input contracts", text: "SHACL shapes check the model before matching and warn when a role or data category cannot take part in a match." },
    { head: "Command line", text: "`airiskkg assess graph.ttl` writes motif matches and candidate risks for scripted runs and batch evaluation." },
  ],
  componentsHead: "Library components",
  components: "Counts for the latest library version.",
  componentRows: [
    { label: "Motifs", count: "motifs", note: "Generative AI, agentic systems, ML serving and training, supply chain" },
    { label: "AI risk patterns", count: "riskPatterns", note: "Each with conditions and a mechanism" },
    { label: "Conditions", count: "conditions", note: "Observed from reported experience and the literature" },
    { label: "Controls", count: "controls", note: "Suggested per AI risk pattern" },
    { label: "Roles", count: "roles", note: "Including role categories" },
    { label: "Data categories", count: "dataCategories", note: "Aligned to the Data Privacy Vocabulary (DPV) where a corresponding term exists" },
    { label: "Design pattern citations", count: "citations", note: "Sources from which motifs are derived" },
  ],
  taxonomiesHead: "Linked risk taxonomies",
  taxonomies: [
    { name: "OWASP Top 10 for LLM Applications", key: "OWASP LLM", url: "https://genai.owasp.org/", text: "Risks of applications built on large language models. Entries are referenced by identifier and link." },
    { name: "OWASP Top 10 for Agentic Applications", key: "OWASP ASI", url: "https://genai.owasp.org/", text: "Risks of agentic applications. Nine of the ten entries have an AI risk pattern." },
    { name: "IBM AI Risk Atlas", key: "IBM", url: "https://www.ibm.com/docs/en/watsonx/saas?topic=ai-risk-atlas", text: "A catalogue of risks in the use of AI, ingested through IBM AI Atlas Nexus." },
    { name: "MIT AI Risk Repository", key: "MIT", url: "https://airisk.mit.edu/", text: "A domain taxonomy of AI risks, used to report the domain of a possible harm." },
    { name: "MIT risk mitigation taxonomy", url: "https://github.com/IBM/ai-atlas-nexus", text: "Mitigation groups and actions, reached from suggested controls." },
    { name: "NIST AI 600-1", url: "https://doi.org/10.6028/NIST.AI.600-1", text: "The generative AI profile of the NIST AI Risk Management Framework, reached through IBM Atlas entries." },
    { name: "ML risk", key: "ML risk", url: "https://doi.org/10.1016/j.dss.2022.113800", text: "Data-level and model-level risks of machine learning systems." },
    { name: "Eticas AI Risk Taxonomy", key: "Eticas", url: "https://taxonomy.eticas.ai/", text: "An open taxonomy for AI audits." },
  ],
  sourcesHead: "Vocabularies and sources",
  sources: [
    { name: "BEAM", url: "http://w3id.org/beam/core#", text: "The vocabulary of the system model, specializing the Boxology notation." },
    { name: "Boxology", url: "https://doi.org/10.1007/s10489-021-02394-3", text: "The notation and design patterns for hybrid learning and reasoning systems on which BEAM builds." },
    { name: "Tool4Boxology", url: "https://doi.org/10.1007/978-3-032-25159-6_11", text: "A semantic toolbox for Boxology models, accepted as an import format." },
    { name: "sBPMN 2.0", url: "https://doi.org/10.1145/3731443.3771361", text: "An OWL formalization of BPMN 2.0, used for the process model." },
    { name: "DPV", url: "https://w3id.org/dpv", text: "The Data Privacy Vocabulary, the alignment target for personal data categories and purposes." },
    { name: "AIRO", url: "https://w3id.org/airo", text: "The AI Risk Ontology, on which the risk chain from risk source to impact is built." },
    { name: "SHACL", url: "https://www.w3.org/TR/shacl/", text: "The W3C constraint language used for the input contracts and the annotation guidance." },
    { name: "SKOS", url: "https://www.w3.org/TR/skos-reference/", text: "The W3C vocabulary used for facets, data categories and mappings between taxonomies." },
    { name: "Agent design pattern catalogue", url: "https://doi.org/10.1016/j.jss.2024.112278", text: "Source of the agentic, guardrail and evaluation motifs." },
    { name: "RAG survey", url: "https://doi.org/10.48550/arXiv.2312.10997", text: "Source of the retrieval-augmented generation motifs." },
    { name: "ML System Design Patterns", url: "https://mercari.github.io/ml-system-design-pattern/", text: "Source of the ML serving, training and lifecycle motifs." },
  ],
};

export const LIBRARY_PAGE = {
  intro: "A read-only view of the library. A motif is structure only, and the risk claim is made by the AI risk pattern that reads it.",
  filter: "Filter entries",
  empty: "No entry matches the filter.",
  versionLabel: "Library version",
  tabs: [
    { kind: "risk", label: "AI risk patterns", back: "All AI risk patterns" },
    { kind: "motif", label: "Motifs", back: "All motifs" },
    { kind: "role", label: "Roles", back: "All roles" },
    { kind: "category", label: "Data categories", back: "All data categories" },
    { kind: "control", label: "Controls", back: "All controls" },
  ],
  headings: {
    description: "Description", mechanism: "Mechanism", conditions: "Conditions", motifs: "Motifs", controls: "Suggested controls",
    taxonomy: "Taxonomy entries", source: "Source", structure: "Structure", roles: "Roles", citations: "Design pattern citations",
    riskPatterns: "AI risk patterns", definition: "Definition", parents: "Parent roles", children: "Child roles", usedBy: "Motifs that use it",
    suggestedBy: "Suggested against", realizedBy: "Candidate structure", nature: "Nature", origin: "Origin",
  },
  derived: { yes: "Derived during propagation", no: "Annotated by the analyst" },
  noMotif: "Evaluated over any motif match whose conditions hold.",
  none: "None.",
};

export const LIMITS = {
  cards: [
    { head: "Represented scope", text: "A risk in a part of the system that is not modeled cannot be identified. An empty result indicates that nothing matched." },
    { head: "Dependence on roles", text: "The role vocabulary is the least grounded part of the method. The authors derived it from design pattern catalogues, and results depend on the fit of the assigned roles." },
    { head: "Structural risks", text: "Risks that reside in content, law or organization, such as the fairness of answers or contract terms, require other methods. The taxonomy links support their identification." },
    { head: "Design-time analysis", text: "PAIR-AI neither monitors nor tests a running system. It complements testing and monitoring." },
    { head: "Repeatability and validity", text: "Identical output across runs demonstrates repeatability. The validity of the candidate risks is a separate question, addressed by evaluation." },
    { head: "Library coverage", text: "Coverage is strongest for generative AI and retrieval-augmented systems. Coverage of classical machine learning and agentic systems is growing." },
  ],
};

export const GLOSSARY = {
  filter: "Filter terms, for example motif, condition or control",
  empty: "No term matches the filter.",
  entries: [
    { term: "AI risk pattern", text: "A motif combined with conditions, a mechanism, taxonomy links and suggested controls." },
    { term: "AIRO", text: "The AI Risk Ontology, on which the risk chain of the risk view is built." },
    { term: "Architecture design pattern", text: "A documented solution applied during design, such as retrieval-augmented generation or guardrails. Cited as the origin of motifs and not modeled." },
    { term: "BEAM", text: "The vocabulary of the system model, based on the Boxology notation: resources and processes connected by use and produce." },
    { term: "Boxology", text: "A graphical notation and set of design patterns for hybrid learning and reasoning systems." },
    { term: "Candidate risk", text: "One AI risk pattern holding at one place in a model. A structural disposition that requires triage. Where several motifs reach the same weakness at the same place, they form one candidate risk." },
    { term: "Condition", text: "A test that an AI risk pattern applies to a motif match: a data category, a context, or the absence of a represented control. Absence is tested only here." },
    { term: "Control", text: "A process or measure that addresses a risk, such as input screening or rate limiting. Controls are suggested per AI risk pattern and can be applied as a rewrite of the model." },
    { term: "Data category", text: "A term on a data element, such as sensitive information or untrusted content. Categories propagate along flow relations." },
    { term: "DPV", text: "The Data Privacy Vocabulary, the alignment target for personal data categories and purposes." },
    { term: "Evidence", text: "The elements of the model on which a candidate risk rests." },
    { term: "Mechanism", text: "The curated explanation of how a structure, under its conditions, can lead to harm. A mechanism takes no part in detection." },
    { term: "Motif", text: "The recurring solution structure of a design, stated as a small graph of roles and flow relations. A motif is structure only and makes no risk claim." },
    { term: "Motif match", text: "One place in a model where the nodes of a motif bind to concrete elements." },
    { term: "Process model", text: "The BPMN model of the business process in which the AI system operates." },
    { term: "Role", text: "A term stating what an element represents, for example RetrievalStep or FoundationLLM. Matching reads roles." },
    { term: "sBPMN", text: "An OWL formalization of BPMN 2.0, the vocabulary of the process model." },
    { term: "SHACL", text: "The W3C constraint language used for the input contracts and the annotation guidance." },
    { term: "System model", text: "The BEAM graph of an AI system: its processes, its resources and the relations between them. The workbench presents it at the Architecture level." },
    { term: "Triage", text: "The recorded human decision on a candidate: Confirmed, Mitigated, Accepted or Not a risk, with a reason and an author." },
  ],
};

export const FOOTER = "PAIR-AI is developed at WU Wien. Candidate risks require human review.";
