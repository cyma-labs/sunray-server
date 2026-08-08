#!/bin/bash
#
# odoo_init_db.lib.sh — Generic Odoo DB initialization + first company/user
#                       provisioning engine.
#
# ┌──────────────────────────────────────────────────────────────────────────┐
# │  ODOO_INIT_DB_LIB_VERSION below is the PROMINENT version marker.          │
# │  This library is SERVER-AGNOSTIC and is a CANDIDATE FOR INCLUSION IN      │
# │  ikb / buildit. Keep it free of any product-specific (Muppy, …) value.   │
# │  Per-server specificities live in the thin wrapper that sources this file │
# │  (e.g. bin/mpy_init_db.sh). When copied across server repos, compare the  │
# │  version string to detect drift.                                         │
# └──────────────────────────────────────────────────────────────────────────┘
#
ODOO_INIT_DB_LIB_VERSION="1.3.0"
#
# What this engine does (driven by the inouk `ik-cli` commands, available on
# any inouk/odoo-derived server):
#   1. init the database  (--init=<module> --without-demo=all --stop-after-init)
#   2. resolve company/user values (env vars, or wizard prompts in interactive)
#   3. ik-cli company setup
#   4. ik-cli user setup
#   5. provision access: explicit password / signup email / console fallback
#
# Two modes:
#   * non-interactive (DEFAULT) — driven entirely by env vars. This is the
#     k8s / App Server / CI provisioning path.
#   * interactive (--interactive) — a wizard prompts the operator for the
#     company/user values (env vars are used as defaults when present).
#
# SMTP auto-fallback:
#   When a password is not provided, the user is normally invited by email
#   (requires IKB_SMTP*). If the SMTP env vars are NOT available, the engine
#   falls back to a LOCAL CONSOLE flow:
#     - interactive : prompt the operator for a password (set directly).
#     - non-interactive : abort early with a clear error.
#   A console-typed plaintext password is fine: Odoo stores it as-is and
#   auto-encrypts it (pbkdf2) on first login / next startup.
#
# ── Configuration knobs (set by the wrapper BEFORE calling odoo_init_db_main) ─
# Required:
#   OIDB_LAUNCHER          : path to the odoo launcher wrapper (e.g. mpy-srv)
#   OIDB_INIT_MODULE       : module(s) to --init. Comma-separated list allowed
#                            (e.g. muppy_allinone_installer, or "a,b,mail").
#   OIDB_MAIN_USER_XMLID   : external-id of the main user (e.g. mod.main_user)
# Optional:
#   OIDB_COMPANY_WEBSITE   : company website URL. If empty, --website is omitted.
#   OIDB_PARTNER_ROOT_NAME : bot/root partner name (e.g. MuppyBot). If empty,
#                            --update-partner / --partner-root-name are omitted.
#   OIDB_PRODUCT_LABEL     : human label for banners/help (default: "Odoo")
#   OIDB_ENV_PREFIX_HINT   : env-var prefix shown in --help (default: "<prefix>")
#                            e.g. "MPY_USERINIT" so help lists the real names.
#   OIDB_IKCLI             : inouk_odoo_cli subcommand name: 'ik-cli' (Odoo 18,
#                            the default) or 'ik_cli' (Odoo 19+).
#   OIDB_POST_INIT_HOOK    : name of a shell function (defined by the wrapper)
#                            called right AFTER the DB init and BEFORE the
#                            company/user setup. Lets a server inject its own
#                            post-init steps (e.g. extra ik-cli calls) without
#                            polluting this server-agnostic engine.
#
# ── Input env vars (mapped by the wrapper from its own namespace) ────────────
# Required:
#   OIDB_USER_EMAIL        : email/login of the user to setup
#   OIDB_USER_NAME         : full name of the user to setup
#   OIDB_USER_COMPANY      : company name of the user to setup
#   APP_PRIMARY_URL        : primary URL of the application
#   APP_LOADBALANCER_URL   : publicly exposed URL (preferred over APP_PRIMARY_URL)
# Optional:
#   OIDB_USER_PASSWORD     : if set, signup email is not sent
#   OIDB_USER_TOTP         : TOTP secret of the user to setup
# SMTP (required only to send the signup email):
#   IKB_SMTP, IKB_SMTP_PORT, IKB_SMTP_SSL, IKB_SMTP_USER,
#   IKB_SMTP_PASSWORD, IKB_EMAIL_FROM
#

INTERACTIVE=0

# Validate that every required configuration knob is set, else fail fast.
_oidb_require_config() {
    local missing=0 var
    for var in OIDB_LAUNCHER OIDB_INIT_MODULE OIDB_MAIN_USER_XMLID; do
        if [ -z "${!var:-}" ]; then
            echo "ERROR: required config '$var' is not set by the wrapper." >&2
            missing=1
        fi
    done
    [ "$missing" -eq 0 ] || exit 2
    if [ -n "${OIDB_POST_INIT_HOOK:-}" ] && ! declare -F "$OIDB_POST_INIT_HOOK" >/dev/null; then
        echo "ERROR: OIDB_POST_INIT_HOOK='$OIDB_POST_INIT_HOOK' is not a defined function." >&2
        exit 2
    fi
    : "${OIDB_PRODUCT_LABEL:=Odoo}"
    : "${OIDB_ENV_PREFIX_HINT:=<prefix>}"
    # inouk_odoo_cli subcommand name: 'ik-cli' on Odoo 18, 'ik_cli' on Odoo 19+.
    # Per-server knob set by the wrapper; default keeps the Odoo 18 name.
    : "${OIDB_IKCLI:=ik-cli}"
    if [ ! -x "$OIDB_LAUNCHER" ]; then
        echo "ERROR: launcher '$OIDB_LAUNCHER' not found or not executable." >&2
        exit 2
    fi
}

usage() {
    local label="${OIDB_PRODUCT_LABEL:-Odoo}"
    local p="${OIDB_ENV_PREFIX_HINT:-<prefix>}"
    cat <<EOF
Usage: $(basename "$0") [--interactive] [--no-interactive] [-h|--help]

Initialize a fresh ${label} database and provision the first
company + user.
(engine: odoo_init_db.lib.sh v${ODOO_INIT_DB_LIB_VERSION})

Modes:
  (default)         Non-interactive. Values are read from environment
                    variables. This is the k8s / CI / App Server path.
  --interactive     Wizard. Prompt for the company/user values (env vars are
                    used as defaults). When SMTP is not configured, prompt for
                    a password instead of sending a signup email.
  --no-interactive  Force the non-interactive default (explicit no-op).
  -h, --help        Show this help and exit.

Environment variables (mapped by the wrapper):
  Required:
    APP_PRIMARY_URL / APP_LOADBALANCER_URL   Application URL (LB preferred).
    ${p}_USER_EMAIL                      User email / login.
    ${p}_USER_NAME                       User full name.
    ${p}_USER_COMPANY                    Company name.
  Optional:
    ${p}_USER_PASSWORD                   If set, no signup email is sent.
    ${p}_TOTP                            TOTP secret.
  SMTP (required only to send the signup email):
    IKB_SMTP, IKB_SMTP_PORT, IKB_SMTP_SSL,
    IKB_SMTP_USER, IKB_SMTP_PASSWORD, IKB_EMAIL_FROM
EOF
}

parse_args() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --interactive)    INTERACTIVE=1 ;;
            --no-interactive) INTERACTIVE=0 ;;
            -h|--help)        usage; exit 0 ;;
            *)
                echo "ERROR: unknown argument '$1'" >&2
                echo "" >&2
                usage >&2
                exit 2
                ;;
        esac
        shift
    done
}

# True (0) iff all four SMTP vars needed by `ik-cli user send-signup-email`
# are non-empty (same predicate as the CLI itself).
detect_smtp() {
    [ -n "${IKB_SMTP:-}" ] \
        && [ -n "${IKB_SMTP_PORT:-}" ] \
        && [ -n "${IKB_SMTP_USER:-}" ] \
        && [ -n "${IKB_SMTP_PASSWORD:-}" ]
}

# prompt_value "label" "default" -> echoes the entered value or the default.
prompt_value() {
    local prompt="$1"
    local default="${2:-}"
    local result
    read -r -p "$prompt (default=$default): " result
    echo "${result:-$default}"
}

# Masked password prompt with confirmation. Echoes the chosen password.
prompt_password() {
    local pw1 pw2
    while true; do
        read -r -s -p "Enter password: " pw1; echo "" >&2
        if [ -z "$pw1" ]; then
            echo "  Password cannot be empty." >&2
            continue
        fi
        read -r -s -p "Confirm password: " pw2; echo "" >&2
        if [ "$pw1" != "$pw2" ]; then
            echo "  Passwords do not match, try again." >&2
            continue
        fi
        echo "$pw1"
        return 0
    done
}

# Echo a launcher invocation (so every CLI call is visible in the logs), then run
# it. Secrets (--password=, --totp-secret=) are masked in the echo but passed
# intact to the command. ALL launcher calls in this engine go through here;
# wrappers' post-init hook functions (OIDB_POST_INIT_HOOK) should use it too,
# for consistent logging.
oidb_run() {
    local a
    local -a shown=()
    for a in "$@"; do
        case "$a" in
            --password=*)    shown+=("--password=********") ;;
            --totp-secret=*) shown+=("--totp-secret=********") ;;
            *)               shown+=("$a") ;;
        esac
    done
    echo "    + ${OIDB_LAUNCHER} ${shown[*]}"
    "${OIDB_LAUNCHER}" "$@"
}

init_db() {
    if [ "$INTERACTIVE" -eq 1 ]; then
        echo ""
        echo "This will initialize the database (${OIDB_INIT_MODULE})."
        read -r -p "Press [Enter] to continue or CTRL-C to abort... " _
    fi
    echo "==> [init_db] Initializing database (module(s): ${OIDB_INIT_MODULE})"
    oidb_run --init="${OIDB_INIT_MODULE}" --without-demo=all --stop-after-init
}

# Resolve company/user values into the *_VALUE globals.
collect_values() {
    if [ "$INTERACTIVE" -eq 1 ]; then
        echo ""
        echo "=== ${OIDB_PRODUCT_LABEL} init wizard ==="
        COMPANY_VALUE="$(prompt_value "Company name" "${OIDB_USER_COMPANY:-}")"
        EMAIL_VALUE="$(prompt_value "User email (login)" "${OIDB_USER_EMAIL:-}")"
        NAME_VALUE="$(prompt_value "User full name" "${OIDB_USER_NAME:-}")"
    else
        COMPANY_VALUE="${OIDB_USER_COMPANY:-}"
        EMAIL_VALUE="${OIDB_USER_EMAIL:-}"
        NAME_VALUE="${OIDB_USER_NAME:-}"
    fi
    TOTP_VALUE="${OIDB_USER_TOTP:-}"

    if [ -z "$EMAIL_VALUE" ]; then
        echo "ERROR: user email is required (${OIDB_ENV_PREFIX_HINT:-<prefix>}_USER_EMAIL)." >&2
        exit 1
    fi
}

setup_company() {
    # Fall back to the user email when no SMTP user is configured (avoids an
    # empty company email).
    local company_email="${IKB_SMTP_USER:-$EMAIL_VALUE}"
    local -a args=(
        "$OIDB_IKCLI" company setup
        --name="$COMPANY_VALUE"
        --email="$company_email"
        --base-url="$APP_EFFECTIVE_URL"
    )
    # Optional knobs: only pass them when the wrapper provided a value.
    if [ -n "${OIDB_COMPANY_WEBSITE:-}" ]; then
        args+=(--website="$OIDB_COMPANY_WEBSITE")
    fi
    if [ -n "${OIDB_PARTNER_ROOT_NAME:-}" ]; then
        args+=(--update-partner --partner-root-name="$OIDB_PARTNER_ROOT_NAME")
    fi
    echo "==> [setup_company] ${COMPANY_VALUE}"
    oidb_run "${args[@]}"
}

setup_user() {
    local -a args=(
        "$OIDB_IKCLI" user setup
        --external-id="$OIDB_MAIN_USER_XMLID"
        --login="$EMAIL_VALUE"
        --name="$NAME_VALUE"
    )
    if [ -n "$TOTP_VALUE" ]; then
        args+=(--totp-secret="$TOTP_VALUE")
    fi
    echo "==> [setup_user] ${EMAIL_VALUE} (external-id=${OIDB_MAIN_USER_XMLID})"
    oidb_run "${args[@]}"
}

# Set a password on the main user (plaintext is fine — Odoo auto-encrypts it).
apply_password() {
    local password="$1"
    echo "==> [apply_password] setting password for ${EMAIL_VALUE}"
    oidb_run "$OIDB_IKCLI" user setup \
        --external-id="$OIDB_MAIN_USER_XMLID" \
        --login="$EMAIL_VALUE" \
        --name="$NAME_VALUE" \
        --password="$password"
}

send_signup() {
    echo "==> [send_signup] no password set, sending signup email to $EMAIL_VALUE"
    oidb_run "$OIDB_IKCLI" user send-signup-email --login="$EMAIL_VALUE" --create
    oidb_run "$OIDB_IKCLI" user get-signup-url --login="$EMAIL_VALUE"
}

provision_access() {
    # 1) An explicit password from the environment always wins.
    if [ -n "${OIDB_USER_PASSWORD:-}" ]; then
        echo "Creating user $EMAIL_VALUE from supplied password."
        apply_password "$OIDB_USER_PASSWORD"
        return 0
    fi

    # 2) SMTP available -> signup email path.
    if detect_smtp; then
        if [ "$INTERACTIVE" -eq 1 ]; then
            local choice
            choice="$(prompt_value "Provision access: [1] send signup email, [2] set a password now" "1")"
            if [ "$choice" = "2" ]; then
                local pw; pw="$(prompt_password)"
                apply_password "$pw"
                echo "Password set. $EMAIL_VALUE can now log in."
                return 0
            fi
        fi
        send_signup
        return 0
    fi

    # 3) No SMTP.
    if [ "$INTERACTIVE" -eq 1 ]; then
        echo ""
        echo "SMTP is not configured -> local console mode."
        echo "Set a password for $EMAIL_VALUE:"
        local pw; pw="$(prompt_password)"
        apply_password "$pw"
        echo "Password set. $EMAIL_VALUE can now log in."
        return 0
    fi

    local p="${OIDB_ENV_PREFIX_HINT:-<prefix>}"
    echo "ERROR: no password provided (${p}_USER_PASSWORD) and SMTP is" >&2
    echo "       not configured (IKB_SMTP/_PORT/_USER/_PASSWORD), so a signup" >&2
    echo "       email cannot be sent. Either set ${p}_USER_PASSWORD," >&2
    echo "       configure SMTP, or re-run with --interactive." >&2
    exit 1
}

# Engine entry point. The wrapper sets the OIDB_* knobs then calls this.
odoo_init_db_main() {
    parse_args "$@"
    _oidb_require_config

    # Use APP_LOADBALANCER_URL if available, otherwise fall back to APP_PRIMARY_URL
    APP_EFFECTIVE_URL="${APP_LOADBALANCER_URL:-${APP_PRIMARY_URL:-}}"

    init_db
    if [ -n "${OIDB_POST_INIT_HOOK:-}" ]; then
        "$OIDB_POST_INIT_HOOK"
    fi
    collect_values
    setup_company
    setup_user
    provision_access
}
