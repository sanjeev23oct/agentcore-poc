# The Semantic Layer in Agentic Apps: Ontology, RDF/RDFS/OWL, and Who Runs It in Production

**Companion to** [16-context-graph-and-semantic-layer.md](./16-context-graph-and-semantic-layer.md).
Doc 16 covers *which AWS services exist* (Neptune, Bedrock GraphRAG, AWS Context, the Prescriptive
Guidance blueprint). This doc covers three other questions:

1. **What job does a semantic layer do for an agent?**
2. **What are RDF, RDFS, OWL, SHACL and the rest, in plain terms?**
3. **Which large organisations run this in production, and on what graph database?**

**How this doc is organised:** **Part A uses AWS sources only**: AWS docs, AWS blogs, AWS
customer pages, Amazon Science. Definitions of the W3C standards come from the standards
themselves and are labelled that way. **Part B** covers other companies' own publications
(engineering papers, talks) and vendor/analyst material. Part B is kept separate so it is never
mistaken for AWS's position. Researched 17 Nov 2026.

---

# Part A: From AWS (and the W3C standards)

## A1. Why an agent needs a semantic layer

An LLM reads words. Enterprise data is stored as tables, columns, codes and joins. Something
has to tell the agent what *"exposure"*, *"active client"* or *"onboarding complete"* means in
this bank, which tables hold it, and which rules apply. Without that, the model guesses.

AWS's clearest real-world evidence is the **MUFG Bank** post (AWS Database Blog, Oct 8 2026).
MUFG's first attempt used LLMs alone on procedure documents. AWS reports that the model *"would
silently invent steps"* and *"the flowcharts created using only large language models (LLMs) were
unusable."* The fix was to ground the agent in an OWL ontology stored in Neptune (see A5).
The post's analogy is *"an AI agent is like a highly skilled new employee with no business
knowledge."* The ontology supplies that business knowledge.

AWS's Prescriptive Guidance frames the goal as **ACE: Accuracy, Consistency, Explainability**.
AWS's Jul 2026 ontology blog makes the same point from the context side: *"The bottleneck is no
longer model intelligence, but how you structure the information these models consume,"* and
*"LLM performance drops significantly as context length increases."* A semantic layer lets the
agent fetch a small, correct slice of context instead of a large, noisy one.

### Two different things are both called a "semantic layer"

| | **Metric / BI semantic layer** | **Ontology / knowledge-graph semantic layer** |
|---|---|---|
| What it defines | Measures and dimensions (e.g. *revenue = sum(amount) where status='booked'*) | Concepts, relationships, constraints and rules (e.g. *a Guarantor is a Party that guarantees a Facility*) |
| Typical form | YAML or SQL objects in the warehouse or dbt | RDF/OWL ontology + knowledge graph (Neptune), or a property-graph schema |
| Agent use | Text-to-SQL with fixed, governed numbers | Understanding meaning, multi-hop relationships, inference, validation, explanation |
| AWS example | The **Metric Store** inside the Prescriptive Guidance design (metrics bound to ontology classes, *"resolved deterministically at query time — no LLM required"*) | MUFG on Neptune; Prescriptive Guidance knowledge layer; Context Ontology Accelerator |

AWS's blueprint combines both, binding each metric definition to an ontology class. Banks
usually need both: the metric layer stops the agent from inventing numbers, and the ontology
stops it from misunderstanding what the numbers refer to.

## A2. The standards stack in plain terms (definitions per W3C specs)

These are W3C standards. Neptune stores and queries the RDF-based ones natively.

| Standard | Plain-language role | Banking example |
|---|---|---|
| **RDF** | The data format. Every fact is a *triple*: subject–predicate–object, using global IDs (IRIs) | `:client42 :hasFacility :fac9` |
| **RDFS** | Basic vocabulary: classes, subclasses, which properties apply to which class (domain/range) | `:CorporateClient rdfs:subClassOf :Client` |
| **OWL 2** | Richer logic: equivalence, disjointness, cardinality, transitive/inverse properties, property chains. A **reasoner** can derive facts that were never stated | *A Party that guarantees a Facility of a Client is a ConnectedParty of that Client* |
| OWL 2 profiles | Trade-offs between expressiveness and speed. **EL**: large class hierarchies, fast (ELK reasoner). **QL**: rewrites queries over relational DBs (used by Ontop/OBDA). **RL**: rule-engine friendly. **DL**: full expressiveness (HermiT reasoner) | MUFG uses **OWL 2 DL** with HermiT |
| **SHACL** | Validation rules ("shapes") for checking data. OWL describes what *can* be inferred; SHACL checks what *must* be present | *Every Facility must have exactly one Borrower and a currency code* |
| **SKOS** | Taxonomies and thesauri: preferred and alternate labels, broader/narrower terms | "attrition" is an alternate label for "customer churn" |
| **SPARQL** | The query language for RDF (SELECT, CONSTRUCT, UPDATE, federation) | "All parties connected to client 42 within 2 hops" |
| **SWRL** | If-then rules on top of OWL | *if X submittedBy Y and Y employedBy Z then X affiliatedWith Z* (AWS's example) |
| **R2RML** | Maps relational tables to RDF so they can be queried as a graph without copying the data | Core-banking `FACILITY` table appears as `:Facility` instances |

**Ontology vs knowledge graph:** the ontology is the schema (classes and rules, called the
**T-Box** in AWS's guide). The knowledge graph is the instance data (the **A-Box**). MUFG
built one shared ontology from head-office procedures and then loaded each branch's procedure as
an instance graph built from that ontology.

### Small illustrative example (Turtle syntax)

```turtle
# T-Box (ontology)
:Client          a owl:Class .
:CorporateClient a owl:Class ; rdfs:subClassOf :Client .
:Facility        a owl:Class .
:hasFacility     a owl:ObjectProperty ; rdfs:domain :Client ; rdfs:range :Facility .
:guarantees      a owl:ObjectProperty ; rdfs:domain :Party  ; rdfs:range :Facility .
# property chain: a guarantor of my facility is connected to me
:connectedTo owl:propertyChainAxiom ( :guarantees [ owl:inverseOf :hasFacility ] ) .

# SHACL shape (validation)
:FacilityShape a sh:NodeShape ; sh:targetClass :Facility ;
  sh:property [ sh:path :currency ; sh:minCount 1 ; sh:maxCount 1 ] .

# A-Box (instance data)
:acme a :CorporateClient ; :hasFacility :fac9 .
:bob  :guarantees :fac9 .
# A reasoner derives:  :bob :connectedTo :acme   (never stated explicitly)
```

The derived fact `:bob :connectedTo :acme` is the kind of relationship an RM or Risk agent needs
for exposure and conflict checks. With an ontology the fact is derived by a reasoner,
deterministically, with provenance. Without one, the agent has to guess it from text.

## A3. Where Neptune fits, and what it does *not* do

| Point | What AWS documents |
|---|---|
| Two data models | Neptune Database supports **RDF/SPARQL** and **property graph** (Gremlin, openCypher). Neptune Analytics uses openCypher. Default SPARQL prefixes include `rdf`, `rdfs`, `owl`, `xsd` |
| OWL loads as-is | *"OWL ontologies are represented in RDF, and therefore can be loaded as is"* (AWS Database Blog, 2022) |
| Named graphs | Every triple belongs to a named graph. The default graph is the union of all named graphs. AWS's blueprint stores **inferred triples in separate named graphs** so derived facts stay distinguishable from asserted ones |
| **Reasoning** | Neptune's SPARQL compliance page lists SPARQL 1.1 Query and Update and **no entailment regime**. Every AWS design reviewed runs reasoning **outside** Neptune: MUFG puts HermiT *"between Amazon Neptune and the AI agent"*; Prescriptive Guidance runs ELK, HermiT, SHACL and SWRL engines on **ECS**; another AWS blog integrates the RDFox reasoner with Neptune |
| Change events | **Neptune DB Streams** (CDC, up to 7 days retention) trigger re-reasoning, re-indexing, and agent cache invalidation |
| Agent access | Neptune MCP Server (openCypher/Gremlin; it runs any query sent, including writes, so scope IAM to read-only) registered behind AgentCore Gateway. See doc 16 |

> **Inconsistency in AWS's own material:** one sentence in the Prescriptive Guidance knowledge-layer
> page mentions *"Neptune's native support for SPARQL 1.1, named graphs, and OWL inference."* The
> same guide's architecture, the MUFG post and the Neptune user guide all put reasoning in an
> external engine. **Plan for an external reasoner** and confirm with AWS before relying on
> anything else.

**RDF or property graph?** AWS uses both:
- **RDF + OWL** when meaning, inference, standards and auditability matter: MUFG, Siemens Energy,
  NXP, the Prescriptive Guidance blueprint, Context Ontology Accelerator (W3C standards).
- **Property graph** when traversal and scale matter more than formal semantics: Wiz's security
  graph, Neptune Analytics for Bedrock GraphRAG, and AWS's Jul 2026 "semantic ontology for AI
  assistants" post, which uses custom relationship types (`CONTAINS`, `BELONGS_TO`) rather than
  OWL.

## A4. The roles a semantic layer plays inside an agent

| Role | What happens | AWS reference |
|---|---|---|
| **1. Grounding for query generation** | The agent maps user words to ontology terms (SKOS labels, vector search over concepts), then generates SPARQL/SQL against real tables | Prescriptive Guidance tools `intent_classification`, `generate_queries`; Jul 2026 ontology blog ("customer churn" ↔ "attrition") |
| **2. Deterministic numbers** | Named metrics are resolved from a governed Metric Store, not computed by the LLM | Prescriptive Guidance Metric Store |
| **3. Inference** | A reasoner derives implied facts (hierarchies, property chains, rules) | MUFG + HermiT; ELK/HermiT/SWRL ensemble |
| **4. Validation / guardrail** | SHACL checks agent-written or extracted data before it is accepted | Prescriptive Guidance Symbolic Reasoning Service |
| **5. Explainability** | Answers cite the graph facts and reasoning provenance (engine, rule, axiom) | MUFG cites inferred facts; blueprint stores reasoning provenance |
| **6. Federated access without copying** | SPARQL over the ontology is translated to SQL on Redshift, Athena, Snowflake or Databricks through R2RML (Ontop) | Prescriptive Guidance VKG Service |
| **7. Access control** | User, group and agent identity (`sub`, `groups`, `act` JWT claims from AgentCore Gateway) drives row/column-level filtering through query rewriting or Lake Formation | Prescriptive Guidance cross-cutting concerns |
| **8. Shared meaning across agents** | One ontology, exposed through MCP, is reused by CRM, Risk and Onboarding agents, so "client" means the same thing to all of them | Context Ontology Accelerator MCP server; Neptune MCP via Gateway |

**Typical request flow (RM assistant):** RM asks a question → orchestrator agent → *semantic
layer tool* (resolve terms → generate query → federate over Neptune and the warehouse → apply the
user's entitlements) → reasoner adds derived relationships → agent answers with cited facts.

## A5. Live projects published by AWS / Amazon

Maturity is stated as AWS describes it. Where AWS's wording is ambiguous, the table says so.

| Organisation | What they built | Graph DB / model | Semantic depth | Maturity per AWS | Reported result |
|---|---|---|---|---|---|
| **MUFG Bank** (Oct 2026) | "AI Flowchart": standardise back-office procedures across ~30 countries (~200k transactions/day) | **Neptune**, RDF/**OWL 2 DL**, **HermiT** reasoner, **Strands** agent on Bedrock | **Full ontology + reasoning** | Described as *"gone live"*. The intro calls the savings "expected" while the results table says "observed", so treat the numbers as early | Flowchart creation 10 → 0.5 person-days; total per branch procedure 11 → 1 person-day (~90%) |
| **Merck** (CAKE) | Change Assessment Knowledge Engine for manufacturing and regulatory change proposals | **Neptune** graph of supply chain + regulatory environment, plus an NLP model | Domain knowledge graph | Production (AWS case study) | Up to 90% faster assessments; 30–70% less manual effort |
| **Siemens Energy** | Knowledge-graph applications with metaphactory | **Neptune**, **RDF** | RDF knowledge graph | Production (AWS + partner case study) | ~1,500 manual hours/year saved (partner-reported) |
| **NXP** | Event-driven RDF import pipeline (CSV/XML → RDF → SPARQL UPDATE LOAD) | **Neptune**, RDF, migrated from a custom RDF store | RDF knowledge graph | Production (AWS blog) | n/a |
| **Amazon Alexa** | Alexa's knowledge graph | **Neptune** | Knowledge graph | Production (AWS customer page) | Serves tens of millions of customers |
| **Amazon COSMO** (SIGMOD 2024) | Commonsense e-commerce knowledge graph mined from behaviour logs with an LLM (COSMO-LM) | Amazon-internal | Large-scale KG, LLM-generated assertions | **Deployed** in search relevance, session recommendation and search navigation | Up to 60% gain on a recommendation task (offline experiment) |
| **Trend Micro** (Apr 2026) | "Company-wise memory" for its Companion security assistant | **Neptune** KG + Mem0 + OpenSearch + Bedrock (Claude) | Entity/relationship graph with human approve/reject loop | *"Remains under evaluation and tuning"* | No metrics published |
| **BMW** | Knowledge graph over its Cloud Data Hub; GraphRAG | **Neptune** via Bedrock KB GraphRAG | Auto-extracted graph | **Prototype** (AWS customer page) | n/a |
| **Wiz** | Security Graph for real-time cloud risk | **Neptune**, property graph, *"100s of billions of nodes"* | Property graph, no ontology | Production | ~20% lower graph DB cost after moving to r8g instances |
| **Smartsheet** | Knowledge-graph apps for GenAI and recommendations | **Neptune** | Knowledge graph | Production (customer quote) | n/a |

**Patterns across these:**
- Only **MUFG** publicly shows the *full* stack (OWL ontology + reasoner + agent), and it's a
  bank. It's the closest AWS-published precedent for this project.
- Most other Neptune customers use a **knowledge graph without formal reasoning**. That is
  the normal starting point.
- **Humans stay in the loop** wherever meaning is decided: MUFG experts own standardisation
  decisions; Trend Micro users approve or reject memories; Context Ontology Accelerator requires
  experts to approve every ontology element.

## A6. AWS tooling to build one (new since doc 16)

| Asset | Status | What it gives you |
|---|---|---|
| **Context Ontology Accelerator** (`github.com/aws/context-ontology-accelerator`, announced **Jul 31 2026**) | Open source, Apache 2.0; self-deploy or with AWS ProServe | AI drafts an ontology from structured and unstructured sources; **domain experts review, edit and approve every element**; stored in **Neptune** using **W3C standards**; OpenSearch Serverless for vectors; **MCP server** for any agent. AWS says this *"will become a fully managed feature native to AWS Context"*, and ontologies built now will carry over |
| **Prescriptive Guidance: Semantic Layer for Agentic AI** | Published guide + sample | Full reference: Neptune T-Box/A-Box, Ontop VKG, ELK/HermiT/SHACL/SWRL on ECS, Metric Store, AgentCore Gateway identity propagation, MCP and A2A tools |
| **"Build a semantic ontology to power AI assistants on AWS", Part 1** (Jul 14 2026) | Blog how-to | Bottom-up ontology from catalog metadata + column profiling. Reports ~200–300 semantic relationships per 1,000 columns and 30–50% business-term reuse after dedup. Uses a property graph, not OWL |
| **Neptune MCP Server** | GA (May 2025) | Agent query access via Gateway (see doc 16) |
| **AWS Context** | Announced Jun 2026, **not GA** | Managed context graph (see doc 16) |

## A7. Recommendation for the bank RM project

Move up this ladder only when the step below stops being good enough:

| Step | What | When it's enough |
|---|---|---|
| 1 | **Glossary + metric layer**: business terms (SKOS-style labels) and governed metric definitions exposed as an MCP tool | Questions are mostly "what is X for client Y" with numbers |
| 2 | **Knowledge graph in Neptune** (client–facility–party–product–document relationships), queried by agents via Neptune MCP behind Gateway | Multi-hop questions: connected parties, group exposure, who owns what |
| 3 | **Formal ontology (OWL + SHACL)** seeded from **FIBO** concepts, generated with **Context Ontology Accelerator**, approved by Risk/Data owners | Several agents and departments must share definitions, or answers must be auditable for regulators |
| 4 | **Reasoner + virtual KG** (HermiT/ELK on ECS, Ontop over Redshift/Snowflake) per Prescriptive Guidance | Derived relationships must be deterministic and explainable; data can't be copied |

Practical notes:
- **Start the ontology narrow**: Client, Party, Facility, Exposure, Collateral, Onboarding Case,
  Document. MUFG started from head-office procedures as a single shared schema.
- **Ontology ownership is a governance role, not an IT task.** Every AWS example keeps domain
  experts as approvers.
- **Keep inferred facts in separate named graphs** so the agent can say "derived" vs "recorded".
- **Budget for a reasoner service.** Neptune stores and queries; it doesn't reason.
- **POC test** (extends [13-poc-plan.md](./13-poc-plan.md)): run 30 RM questions three ways
  (plain RAG, graph via Neptune MCP, graph + ontology) and score them with AgentCore Evaluations'
  groundedness evaluator ([12-evaluations.md](./12-evaluations.md)).

## A8. Videos from AWS channels (2026)

Upload dates and lengths come from each video's YouTube page metadata (checked 17 Nov 2026).
The videos have not been reviewed in full. re:Invent 2026 sessions (early Dec) should appear on
the AWS Events channel later.

| Date | Video | Channel | Length | Why watch |
|---|---|---|---|---|
| 2026-01-29 | [Build your first GraphRAG Powered Agent! (No Graph Expert Required)](https://www.youtube.com/watch?v=gv6zK265OUE) | AWS Events (Databases for AI) | 59 min | Hands-on starting point: an agent on a Neptune graph |
| 2026-01-30 | [Build Knowledge Graph-powered AI Agents For Your Use Case](https://www.youtube.com/watch?v=6B29VDvPPzc) | AWS Events (Databases for AI) | 60 min | Modelling a KG for your own domain, then exposing it to agents |
| 2026-03-16 | [AI-Powered Graph Building with Amazon Neptune](https://www.youtube.com/watch?v=HGgUTW99sDQ) | AWS Events | — | Using agentic AI to build the Neptune graph itself |
| 2026-05-14 | [Build an Agentic GraphRAG System in 1 Hour (MCP + Knowledge Graph)](https://www.youtube.com/watch?v=LnCXoIr0Mw8) | AWS Events (Databases for AI) | 60 min | Closest to our pattern: KG behind an MCP server for agents |
| 2026-06-10 | [Capture the 'Why': Building Context Graphs for Explainable AI Agents on AWS](https://www.youtube.com/watch?v=RofHzGgzj5E) | AWS London Ontario Meetup (community) | 36 min | Explainability and decision trails using context graphs on AWS |
| 2026-06-18 | [AWS Summit New York 2026 highlights](https://www.youtube.com/watch?v=T52C-stGF3I) | AWS Events | 7 min | Summit where AWS Context and AgentCore Harness GA were announced |

## AWS sources

- [How MUFG Bank aims to cut flowchart work by up to 90% with ontology-grounded AI on Amazon Neptune and Amazon Bedrock (AWS Database Blog, Oct 2026)](https://aws.amazon.com/blogs/database/how-mufg-bank-aims-to-cut-flowchart-work-by-up-to-90-with-ontology-grounded-ai-on-amazon-neptune-and-amazon-bedrock/)
- [Semantic Layer for Agentic AI: Knowledge Layer (AWS Prescriptive Guidance)](https://docs.aws.amazon.com/prescriptive-guidance/latest/semantic-layer-agentic-ai-ontology-reasoning-virtual-knowledge-graph/knowledge-layer.html)
- [Amazon Web Services introduces Context Ontology Accelerator (What's New, Jul 31 2026)](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-context--ontology-accelarator-generally-available)
- [aws/context-ontology-accelerator (GitHub)](https://github.com/aws/context-ontology-accelerator)
- [Build a semantic ontology to power AI assistants on AWS, Part 1 (AWS Database Blog, Jul 2026)](https://aws.amazon.com/blogs/database/build-a-semantic-ontology-to-power-ai-assistants-on-aws-part-1/)
- [SPARQL standards compliance in Amazon Neptune](https://docs.aws.amazon.com/neptune/latest/userguide/feature-sparql-compliance.html)
- [Model-driven graphs using OWL in Amazon Neptune (AWS Database Blog, 2022)](https://aws.amazon.com/blogs/database/model-driven-graphs-using-owl-in-amazon-neptune)
- [Use semantic reasoning to infer new facts from your RDF graph by integrating RDFox with Amazon Neptune (AWS Database Blog)](https://aws.amazon.com/blogs/database/use-semantic-reasoning-to-infer-new-facts-from-your-rdf-graph-by-integrating-rdfox-with-amazon-neptune)
- [Amazon Neptune customers](https://aws.amazon.com/neptune/customers/)
- [Merck case study (AWS)](https://aws.amazon.com/solutions/case-studies/merck/)
- [Siemens Energy + metaphactory on Neptune (AWS case study)](https://aws.amazon.com/solutions/case-studies/Siemens-Energy-metaphacts-AWSMarketplace-case-study)
- [How NXP performs event-driven RDF imports to Amazon Neptune (AWS Database Blog)](https://aws.amazon.com/blogs/database/how-nxp-performs-event-driven-rdf-imports-to-amazon-neptune-using-aws-lambda-and-sparql-update-load)
- [Company-wise memory in Amazon Bedrock with Amazon Neptune and Mem0 (AWS ML Blog, Apr 2026)](https://aws.amazon.com/blogs/machine-learning/company-wise-memory-in-amazon-bedrock-with-amazon-neptune-and-mem0/)
- [COSMO: A large-scale e-commerce common sense knowledge generation and serving system at Amazon (Amazon Science, SIGMOD 2024)](https://www.amazon.science/publications/cosmo-a-large-scale-e-commerce-common-sense-knowledge-generation-and-serving-system-at-amazon)
- [Building commonsense knowledge graphs to aid product recommendation (Amazon Science blog)](https://amazon.science/blog/building-commonsense-knowledge-graphs-to-aid-product-recommendation)

---

# Part B: Other companies and third-party views (not AWS)

Nothing in this part is confirmed by AWS. Company-authored papers are the strongest evidence
here. Vendor and analyst material is labelled as such.

## B1. Large organisations' own publications

| Organisation | What | Graph tech | Evidence quality | Key fact |
|---|---|---|---|---|
| **LinkedIn** | KG-augmented RAG for customer-service Q&A, built from historical tickets (intra-ticket structure + inter-ticket links) | Own KG (DB not the focus) | **Peer-reviewed** (SIGIR 2024, LinkedIn authors) | Deployed ~6 months in LinkedIn's support team; **median per-issue resolution time −28.6%**; offline retrieval MRR +77.6% |
| **AstraZeneca** | Biological Insights Knowledge Graph (BIKG): 50+ public and internal sources, used for target identification and ML | Own pipeline (Spark, PyTorch, Azure ML) | Company papers and talks | Production pipeline; cross-graph queries with a Competitive Intelligence KG. No independent impact numbers |
| **Goldman Sachs** | **Legend** / PURE: model-driven data platform, open-sourced via FINOS (2020); used to extend ISDA's Common Domain Model | Logical modelling language, not OWL | Linux Foundation / FINOS announcements | Shows a large bank investing in a *semantic model of its data*, outside the RDF stack |
| **Klarna** | "Kiki" internal assistant over a company knowledge graph, LLM on top, used via Slack | **Neo4j** (property graph) | **Vendor story** + CEO interviews | 250k+ questions (~2,000/day) since Jun 2023; adoption figures vary by source (85–90%) |

## B2. Banking and financial services

- **FIBO** (EDM Council's Financial Industry Business Ontology, OWL) is the standard starting
  vocabulary for bank ontologies. A Jul 2026 Neo4j blog puts the production release at
  ~2,446 classes and advises **reusing a curated subset**, not the whole ontology (single source).
- **Morgan Stanley**: consultant case study (Semantic Arts) describes a core ontology plus a domain
  model and adoption of an RDF knowledge base; Stardog markets a credit/operational-risk KG
  use case. **Consultant/vendor material**, no architecture or results disclosed.
- **JPMorgan**: a 2022 Knowledge Graph Forum talk on an in-house KG. Technology not stated.
- **Dow Jones Risk & Compliance**: Oxford Semantic Technologies announced its **RDFox**
  reasoner would enhance Dow Jones products including Risk & Compliance. **No source ties
  Dow Jones to Neptune**, so don't cite it as a Neptune example.
- **Freedom Mortgage on Palantir AIP/Ontology**: a third-party write-up describes compliance,
  document and customer-interaction applications launched in ~90 days. No primary metrics.
- **Not found:** no public production case study of an ontology-driven agent at Wells Fargo,
  HSBC, UBS, Deutsche Bank or Citi. An Oct 2026 Futurum analyst report mentions *"a leading
  bank"* deploying an ontology-based semantic layer across enterprise agents, unnamed.
  **MUFG (Part A) remains the best-documented bank example.**

## B3. Platform vendors' semantic layers for agents (2026)

| Vendor | Product | Model | Agent access | Status notes |
|---|---|---|---|---|
| Microsoft | **Fabric IQ** (ontology + graph + data agents) | Business ontology | Ontology reportedly exposed via **MCP** to any vendor's agents | Fabric IQ announced GA at Build 2026; the **ontology item still labelled preview** in Oct 2026 per Atlan / Towards AI |
| Palantir | **Ontology + AIP** (AIP Logic, Chatbot Studio, Evals) | Proprietary object/action ontology | Agents read and write through permissioned actions with audit | Palantir docs; no named bank verified |
| Snowflake | Semantic Views → Cortex Agents | Metric / BI semantic layer | Cortex Agents | Third-party reports: SQL GA Mar 2026 |
| Databricks | Metric Views / Unity Catalog Business Semantics → Genie | Metric / BI semantic layer | Genie, MCP | Third-party reports: GA Apr 2026 |
| dbt Labs | dbt Semantic Layer (MetricFlow) | Metric / BI semantic layer | dbt MCP server | Portable across warehouses |
| Neo4j | Context Engine (Oct 2026), Aura Agent | Property graph | MCP | Vendor launch |
| Graphwise (Ontotext + PoolParty), Stardog, metaphacts, RDFox | RDF/OWL platforms | RDF/OWL/SHACL | Varies | metaphactory and PoolParty both have AWS/Neptune integrations |

**Healthdirect Australia** is often cited as an RDF success story. Its health thesaurus and
knowledge graph are built on PoolParty/Graphwise with a SPARQL endpoint. **No source found ties
it to Neptune.**

## B4. Recurring third-party themes

- **"The graph is for retrieval, the ontology is for meaning."** Most sources agree enterprise
  agents need both, plus a metric layer for numbers.
- **Unresolved semantics get amplified.** If "counterparty" means different things in different
  systems, a knowledge graph built on top inherits and spreads the inconsistency.
  Reconcile definitions before loading data.
- **Vendor benchmark (unverified):** one comparison reports that adding three dbt models lifted
  text-to-SQL accuracy from 64.5% to 90.0% without a semantic layer. Treat as a hint that *data
  modelling itself* is a large part of the gain.
- Celent (banking edition) argues that agent explainability in banks needs **structured knowledge,
  shared ontologies and machine-readable regulation** rather than ever-larger document stores.

## B5. Videos from other channels (2026)

Upload dates come from YouTube page metadata (checked 17 Nov 2026), or the conference date for
KGC. The videos have not been reviewed in full. Vendor channels are marked.

**Banking and FIBO**

| Date | Video | Channel | Length |
|---|---|---|---|
| 2026-05-04 | [From data to meaning: educating AI in banking with ontologies](https://www.youtube.com/watch?v=sYnhqC9Kd3s) | Capco (consultancy) | 27 min |
| 2026-05-06 | [Mike Bennett: The FIBO Journey, an Ontology for Financial Interoperability](https://www.youtube.com/watch?v=qmCrMe9gsck) | Ontology Summit | 61 min |
| May 2026 | [Ontology as a Semantic Layer for Agentic AI Applications](https://watch.knowledgegraph.tech/videos/ontology-as-a-semantic-layer-for-agentic-ai-applications) (KGC 2026 workshop, **paid**): relational schema → OWL, SHACL rules, Bedrock NL→SPARQL, Ontop, Neptune, agent tools | Knowledge Graph Conference | 90 min |
| 2026-02-23 | [FDIC 2026 Data Summit: Exploring FIBO Ownership Graphs](https://www.youtube.com/watch?v=WSvLWFA9phA) | Tom Sawyer Software (vendor) | 4 min |
| 2026-07-23 | [Ontology Driven Agent for Banking Sector](https://www.youtube.com/watch?v=7rqZkYQgSzo) | Synoptix AI (vendor) | 6 min |
| 2026-11-06 | [Data Ontology Explained: Banking Examples & Enterprise AI Agents](https://www.youtube.com/watch?v=toQMCBBPENo) | The Data & AI Hub | 14 min |

**Concepts and architecture talks**

| Date | Video | Channel | Length |
|---|---|---|---|
| 2026-07-22 | [Why Agentic Systems Need Ontologies (Frank Coyle, UC Berkeley)](https://www.youtube.com/watch?v=Sir59K8ZDPU) | AI Engineer | 21 min |
| 2026-07-22 | [Thinner Agents on a Smarter Substrate: The Ontology-based Semantic Layer (Emil Eifrem, Neo4j)](https://www.youtube.com/watch?v=VGN22pPpb-8) | AI Engineer (vendor speaker) | 11 min |
| 2026-05-28 | [Context Graphs for Explainable, Decision-Aware AI Agents (Neo4j)](https://www.youtube.com/watch?v=abvQEhvRI_c) | AI Engineer (vendor speakers) | 17 min |
| 2026-08-02 | [Dougal Watt: Human-Guided, LLM-Assisted Ontology Modeling](https://www.youtube.com/watch?v=YiskiLFCo-Y) | Knowledge Graph Insights podcast | 33 min |
| 2026-06-12 | [Context is King #5: Ontologies as Executable Context for AI Agents](https://www.youtube.com/watch?v=yABA1YQDH2I) | Aiven (vendor) | 22 min |
| 2026-09-23 | [Semantic Layer vs Ontology: Why Enterprise AI Agents Need Both](https://www.youtube.com/watch?v=nVjGhTpg-Jg) | Kanerika (consultancy) | — |
| 2026-04-10 | [Ontology vs Semantic Layer: What's the Difference?](https://www.youtube.com/watch?v=_hCYSPcMgOk) | Atlan (vendor) | 21 min |

**Hands-on with Neptune / AWS (community)**

| Date | Video | Channel | Length |
|---|---|---|---|
| 2026-11-03 | [Context Ontology Accelerator by AWS, as I understand it](https://www.youtube.com/watch?v=vW82N1Jrt7o) | Martin Ristov (individual) | 36 min |
| 2026-08-02 | [Knowledge Graph Full Hands-On Course: GraphRAG using Amazon Bedrock & Neptune](https://www.youtube.com/watch?v=l4Ebh4_UBLw) | AaiTech | 77 min |
| 2026-06-19 | [AWS Summit New York 2026: Key Takeaways on Agents and Context (Holger Mueller)](https://www.youtube.com/watch?v=nLp-2cBscvk) | Constellation Research (analyst) | 6 min |

**Other platforms' semantic layers (for comparison)**

| Date | Video | Channel | Length |
|---|---|---|---|
| 2026-09-01 | [Agentic AI on Databricks with an Ontology-Driven Semantic Layer](https://www.youtube.com/watch?v=OKmQOOQLl3o) | Databricks Events | 23 min |
| 2026-06-24 | [Is Ontology REPLACING the Semantic Model?](https://www.youtube.com/watch?v=y1iw0tf4lzY) (Microsoft Fabric IQ) | Guy in a Cube | 5 min |

## Third-party sources

- [Retrieval-Augmented Generation with Knowledge Graphs for Customer Service Question Answering (LinkedIn, SIGIR 2024, arXiv 2404.17723)](https://arxiv.org/abs/2404.17723v1)
- [AstraZeneca BIKG (bioRxiv 2021)](https://www.biorxiv.org/content/10.1101/2021.10.28.466262v1.full.pdf)
- [Goldman Sachs open sources its data modeling platform through FINOS (Linux Foundation)](https://www.linuxfoundation.org/press/press-release/goldman-sachs-open-sources-its-data-modeling-platform-through-finos)
- [Klarna customer story (Neo4j, vendor)](https://neo4j.com/customer-stories/klarna/)
- [The Ontologies You Shouldn't Build Yourself (Neo4j blog, FIBO size)](https://medium.com/neo4j/the-ontologies-you-shouldnt-build-yourself-a-field-guide-for-knowledge-graph-builders-7088dab7c37c)
- [Morgan Stanley case study (Semantic Arts, consultant)](https://www.semanticarts.com/morgan-stanley-case-study/)
- [Stardog: Financial Services (vendor)](https://www.stardog.com/industries/financial-services/)
- [Dow Jones enhances product line with semantic innovation (Oxford Semantic, vendor)](https://oxfordsemantic.tech/blog/dow-jones-enhances-product-line-with-semantic-innovation)
- [Palantir AIP overview (Palantir docs)](https://www.palantir.com/docs/foundry/aip)
- [Freedom Mortgage / Palantir write-up (third-party)](https://www.besthub.dev/articles/how-palantir-turns-enterprise-ai-into-actionable-business-intelligence-1d21f66a1dec)
- [Futurum: Solving the Agentic Context Dilemma (analyst, Oct 2026)](https://futurumgroup.com/wp-content/uploads/2026/10/Solving-the-Agentic-Context-Dilemma-Inside-Neo4js-Strategy-to-Build-an-Operational-World-Model.pdf)
- [VentureBeat: Enterprise AI agents keep operating from different versions of reality (Fabric IQ)](https://venturebeat.com/data/enterprise-ai-agents-keep-operating-from-different-versions-of-reality)
- [Atlan: What is Fabric IQ (vendor)](https://atlan.com/know/microsoft-fabric/what-is-fabric-iq/)
- [dbt: Bring structured context to Snowflake Intelligence with dbt](https://www.getdbt.com/blog/bring-structured-context-to-snowflake-intelligence-with-dbt)
- [Knowi: Semantic layer tools (vendor roundup)](https://www.knowi.com/blog/semantic-layer-tools/)
- [Healthdirect: Australian Health Thesaurus](https://about.healthdirect.gov.au/australian-health-thesaurus)
- [Celent: Knowledge Management in Agentic Systems, Banking Edition](https://www.celent.com/en/insights/knowledge-management-in-agentic-systems-standards-banking-edition)
- [Atlan: Ontology vs Knowledge Graph (vendor)](https://atlan.com/know/ai-agent/knowledge-graph/ontology-vs-knowledge-graph/)
