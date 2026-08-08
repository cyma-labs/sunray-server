#!/bin/bash
#
# sunray_init_db.sh — Initialize a fresh Sunray database and provision the first
#                     company + user.
#
# This is the thin SUNRAY WRAPPER around the generic engine
# bin/odoo_init_db.lib.sh (server-agnostic, candidate for ikb/buildit). It only
# sets the Sunray-specific knobs and maps the public env namespace
# (MPY_USERINIT_*) onto the engine's generic input vars, then delegates.
#
# Public contract (unchanged): invoked by path, with no args, non-interactive,
# from App Definitions, k8s package profiles (db_init_command) and the
# devcontainer. MPY_USERINIT_* remains the documented public env — renaming it
# would break those deployment paths, which is exactly why the mapping below
# lives in the wrapper and not in the engine.
#
# Two modes:
#   * non-interactive (DEFAULT) — env-var driven (k8s / App Server / CI path).
#   * interactive (--interactive) — wizard (see engine help). This is what
#     `make initdb` uses.
#
# Env vars consumed (public namespace)
# ------------------------------------
# Required:
#   - MPY_USERINIT_USER_EMAIL    : email/login of the user to setup
#   - MPY_USERINIT_USER_NAME     : full name of the user to setup
#   - MPY_USERINIT_USER_COMPANY  : company name of the user to setup
#   - APP_PRIMARY_URL            : primary URL of the application
#   - APP_LOADBALANCER_URL       : publicly exposed URL (preferred over
#                                  APP_PRIMARY_URL when set).
# Optional:
#   - MPY_USERINIT_USER_PASSWORD : if set, signup email is not sent
#   - MPY_USERINIT_TOTP          : TOTP secret of the user to setup
#   - MPY_USERINIT_EXTERNAL_ID   : external-id of the main user
#                                  (default: base.user_admin — Sunray ships no
#                                  sunray_core.main_user record of its own)
# SMTP (required only to send the signup email):
#   - IKB_SMTP, IKB_SMTP_PORT, IKB_SMTP_SSL, IKB_SMTP_USER,
#     IKB_SMTP_PASSWORD, IKB_EMAIL_FROM
#
# Usage:
#   sunray_init_db.sh [--interactive] [--no-interactive] [-h|--help]
#

set -euo pipefail

# Resolve paths relative to this script (bin/), no hardcoded deploy path.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Sunray specificities (the per-server knobs) ---
OIDB_LAUNCHER="$SCRIPT_DIR/sunray-srvr"
OIDB_IKCLI="ik-cli"               # Sunray is Odoo 18-based -> inouk_odoo_cli subcommand is 'ik-cli'
OIDB_INIT_MODULE="sunray_core"
OIDB_MAIN_USER_XMLID="${MPY_USERINIT_EXTERNAL_ID:-base.user_admin}"
OIDB_COMPANY_WEBSITE="https://gitlab.com/cmorisse/inouk-sunray-server"
OIDB_PARTNER_ROOT_NAME="SunrayBot"
OIDB_PRODUCT_LABEL="Sunray"
OIDB_ENV_PREFIX_HINT="MPY_USERINIT"

# --- Map the public MPY_USERINIT_* env onto the engine vars ---
OIDB_USER_EMAIL="${MPY_USERINIT_USER_EMAIL:-}"
OIDB_USER_NAME="${MPY_USERINIT_USER_NAME:-}"
OIDB_USER_COMPANY="${MPY_USERINIT_USER_COMPANY:-}"
OIDB_USER_PASSWORD="${MPY_USERINIT_USER_PASSWORD:-}"
OIDB_USER_TOTP="${MPY_USERINIT_TOTP:-}"

# shellcheck source=odoo_init_db.lib.sh
source "$SCRIPT_DIR/odoo_init_db.lib.sh"

odoo_init_db_main "$@"
