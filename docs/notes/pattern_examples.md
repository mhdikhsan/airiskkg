# Architectural Motif and Risk Pattern Examples

Dokumen ini berisi dua contoh architectural motif dan dua contoh risk pattern
yang diambil dari ontology dan output assessment repository ini. Contoh
instance memakai UC6, yaitu `RAG-based Chatbot System`.

Sumber utama:

- `ontology/patterns/motif.ttl`
- `ontology/patterns/risk_pattern_library.ttl`
- `ontology/example/uc6.ttl`
- `outputs/uc6_assessment/motif_matches.ttl`
- `outputs/uc6_assessment/risk_findings.ttl`

## Architectural Motif Examples

### 1. Vector-based Information Retrieval Motif

IRI: `pat:VectorBasedInformationRetrievalMotif`

Definisi ringkas: proses retrieval memakai query dan vector store atau knowledge
source, lalu menghasilkan retrieved result atau retrieved context.

Struktur motif:

| Pattern node | Expected role | Contoh UC6 |
| --- | --- | --- |
| `pat:VectorIR_QueryNode` | `pair:UserInput` | `uc6:ReformulatedQuery` |
| `pat:VectorIR_VectorStoreNode` | `pair:VectorStore` | `uc6:ProductInformationVectorDB` |
| `pat:VectorIR_RetrievalStepNode` | `pair:RetrievalStep` | `uc6:ProductInformationRetrieval` |
| `pat:VectorIR_RetrievedResultNode` | `pair:RetrievedContext` | `uc6:EmbeddedProductInfo` |

Contoh alur di UC6:

```ttl
uc6:ProductInformationRetrieval
    pair:playsRole pair:RetrievalStep ;
    beam:use uc6:ReformulatedQuery ;
    beam:use uc6:ProductInformationVectorDB ;
    beam:produce uc6:EmbeddedProductInfo .
```

Maknanya: sistem mengambil query yang sudah direformulasi, mencari konteks pada
vector DB produk, lalu menghasilkan konteks produk yang akan dipakai oleh proses
berikutnya.

### 2. Query Rewriting Motif

IRI: `pat:QueryRewritingMotif`

Definisi ringkas: LLM mereformulasi user query menjadi query alternatif yang
kemudian dipakai untuk retrieval.

Struktur motif:

| Pattern node | Expected role | Contoh UC6 |
| --- | --- | --- |
| `pat:QueryRewrite_LLMNode` | `pair:FoundationLLM` | `uc6:LLM` |
| `pat:QueryRewrite_RewriteStepNode` | `pair:QueryReformulationStep` | `uc6:LlatrievalScoringAndQueryReformulation` |
| `pat:QueryRewrite_RewrittenQueryNode` | `pair:RewrittenQuery` | `uc6:ReformulatedQuery` |
| `pat:QueryRewrite_RetrievalStepNode` | `pair:RetrievalStep` | `uc6:ProductInformationRetrieval` |
| `pat:QueryRewrite_RetrievedContextNode` | `pair:RetrievedContext` | `uc6:EmbeddedProductInfo` |

Contoh alur di UC6:

```ttl
uc6:LlatrievalScoringAndQueryReformulation
    pair:playsRole pair:QueryReformulationStep ;
    beam:use uc6:LLM ;
    beam:produce uc6:ReformulatedQuery ;
    beam:inform uc6:ProductInformationRetrieval .

uc6:ProductInformationRetrieval
    pair:playsRole pair:RetrievalStep ;
    beam:use uc6:ReformulatedQuery ;
    beam:produce uc6:EmbeddedProductInfo .
```

Maknanya: LLM dipakai untuk membuat query baru, lalu query itu dipakai ulang
oleh proses retrieval untuk mengambil konteks yang lebih relevan.

## Risk Pattern Examples

### 1. Prompt Injection Interpretation

IRI: `pat:PromptInjectionInterpretation`

Label: `Prompt injection interpretation`

Kondisi utama: konten tidak tepercaya masuk ke prompt context atau generation
context. Dalam library, kondisi ini direpresentasikan oleh
`pat:PromptInjection_UntrustedPromptContextCondition`.

Risk taxonomy yang dapat terindikasi:

- `owasp:llm01-prompt-injection`
- `atlas:prompt-injection`
- `mit:subdomain-2-2`
- `mit:subdomain-4-3`

Contoh finding di UC6:

```ttl
<.../prompt-injection>
    a pair:RiskFinding ;
    rdfs:label "Candidate prompt injection exposure"@en ;
    dct:description "Untrusted user or retrieved content can enter LLM prompt or generation context."@en ;
    pair:findingStatus "candidate" ;
    pair:generatedByMotif pat:VectorBasedInformationRetrievalMotif ;
    pair:hasEvidenceElement
        uc6:EmbeddedProductInfo ,
        uc6:EventSummary ,
        uc6:LLM ,
        uc6:LLMPrompting .
```

Maknanya: retrieved content seperti `uc6:EmbeddedProductInfo` mengandung
`pair:UntrustedContent` dan bisa masuk ke proses generation yang menghasilkan
output user-facing.

Suggested controls dari library:

- `pat:Control_InputValidationAndPromptIsolation`
- `pat:Control_Guardrails`
- `pat:Control_LoggingMonitoringAndEvals`

### 2. Sensitive Data Retrieval Exposure Interpretation

IRI: `pat:SensitiveDataRetrievalExposureInterpretation`

Label: `Sensitive data retrieval exposure interpretation`

Kondisi utama: retrieved context yang sensitif mencapai LLM generation step dan
user-facing output tanpa disclosure control yang direpresentasikan di graph.

Risk taxonomy yang dapat terindikasi:

- `owasp:llm02-sensitive-information-disclosure`
- `atlas:exposing-personal-information`
- `mit:subdomain-2-1`

Contoh finding di UC6:

```ttl
<.../sensitive-data-retrieval-exposure>
    a pair:RiskFinding ;
    rdfs:label "Candidate sensitive data retrieval exposure"@en ;
    dct:description "Sensitive retrieved context reaches an LLM generation step and user-facing output without a represented disclosure control."@en ;
    pair:findingStatus "candidate" ;
    pair:generatedByMotif pat:VectorBasedInformationRetrievalMotif ;
    pair:hasEvidenceElement
        uc6:ProductInformationVectorDB ,
        uc6:EmbeddedProductInfo ,
        uc6:LLM ,
        uc6:LLMPrompting ,
        uc6:EventSummary .
```

Maknanya: `uc6:ProductInformationVectorDB` dan `uc6:EmbeddedProductInfo`
mengandung `uc6:PrivateProductInformation`, yang merupakan turunan dari
`pair:SensitiveInformation`. Karena konteks itu dapat mengalir ke LLM dan
output user-facing, assessment menghasilkan candidate risk finding.

Suggested controls dari library:

- `pat:Control_DataMinimizationAndRedaction`
- `pat:Control_RetrievalAccessControl`
- `pat:Control_OutputValidationAndSanitization`
- `pat:Control_Guardrails`
