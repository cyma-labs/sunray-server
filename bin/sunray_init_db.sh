#!/bin/bash
echo "Launching Database "
echo "  /opt/muppy/appserver-sunray18/bin/mpy_init_db.sh"
echo -e "\n"
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


bin/sunray-srvr setupcompany --name="$MPY_USERINIT_USER_COMPANY" \
    --email=$IKB_SMTP_USER \
    --website="https://gitlab.com/cmorisse/inouk-sunray-server" \
    --base-url=$APP_PRIMARY_URL \
    --update-partner \
    --partner-root-name="SunrayBot"

# We check if password is set, if not, we will send a signup email
if [ -z "$MPY_USERINIT_USER_PASSWORD" ]; then
    echo "No password set, signup email will be sent to $MPY_USERINIT_USER_EMAIL"
    bin/sunray-srvr setupuser --external-id=muppy_core.main_user \
        --login=$MPY_USERINIT_USER_EMAIL \
        --name="$MPY_USERINIT_USER_NAME"
    bin/sunray-srvr sendsignupemail --login=$MPY_USERINIT_USER_EMAIL --create-user
    bin/sunray-srvr getsignupurl --login=$MPY_USERINIT_USER_EMAIL

else
    echo "Creating user $MPY_USERINIT_USER_EMAIL from supplied password and TOTP secret."
    bin/sunray-srvr setupuser --external-id=muppy_core.main_user \
        --login=$MPY_USERINIT_USER_EMAIL \
        --name="$MPY_USERINIT_USER_NAME" \
        --password=$MPY_USERINIT_USER_PASSWORD
fi