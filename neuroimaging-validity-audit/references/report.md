# Report contract

The report is written for a scientist who reads the first screen, decides whether the
paper's claims hold, and only then looks at detail. Everything that decides a verdict goes
in the main body. Everything that documents how the verdict was reached goes in the
appendix. Start from `templates/audit_template.qmd`, which already has this shape. The
template needs no R or Python kernel for a document-only audit; add executable chunks only
for checks actually run.

## Shape

Main body, in this order. Budgets count prose words only: not YAML, code, tables,
captions, headings, status lines, or appendix.

1. **The two callouts** (AI-generated; preliminary), at most 60 words each. The first says it
   was written by an AI agent (identity recorded in the run registry; never name the
   auditing model) and states the human and independent review status. They carry the AI and preliminary caveats for the whole
   report; the body does not repeat them.
2. **Bottom line** (at most 150 words). The first sentence states the verdict on the central
   claim(s). Then one sentence each: what remains supported, what changes, what is
   unresolved. If a correction or corrigendum is warranted, one sentence names what it
   should address.
3. **Claims table.** One row per central claim: `Claim ID | Verdict | Revised wording | Next
   check`. This is the only place revised claim wording appears; claims that survive
   unchanged say so.
4. **Findings that change a conclusion.** Only findings of major or moderate severity,
   ordered by consequence. Each uses the finding record below, at most 150 words of prose
   (heading and status line excluded); tables and figures are extra. A record that needs
   more than three *Evidence* sentences moves its extra numbers to a table beside it or to
   *Finding detail* in the appendix.
5. **Minor findings.** One table: `ID | Issue | Location | Fix`. The Issue cell is one
   sentence; supporting numbers go to *Finding detail* in the appendix.
6. **Checks.** One summary table: `Check | Result | Changes the verdict?`, then at most one
   paragraph (about 100 words) on what the pattern across checks shows. Proposed checks
   say "proposed" in the Result cell.
7. **Assessment** (at most 200 words). One bullet per central claim: present-day confidence
   and the one or two reasons that decide it, separating justification at publication
   from confidence today. Then one sentence crediting what the authors did well. No
   numerical confidence scores and no paper-wide verdict.

Appendix: headings tagged `{.appendix}`, which Quarto places after the body. Sections, in
order: scope and materials (artifacts, versions, inspected vs available, upstream
processing held fixed); claim ledger and mechanism table (the two tables from SKILL.md);
full check ledger (`Check | Inputs | Executed/read-only/proposed | Result | Limitations`);
finding detail; rejected candidate criticisms (`Candidate | Counterargument | Reason
rejected`); clean checks; adjudication (one paragraph on the rebuttal pass and what it
changed); verification performed; run commands and session info. Tables and code, minimal
prose.

Main body target: at most 1500 prose words. When the body runs long, move material to the
appendix instead of compressing sentences.

## Additional evidence provenance

Keep supplied evidence separate from discovered evidence. Save new material under
`audit/additional-evidence/`; paths in the report are relative to `audit/`. Include this
table in the materials appendix, recording versions/commits when available and identifying
which findings depend on each source. Record failed retrievals and prep gaps subsequently
resolved. If no additional material was retrieved, say so.

| Source URL | Retrieval date | Local file | Findings |
|---|---|---|---|

For a source that cannot be saved, give the stable URL and what was inspected. Keep the
prepared inputs unchanged; new evidence does not modify the common starting snapshot.

## Finding record

```
### F3 — Pooled-vs-multigroup comparison is not a valid nested test {#f3}

**Verified error · moderate · affects C2.**

*Evidence.* Two or three sentences. Numbers that decide the finding go here or in an
adjacent table; the rest go to the appendix. The whole record is at most 150 words of prose. Executed checks state their result; proposed
checks say "proposed". Source locations (section, table, file) go in parentheses at the
end of the sentence they support; quotes are verified against the source.

*Consequence.* One or two sentences: what changes in the conclusion, what remains supported.

*Next check.* One sentence with its decision rule, or "None needed."
```

- **Status** is one of: verified error · sensitivity demonstrated · unresolved concern ·
  reporting gap. **Severity** (major / moderate / minor) is the effect on the named claim;
  confidence, when it differs from what the status implies, is one word after the severity.
- The mechanism and direction (false positive, false null, interpretation overreach) is
  stated in the first *Evidence* sentence when it is not obvious from the heading.
- An adopted counterargument is one sentence inside *Evidence*; rejected ones go to the
  appendix table.
- A code chunk whose output the record quotes inline sits directly under the status line,
  folded. Other chunks go to the appendix.
- A figure that decides a finding sits after its record with a caption of at most 40 words
  saying what it shows and what it establishes. Brain maps also state space, threshold and
  orientation. Inputs, versions and seeds go to the appendix check ledger. No figure is
  invented to fill a slot.
- A check that found no issue is a row under *Clean checks* in the appendix, not a record.

## Sentences

- Every section and finding opens with its conclusion.
- A number appears in prose only when it decides a verdict; otherwise it lives in a table.
- Name a file, function or script only when the reader must open it; otherwise say what it does.
- Each caveat is stated once, where it applies.
- Describe results, not the process of getting them. Sentences such as "The chunk below
  refits…" or "The audit then…" are left out.
- Paper-reported values, recomputations and approximate checks are labelled as such where
  they appear.

## Render and verify

- Save `audit.qmd`, `audit.html`, `figures/` and check outputs in the paper's report
  folder, with relative paths, so the folder can be moved. For a corpus, one folder per
  paper plus a corpus summary that names shared dependencies.
- Keep `embed-resources: true`, the table of contents and folded code. Render with
  `uv run quarto render audit.qmd`; confirm the exit status and `Output created`. If
  Quarto or a dependency is missing, deliver the source and figures with the exact blocker.
- Extract the rendered text and check every number, status and caption in the body
  against the tables it summarises. Check evidence for claims as carefully as evidence
  against them.
- Open the embedded figures (decode the base64 PNGs if needed) and check for empty panels,
  clipped labels and caption mismatches. Confirm images are embedded, not linked.
- Report the body word count (prose only) and what was checked in *Verification performed*.
- Keep the report private; publication or upload requires an explicit user request.
