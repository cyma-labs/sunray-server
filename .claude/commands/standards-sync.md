Audit consistency between CLAUDE.md (the canonical prose source of Sunray's house conventions)
and `.claude/code_review_standards.md` (the compact `STD-NN` checklist distilled from it) —
catch drift between the two, not code issues. This is a documentation-consistency check, not a
code review; it never touches `project_addons/`, `project_addons_advanced/`, or any application
code.

The linking convention: a convention's prose in CLAUDE.md carries an inline tag naming the
`STD-NN` id(s) that distill it, e.g. `**Audit Logging Policy** (STD-06)`. That tag is the only
thing connecting the two files — there is no other cross-reference.

## What to check

1. Read `.claude/code_review_standards.md` in full — list every `STD-NN` id present.
2. `grep -n "STD-[0-9]" CLAUDE.md` — list every `STD-NN` id tagged in CLAUDE.md, and where.
3. Report three categories, don't skip any even if empty:
   - **Orphaned checklist entries** — an `STD-NN` exists in the checklist but is never tagged
     anywhere in CLAUDE.md. Not automatically a bug: some rules are checklist-native (written
     straight from reading the codebase, or ported from another repo's checklist) rather than
     distilled from CLAUDE.md prose. The checklist marks the known ones explicitly — say which
     of the two it looks like, don't assume it's an error.
   - **Dangling CLAUDE.md tags** — CLAUDE.md tags an `STD-NN` that doesn't exist (or no longer
     exists, e.g. renumbered) in the checklist. This one *is* always a bug — fix by finding what
     it was renamed to (check git history for the id) or removing the stale tag.
   - **Candidate untagged conventions** — best-effort scan of CLAUDE.md's "Development
     Guidelines" and "Coding Conventions" sections for prescriptive language
     (must/never/always/the standard is/flag:) that has no `STD-NN` tag nearby and isn't already
     covered by an existing tagged rule. This needs judgment, not just grep — read the
     surrounding paragraph before flagging; a false positive here just means "consider
     formalizing this", not "this is broken".

## Reporting

Plain text summary, one short bullet per finding, grouped under the three headers above (omit a
header entirely if that category is empty — don't write "none found"). For each finding, give
enough to act: the `STD-NN` id and/or the CLAUDE.md line/section. End with a one-line count
("N orphaned, N dangling, N candidates") so drift is visible over time even without reading the
detail.

Do not edit either file yourself unless the user asks after seeing the report — this command
reports drift, it doesn't resolve it.

$ARGUMENTS
