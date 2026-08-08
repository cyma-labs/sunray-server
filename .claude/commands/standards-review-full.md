Run a **full-repo** STD-NN conformance sweep — one agent per addon, across **both** addon roots,
each checked against `.claude/code_review_standards.md`. This is heavier than `/standards-review`
(which only checks the current branch's diff) — it's the periodic, whole-codebase pass, not a
per-PR tool. Sunray only has ~4 addons, so it's cheap compared to a large repo, but it still
re-reads every file: invoke it deliberately (a release check, or when the checklist itself has
grown enough that a fresh full pass is worth it).

1. List the addons yourself first — `ls -d project_addons/*/ project_addons_advanced/*/` from the
   repo root. Keep the **full repo-relative path** (e.g. `project_addons/sunray_core`), strip the
   trailing slash, and drop any non-addon entry (there is a `README.md` under `project_addons/`;
   a real addon has a `__manifest__.py`). Don't spend an agent call on this, it's one line of
   Bash. If `$ARGUMENTS` names specific addons instead of asking for everything, use that subset
   — resolve each name to its full path.
2. Launch the workflow: `Workflow({name: 'standards-review-full', args: {addons: [...]}})`, passing
   the **paths**, not the basenames — several rules (STD-01 especially) turn on which root an
   addon sits under. It runs one agent per addon in parallel, each reading the checklist and
   reviewing every `.py`/`.xml` file in that addon, then returns combined, severity-sorted
   findings plus the list of clean addons.
3. This runs in the **background** — tell the user it's launched (mention the addon count) and
   move on. Don't poll for it. You'll get a task-notification when it completes.
4. When it completes: write the combined findings to a dated report at
   `docs/standards_review_full_<YYYY-MM-DD>.md` (run `date` if you're not sure of the date — don't
   guess it). Structure: a summary line (N findings, N addons clean, breakdown by severity), then
   one section per addon that has findings — skip clean addons from the body, they're already
   counted in the summary. Each finding: file:line, `STD-NN` id, summary, failure scenario.
5. Also call `ReportFindings` with the same findings (most severe first) so they render in the UI,
   not just the file.
6. Relay to the user: total findings, severity breakdown, how many addons were clean, and the
   report file path. Don't re-summarize away the `STD-NN` references or file:line detail — those
   are what make a finding actionable.

$ARGUMENTS
