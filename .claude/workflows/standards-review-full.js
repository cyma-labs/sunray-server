export const meta = {
  name: 'standards-review-full',
  description: 'Full-repo STD-NN conformance review, one agent per addon across both addon roots',
  phases: [
    { title: 'Review', detail: 'one agent per addon, checked against .claude/code_review_standards.md' },
  ],
}

// args.addons is required: an array of repo-relative addon PATHS, not basenames — Sunray has two
// roots (project_addons/ and project_addons_advanced/) and several rules turn on which one a file
// sits in, so the root has to survive into the agent prompt.
//   e.g. ['project_addons/sunray_core', 'project_addons_advanced/sunray_advanced_core']
// The invoking command computes this itself via `ls -d` — no fs access here, and there's no
// reason to spend an agent call on listing two directories.

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string', description: 'repo-relative path' },
          line: { type: 'integer' },
          std_id: { type: 'string', description: 'e.g. STD-06' },
          summary: { type: 'string' },
          failure_scenario: { type: 'string', description: 'concrete: what breaks, for whom, under what condition' },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
        required: ['file', 'std_id', 'summary', 'failure_scenario', 'severity'],
      },
    },
  },
  required: ['findings'],
}

const addons = args && args.addons
if (!addons || !addons.length) {
  throw new Error("standards-review-full requires args.addons (array of repo-relative addon paths, e.g. 'project_addons/sunray_core') — the invoking command computes this via `ls -d`, it is not discovered here.")
}

phase('Review')
log(`Reviewing ${addons.length} addons in parallel against .claude/code_review_standards.md`)

const results = await parallel(addons.map(addonPath => () => {
  const name = addonPath.split('/').filter(Boolean).pop()
  const root = addonPath.split('/').filter(Boolean)[0]
  const isAdvanced = root === 'project_addons_advanced'

  return agent(
    `Review every .py and .xml file under ${addonPath}/ (this addon only, not the rest of the ` +
    `repo) for conformance to Sunray's house coding conventions.

This addon sits under \`${root}/\`, i.e. it is part of the ` +
    (isAdvanced ? 'PAID/Advanced edition (ELv2)' : 'CORE edition (FSL)') + `. That matters for ` +
    `STD-01 (paid features belong in project_addons_advanced/ and extend core models via ` +
    `_inherit; core addons must not carry paid-only behaviour) — keep it in mind rather than ` +
    `judging files by basename alone.

Read \`.claude/code_review_standards.md\` in full first — it is the canonical, numbered ` +
    `checklist (STD-01..STD-25 at the time of writing; more may exist by the time you run this ` +
    `— read the actual file, don't assume the count). This is a style/consistency review, NOT a ` +
    `correctness or security review — don't flag bugs or vulnerabilities, only convention ` +
    `violations. Skip rules that don't apply to a given file type (XML-specific rules don't ` +
    `apply to .py files, etc.).

For every genuine violation, report: the exact repo-relative file path and line number, the ` +
    `STD-NN id it breaks, a one-sentence summary, and a CONCRETE failure scenario (what breaks, ` +
    `for whom, under what condition — not just "violates the convention", say what the ` +
    `convention exists to prevent). Severity: 'high' for a missing audit event (STD-06), an ` +
    `unguarded passkey registration (STD-07), a paid feature in the core addon (STD-01) or a ` +
    `@processor_method without sudo() (STD-08, it crashes under IMQ); 'medium' for most other ` +
    `violations; 'low' for naming/cosmetic nits (STD-11, STD-12, STD-16, STD-21).

Be conservative — a false positive costs more than a miss. If nothing in this addon violates ` +
    `the checklist, return an empty findings array. Don't pad the report to seem thorough.`,
    { label: `review:${name}`, phase: 'Review', schema: FINDINGS_SCHEMA }
  ).then(r => (r && r.findings ? r.findings : []).map(f => ({ ...f, addon: name, addonPath })))
}))

const allFindings = results.filter(Boolean).flat()
const order = { high: 0, medium: 1, low: 2 }
allFindings.sort((a, b) => (order[a.severity] ?? 1) - (order[b.severity] ?? 1))

const cleanAddons = addons.filter(p => !allFindings.some(f => f.addonPath === p))
log(`${allFindings.length} finding(s) across ${addons.length} addons (${cleanAddons.length} clean)`)

return { addons, cleanAddons, findings: allFindings }
