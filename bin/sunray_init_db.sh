#!/bin/bash

# Function to log with timestamp and step info
log_step() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUNRAY-INIT: $1"
}

log_step "Starting Sunray database initialization"
log_step "Script: /opt/muppy/appserver-sunray18/bin/sunray_init_db.sh"
echo -e "\n"

log_step "Installing sunray_core module"
/opt/muppy/appserver-sunray18/bin/sunray-srvr -i sunray_core  --without-demo=all --stop-after-init

#
# Sunray Server setup
#
#   Depending on MPY_USERINIT_USER_PASSWORD being set, this script will configure differently:
#  - If MPY_USERINIT_USER_PASSWORD is set, we create a user with the given password and signup mail is not sent.
#  - If MPY_USERINIT_USER_PASSWORD is not set, we create a user with the given email and name ans we send signup mail.
#  - In all cases, User is 'base.user_admin' (id=2)
#
# Used ENV Vars in this script
# - MPY_USERINIT_EXTERNAL_ID: external id of the user to setup
# - MPY_USERINIT_USER_EMAIL: email of the user to setup
# - MPY_USERINIT_USER_NAME: name of the user to setup
# - MPY_USERINIT_USER_COMPANY: company name of the user to setup
#
# Next are used only for on premise deployment
#
# - MPY_USERINIT_USER_PASSWORD: Optional password of user. If set, signup email is not sent.
# - MPY_USERINIT_TOTP: Optional TOTP secret of the user to setup (optional)
#
# Next is always required
#
# - APP_PRIMARY_URL: primary URL of the application
#
# SMTP is passed on command line via IKB ENV Vars (Required only to send signup email)
# - IKB_SMTP
# - IKB_SMTP_PORT
# - IKB_SMTP_SSL
# - IKB_SMTP_USER
# - IKB_SMTP_PASSWORD
# - IKB_EMAIL_FROM
#
# New environment variables for company setup:
# - MPY_USERINIT_WEBSITE: Website URL for company (default: https://gitlab.com/cmorisse/inouk-sunray-server)
# - MPY_USERINIT_PARTNER_ROOT_NAME: Partner root name (default: SunrayBot)

# Use APP_LOADBALANCER_URL if available, otherwise fall back to APP_PRIMARY_URL
APP_EFFECTIVE_URL="${APP_LOADBALANCER_URL:-$APP_PRIMARY_URL}"

log_step "Setting up company configuration"
log_step "  Company: $MPY_USERINIT_USER_COMPANY"
log_step "  Email: $IKB_SMTP_USER"
log_step "  Website: $MPY_USERINIT_WEBSITE"
log_step "  Base URL: $APP_PRIMARY_URL"
log_step "  Partner root name: $MPY_USERINIT_PARTNER_ROOT_NAME"

bin/sunray-srvr setup-company --name="$MPY_USERINIT_USER_COMPANY" \
    --email=$IKB_SMTP_USER \
    --website="$MPY_USERINIT_WEBSITE" \
    --base-url=$APP_PRIMARY_URL \
    --update-partner \
    --partner-root-name="$MPY_USERINIT_PARTNER_ROOT_NAME"

# We check if password is set, if not, we will send a signup email
log_step "Setting up user account"
if [ -z "$MPY_USERINIT_USER_PASSWORD" ]; then
    log_step "No password set, will send signup email to $MPY_USERINIT_USER_EMAIL"
    
    log_step "Creating user without password"
    bin/sunray-srvr setup-user --external-id=$MPY_USERINIT_EXTERNAL_ID \
        --login=$MPY_USERINIT_USER_EMAIL \
        --name="$MPY_USERINIT_USER_NAME"
    
    log_step "Sending signup invitation email"
    bin/sunray-srvr send-signup-email --login=$MPY_USERINIT_USER_EMAIL --create-user
    
    log_step "Getting signup URL for user"
    bin/sunray-srvr get-signup-url --login=$MPY_USERINIT_USER_EMAIL

else
    log_step "Creating user $MPY_USERINIT_USER_EMAIL with supplied password"
    bin/sunray-srvr setup-user --external-id=$MPY_USERINIT_EXTERNAL_ID \
        --login=$MPY_USERINIT_USER_EMAIL \
        --name="$MPY_USERINIT_USER_NAME" \
        --password=$MPY_USERINIT_USER_PASSWORD
fi

log_step "Sunray database initialization completed"