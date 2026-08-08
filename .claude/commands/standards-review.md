Run a Sunray house-conventions quality-control pass — conformance to `.claude/code_review_standards.md`,
not correctness/security (that's `/code-review` and `/security-review`).

Launch the `sunray-standards-review` subagent (via the `Agent` tool, `subagent_type:
sunray-standards-review`) in the **foreground** (this is a single interactive review, not
background work — the user is waiting on the result). Do not pre-compute the diff or read the
checklist yourself first: the agent owns that process end to end per its own instructions.

If `$ARGUMENTS` is non-empty, pass it through verbatim in the agent prompt as the requested scope
(specific files/modules/paths, or a different base branch to diff against) instead of the default
current-branch-diff behavior. If empty, just ask it to review the current branch/diff as usual.

When the agent reports back, relay its findings to the user as-is — don't re-summarize away the
`STD-NN` references or the file:line detail, those are what make a finding actionable.

$ARGUMENTS
