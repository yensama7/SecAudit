# Security Audit Intelligence System — Implementation Plan

## 1. Project objective

Build a terminal-first security auditing system that runs inside **Claude Code**.

When a user opens a repository in Claude Code and starts the security audit, the system must automatically execute two stages in sequence:

1. **Security Auditor:** inspect the repository, identify and investigate potential vulnerabilities, and produce a structured set of findings.
2. **Audit Intelligence:** automatically take the auditor's findings, search historical audit reports for related vulnerability patterns, investigate relevant matches against the repository, and produce a final evidence-backed judgement.

The user should not have to manually invoke Audit Intelligence or copy findings between stages.

The two stages must remain separate in responsibility:

- The **audit methodology** defines how Claude examines code.
- The **knowledge base** stores historical audit reports and findings.
- The **orchestrator** controls the sequence and passes structured results from one stage to the next.

The system must remain usable from the Claude Code terminal. A web dashboard is not required for the first version.

---

## 2. Core workflow: automatic handoff

The central requirement is a deterministic, automatic transition from Security Auditor to Audit Intelligence.

```text
User opens a repository in Claude Code
                  |
                  v
       Start Security Audit
                  |
                  v
       Repository discovery
                  |
                  v
       Security Auditor
                  |
                  v
       Full source-file coverage check
                  |
                  v
       Vulnerability investigation
                  |
                  v
       Structured auditor findings
                  |
                  v
       Save audit handoff artifact
                  |
                  v
       AUTOMATIC HANDOFF
                  |
                  v
       Audit Intelligence
                  |
                  v
       Retrieve similar historical findings
                  |
                  v
       Compare and investigate against code
                  |
                  v
       Verify, reject or qualify matches
                  |
                  v
       Final ranked security report
```

### Handoff requirements

The orchestrator must:

1. Start both stages from one user-facing command or skill invocation.
2. Run Security Auditor first.
3. Wait for Security Auditor to finish and validate its output.
4. Save the auditor's findings and repository coverage information to a machine-readable handoff file.
5. Automatically invoke Audit Intelligence using that handoff file.
6. Pass the repository context and exact file/line references needed for investigation.
7. Wait for Audit Intelligence to finish.
8. Combine the results into one final report, preserving which findings came from direct code analysis and which were informed by historical audit intelligence.

Audit Intelligence must not run against an incomplete or invalid handoff artifact. If the auditor stage fails, the orchestrator must report the failure rather than silently skipping ahead.

**Important implementation constraint:** Do not depend on Claude merely remembering to switch stages. Encode the sequence in the parent orchestration skill and use scripts/state files to validate stage completion. The parent skill should explicitly direct Claude to call the Audit Intelligence tools after the auditor output is validated.

---

## 3. Claude Code architecture

Use Claude Code as the terminal interface and reasoning environment.

### Proposed structure

```text
security-audit-system/
|
|-- .claude/
|   |-- skills/
|       |-- security-audit/
|       |   |-- SKILL.md
|       |   |-- methodology/
|       |   |   |-- audit-lifecycle.md
|       |   |   |-- severity-model.md
|       |   |   |-- evidence-requirements.md
|       |   |   |-- false-positive-verification.md
|       |   |-- languages/
|       |   |   |-- solidity/
|       |   |   |   |-- taxonomy.md
|       |   |   |   |-- audit-checklist.md
|       |   |   |   |-- vulnerability-patterns.md
|       |   |   |-- rust/
|       |   |       |-- taxonomy.md
|       |   |       |-- audit-checklist.md
|       |   |       |-- vulnerability-patterns.md
|       |   |-- workflows/
|       |   |   |-- repository-discovery.md
|       |   |   |-- full-source-coverage.md
|       |   |   |-- vulnerability-hunting.md
|       |   |   |-- intelligence-handoff.md
|       |   |   |-- finding-verification.md
|       |   |-- templates/
|       |       |-- findings.schema.json
|       |       |-- final-report.md
|
|-- intelligence-engine/
|   |-- api/
|   |-- ingestion/
|   |-- retrieval/
|   |-- mcp/
|   |-- database/
|   |-- tests/
|
|-- scripts/
|   |-- discover_sources.py
|   |-- validate_coverage.py
|   |-- validate_handoff.py
|   |-- build_final_report.py
|
|-- config/
|   |-- sources.yaml
|   |-- languages.yaml
|
|-- storage/
|   |-- reports/
|
|-- PLAN.md
```

The exact folder layout can change during implementation, but keep the methodology, intelligence service and orchestration responsibilities distinct.

### Trail of Bits foundation

Review and selectively reuse relevant skills from:

- https://github.com/trailofbits/skills

Investigate relevant skills such as audit context building, entry-point analysis, variant analysis, false-positive checking, Rust review and static analysis.

Do not blindly copy every skill. Select the ones that fit the intended workflow, document adaptations, preserve attribution and comply with the repository's licence. Keep upstream-derived skills identifiable so they can be updated independently.

---

## 4. Security Auditor stage

### 4.1 Repository discovery

When invoked in a repository, the auditor must:

- Identify the repository root and project type.
- Identify the target language or languages.
- Discover every in-scope source file, including `.sol` or `.rs` files as applicable.
- Identify imports, modules, interfaces, libraries, dependencies and generated/vendor code.
- Map important cross-file relationships and call paths.
- Identify entry points, privileged operations, trust boundaries and state-changing functions.
- Record exclusions and the reason for each exclusion.

Do not silently exclude a source file because it is large, unfamiliar or difficult to analyse. If a file cannot be examined, record it as incomplete and explain why.

### 4.2 Full source-file coverage

The auditor must inspect every relevant in-scope source file.

Use a coverage ledger containing at least:

- File path
- Language
- Discovered status
- Examination status
- Cross-reference status
- Exclusion status and reason, if applicable
- Notes or unresolved questions

The audit cannot be marked complete while any in-scope file remains unexamined.

For large repositories, use staged file analysis, AST-assisted discovery, summaries and cross-file tracing. Do not attempt to place the entire repository into one context window. The requirement is complete, recorded examination, not one giant prompt.

### 4.3 Language-specific methodology

Maintain separate taxonomies and checklists.

**Solidity / EVM examples:**

- Access control and authorization
- Reentrancy and external-call ordering
- Arithmetic, precision and rounding
- Oracle and price manipulation
- Accounting and balance inconsistencies
- Signature verification and replay protection
- Initialization and upgradeability
- Denial of service and gas-related logic
- Incorrect assumptions about token behaviour
- State-transition and invariant violations

**Rust examples:**

- Unsafe code and FFI boundaries
- Input validation and deserialization
- Authorization and trust boundaries
- Error handling and panic behaviour
- Concurrency and shared-state assumptions
- Resource exhaustion and denial of service
- Integer handling and conversions
- Dependency and feature configuration
- Solana-specific account ownership, signer, writable and PDA validation where relevant

These are investigation categories, not automatic vulnerability verdicts. The auditor must reason about the actual program, its assumptions and reachable execution paths.

### 4.4 Finding requirements

Every proposed finding should contain:

- Unique finding ID
- Title
- Severity: Critical, High, Moderate or Low
- Confidence, separately from severity
- Affected files and exact line ranges
- Relevant functions and cross-file relationships
- Root cause
- Preconditions and reachability
- Concrete impact
- Evidence from the current repository
- Recommended remediation
- Verification status

Return up to the 20 strongest distinct, substantiated findings. Do not invent findings to reach 20. If fewer than 20 can be supported, return fewer.

---

## 5. Automatic handoff contract

The Security Auditor must write a structured artifact when it completes.

Suggested per-audit output:

```text
.security-audit/
|-- run.json
|-- source-inventory.json
|-- coverage.json
|-- auditor-findings.json
|-- intelligence-results.json
|-- final-report.md
```

The `auditor-findings.json` file is the handoff contract between the two stages.

It should include:

- Audit run ID
- Repository identity and commit hash, when available
- Target languages and frameworks
- In-scope file inventory
- Coverage status and exclusions
- Findings and their evidence
- Unresolved questions
- Relevant functions, symbols and file references

Before handoff, a validator must check that:

- The JSON conforms to its schema.
- Every finding has evidence and a location.
- Severity and confidence use allowed values.
- Coverage is complete or explicitly marked incomplete.
- The repository revision is recorded where possible.

The orchestrator then automatically starts the Audit Intelligence stage.

If coverage is incomplete, the system must clearly mark the audit incomplete. It may perform intelligence analysis on the available findings, but it must not present the overall audit as complete.

---

## 6. Audit Intelligence stage

Audit Intelligence is an independent knowledge and retrieval service. It does not replace the Security Auditor or independently declare a vulnerability based only on similarity.

Its job is to retrieve relevant historical findings and help Claude investigate whether similar weaknesses exist in the current repository.

### 6.1 Sources

Initial sources to evaluate:

- Cyfrin
- Trail of Bits
- OpenZeppelin
- Sherlock
- Code4rena

Use public reports and repositories where access and reuse terms permit. Preserve source URLs, report identifiers, original severity and licence/reuse information. Do not assume that public availability grants permission to redistribute every report.

### 6.2 Ingestion pipeline

```text
Approved source repositories and publications
                  |
                  v
         Collect new or changed reports
                  |
                  v
        Preserve original documents
                  |
                  v
          Extract report content
                  |
                  v
       Identify individual findings
                  |
                  v
       Normalize structured metadata
                  |
                  v
       Validate and deduplicate records
                  |
                  v
          Generate embeddings
                  |
                  v
          Update search indexes
```

Ingestion should be incremental. Track source revisions, report hashes and ingestion status so unchanged reports are not repeatedly processed.

### 6.3 Finding-level storage

Do not store an entire report as one vector and expect precise retrieval.

Preserve the original report, but extract and index each individual finding separately.

Each finding should retain:

- Source and report identity
- Original finding title and text
- Original severity and normalized severity
- Language and ecosystem
- Vulnerability category
- Root cause
- Vulnerability pattern
- Preconditions
- Impact
- Remediation
- Affected functions or code snippets, when available
- Original report URL and location
- Extraction and validation status
- Content hash and embedding model/version

Store the original text alongside any AI-generated summary. Generated summaries must never replace source evidence.

### 6.4 Recommended database architecture

Use three storage layers:

**Object storage — MinIO or S3**

Store original PDFs, Markdown, JSON and other permitted source documents.

**PostgreSQL**

Store sources, reports, individual findings, vulnerability patterns, references, ingestion jobs and provenance.

**pgvector**

Store finding embeddings and support semantic similarity retrieval.

Use PostgreSQL full-text search alongside pgvector. This provides both exact technical-term retrieval and conceptual similarity without requiring a separate search database in the first version.

---

## 7. Retrieval and investigation workflow

For each auditor finding, Audit Intelligence should:

1. Read the structured finding and its code context.
2. Apply metadata filters for language, ecosystem and relevant vulnerability category.
3. Run keyword/full-text search.
4. Run vector similarity search.
5. Merge and deduplicate the candidate results.
6. Rerank candidates for relevance.
7. Return a small, useful set of historical findings, initially around 5–10 per query.
8. Include original source references and the conditions that made each historical finding valid.
9. Ask Claude to compare the historical root cause and preconditions with the current implementation.
10. Investigate relevant callers, callees, state changes, permissions and execution paths.
11. Record whether the match is confirmed, rejected, inconclusive or merely related.

### Vulnerability fingerprints

Create normalized fingerprints to retrieve findings that share an underlying weakness despite different names or terminology.

A fingerprint can include:

- Language and ecosystem
- Vulnerability category
- Operation or state transition
- Trust boundary
- Relevant control-flow or data-flow relationship
- Preconditions
- Impact

For example, two findings may both involve an external interaction occurring before an accounting update, even if their function names and variable names are entirely different.

Fingerprints improve retrieval, but they are not proof of a vulnerability.

### MCP interface

Expose the intelligence engine to Claude Code through an MCP server.

Initial tools:

| MCP tool | Responsibility |
|---|---|
| `search_audit_findings` | Hybrid search across historical findings |
| `get_finding_details` | Retrieve the full structured finding |
| `get_audit_reference` | Retrieve original report provenance and location |
| `search_vulnerability_patterns` | Search normalized vulnerability fingerprints |
| `get_related_findings` | Retrieve linked or related findings |

Keep the MCP tools focused. They should return evidence and references, not a pre-decided security verdict.

---

## 8. Final judgement and reporting

After Audit Intelligence completes, produce one final report.

For each finding, distinguish:

- **Direct analysis:** Evidence discovered by examining the current repository.
- **Historical match:** Related findings retrieved from previous audits.
- **Verification judgement:** Whether the current code exhibits the same underlying weakness.
- **Confidence:** How strongly the available evidence supports the conclusion.

Possible historical-comparison outcomes:

- Confirmed related vulnerability
- Similar pattern, but vulnerability not established
- Historical match rejected
- Inconclusive; additional context required
- No relevant historical match found

The absence of a historical match does not mean the code is safe.

The final report should include:

1. Repository and revision information.
2. Audit scope and source-file coverage.
3. Executive summary.
4. Findings ranked by severity.
5. Evidence, file paths and line references.
6. Historical references and comparison results.
7. Verification judgement and confidence.
8. Remediation recommendations.
9. Excluded files, limitations and unresolved questions.

The report must not inflate severity or confidence merely because a similar historical finding was severe.

---

## 9. Technology choices

| Area | Initial choice |
|---|---|
| Terminal interface and reasoning | Claude Code |
| Audit methodology | Trail of Bits skills + custom skills |
| Orchestration | Parent Claude Code skill + scripts |
| Deterministic validation | Python |
| Intelligence backend | Python + FastAPI |
| Tool interface | MCP |
| Relational database | PostgreSQL |
| Vector search | pgvector |
| Original document storage | MinIO or S3 |
| PDF extraction | PyMuPDF |
| Markdown extraction | Markdown parsers |
| Embeddings | Pluggable embedding model |
| Retrieval | PostgreSQL full-text + pgvector |
| Reranking | Pluggable reranker |
| Evaluation | Previously audited repositories and known findings |

Keep model and embedding providers configurable. The historical knowledge base should not be tied to one AI provider.

---

## 10. Implementation phases

### Phase 1 — Claude Code orchestration and auditor

- [ ] Inspect Trail of Bits skills and select relevant components.
- [ ] Document licensing and attribution requirements.
- [ ] Create the parent `security-audit` skill.
- [ ] Define the audit lifecycle and severity model.
- [ ] Create Solidity taxonomy and checklist.
- [ ] Create Rust taxonomy and checklist.
- [ ] Implement source-file discovery.
- [ ] Implement the source coverage ledger.
- [ ] Define the findings JSON schema.
- [ ] Implement handoff validation.
- [ ] Test the auditor on controlled educational repositories.

**Exit condition:** One Claude Code invocation runs the auditor, checks coverage and creates a valid structured handoff artifact.

### Phase 2 — Audit ingestion

- [ ] Select permitted initial report sources.
- [ ] Build source-specific collectors.
- [ ] Preserve original documents and provenance.
- [ ] Extract individual findings.
- [ ] Normalize metadata and severity.
- [ ] Validate extraction against source text.
- [ ] Deduplicate reports and findings.
- [ ] Track incremental ingestion.

**Exit condition:** Historical reports are represented as searchable, traceable individual findings.

### Phase 3 — Knowledge base and retrieval

- [ ] Set up PostgreSQL.
- [ ] Enable pgvector.
- [ ] Create source, report, finding and fingerprint tables.
- [ ] Implement full-text search.
- [ ] Generate finding embeddings.
- [ ] Implement vector similarity search.
- [ ] Add metadata filters.
- [ ] Merge and deduplicate search results.
- [ ] Add reranking.
- [ ] Benchmark retrieval latency and relevance.

**Exit condition:** A query can retrieve relevant historical findings with their original references.

### Phase 4 — MCP integration and automatic handoff

- [ ] Implement the MCP server.
- [ ] Expose the initial retrieval tools.
- [ ] Connect MCP to Claude Code.
- [ ] Update the parent skill to invoke Audit Intelligence automatically after successful handoff validation.
- [ ] Pass findings, code references and repository revision.
- [ ] Save intelligence results.
- [ ] Generate the final combined report.
- [ ] Test failure handling and incomplete coverage.

**Exit condition:** A single Claude Code invocation completes both stages without manual intervention.

### Phase 5 — Evaluation and improvement

- [ ] Build a benchmark from previously audited repositories.
- [ ] Compare direct auditor results with known findings.
- [ ] Measure precision and recall.
- [ ] Measure severity classification accuracy.
- [ ] Measure source-file coverage.
- [ ] Measure retrieval relevance and latency.
- [ ] Measure whether historical intelligence improves detection.
- [ ] Investigate false positives and missed findings.
- [ ] Refine taxonomies, prompts and retrieval.

**Exit condition:** The system has measurable performance and known limitations, rather than relying on anecdotal successful audits.

### Phase 6 — Optional standalone product

Only after the terminal workflow is reliable:

- [ ] Build a React dashboard.
- [ ] Add repository upload or Git integration.
- [ ] Add audit history and comparison.
- [ ] Add knowledge-base administration.
- [ ] Add user and project management.
- [ ] Add background audit execution and progress tracking.

The dashboard must use the same auditor and intelligence backend. Do not create a separate auditing implementation for the web application.

---

## 11. Non-negotiable engineering principles

1. **One invocation, two automatic stages.** The user starts the security audit once; Audit Intelligence follows automatically.
2. **Separate methodology from knowledge.** Updating historical reports must not require rewriting the audit skill.
3. **Complete, recorded source coverage.** Never claim a complete audit if relevant files were skipped.
4. **Evidence before judgement.** Every reported vulnerability must be supported by current-code evidence.
5. **Similarity is not confirmation.** Historical findings guide investigation; they do not establish a vulnerability by themselves.
6. **Preserve provenance.** Every retrieved finding must be traceable to its original report.
7. **Keep the knowledge portable.** Avoid coupling the database to Claude or any single model provider.
8. **Validate structured handoffs.** The second stage must consume a validated artifact, not an informal summary.
9. **Do not force 20 findings.** Return up to 20 substantiated, distinct findings.
10. **Measure quality.** Evaluate coverage, precision, recall, severity accuracy and retrieval performance.

---

## 12. First milestone

Build the smallest complete end-to-end version before expanding the source collection or creating a frontend.

**Demonstration:**

1. Open a controlled Solidity repository in Claude Code.
2. Invoke the parent security-audit skill once.
3. Claude inventories and examines every in-scope Solidity file.
4. Security Auditor produces structured findings and a coverage ledger.
5. The orchestrator validates and saves the handoff artifact.
6. The orchestrator automatically invokes Audit Intelligence.
7. Audit Intelligence retrieves related historical findings from a small PostgreSQL + pgvector dataset.
8. Claude investigates the matches against the actual code.
9. Claude produces one final report containing direct findings, historical comparisons, verification judgements and source references.

**Definition of success:** The entire workflow runs from the Claude Code terminal, with no manual stage switching, while the audit methodology remains independent of and unchanged by growth in the historical knowledge base.
