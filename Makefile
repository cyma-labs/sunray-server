# Makefile — unified entry point for Sunray server dev commands. Run `make` to list targets.
# DB connection relies on the standard PG* environment variables.
#
# Agent note (CLAUDE.md §"Server & Service Operations"): every target except `help`,
# `diff-vs-default`, `code-review` and `test-list` boots/stops/upgrades the sunray server or an
# IMQ worker. Claude must NOT run those itself — it hands the `make …` line to the user, waits
# for confirmation, then does the read-only follow-up (analyze the log named in each target's
# `make help` line). `help`, `diff-vs-default`, `code-review` and `test-list` are pure
# read-only/print and safe for the agent to run itself.

# Recipes run under bash (not /bin/sh -> dash) so `time` is the clean shell builtin
# (real/user/sys) instead of the verbose /usr/bin/time output.
SHELL := /bin/bash

.DEFAULT_GOAL := help

# Modules for `make update` / `make test` (override: `make <target> ADDONS=sunray_core`).
ADDONS ?= all

# Optional Odoo --test-tags filter for `make test` (empty = run every test).
TAGS ?=

# Odoo --dev mode for `make run-gui` (xml = live view reload). Disable with DEV= (empty).
DEV ?= xml

# IMQ queues handled by `make run-wrkr`. sunray_advanced_core declares exactly one queue
# ('sunray', see its data/imq_queue.xml); '*' or a glob/regex are also accepted.
QUEUES ?= sunray

# Number of messages `make run-wrkr` processes before the worker exits (--max-messages).
# No supervisor loop: the worker runs once, processes up to this many, then stops.
MESSAGES ?= 20

# Base branch for `make diff-vs-default` (override: `make diff-vs-default DEFAULT=sunray_config_proxy`).
DEFAULT ?= main

# node_exporter textfile dir that `make run-wrkr` writes its .prom metrics into
# (imq-worker --metrics-export-mode=textfile default --textfile-dir). Lives under
# /var/lib so creating it needs sudo once; afterwards it persists across reboots.
TEXTFILE_DIR ?= /var/lib/node_exporter/textfile

.PHONY: help initdb backup-db kill update test test-list run-gui run-wrkr metrics-dir clean-logs diff-vs-default code-review

help: ## Show this help (read-only — safe for the agent to run itself)
	@printf '\n\033[1mSunray server dev commands\033[0m — usage: make <target> [VAR=value]   (params listed per target)\n\n'
	@printf '\033[33mAGENT RULE (CLAUDE.md §"Server & Service Operations"): every target except `help`,\n'
	@printf '`diff-vs-default`, `code-review` and `test-list` boots/stops/upgrades the sunray server or\n'
	@printf 'an IMQ worker. Do NOT run those yourself — hand the make line to the user, wait, then do\n'
	@printf 'the read-only follow-up: read the log named below. `help`/`diff-vs-default`/`code-review`/\n'
	@printf '`test-list` are pure read-only/print, safe to run unprompted.\033[0m\n\n'
	@printf '\033[1mBefore a dev session: stop the systemd units.\033[0m On a provisioned App Server the\n'
	@printf 'Odoo server and the IMQ worker are supervised, so `make kill` cannot hold them down —\n'
	@printf 'systemd respawns the worker within seconds and it keeps a DB/registry lock that makes\n'
	@printf '`make update` / `make test` flaky:\n\n'
	@printf '  sudo systemctl stop mpy_anyv2_appsrv_sunray_srv.service mpy_anyv2_appsrv_sunray_imqwrkr0.service\n'
	@printf '  ...  dev session: make run-gui / make update / make test ...\n'
	@printf '  sudo systemctl start mpy_anyv2_appsrv_sunray_srv.service mpy_anyv2_appsrv_sunray_imqwrkr0.service\n\n'
	@printf '(`mpy_anyv2_appsrv_sunray_wrkr.service` is the FastAPI ForwardAuth worker — a different\n'
	@printf 'component, out of this Makefile'"'"'s reach; leave it be unless you are testing it.)\n\n'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@printf '\n'

diff-vs-default: ## Show branch diff vs DEFAULT (local branch preferred over origin/DEFAULT, which can drift stale behind it). Param DEFAULT=<branch> (default main), e.g. make diff-vs-default DEFAULT=sunray_config_proxy [read-only, safe for the agent]
	@if git show-ref --verify --quiet refs/heads/$(DEFAULT); then \
		base=$(DEFAULT); \
	elif git show-ref --verify --quiet refs/remotes/origin/$(DEFAULT); then \
		base=origin/$(DEFAULT); \
		printf '\033[33mnote: no local branch '"'"'%s'"'"' — falling back to origin/%s\033[0m\n' "$(DEFAULT)" "$(DEFAULT)"; \
	else \
		echo "error: neither local '$(DEFAULT)' nor 'origin/$(DEFAULT)' exist." >&2; \
		exit 1; \
	fi; \
	mb=$$(git merge-base $$base HEAD); \
	n=$$(git rev-list --count $$base...HEAD); \
	printf '\033[1mbase:\033[0m %s (merge-base %s) — \033[1m%s\033[0m commit(s) ahead of it\n\n' "$$base" "$${mb:0:8}" "$$n"; \
	git diff --stat $$base...HEAD

code-review: ## Explain the 5 Claude Code review/audit commands, their default scope, and how to override it [read-only, safe for the agent]
	@printf '\n\033[1mSunray has 5 review/audit commands — these run inside Claude Code, not make:\033[0m\n\n'
	@printf '  \033[36m/code-review\033[0m       Correctness, simplification, efficiency. Bugs, logic errors,\n'
	@printf '                    reuse/dedup opportunities. Generic quality review — not Sunray-specific.\n'
	@printf '                    Scope (default): current diff (working tree + branch vs its base).\n'
	@printf '                    Options: effort level low/medium/high/xhigh/max (fewer high-confidence\n'
	@printf '                    findings -> broader/uncertain coverage), or `ultra` for a multi-agent\n'
	@printf '                    cloud review — of the local branch, or `ultra <PR#>` for a GitHub PR.\n'
	@printf '                    --comment posts inline PR comments, --fix applies findings.\n'
	@printf '                    e.g. /code-review high --fix   |   /code-review ultra 42\n\n'
	@printf '  \033[36m/security-review\033[0m   Security review of the pending changes on the current branch.\n'
	@printf '                    Built-in, not Sunray-specific. Worth running on anything touching\n'
	@printf '                    the REST API, session handling, setup tokens or passkeys.\n\n'
	@printf '  \033[36m/standards-review\033[0m  Conformance to Sunray house conventions only (.claude/code_review_standards.md):\n'
	@printf '                    audit-event routing, XML id naming, sudo-first IMQ processors, Odoo 18\n'
	@printf '                    view syntax, advanced-addon isolation, etc. NOT correctness or security.\n'
	@printf '                    Scope (default): branch diff vs `make diff-vs-default`'"'"'s resolved base\n'
	@printf '                    (main unless told otherwise) + uncommitted/staged changes.\n'
	@printf '                    Options: pass free-text scope as an argument to override — specific\n'
	@printf '                    files/modules, "only the uncommitted changes", or a different base branch.\n'
	@printf '                    e.g. /standards-review only the uncommitted changes\n'
	@printf '                         /standards-review project_addons/sunray_core/controllers/rest_api.py\n\n'
	@printf '  \033[36m/standards-sync\033[0m    Documentation-consistency audit: is CLAUDE.md still in sync with\n'
	@printf '                    `.claude/code_review_standards.md` (STD-NN tags)? Not a code review — never\n'
	@printf '                    touches project_addons/. Reports orphaned checklist ids, dangling CLAUDE.md\n'
	@printf '                    tags, and untagged conventions worth formalizing.\n'
	@printf '                    Scope: the 2 doc files above, no arguments.\n\n'
	@printf '  \033[36m/standards-review-full\033[0m  Full-repo conformance sweep — NOT diff-scoped. One agent per\n'
	@printf '                    addon across BOTH roots (project_addons/ + project_addons_advanced/, ~4\n'
	@printf '                    addons), each checked against the same checklist as /standards-review.\n'
	@printf '                    Cheap here compared to a large repo (~4 agents), but still a periodic\n'
	@printf '                    /release pass rather than a per-PR tool. Runs in the background.\n'
	@printf '                    Scope (default): every addon. Pass addon names as an argument to\n'
	@printf '                    restrict to a subset.\n'
	@printf '                    Output: docs/standards_review_full_<date>.md + ReportFindings.\n'
	@printf '                    e.g. /standards-review-full\n'
	@printf '                         /standards-review-full sunray_core sunray_advanced_core\n\n'
	@printf '\033[33mOn a PR: /code-review for bugs, /standards-review for house-style conformance,\n'
	@printf '/security-review when the change touches the auth/session surface.\n'
	@printf 'Run /standards-sync periodically (not per-PR) to keep the checklist from going stale.\n'
	@printf 'Run /standards-review-full even less often (release-time).\n'
	@printf 'This target only documents them — `make code-review` cannot launch a Claude Code command.\033[0m\n\n'

# The dump lands in the repo root next to the logs, but its name deliberately does NOT match the
# `sunray-srvr*.log` glob — `make clean-logs` must never sweep away a database backup.
# A failed dump deletes its own partial file: a truncated .pg_dump that looks like a backup is
# worse than no backup at all.
backup-db: ## Dump PGDATABASE to sunray-db-<timestamp>.pg_dump in the repo root (pg_dump -Fc, compressed). Server does NOT need to be stopped. Kept out of clean-logs. Prints the pg_restore line when done. [user-run, writes a large file]
	@out=sunray-db-$$(date +%Y%m%d-%H%M%S).pg_dump; \
	echo "Dumping '$(PGDATABASE)' -> $$out …"; \
	if pg_dump --format=custom --file="$$out" $(PGDATABASE); then \
		printf '\033[32mbackup-db: %s written to %s\033[0m\n' "$$(du -h "$$out" | cut -f1)" "$$out"; \
		echo "restore:   pg_restore -d $(PGDATABASE) --clean --if-exists $$out"; \
	else \
		rm -f "$$out"; \
		printf '\033[31mbackup-db: FAILED — partial file removed, no backup kept.\033[0m\n' >&2; \
		exit 1; \
	fi

initdb: ## Fresh Sunray DB via interactive wizard: dropdb + createdb (PGDATABASE) + bin/sunray_init_db.sh. Requires NO active cnx to the DB. Env: MPY_USERINIT_USER_EMAIL/_NAME/_COMPANY + APP_PRIMARY_URL (see bin/sunray_init_db.sh --help). [user-run, interactive, DESTRUCTIVE]
	dropdb $(PGDATABASE)
	createdb $(PGDATABASE)
	bin/sunray_init_db.sh --interactive

# IMPORTANT, two rules for this recipe:
#  1. Never write the literal process name (s+unray-srvr) in the echoes — it would land in the
#     recipe shell's cmdline and make pgrep/pkill '[s]unray-srvr' match (and kill) the recipe
#     itself. Match with the bracketed '[s]unray-srvr'; display label as 'sunray server'.
#  2. Use SIGKILL (-9). Since the run-gui/run-wrkr recipe subshells install a 'trap … INT TERM
#     EXIT' and their cmdline contains sunray-srvr, one pkill -9 kills the GUI AND the worker
#     AND those wrapper shells in a single shot, with nothing left tailing a dead process.
kill: ## Kill running sunray server (GUI) + IMQ worker so an upgrade/test won't fail on DB/registry locks. Reports running/killed count. Auto-run as a prereq of `update` and `test`. ('[s]unray-srvr' avoids matching pkill itself.) [user-run]
	@n=$$(pgrep -fc '[s]unray-srvr' || true); \
	if [ "$${n:-0}" -gt 0 ]; then \
		echo "sunray server: $$n process(es) running — killing…"; \
		pkill -9 -f '[s]unray-srvr'; \
		sleep 1; \
		left=$$(pgrep -fc '[s]unray-srvr' || true); \
		echo "sunray server: $$((n - $${left:-0})) killed, $${left:-0} still running."; \
	else \
		echo "sunray server: no process running — nothing to kill."; \
		sleep 1; \
	fi

update: kill ## Upgrade modules (sunray-srvr -u --stop-after-init), killing the server first. Prints ERROR/CRITICAL lines from sunray-srvr-update.log when done (even on failure). Param ADDONS=<module> (default all), e.g. make update ADDONS=sunray_core [user-run]
	@if [ -f sunray-srvr-update.log ]; then mv sunray-srvr-update.log sunray-srvr-update.$$(date +%Y%m%d-%H%M%S).log; fi
	@set +e; \
	time bin/sunray-srvr -u $(ADDONS) --stop-after-init --logfile=sunray-srvr-update.log; \
	status=$$?; \
	echo ""; \
	errors=$$(awk '$$4 == "ERROR" || $$4 == "CRITICAL"' sunray-srvr-update.log); \
	if [ -n "$$errors" ]; then \
		printf '\033[31m--- ERROR/CRITICAL lines in sunray-srvr-update.log ---\033[0m\n'; \
		echo "$$errors"; \
	else \
		printf '\033[32msunray-srvr-update.log: no ERROR/CRITICAL lines.\033[0m\n'; \
	fi; \
	exit $$status

# --workers=0 is REQUIRED here: Odoo's test runner needs the single-process mode (this is what
# bin/test_server.sh does too). With workers>0 the tests do not run in the master process.
test: kill ## Run tests (sunray-srvr --test-enable --workers=0 --stop-after-init), killing the server first. Prints the odoo.tests result lines; full detail in sunray-srvr-tests.log. Params ADDONS=<module> (default all), TAGS=<test-tags> (optional), e.g. make test ADDONS=sunray_core TAGS=/sunray_core:TestAccessRules [user-run]
	@if [ -f sunray-srvr-tests.log ]; then mv sunray-srvr-tests.log sunray-srvr-tests.$$(date +%Y%m%d-%H%M%S).log; fi
	@set +e; \
	time bin/sunray-srvr --test-enable --stop-after-init --workers=0 -u $(ADDONS) $(if $(TAGS),--test-tags=$(TAGS)) --logfile=sunray-srvr-tests.log; \
	status=$$?; \
	echo ""; \
	results=$$(grep -E 'odoo\.tests\.(stats|result)' sunray-srvr-tests.log); \
	if [ -n "$$results" ]; then \
		printf '\033[1m--- odoo.tests summary (sunray-srvr-tests.log) ---\033[0m\n'; \
		echo "$$results"; \
	else \
		printf '\033[33mNo odoo.tests lines in sunray-srvr-tests.log — did the tests run at all?\033[0m\n'; \
	fi; \
	exit $$status

test-list: ## List available test classes with their ready-to-paste commands (bin/test_server.sh --list-tests). Use the class name as TAGS=/<module>:<Class> for `make test`. [read-only, safe for the agent]
	@bin/test_server.sh --list-tests

clean-logs: ## Delete all sunray-srvr*.log files (current + timestamped rotations) in the repo root. Does NOT stop running servers (they keep writing to the unlinked inode until restart). [user-run]
	@n=$$(ls sunray-srvr*.log 2>/dev/null | wc -l); \
	rm -f sunray-srvr*.log; \
	echo "clean-logs: removed $$n sunray-srvr*.log file(s)."

# --- Dev run: 2 long-running components, 1 per terminal (run-gui + run-wrkr) ---

# --workers=4 (multiprocessing) is required for inouk_notifications' toasts (ik_notify /
# ik_notify_with_link) to be delivered over the bus — do not drop it back to 0.
run-gui: ## [terminal 1] Long-running GUI/web server; logs to sunray-srvr.log + live tail -F in this terminal (Ctrl-C stops both). Param DEV=<mode> (default xml live-reload; DEV= to disable). [user-run, blocking]
	@if [ -f sunray-srvr.log ]; then mv sunray-srvr.log sunray-srvr.$$(date +%Y%m%d-%H%M%S).log; fi
	@# Pre-create the file: Odoo creates it itself a moment after startup, and `tail -F` would
	@# otherwise print a "cannot open … No such file" error before its first retry succeeds.
	@touch sunray-srvr.log
	@bin/sunray-srvr $(if $(DEV),--dev=$(DEV)) --workers=4 --logfile=sunray-srvr.log & \
	srv_pid=$$!; \
	trap 'kill $$srv_pid 2>/dev/null' INT TERM EXIT; \
	echo "sunray server started (pid $$srv_pid) — tailing sunray-srvr.log (Ctrl-C stops the server)…"; \
	tail --pid=$$srv_pid -F sunray-srvr.log

metrics-dir: ## Idempotently create the node_exporter textfile dir (TEXTFILE_DIR, default /var/lib/node_exporter/textfile) writable by the worker user. sudo only on first run (skipped once writable). Auto-run as a prereq of run-wrkr. [user-run, one-time]
	@test -w $(TEXTFILE_DIR) || { \
		echo "Creating $(TEXTFILE_DIR) (sudo)…"; \
		sudo mkdir -p $(TEXTFILE_DIR) && \
		sudo chmod 1777 $(TEXTFILE_DIR); \
	}

# Requires sunray_advanced_core to be installed: it is the only addon declaring an IMQ queue
# ('sunray') and @processor_method processors here (see models/sunray_configuration_proxy.py).
run-wrkr: metrics-dir ## [terminal 2] Run ONE IMQ worker (no supervisor loop — cannot leak); it processes up to MESSAGES tasks then exits. Requires sunray_advanced_core installed; WITHOUT a worker, async tasks stay pending. Logs to sunray-srvr-wrkr.log + live tail -F (Ctrl-C stops both). Params QUEUES=<glob> (default sunray), MESSAGES=<n> (default 20), e.g. make run-wrkr MESSAGES=80 [user-run, blocking]
	@if [ -f sunray-srvr-wrkr.log ]; then mv sunray-srvr-wrkr.log sunray-srvr-wrkr.$$(date +%Y%m%d-%H%M%S).log; fi
	@bin/sunray-srvr imq-worker --queues='$(QUEUES)' \
		--metrics-export-mode=textfile \
		--max-thread-delta=80 \
		--max-messages=$(MESSAGES) \
		>sunray-srvr-wrkr.log 2>&1 & \
	wrkr_pid=$$!; \
	trap 'kill $$wrkr_pid 2>/dev/null' INT TERM EXIT; \
	echo "imq-worker started (pid $$wrkr_pid) — tailing sunray-srvr-wrkr.log (Ctrl-C stops the worker)…"; \
	tail --pid=$$wrkr_pid -F sunray-srvr-wrkr.log
