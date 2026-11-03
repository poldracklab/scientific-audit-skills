# Report contract

The report is written for a scientist who reads the first screen, decides whether the
paper's claims hold, and only then looks at detail. Everything that decides a verdict goes
in the main body. Everything that documents how the verdict was reached goes in the
appendix. Start from `templates/audit_template.qmd`, which already has this shape.

## Shape

Main body, in this order. Budgets count prose words only: not YAML, code, tables,
captions, headings, status lines, or appendix.

1. **The two callouts** (AI-generated; preliminary), at most 60 words each. They carry the
   AI and preliminary caveats for the whole report; the body does not repeat them.
2. **Bottom line** (at most 150 words). The first sentence states the verdict on the central
   claim(s). Then one sentence each: what reproduces, what changes, what is unresolved.
3. **Claims table.** One row per central claim: `Claim | Verdict | What changes | Next check`.
   Ratings use the four-level scale from the Assessment. This is the only place a revised
   claim wording appears.
4. **Findings that change a conclusion.** Only findings of major or moderate severity,
   ordered by consequence. Each uses the finding record below, at most 150 words of prose
   (heading and status line excluded); tables and figures are extra. A record that needs
   more than three *Evidence* sentences moves its extra numbers to a table beside it or to
   *Finding detail* in the appendix.
5. **Minor findings.** One table: `ID | Issue | Location | Fix`. The Issue cell is one
   sentence; supporting numbers go to *Finding detail* in the appendix.
6. **Robustness.** One summary table: `Check | Result | Changes the verdict?`, then at most
   one paragraph (about 100 words) on what the pattern across checks shows. Leave-one-out
   tables, decomposition tables and full sensitivity output go to the appendix.
7. **Assessment** (at most 200 words). One bullet per central claim: rating (strong /
   moderate / weak / hypothesis-generating) and the one or two reasons that decide it.
   Then one sentence on computational reproducibility and one crediting what the authors
   did well.

Appendix: headings tagged `{.appendix}`, which Quarto places after the body. Sections, in
order: materials and provenance; analytic choices or prereg deviations table; full
robustness output; finding detail; clean checks; verification performed; run commands and
session info. Tables and code, minimal prose.

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
### F2 — The pooled model analyzed 651 participants, not the stated 672 {#f2}

**Verified error (reporting) · moderate · affects C1.**

*Evidence.* Two or three sentences. Numbers that decide the finding go here or in an
adjacent table; the rest go to the appendix. The whole record is at most 150 words of prose. Source locations (section, table, file) go in
parentheses at the end of the sentence they support.

*Consequence.* One or two sentences: what changes in the conclusion, what remains supported.

*Next check.* One sentence with its decision rule, or "None needed."
```

- **Status** is one of: verified error (code) · verified error (reporting) · major
  discrepancy · sensitivity demonstrated · prereg deviation · interpretive limit ·
  reporting gap. **Severity** (major / moderate / minor) is the effect on the named claim.
- An adopted counterargument is one sentence inside *Evidence*.
- A code chunk whose output the record quotes inline sits directly under the status line,
  folded. Other chunks go to the appendix.
- A figure that decides a finding sits after its record with a caption of at most 40 words
  saying what it shows and what it establishes. Inputs, versions and seeds go to the appendix.
- A check that found no problem is a row under *Clean checks* in the appendix, not a record.

## Sentences

- Every section and finding opens with its conclusion.
- A number appears in prose only when it decides a verdict; otherwise it lives in a table.
- Name a file, function or script only when the reader must open it; otherwise say what it does.
- Each caveat is stated once, where it applies.
- Describe results, not the process of getting them. Sentences such as "The chunk below
  refits…" or "The audit then…" are left out.

## Render and verify

- Render with `uv run quarto render <file>.qmd` and confirm `Output created`.
- Extract the rendered text and check every number and status in the body against the
  tables it summarises; drafted prose has repeatedly contradicted its own tables.
- Open the embedded figures and check labels, panels and captions.
- Report the body word count (prose only) in *Verification performed*.
