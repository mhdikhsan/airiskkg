# Architectural Motif and Risk Pattern Examples

This document contains two architectural motif examples and two risk pattern
examples taken from the ontology and assessment output in this repository.
The instance examples use UC6, the `RAG-based Chatbot System`.

Main sources:

- `ontology/patterns/motif.ttl`
- `ontology/patterns/risk_pattern_library.ttl`
- `ontology/example/uc6.ttl`
- `outputs/uc6_assessment/motif_matches.ttl`
- `outputs/uc6_assessment/risk_findings.ttl`

## Architectural Motif Examples

### 1. Vector-based Information Retrieval Motif

IRI: `pat:VectorBasedInformationRetrievalMotif`

Brief definition: a retrieval process uses a query and a vector store or
knowledge source, then produces a retrieved result or retrieved context.

Motif structure:

| Pattern node | Expected role | UC6 example |
| --- | --- | --- |
| `pat:VectorIR_QueryNode` | `pair:UserInput` | `uc6:ReformulatedQuery` |
| `pat:VectorIR_VectorStoreNode` | `pair:VectorStore` | `uc6:ProductInformationVectorDB` |
| `pat:VectorIR_RetrievalStepNode` | `pair:RetrievalStep` | `uc6:ProductInformationRetrieval` |
| `pat:VectorIR_RetrievedResultNode` | `pair:RetrievedContext` | `uc6:EmbeddedProductInfo` |

Example flow in UC6:

```ttl
uc6:ProductInformationRetrieval
    pair:playsRole pair:RetrievalStep ;
    beam:use uc6:ReformulatedQuery ;
    beam:use uc6:ProductInformationVectorDB ;
    beam:produce uc6:EmbeddedProductInfo .
```

Meaning: the system takes a reformulated query, searches the product vector
DB for context, then produces product context that will be used by the next
process.

### 2. Query Rewriting Motif

IRI: `pat:QueryRewritingMotif`

Brief definition: an LLM reformulates the user query into an alternative
query, which is then used for retrieval.

Motif structure:

| Pattern node | Expected role | UC6 example |
| --- | --- | --- |
| `pat:QueryRewrite_LLMNode` | `pair:FoundationLLM` | `uc6:LLM` |
| `pat:QueryRewrite_RewriteStepNode` | `pair:QueryReformulationStep` | `uc6:LlatrievalScoringAndQueryReformulation` |
| `pat:QueryRewrite_RewrittenQueryNode` | `pair:RewrittenQuery` | `uc6:ReformulatedQuery` |
| `pat:QueryRewrite_RetrievalStepNode` | `pair:RetrievalStep` | `uc6:ProductInformationRetrieval` |
| `pat:QueryRewrite_RetrievedContextNode` | `pair:RetrievedContext` | `uc6:EmbeddedProductInfo` |

Example flow in UC6:

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

Meaning: the LLM is used to create a new query, which is then reused by the
retrieval process to fetch more relevant context.

## Risk Pattern Examples

### 1. Prompt Injection Interpretation

IRI: `pat:PromptInjectionInterpretation`

Label: `Prompt injection interpretation`

Main condition: untrusted content enters the prompt context or generation
context. In the library, this condition is represented by
`pat:PromptInjection_UntrustedPromptContextCondition`.

Risk taxonomy entries that may be indicated:

- `owasp:llm01-prompt-injection`
- `atlas:prompt-injection`
- `mit:subdomain-2-2`
- `mit:subdomain-4-3`

Example finding in UC6:

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

Meaning: retrieved content such as `uc6:EmbeddedProductInfo` contains
`pair:UntrustedContent` and can enter the generation process that produces
user-facing output.

Suggested controls from the library:

- `pat:Control_InputValidationAndPromptIsolation`
- `pat:Control_Guardrails`
- `pat:Control_LoggingMonitoringAndEvals`

### 2. Sensitive Data Retrieval Exposure Interpretation

IRI: `pat:SensitiveDataRetrievalExposureInterpretation`

Label: `Sensitive data retrieval exposure interpretation`

Main condition: sensitive retrieved context reaches the LLM generation step
and user-facing output without a disclosure control represented in the
graph.

Risk taxonomy entries that may be indicated:

- `owasp:llm02-sensitive-information-disclosure`
- `atlas:exposing-personal-information`
- `mit:subdomain-2-1`

Example finding in UC6:

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
