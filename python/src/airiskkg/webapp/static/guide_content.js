/* The prose of the user guide, as data. Inline markup: **bold**, *italic*, `code`, [text](link). */

export const GUIDE_VERSION = "1.0.0";
export const CONTACT = { label: "WU Wien", url: "https://www.wu.ac.at/en/" };

export const SECTIONS = [
  { id: "tour", nav: "Tour", title: "What is PAIR-AI", minutes: 5 },
  { id: "concepts", nav: "Concepts", title: "Risk and design patterns", minutes: 3 },
  { id: "workbench", nav: "Workbench", title: "Modeling views", minutes: 4 },
  { id: "walkthrough", nav: "Walkthrough", title: "Step-by-step procedure", minutes: 8 },
  { id: "reading", nav: "Tool results", title: "Tool results", minutes: 2 },
  { id: "under-the-hood", nav: "Knowledge graphs", title: "Access in knowledge graphs", minutes: 6 },
  { id: "library", nav: "Library", title: "Library", minutes: 3 },
  { id: "limits", nav: "Current features", title: "Current features", minutes: 2 },
  { id: "glossary", nav: "Glossary", title: "Glossary", minutes: 2 },
];

export const HOME = {
  kicker: "User guide",
  title: "Pattern-based risk assessment for AI systems during system design",
  lead: "PAIR-AI represents an AI system and its business process as a knowledge graph, recognizes known structures in that graph, and raises candidate risks for review by the responsible team.",
  primary: { label: "Take the 5-minute tour", href: "#/tour" },
  secondary: [
    { label: "Browse the library", href: "#/library" },
    { label: "Open the workbench", href: "/" },
  ],
  search: "Search the guide, glossary and library",
  strip: [
    { head: "Description", text: "A method and workbench that derive candidate risks from a model of an AI system." },
    { head: "Intended users", text: "System architects, students, and risk and governance teams." },
    { head: "Basis", text: "A knowledge graph of motifs and AI risk patterns linked to OWASP, IBM, MIT and other risk taxonomies." },
    { head: "Scope", text: "The method reads the represented design. Findings are candidates and require human triage." },
  ],
  readersHead: "Reading routes",
  readers: [
    { name: "Student", sections: ["tour", "walkthrough", "reading", "limits"], text: "Learn the method by following one example from model to candidate finding." },
    { name: "Partner or practitioner", sections: ["tour", "workbench", "library", "limits"], text: "Assess the use of the workbench and the content of the library for a system in your organization." },
    { name: "Knowledge graph engineer", sections: ["concepts", "under-the-hood", "library", "glossary"], text: "Examine the vocabulary, the SPARQL queries and the structure of the results." },
  ],
  flowHead: "Assessment flow",
  flow: [
    { name: "Process model", question: "Who does what, and where does data matter?", output: "BPMN model", step: 1 },
    { name: "System model", question: "How is the system built?", output: "BEAM graph", step: 2 },
    { name: "Annotate", question: "What does each element represent?", output: "Roles and data categories", step: 3 },
    { name: "Run", question: "Which known risks does the structure allow?", output: "Candidate findings", step: 5 },
    { name: "Triage", question: "Which candidates apply, and what follows from them?", output: "Decisions with reasons", step: 6 },
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
    steps: ["Select **Starter**", "Select **Run assessment**", "Select a finding", "Read its evidence"],
  },
};

export const TOUR = {
  intro: [
    "PAIR-AI identifies risks that the structure of an AI system makes possible. An analyst models the system and the business process around it and annotates each element with a role. The method compares this model with a curated library and reports where a known risk can arise.",
    "The method applies wherever a model of the system exists, both before implementation and in the review of a system in operation. It reads the represented design and does not execute the system, observe traffic or inspect model outputs. Each result is a candidate risk finding that the responsible team reviews.",
  ],
  conceptsHead: "Main concepts",
  concepts: [
    { head: "Role", text: "A term that states what an element of the model represents, for example `PublicUserInput`, `RetrievalStep` or `FoundationLLM`. Matching reads roles and ignores the names given to elements." },
    { head: "Motif", text: "The recurring solution structure of a design, stated as a small graph of roles and flow relations, for example a retrieval step that uses a user query and a knowledge source and produces retrieved context. A motif is structure only." },
    { head: "Candidate risk finding", text: "Raised when a motif match satisfies the conditions of an AI risk pattern, for example that the input is public or that no screening step is represented." },
  ],
  quick: "**Five-minute tour.** Open the workbench, select **Starter**, then **Run assessment**. Select a finding to highlight the elements it rests on. The example below explains how such a finding is derived.",
  exampleHead: "Example",
  example: "The starter scene models the customer support of a shop. A customer submits a question, a chatbot answers it from the knowledge base, and a support agent reviews the draft when the confidence of the chatbot is low. The following steps show how one candidate finding is derived.",
  resultHead: "Result for starter example",
  result: "An assessment of the complete starter scene produces the candidate risks below. The process model states that the question contains personal data, so the set changes when the process model is excluded.",
  scopes: [
    { id: "full", label: "Process model and system model" },
    { id: "system", label: "System model only" },
  ],
  columns: ["Candidate risk", "Reason", "Evidence"],
  triageHead: "Triage process",
  triage: "The review by the support agent clears *Improper output handling* for the complete activity, although confident answers bypass the review, because the AI risk pattern tests whether a review follows on some path. The removal of a finding does not establish that the risk is handled.",
};

export const STEPPER = {
  aria: "System model of the support chatbot: the customer question and the knowledge base are used by Find passages, which produces Passages. Build prompt uses the question, the passages and the answering instructions to produce a Prompt. Generate answer uses the Prompt and a hosted LLM to produce the Answer.",
  svg: `<defs><marker id="g-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#7c8698"/></marker></defs>
    <path class="e" data-k="q-fp" d="M110,62 L170,92"/>
    <path class="e" data-k="kb-fp" d="M110,152 L170,118"/>
    <path class="e" data-k="fp-ps" d="M290,105 L330,105"/>
    <path class="e" data-k="ps-bp" d="M430,105 L470,140"/>
    <path class="e" data-k="q-bp" d="M110,50 C330,20 450,60 485,128"/>
    <path class="e" data-k="in-bp" d="M465,212 L488,176"/>
    <path class="e" data-k="bp-pr" d="M560,175 L560,203"/>
    <path class="e" data-k="pr-ga" d="M500,238 C420,245 380,262 332,268"/>
    <path class="e" data-k="llm-ga" d="M110,262 L188,268"/>
    <path class="e" data-k="ga-an" d="M330,272 C430,300 500,290 578,280"/>
    <g class="n res" data-k="q"><rect x="10" y="38" width="100" height="44" rx="14"/><text x="20" y="58">Customer question</text><text class="role" x="20" y="74">PublicUserInput</text></g>
    <g class="n res" data-k="kb"><rect x="10" y="130" width="100" height="44" rx="14"/><text x="20" y="150">Knowledge base</text><text class="role" x="20" y="166">KnowledgeSource</text></g>
    <g class="n proc" data-k="fp"><rect x="170" y="83" width="120" height="44"/><text x="182" y="103">Find passages</text><text class="role" x="182" y="119">RetrievalStep</text></g>
    <g class="n res" data-k="ps"><rect x="330" y="83" width="100" height="44" rx="14"/><text x="342" y="103">Passages</text><text class="role" x="342" y="119">RetrievedContext</text></g>
    <g class="n res" data-k="in"><rect x="345" y="196" width="120" height="44" rx="14"/><text x="357" y="216">Answering instr.</text><text class="role" x="357" y="232">SystemPrompt</text></g>
    <g class="n proc" data-k="bp"><rect x="470" y="130" width="180" height="44"/><text x="482" y="150">Build prompt</text><text class="role" x="482" y="166">PromptConstructionStep</text></g>
    <g class="n res" data-k="pr"><rect x="500" y="205" width="120" height="40" rx="14"/><text x="512" y="222">Prompt</text><text class="role" x="512" y="237">PromptTemplate</text></g>
    <g class="n model" data-k="llm"><rect x="10" y="240" width="100" height="44" rx="14"/><text x="20" y="260">Hosted LLM</text><text class="role" x="20" y="276">FoundationLLM</text></g>
    <g class="n proc" data-k="ga"><rect x="190" y="250" width="140" height="44"/><text x="202" y="270">Generate answer</text><text class="role" x="202" y="286">GenerationStep</text></g>
    <g class="n res" data-k="an"><rect x="580" y="258" width="130" height="40" rx="14"/><text x="592" y="275">Answer</text><text class="role" x="592" y="290">UserFacingOutput</text></g>
    <text class="legend" x="470" y="22">Rounded: resource. Square: step.</text>`,
  steps: [
    { tab: "Model", roles: false, hi: [], flag: [], e: [], e2: [], text: "**Model.** The system model has ten elements. Resources have rounded corners and steps have square corners, joined by `use` and `produce`. Without roles, the model supports no match." },
    { tab: "Annotate", roles: true, hi: [], flag: [], e: [], e2: [], text: "**Annotate.** Each element receives a role, shown beneath its name. The question is a `PublicUserInput`, because it originates from the open internet. The hosted model also carries `ExternalModel`." },
    { tab: "Match a motif", roles: true, hi: ["q", "kb", "fp", "ps"], flag: [], e: ["q-fp", "kb-fp", "fp-ps"], e2: [], text: "**Match a motif.** The Information Retrieval motif matches: a retrieval step uses a user input and a knowledge source and produces retrieved context. A motif match states that this structure is present." },
    { tab: "Check conditions", roles: true, hi: ["fp", "ps", "bp", "pr", "ga"], flag: ["q"], e: ["fp-ps", "ps-bp", "bp-pr", "pr-ga", "q-fp"], e2: [], text: "**Check conditions.** Propagation marks the public question as untrusted content, and the data flow carries this category through the passages to *Generate answer*. The AI risk pattern for prompt injection then tests whether an input screening step is represented on that path, and none is." },
    { tab: "Candidate finding", roles: true, hi: ["ga", "llm"], flag: ["q", "ps", "an"], e: ["llm-ga"], e2: ["ga-an"], text: "**Candidate finding.** Candidate risk *Prompt injection* (OWASP LLM01). Evidence: Customer question, Passages, Generate answer, Hosted LLM, Answer. The team decides whether a screening step exists outside the model, whether one should be added, or whether the risk is accepted." },
  ],
};

export const RISK_REASONS = [
  { label: "Prompt injection", has: "Prompt", text: "The question is also written into the prompt, which forms a second path to the model." },
  { label: "Prompt injection", text: "A public question shapes what is retrieved, and the passages reach the model with no input screening step in between." },
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
    { head: "Candidate risk finding", kind: "risk", text: "One AI risk pattern holding at one place in a model, with the elements it rests on as evidence." },
    { head: "Candidate risk", kind: "risk", text: "The findings of one AI risk pattern over the same evidence, presented as one entry for review." },
  ],
  howHead: "Derivation of a motif",
  how: "A motif is derived by modeling the structure that a source documents. Each participant becomes a node with an expected role and class, and each interaction becomes a `use` or `produce` edge. Where a source shows one step handing over to another, the resource exchanged between them is declared, because the graph is bipartite. Intent, applicability and consequences are omitted at this level. Consequences are stated by the AI risk pattern.",
  absence: "**Presence in motifs, absence in conditions.** Matching is monotone: a motif that matches a model also matches every extension of that model. A motif therefore asserts presence only. Absence is tested in a condition and only over the submitted model, so a finding states that no control is represented in the model.",
};

export const WORKBENCH = {
  intro: "The editor and the canvas present the same Turtle document and remain synchronized in both directions. Each view addresses a different question.",
  views: [
    { id: "library", tab: "Library", paragraphs: [
      "The workbench starts on the Library when no model is loaded, and the **Library** button in its header reopens it at any time. The **Guide** button beside it opens this guide. **Open in workbench** on a library entry in this guide opens the same entry in the workbench.",
      "The Library lists each AI risk pattern with its mechanism, its possible consequences and its suggested controls, and each motif drawn from its own declaration. **Add to canvas** inserts a motif with the context that a selected risk requires.",
    ] },
    { id: "process", tab: "Process", paragraphs: [
      "A BPMN canvas for the process model: pools and lanes, events, gateways, activities, data objects and data stores. An activity names the AI system that performs it, and its chip opens the system model.",
      "Statements made from the business perspective, for example that a data object holds personal data, reach the system model through a bridge. System steps belong to the system model.",
    ] },
    { id: "system", tab: "Architecture", paragraphs: [
      "A Boxology canvas for the system model. Steps and resources are connected with `use` and `produce`, and a step reaches another step only through a resource that one produces and the other uses.",
      "Each element receives roles and data categories from a picker that offers the applicable terms first. Motifs can be inserted from a tray, already connected and annotated. Annotation is the precondition for matching.",
    ] },
    { id: "risk", tab: "Risk", paragraphs: [
      "The assessment on one diagram in the notation of risk storming: each candidate risk is placed above the elements it refers to, with stated risks drawn solid and derived ones dashed.",
      "The team states its own risks, records consequences, controls and priorities, and triages each candidate. Severity is recorded as a judgement together with its author and is never computed.",
    ] },
    { id: "further", tab: "Further functions", rows: [
      ["Findings", "Findings are grouped into candidate risks, so a weakness reached through nested motifs appears once. Selecting one highlights its evidence on the canvas."],
      ["Possible risks", "Addresses a model that states less than a motif requires, such as an element with a coarser role, without a role, or missing. Suggestions leave detection unchanged."],
      ["Controls", "**Apply to this finding** inserts the step a finding suggests, bound to the elements the finding cites, and repeats the assessment."],
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
      title: "Model the business process", view: "Process",
      actions: ["Select **Process** above the canvas.", "Add pools and lanes, start and end events, activities, and data stores with their read and write relations.", "Name each activity with a leading verb.", "For each activity performed by an AI system, name that system so that the **AI system** chip appears on the activity.", "Select **Validate** and resolve the entries under **Input contract**."],
      starter: "*Answer question* is refined by the *Support chatbot* system, and *Knowledge base* is a data store that the chatbot reads and the support agent writes.",
      question: "Should *Generate answer* be a task in the process model?",
      answer: "No. *Answer question* is the business activity. Retrieval, prompt construction and generation belong to the system model, which keeps the system boundary visible.",
    },
    {
      title: "Model the system", view: "Architecture",
      actions: ["Select **Architecture** above the canvas and create a system with **+ system**.", "Add steps and resources from **Elements**, or insert a structure from **Architectural motifs**.", "Connect elements from the port of a node. The connection is `use` when a step reads a resource and `produce` when a step writes one.", "Select **Validate** and confirm that each step uses and produces a resource."],
      starter: "*Find passages* uses the question and the knowledge base and produces *Passages*. Data reaches the answer through *Generate answer*, which uses the hosted model.",
      question: "Can *Find passages* connect directly to *Build prompt*?",
      answer: "No. The graph is bipartite. *Find passages* produces *Passages*, and *Build prompt* uses them. Motifs match on the resource between the two steps, so its omission can conceal a risk.",
    },
    {
      title: "Annotate the elements", view: "Roles and data categories",
      actions: ["Open **Annotate** in the drawer, or select an element on the canvas.", "Assign the most specific role that fits. An element can hold several roles.", "Mark personal or sensitive data with a data category.", "Select **Apply annotations** and confirm that the count of untagged elements reaches zero."],
      starter: "*Customer question* is a `PublicUserInput`, and *Hosted LLM* carries both `FoundationLLM` and `ExternalModel`.",
      question: "A role is under consideration because it would produce a finding. How should the role be chosen?",
      answer: "The role should describe the element. Selecting roles to obtain a result makes the assessment reproduce the expectations of the analyst. A concept without a suitable role is useful feedback on the role vocabulary.",
    },
    {
      title: "Record risks before the assessment", view: "Risk",
      actions: ["Select **Risk** above the canvas and use **Hide the run** while the team works.", "For each part of the system, state what could fail and where.", "Attach each stated risk to the element or activity it refers to."],
      starter: "A stated risk reads: the generated answer reaches the customer with no check against the passages.",
      question: "Is \"the LLM may hallucinate\" a sufficient entry?",
      answer: "It requires a location. A risk tied to an element can be compared with a finding, which is the purpose of recording it in advance.",
    },
    {
      title: "Run the assessment", view: "Findings",
      actions: ["Select **Run assessment**.", "Open **Findings** and select an entry.", "Inspect the evidence elements highlighted on the canvas and confirm that each corresponds to the intended part of the system."],
      starter: "The complete scene yields six candidate risks, listed in the [tour](#/tour).",
      question: "An assessment produces no findings. What does this result indicate?",
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
      starter: "An input screening step added before *Generate answer* addresses the prompt injection candidates, one path at a time.",
      question: "A finding no longer appears after a control is added. Is the risk handled?",
      answer: "The model now represents the control. Whether the control operates as intended is a question for testing and operations, which lie outside the scope of PAIR-AI.",
    },
  ],
};

export const READING = {
  exampleHead: "Example finding",
  riskPattern: "PromptInjectionRiskPattern",
  evidenceLabel: "Prompt injection",
  labels: { condition: "Condition", mechanism: "Mechanism", evidence: "Evidence", controls: "Suggested controls", taxonomy: "Taxonomy entries" },
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
    { head: "Output", text: "A finding is a node that can be queried.", code: `?riskFinding a pair:RiskFinding ;
    pair:findingStatus "candidate" ;
    pair:generatedByRiskPattern pat:PromptInjectionRiskPattern ;
    pair:generatedFromMatch ?match ;
    pair:hasEvidence ?untrustedContent, ?generationStep ;
    pair:hasCandidateRiskTaxonomyEntry ?riskTaxonomyEntry ;
    pair:hasSuggestedControl ?suggestedControl .` },
  ],
  properties: [
    { head: "Reproducibility", text: "The same graph yields the same findings. `airiskkg kb-version --json` prints a fingerprint of the knowledge base that can be stored with each result." },
    { head: "Open-world reading", text: "The graph is read under the open-world assumption. The closed check for a represented control ranges only over the submitted graph." },
    { head: "Input contracts", text: "SHACL shapes check the model before matching and warn when a role or data category cannot take part in a match." },
    { head: "Command line", text: "`airiskkg assess graph.ttl` writes motif matches and findings for scripted runs and batch evaluation." },
  ],
  componentsHead: "Library components",
  components: "Counts for the latest library version.",
  componentRows: [
    { label: "Motifs", count: "motifs", note: "Generative AI, agentic systems, ML serving and training, supply chain" },
    { label: "AI risk patterns", count: "riskPatterns", note: "Each with conditions and a mechanism" },
    { label: "Conditions", count: "conditions", note: "" },
    { label: "Controls", count: "controls", note: "Suggested per AI risk pattern" },
    { label: "Roles", count: "roles", note: "Including role categories" },
    { label: "Data categories", count: "dataCategories", note: "" },
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
  openInWorkbench: "Open in workbench",
  versionLabel: "Library version",
  tabs: [
    { kind: "risk", label: "AI risk patterns" },
    { kind: "motif", label: "Motifs" },
    { kind: "role", label: "Roles" },
    { kind: "category", label: "Data categories" },
    { kind: "control", label: "Controls" },
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
    { head: "Repeatability and validity", text: "Identical output across runs demonstrates repeatability. The validity of the findings is a separate question, addressed by evaluation." },
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
    { term: "BEAM", text: "The vocabulary of the system model, based on the Boxology notation: resources and steps connected by use and produce." },
    { term: "Boxology", text: "A graphical notation and set of design patterns for hybrid learning and reasoning systems." },
    { term: "Candidate risk", text: "The findings of one AI risk pattern over the same evidence, presented as one entry for review. Where several motifs reach the same weakness at the same place, their findings form one candidate risk." },
    { term: "Candidate risk finding", text: "One AI risk pattern holding at one place in a model. A structural disposition that requires triage." },
    { term: "Condition", text: "A test that an AI risk pattern applies to a motif match: a data category, a context, or the absence of a represented control. Absence is tested only here." },
    { term: "Control", text: "A step or measure that addresses a risk, such as input screening or rate limiting. Controls are suggested per AI risk pattern and can be applied as a rewrite of the model." },
    { term: "Data category", text: "A term on a data element, such as sensitive information or untrusted content. Categories propagate along flow relations." },
    { term: "DPV", text: "The Data Privacy Vocabulary, the alignment target for personal data categories and purposes." },
    { term: "Evidence", text: "The elements of the model on which a finding rests." },
    { term: "Mechanism", text: "The curated explanation of how a structure, under its conditions, can lead to harm. A mechanism takes no part in detection." },
    { term: "Motif", text: "The recurring solution structure of a design, stated as a small graph of roles and flow relations. A motif is structure only and makes no risk claim." },
    { term: "Motif match", text: "One place in a model where the nodes of a motif bind to concrete elements." },
    { term: "Process model", text: "The BPMN model of the business process in which the AI system operates." },
    { term: "Role", text: "A term stating what an element represents, for example RetrievalStep or FoundationLLM. Matching reads roles." },
    { term: "sBPMN", text: "An OWL formalization of BPMN 2.0, the vocabulary of the process model." },
    { term: "SHACL", text: "The W3C constraint language used for the input contracts and the annotation guidance." },
    { term: "System model", text: "The BEAM graph of an AI system: its steps, its resources and the relations between them. The workbench presents it at the Architecture level." },
    { term: "Triage", text: "The recorded human decision on a candidate: Confirmed, Mitigated, Accepted or Not a risk, with a reason and an author." },
  ],
};

export const FOOTER = "PAIR-AI is developed at WU Wien. Findings are candidates for human review.";
