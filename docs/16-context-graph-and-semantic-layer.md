# Context Graphs, Ontologies, and the Semantic Context Layer (Neptune, AWS Context, GraphRAG)

**How this doc is organised:** **Part A uses AWS sources only**: AWS documentation, AWS
announcements, AWS blogs, the AWS-maintained `awslabs/mcp` repo, and AWS-staff posts on AWS
Builder Center (labelled as such, since those are not official docs). **Part B collects
third-party analysis and vendor opinion**, kept separate so it is never mistaken for AWS's
position. Researched Nov 2026.

---

# Part A: From AWS

## Terminology used in this doc

| Term | Meaning |
|---|---|
| **Knowledge graph** | Data stored as entities (nodes) and relationships (edges) |
| **Ontology** | The formal vocabulary and rules of a domain (classes, properties, constraints, inference rules), expressed in W3C standards such as RDF, OWL, SHACL |
| **Semantic layer** | A mapping from business terms to the physical data, so people and agents can ask questions in business language |
| **GraphRAG** | Retrieval that, after vector search, follows graph links to pull in related content for multi-hop questions |
| **Context graph / context layer** | Industry term for a graph of data assets, business definitions, rules and usage that agents query at runtime. AWS's product in this space is **AWS Context** |

## What AWS offers (four distinct things)

### 1. Amazon Neptune: the graph database

| | Neptune Database | Neptune Analytics |
|---|---|---|
| Role (AWS docs) | Serverless graph database for workloads up to 100,000 queries/sec, Multi-AZ, multi-Region | Memory-optimised analytics engine: graph algorithms, low-latency queries, **vector search within graph traversals** |
| Query languages | Gremlin, openCypher, SPARQL (RDF) | openCypher |
| Typical use | Social, fraud alerting, Customer 360 | Data-science/exploratory analysis; the engine behind Bedrock GraphRAG |

Data can be loaded from a Neptune Database graph or snapshot, or from S3, into Neptune Analytics.

**Agent access: Amazon Neptune MCP Server** (announced May 2025, open source in `awslabs/mcp`):
fetches status and schema, and runs openCypher and Gremlin against Neptune Database and
openCypher against Neptune Analytics. AWS's README warns the server **will run any query sent to
it, including mutating ones**, so scope its IAM permissions to read-only where possible. AWS
also lists a separate **Neptune MCP Memory Server** that stores agent memory as a knowledge graph.

**Pattern with AgentCore** (AWS Industries blog, May 31 2026, wealth-management reference):
*"The Neptune Model Context Protocol (MCP) server registers with the Amazon Bedrock AgentCore
Gateway."* A graph agent converts natural language into openCypher, validates the syntax and
logic of the query, then runs it against Neptune Analytics. For complex analysis it adds Neptune
Analytics' built-in algorithms (centrality, similarity, clustering). The MCP server "owns the
Neptune connection and query execution," so other agents can reuse it.

### 2. Bedrock Knowledge Bases GraphRAG: managed, no ontology needed

AWS: *"Amazon Bedrock Knowledge Bases offers a fully managed GraphRAG feature with Amazon
Neptune."* It automatically identifies relationships between entities and structural elements
in ingested documents. At query time: vector search → retrieve linked graph nodes → traverse the
graph → answer with the enriched context.

Limits (AWS devguide):
- **"Configuration options to customize the graph build are not supported"**, so you cannot
  impose your own ontology/schema
- **S3 is the only data source**
- 1,000 files per data source (can request up to 10,000)
- No autoscaling for the Neptune Analytics graph
- You pick a foundation model for graph construction
- Regions: N. Virginia, Oregon, Frankfurt, London, Ireland, Tokyo, Singapore
- Deleting the knowledge base does **not** delete the Neptune Analytics graph, which keeps
  incurring charges until you delete it

**Best for:** document-heavy Q&A where answers span several documents. It extracts *a* graph
from your documents. It does not model *your* domain.

### 3. AWS Context: AWS's managed context-graph service (announced Jun 17 2026, not yet GA)

Announced at AWS Summit New York alongside AgentCore Harness GA. AWS's wording: *"AWS Context
is a new service that automatically builds a knowledge graph from your existing data that can be
used by your agents."*

From the AWS announcement:
- Infers relationships among data assets, business rules and domain knowledge.
- Described as "an agentic search layer for an organization's data," built on the same knowledge
  graph technology as **Amazon Quick**.
- Metadata stored in **Apache Iceberg format in S3 Tables**.
- *"Built-in governance to ensure agents can only access the information they're supposed to
  access."*
- Learns which sources give correct results and improves as agents use it.
- Integrates with the newly announced **Amazon Bedrock Managed Knowledge Base** (managed RAG
  with S3, SharePoint, Confluence and Google Drive connectors).

From an AWS-staff post on AWS Builder Center (Jun 21 2026, not official docs):
- Draws on **AWS Glue Data Catalog** (business descriptions, glossary terms, skill assets),
  **SageMaker Unified Studio** and **Lake Formation**.
- *"Every query inherits the calling user's IAM and Lake Formation permissions."*
- Agents reach it through agentic search APIs and **MCP tools**, from agents on **AgentCore, EKS,
  or any MCP-compatible framework**. That means a LangGraph agent can use it as well.
- The graph holds structural metadata, business context added by data stewards, and behaviour
  patterns learned from agent usage.
- Explicitly says AWS Context is not yet generally available.

**Not published by AWS as of Nov 2026:** GA date, pricing, regions, or what database it runs on.
**AWS has not said AWS Context runs on Neptune.** The accurate framing for stakeholders is:
*"AWS announced a separate managed context-graph service, AWS Context. Neptune remains the graph
database AWS uses in its graph and ontology reference architectures."*

### 4. AWS Prescriptive Guidance: ontology-driven semantic layer

*"Semantic Layer for Agentic AI using Ontology, Symbolic Reasoning, and Virtual Knowledge
Graph"* (Don Simpson, Taylor Riggan, Chun Schiros, AWS). This is AWS's blueprint for formal
ontologies with agents, aimed at regulated industries needing auditable answers. Goal: **ACE**,
which stands for **Accuracy, Consistency, Explainability**.

**How the ontology is worked on in this design:**
1. **Ontology induction**: the ontology is generated automatically from data catalogs (AWS Glue
   Data Catalog, SageMaker Catalog), with **human-in-the-loop workflows for semantic governance**.
2. **W3C standards**: RDF/RDFS/OWL for classes and relationships, **SHACL** for constraints,
   **SWRL** for rules, **SPARQL** for queries, **R2RML** for mapping ontology terms to database
   tables.
3. **Virtual knowledge graph** via **ontology-based data access (OBDA)** using open-source
   **Ontop**. Existing data sources are queried in place, *"without requiring upfront data
   migration, materializing only what requires reasoning or cross-domain integration."*
4. **Symbolic reasoning**: OWL reasoners (**ELK, HermiT**) and SHACL validators provide
   *"continuous knowledge graph validation through automated reasoning."* Reasoning runs in these
   external components, not inside Neptune.
5. **Neurosymbolic approach**: deterministic symbolic reasoning combined with probabilistic LLM
   capabilities.
6. Unstructured documents are processed with unstructured.io and stored in OpenSearch for vector
   and semantic search.

**Architecture:** Data → Knowledge → Intelligence → Orchestration layers, exposed through **MCP
and A2A**. MCP tools: `intent_classification`, `generate_queries`, `execute_queries`,
`graphrag_search`, `reasoning`, plus a top-level `ask` tool and a pre-built Q&A agent. You can
adopt the whole agent, call individual tools from your own agent, or build a custom agent on the
interfaces. Services: Neptune, Bedrock + AgentCore, ECS, Glue Data Catalog, SageMaker Catalog,
OpenSearch. A sample attachment (`attachment.zip`) is downloadable from the guide.

## Choosing between them

| Need | Pick | Effort |
|---|---|---|
| Multi-hop Q&A over documents | **Bedrock KB GraphRAG** | Low (managed) |
| Agent queries an existing graph / relationship data | **Neptune + Neptune MCP Server behind AgentCore Gateway** | Medium |
| Agents must understand lakehouse data (which table, which join, who may see it) | **AWS Context** once GA; Glue Data Catalog business context meanwhile | Low–medium, not GA |
| Regulated domain, explainable/auditable answers, shared business definitions across agents | **Prescriptive Guidance ontology semantic layer** | High (needs ontology/knowledge-engineering skills) |

## Implications for the LangGraph → AgentCore decision

- **None of these requires Harness or a rewrite.** Each is reached as a tool: MCP via Gateway, or
  the Bedrock KB retrieve API. A LangGraph agent on Runtime (or self-hosted) can use all of them,
  which supports the hybrid recommendation in [README.md](./README.md).
- **Gateway is the integration point.** Register the Neptune MCP server, or the semantic layer's
  MCP tools, as Gateway targets: tools can be added without redeploying the agent, and Policy can
  control which agents call them. See [07-gateway-identity-memory.md](./07-gateway-identity-memory.md)
  and [11-guardrails.md](./11-guardrails.md).
- **AgentCore Memory is not a context graph.** Memory holds conversation and user state for an
  agent. A context graph holds shared organisational knowledge across agents. They complement
  each other.
- **Don't plan production on AWS Context yet.** No GA date, pricing or regions as of Nov 2026.
  Re-check after re:Invent (early Dec 2026).
- **Ontology work is a people cost, not just a service cost.** The formal path needs someone who
  can model and govern a domain in OWL/SHACL. Starting with GraphRAG or catalog-driven context
  and moving up later is a lower-risk path.
- **Suggested POC add-on** (see [13-poc-plan.md](./13-poc-plan.md)): load 20–50 real internal
  documents into a GraphRAG knowledge base, expose retrieval to the LangGraph agent as a tool via
  Gateway, and compare multi-hop answer accuracy against plain vector RAG using AgentCore
  Evaluations' groundedness evaluator ([12-evaluations.md](./12-evaluations.md)).

## AWS sources

- [AWS Summit New York 2026: New ways to make AI agents more effective at work](https://www.aboutamazon.com/news/aws/aws-summit-nyc-2026-ai-agents)
- [Build a knowledge base with Amazon Neptune Analytics graphs (Bedrock user guide)](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-graphs.html)
- [What is Neptune Analytics?](https://docs.aws.amazon.com/neptune-analytics/latest/userguide/what-is-neptune-analytics.html)
- [When to use Neptune Analytics and when to use Neptune Database](https://docs.aws.amazon.com/neptune-analytics/latest/userguide/neptune-analytics-vs-neptune-database.html)
- [Amazon Neptune announces MCP Server (What's New, May 2025)](https://aws.amazon.com/about-aws/whats-new/2025/05/amazon-neptune-mcp-server/)
- [Amazon Neptune MCP Server (awslabs/mcp)](https://awslabs.github.io/mcp/servers/amazon-neptune-mcp-server)
- [Semantic Layer for Agentic AI using Ontology, Symbolic Reasoning, and Virtual Knowledge Graph (AWS Prescriptive Guidance)](https://docs.aws.amazon.com/prescriptive-guidance/latest/semantic-layer-agentic-ai-ontology-reasoning-virtual-knowledge-graph/semantic-layer-agentic-ai-ontology-reasoning-virtual-knowledge-graph.html)
- [Building an Intelligent Wealth Management Platform, Part 1 (AWS Industries blog)](https://aws.amazon.com/blogs/industries/the-art-of-the-possible-building-an-intelligent-wealth-management-platform-part-1/)
- [How AWS Context Fixes That with Knowledge Graphs (AWS Builder Center, AWS-staff post)](https://builder.aws.com/content/3FSAU66iuOrNTFGCgBSqlX4ab0u/your-ai-agents-are-making-decisions-without-context-how-aws-context-fixes-that-with-knowledge-graphs)

---

# Part B: Third-party views (not AWS; treat as analysis or opinion)

Nothing in this part is confirmed by AWS. Use it for context and questions to ask AWS, not as
facts to present.

## On AWS Context

- **Steward review before production** (Caylent): inferred relationships are reviewed by data
  stewards in a console and "promoted" to production. Caylent warns *"a popular-but-wrong join
  path can reinforce itself unless curation catches it"*, so usage-based learning does not
  guarantee correctness.
- **Lock-in nuance** (Caylent): the Iceberg metadata is portable, but the inference, search and
  learning behaviour can't be reproduced outside AWS.
- **Not a chatbot** (Caylent): unlike Amazon Quick, it exposes organisational context to agents
  you build. It isn't an end-user Q&A product.
- **Companion launches** (VentureBeat, Caylent): S3 Annotations reported as generally available;
  Glue Data Catalog skill assets / semantic search reported in preview (us-east-1, us-east-2,
  us-west-2, eu-west-1).
- **Analyst view** (Holger Mueller, Constellation Research, via VentureBeat): *"every agentic
  platform vendor needs a context capability"*; main risk *"is going to be performance,
  especially for transactional data."*
- **Neptune link is unconfirmed:** some posts associate AWS Context with Neptune. They are
  describing a separate open-source "Context Ontology Accelerator" or an internal AWS system, not
  the managed service.

## On Neptune vs a "context layer" (Atlan, a vendor that sells one)

- Neither Neptune edition includes a built-in ontology reasoner, so inference must run externally
  or be pre-computed. This is consistent with AWS's Prescriptive Guidance using external
  ELK/HermiT reasoners.
- Atlan argues Neptune and its MCP server "store and traverse" but don't carry business meaning,
  ownership, lineage or policy, which a context layer adds. **Vendor positioning.**
- Atlan says GraphRAG suits a single, well-scoped agent but teams outgrow it when many agents or
  business units need the same governed graph. **Vendor opinion, no data given.**

## Industry landscape (2026)

- Competing context/semantic products: Snowflake Horizon Context and Cortex Sense, Microsoft
  Fabric IQ (ontology-based), Neo4j Context Engine (Oct 2026), Redis context platform, Pinecone
  Nexus (VentureBeat, Neo4j).
- Gartner reportedly listed Semantic Layers and GraphRAG among its 2026 top data & analytics
  trends; Forrester (Jun 2026) argued context is "the missing layer in AI-ready data." Both are
  second-hand reports and the originals weren't checked.
- Rule of thumb common across sources: **the graph is for retrieval, the ontology is for meaning**,
  and enterprise agents usually need both.

## Third-party sources

- [Caylent: AWS Context, AWS's Automated Knowledge Graph for AI Agents](https://caylent.com/blog/aws-context-aws-automated-knowledge-graph-for-ai-agents)
- [VentureBeat: AWS enters the context layer race](https://venturebeat.com/data/aws-enters-the-context-layer-race-with-a-graph-that-learns-from-agents-not-manual-curation)
- [Atlan: Amazon Neptune vs a Knowledge Graph Context Layer (vendor)](https://atlan.com/know/ai-agent/knowledge-graph/amazon-neptune-vs-knowledge-graph-context-layer/)
- [Atlan: Context Graph vs Ontology (vendor)](https://atlan.com/know/context-graph-vs-ontology/)
- [Forrester via Strategy: Context Is the Missing Layer in AI-Ready Data](https://software.strategy.com/research-and-reports/combine-semantics-ontology-and-knowledge-graphs-for-ai-ready-data)
- [Neo4j Context Engine launch](https://neo4j.com/?p=433599)
