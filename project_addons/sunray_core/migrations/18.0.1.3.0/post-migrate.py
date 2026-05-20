"""Normalize sunray.email_otp_template_id to a numeric DB id.

The parameter historically stored an XML ID string (module.name), but the
res.config.settings Many2one+config_parameter field stores a numeric id.
The two representations conflicted: once an admin saved General Settings,
the parameter flipped to a bare numeric id and env.ref() crashed on it.
Both the data file and the controller now use the numeric id; this migration
brings already-deployed instances to that format regardless of prior state.
"""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    icp = env['ir.config_parameter']
    key = 'sunray.email_otp_template_id'
    value = icp.get_param(key)

    template_obj = False
    if value and '.' in value:  # legacy XML ID
        template_obj = env.ref(value, raise_if_not_found=False)
    elif value and value.isdigit():  # already numeric — preserve admin choice
        template_obj = env['mail.template'].browse(int(value)).exists()
    if not template_obj:  # empty / corrupt / missing
        template_obj = env.ref(
            'sunray_core.mail_template_email_otp_default', raise_if_not_found=False
        )

    if template_obj:
        icp.set_param(key, str(template_obj.id))
