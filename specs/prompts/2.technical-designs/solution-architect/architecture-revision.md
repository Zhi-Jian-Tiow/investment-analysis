## Architecture Revision Prompt

### Executive Context

You are revising a Solution Architecture Document based on findings from an independent
architecture review. Your task is to:

1. **Analyze the provided review document** to extract all identified issues, their severity levels, and recommendations
2. **Categorize issues** by severity (CRITICAL, HIGH, MEDIUM, LOW)
3. **Resolve all CRITICAL and HIGH severity issues** in the architecture document
4. Maintain the document's publication-ready status, architectural coherence, and internal consistency

---

### Input Documents

You will be provided with:

1. **Architecture Review Document** — contains all identified issues, severities, sections affected, and recommendations
   - Issues are formatted as: `<SEVERITY>-<IDENTIFIER>: <Title>`
   - Each issue includes: Section reference, Description, Impact, and Recommendation
2. **Original Architecture Document** — the document to be revised based on review findings

**Analysis Task (before beginning revisions):**

1. Extract ALL issues from the review document
2. Group them by severity level (CRITICAL, HIGH, MEDIUM, LOW)
3. Map each issue to the specific sections of the architecture document it affects
4. Identify cross-issue dependencies (e.g., resolving issue A may require changes for issue B)
5. Document this analysis as a mental checklist before proceeding

---

### Scope & Constraints

**In Scope:**

- The primary architecture document and all embedded Mermaid diagrams
- All sections, cross-references, and tables affected by identified issues
- Any new sections or subsections required to address the review findings
- Internal consistency and coherence across all document sections

**Out of Scope (unless explicitly broken by changes):**

- Referenced documents (e.g., ADR summaries, PRD, BAS) — treat as read-only reference
- External system documentation or third-party specifications
- Sections unaffected by any identified review issues

**Hard Constraints (non-negotiable):**

- ALL CRITICAL severity issues must be fully resolved with no exceptions
- ALL HIGH severity issues must be fully resolved OR documented with explicit architectural trade-off justification
- NO issues may be deferred to future versions
- Core architectural principles must remain in effect unless explicitly overridden by CRITICAL findings
- NO incomplete sections, floating TODOs, or placeholder text in final output
- Document must be coherent and internally consistent when read end-to-end

---

### Resolution Process

**Phase 1: Issue Extraction & Analysis**

1. Read the review document completely to understand its structure and content
2. Extract each identified issue with:
   - Issue identifier (e.g., CRIT-R-001, HIGH-R-005)
   - Severity level (CRITICAL, HIGH, MEDIUM, LOW)
   - Affected section(s) in the architecture document
   - Problem description
   - Recommended resolution approach
3. Create a categorized checklist of ALL issues by severity
4. Identify dependencies: which issues, if resolved, affect other issues?
5. **Report your analysis** before beginning revisions (list all issues found, organized by severity)

**Phase 2: Prioritized Resolution**

- **First**, resolve all CRITICAL issues in order (these often enable or constrain HIGH issues)
- **Second**, resolve all HIGH issues (document trade-offs if necessary)
- **Third**, resolve all MEDIUM issues (if critical/high are otherwise complete)
- **Skip or defer** LOW severity issues unless they're trivial to address

**Phase 3: Resolution per Issue**
For each issue being resolved, produce:

- Updated text in the affected section(s)
- Any new subsections, tables, or workflows required
- Updated Mermaid diagrams if processes/flows are affected
- Cross-reference updates in TOC and related sections
- Explicit note of which architectural principle(s), if any, are affected

**Phase 4: Cross-Document Consistency Check**
After all issues are resolved, verify:

- All sections that reference the changed topics are updated and consistent
- No contradictions between Security (§14), Data Architecture (§12), and Workflows (§10)
- All Mermaid diagrams are syntactically valid and semantically consistent
- TOC matches all section headings exactly
- All internal cross-references (e.g., §14.1, Figure 3) are accurate
- Architectural principles are coherent or conflicts are explicitly documented

---

### Output Specification

**Format & Style:**

- Maintain existing markdown structure, heading hierarchy, and formatting conventions
- Preserve tone: formal, technical, decisive (not tentative)
- Tables use the existing style (pipe-delimited, aligned)
- Code blocks remain monospace; Mermaid blocks use standard syntax

**Diagram Requirements:**

- All Mermaid diagrams must be validated with mermaid-diagram-validator before inclusion
- Diagrams must render without errors and maintain clarity
- No Unicode special characters (en-dashes, arrows) — use ASCII only
- Use `<br/>` for multi-line labels instead of `\n`

**Document Structure:**

- Output is a complete, self-contained revision (not a patch file or change log)
- No "TODO" comments or incomplete sections
- Table of Contents must match all section headings
- Internal links (e.g., "ADR-003") remain consistent throughout

**Issue Resolution Documentation:**

- For each issue fixed, note in a comment which issue was addressed (internal tracking)
- If an issue required trade-offs or departures from approved decisions, document explicitly
- If an issue was intentionally deferred, provide clear justification

**Verification Checklist (before final output):**

- [ ] All CRITICAL severity issues from the review have been fully resolved
- [ ] All HIGH severity issues from the review have been fully resolved or have explicit trade-off documentation
- [ ] All sections affected by resolved issues have been updated consistently
- [ ] No new contradictions have been introduced
- [ ] All Mermaid diagrams are valid (per mermaid-diagram-validator)
- [ ] TOC is complete and matches all section headings
- [ ] Cross-references are consistent (e.g., "§14.1" matches Section 14.1)
- [ ] Architectural principles are upheld or conflicts are explicitly justified
- [ ] All monetary/precision values use `Decimal` or `NUMERIC` as specified
- [ ] No sections remain as stubs or placeholders
- [ ] Document is coherent and complete end-to-end

---

### Handling Conflicts

**If resolving one issue conflicts with another:**
Document the conflict explicitly in an "Architectural Trade-offs" section. Include:

- Which issues are in conflict
- Why the conflict exists
- Which resolution takes precedence and why
- What acceptance criteria or documentation mitigates the remaining risk

Example format:

```
⚠️ **Architectural Trade-off**: Resolving Issue A (adds service X) increases complexity
that conflicts with Issue B's simplicity requirement. Rationale: Issue A is CRITICAL
(regulatory requirement), so it takes precedence. Mitigation: Issue B's scope is
narrowed to accept the added complexity as necessary operational overhead.
```

**If an issue requires departing from an approved architectural principle:**
Clearly identify:

- Which principle (e.g., P-007) is affected
- Why the issue forces the departure
- Document this as a justified exception and note it in the architectural principles section

---

### Success Criteria (Definition of Done)

A revision is complete and publication-ready when:

✅ **Issue Coverage:** All issues extracted from the review are accounted for (resolved, deferred with justification, or identified as out-of-scope)  
✅ **CRITICAL issues:** 100% resolved with no exceptions or deferred items  
✅ **HIGH issues:** 100% resolved or documented with explicit architectural trade-off justification  
✅ **Consistency:** No contradictions between sections; all references are accurate  
✅ **Diagram Validity:** All Mermaid diagrams are validated and render without errors  
✅ **TOC Accuracy:** Table of Contents matches all section headings exactly  
✅ **Cross-references:** All internal links (§14.1, Figure 3, etc.) are accurate  
✅ **Architectural Coherence:** Core principles are upheld; any departures are justified  
✅ **Completeness:** No placeholder text, TODO comments, or incomplete sections  
✅ **End-to-End Readability:** Document is coherent and understandable when read sequentially

---

### Implementation Notes

**For the AI performing revisions:**

1. **Before Starting Revisions:** Report your complete issue analysis to the user (list all issues found, organized by severity level)
2. **During Revisions:** Keep track of which issues you're addressing in each section edit
3. **After Each Issue:** Verify no new contradictions are introduced
4. **Before Final Output:** Run through the entire "Definition of Done" checklist
5. **Edge Cases:** If you encounter an issue that cannot be fully resolved within the scope or constraints, document it explicitly with your reasoning

**If you encounter ambiguity:**

- Consult the review document recommendations first
- Apply the principle of simplicity (P-001) as a tiebreaker
- Document your interpretation if the review text is unclear
