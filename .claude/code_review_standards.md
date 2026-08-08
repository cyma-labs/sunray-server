# Code Review Standards (Sunray house style)

Self-contained checklist of Sunray-specific conventions for code quality review — independent of
any particular tool, so it can be fed to Claude Code, another LLM, or read by a human directly.

This is a **living document**. When a review misses something or flags something that
shouldn't have been flagged, add/fix a rule here (with the *why*, not just the *what*) rather
than only telling the reviewing agent once. `CLAUDE.md` remains the canonical source for full
explanations and code examples — this file is the compact, review-oriented distillation.

Each rule has a stable ID (`STD-NN`) so findings can reference it and new rules can be appended
without renumbering existing ones.

---

## Editions & module boundaries

**STD-01 — Paid features live in `project_addons_advanced/`, and extend via `_inherit`.**
Anything belonging to the Advanced/Enterprise edition goes in
`project_addons_advanced/sunray_advanced_core/` (or another advanced addon), extends base models
with `_inherit`, and adds API endpoints by extending the `RestAPI` controller class. Never edit
a core model/controller in place to add a paid capability.
Why: the two editions ship separately (FSL core / ELv2 advanced). A paid behaviour welded into
`sunray_core` cannot be removed from a core-only deployment, which breaks the licence split.
Flag: a field/method/endpoint that only makes sense for the paid edition appearing under
`project_addons/`, or an advanced addon modifying a core file rather than inheriting it.

**STD-02 — System parameters are declared in XML data files, with NO default in code.**
Every `ir.config_parameter` a feature reads must exist as a record in the addon's
`data/ir_config_parameter.xml`. Code reads it and fails loudly if it's absent — it does not
substitute a hardcoded fallback.
Why: a code-side default silently masks a missing/renamed parameter, so an environment can run
for months on a value nobody chose and nobody can see in the UI.
Flag: `get_param('x', 'some_default')` (a literal second argument) for a Sunray-owned key, or a
new key read in code with no matching XML record.

**STD-03 — Workers detect features by presence in the API response, not by version.**
When the server exposes an optional capability, it adds an object to the config payload (e.g.
`remote_auth`); workers check whether that object is there. Don't add version numbers or
edition flags for workers to branch on.
Flag: a version/edition string added to an API response for the worker to compare against.

## API contract

**STD-04 — A REST controller change updates `docs/API_CONTRACT.md`.**
Any change to `project_addons/sunray_core/controllers/rest_api.py` or
`project_addons_advanced/sunray_advanced_core/controllers/rest_api.py` that affects the contract
— new endpoint, changed parameter, modified response shape or status code — must come with the
matching edit to `docs/API_CONTRACT.md` in the same change.
Why: `API_CONTRACT.md` is the authoritative spec the worker implementations are written against;
they are separate repos and cannot see the server code.
Flag: a diff touching a `rest_api.py` route signature or response body with no `API_CONTRACT.md`
hunk alongside it.

**STD-05 — The server owns all validation and defaults; workers stay thin.**
Business rules, validation and default values belong in the server. A worker is a translation
layer. Within this repo the reviewable form is: don't add an endpoint that expects the caller to
have pre-validated its input, and don't document a worker-side default.
Flag: an endpoint whose docstring/contract entry says the worker should check something first.

## Security & audit

**STD-06 — All audit events go through `sunray.audit.log.create_audit_event()`.**
One unified method, called with `event_type`, `details`, `severity` (+ the optional
`sunray_user_id`, `sunray_worker`, `ip_address`, `user_agent`, `request_id`, `event_source`,
`username`). Severity is one of `info` / `warning` / `error` / `critical` — `critical` for
security events.
Why: a second logging path means events that never reach the audit views, the `srctl auditlog`
CLI, or an export — i.e. an audit trail with holes exactly where someone built a shortcut.
Flag: a new `_log_*` / `log_xxx_event` helper on any model, a direct `create()` on
`sunray.audit.log`, or a security-relevant action (session, passkey, token, worker migration)
with no audit call at all.

**STD-07 — Passkey registration is authorized by a setup token, validated in the model layer.**
Registration flows go through `register_with_setup_token`; the token check lives in the model,
not in the controller.
Why: the controller is one of several entry points (REST, CLI, wizard). A check in the
controller is a check that the CLI path skips.
Flag: a passkey-creating path that doesn't consume a setup token, or a token validated in a
controller before calling an unguarded model method.

## IMQ processors

**STD-08 — `self = self.sudo()` is the first line of a `@processor_method`.**
IMQ captures `uid` from the record's env at enqueue time. Enqueued from an `auth='none'`
controller, that `uid` is `False` (public user), which produces FK violations on `write_uid` and
type errors in SQL. The method does privileged work, so it owns the escalation.
Flag: a `@processor_method` whose body doesn't start with `self = self.sudo()`, or one that
sprinkles `.sudo()` on individual calls instead.

**STD-09 — IMQ logger propagation.**
A `@processor_method` (and every method it calls that logs) takes `_imq_logger=None` as its
**last** kwarg, builds `_task_logger = _imq_logger or _logger` right after the `sudo()` line,
and uses `_task_logger` throughout — never the module `_logger` directly in that path. Nested
calls receive **`_imq_logger=_imq_logger`**, not `_task_logger`, so each callee falls back to
its own module logger.
Why: `_imq_logger` writes into the IMQ message log visible in `imq-ctl`. Logging to the module
logger instead means the task's own journal is empty at the moment someone is debugging it.
Flag: `_logger` used inside a processor path; `_imq_logger` placed before another kwarg;
`_task_logger` forwarded to a callee; a missing `_task_logger` line.

## Odoo conventions

**STD-10 — Odoo 18 view syntax, never `attrs=`.**
Use `invisible="not other_field"`, `readonly="state == 'done'"`, `required="is_required"`.
`attrs` is removed in Odoo 18 and fails at view load.
Flag: any `attrs="{...}"` in a view.

**STD-11 — Recordset variables carry an `_obj` / `_objs` suffix.**
`user_obj = self.env['sunray.user'].browse(...)`, `host_objs = ...search([])`. Exception:
`for record in self:` inside compute methods is the standard Odoo idiom — don't flag it.

**STD-12 — Relational fields carry an `_id` / `_ids` suffix.**
`host_id = fields.Many2one(...)`, `passkey_ids = fields.One2many(...)`. Method parameters follow
the same convention.

**STD-13 — Return `False`, not `None`, for "no record".**
A method expected to return a recordset returns `False` when it finds nothing, so truthiness
checks and `self.field_id = method() or False` behave.
Flag: `return None` (explicit or implicit fall-through) on a recordset-returning method.

**STD-14 — List view fields are `optional="show"`.**
So users can adapt the displayed columns themselves.
Flag: a new `<list>` whose fields carry no `optional` attribute.

**STD-15 — Never declare `created_by` / `created_date` / `modified_by` / `modified_date`.**
Odoo already provides `create_uid`, `create_date`, `write_uid`, `write_date` on every model.
Flag: any of the four redeclared, under any spelling.

**STD-16 — XML record IDs use the `__` separator.**
`{object}__formview` / `__treeview` / `__searchview` / `__kanbanview`,
`{object}__actwindow`, `{object}__menu`, `{wizard}__formview`. Single `_` inside a name segment,
double `__` between the object name and the type suffix.
Flag: a single `_` before the type suffix, or an ad-hoc id like `view_sunray_host_form`.

**STD-17 — Model technical names are prefixed `sunray.`.**
Main models `sunray.{object}` (`sunray.host`), association models
`sunray.{parent}.{child}` (`sunray.host.access.rule`), wizards `sunray.{name}.wizard`.
Flag: a new `_name` without the prefix (models inherited from Odoo/inouk addons excepted).

**STD-18 — A user-facing yes/no choice is a `Selection`, not a `Boolean`.**
Use `fields.Selection([...])` (rendered as radios) rather than `fields.Boolean` when the user is
picking between two named behaviours — the label of each option says what it does, where a
checkbox only names one side.
Flag: a new `Boolean` whose `string` reads as a mode/policy choice rather than a plain on/off.
Not a violation: a genuine toggle (`active`, `is_enabled`).

**STD-19 — Smart buttons are pure XML.**
A button navigating to a filtered list uses a dedicated `ir.actions.act_window` whose `domain`
references `active_id`, with `type="action"` — no Python method. Action id:
`{parent_model}__{related}_actwindow`. `context` pre-fills the inverse field so creation from
the filtered list auto-links. Reference: `sunray_configuration_proxy__hosts_actwindow`.
Flag: a new `action_view_*` Python method whose domain is static — it should have been XML. A
Python method IS correct when the domain is genuinely dynamic (computed from aggregated data).

**STD-20 — Multi-value config fields: one value per line + a `get_xxx(format='json')` accessor.**
Text fields holding IPs, CIDRs, URL patterns etc. store one value per line, ignore lines
starting with `#`, support trailing `#` comments, and are read through an accessor taking a
`format` parameter (default `'json'`, returning a list) rather than parsed at each call site.
Flag: a new multi-value Text field with comma/JSON storage, or parsed inline by its callers.

## UI polish

*(STD-21 and STD-22 are checklist-native — they are not written up in CLAUDE.md. `/standards-sync`
will list them as untagged; that is expected, not drift.)*

**STD-21 — Font Awesome icons need a `title`.**
Any `<i class="fa fa-...">` must carry `title="..."` (`"Warning"`, `"Info"`, `"Success"`,
`"Error"`, …). Without it the browser logs an accessibility warning (icon with no accessible
text).

**STD-22 — Alert boxes use Bootstrap classes and the right ARIA role.**
`<div class="alert alert-{info|warning|success|danger}" role="{status|alert}">` rather than an
ad-hoc `text-info` div. `role="status"` for informational content, `role="alert"` for
warnings/errors.

## Tests

**STD-23 — Test scaffolding.**
Test files live in the addon's `tests/` directory (either root), are named `test_*.py`, hold
classes named `Test*` with `test_*` methods, and inherit `odoo.tests.common.TransactionCase`.
Create **minimal viable records** — required fields plus only what the test exercises; check the
model for `required=True` before adding fields "just in case". Mock external dependencies with
`unittest.mock.patch`.
Flag: a test creating a record with fields the assertions never touch; a test hitting a real
network dependency.

## Process

**STD-24 — Feature-first: no ad-hoc SQL or throwaway scripts for data work.**
When Sunray server data needs manipulating and no feature covers it, the change should add the
feature (GUI or CLI via `srctl`), not a one-off SQL statement or Python script.
Flag: a diff adding a maintenance script or raw SQL where a `srctl` subcommand or a button was
the fix.

**STD-25 — All project tools live in `bin/`.**
Executable scripts and utilities go in `bin/`, not the repo root or an addon directory.
Flag: a new `.sh` / `.py` tool committed outside `bin/`.

---

## Out of scope for this checklist

Things this checklist deliberately does not cover (already caught elsewhere, or not a
"standards" concern):
- Correctness bugs, security vulnerabilities, logic errors — that's `/code-review`'s and
  `/security-review`'s job. This checklist is about *conformance to house conventions*.
- Anything already enforced by linters/type checkers.
