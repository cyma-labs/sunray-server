# -*- coding: utf-8 -*-
{
    'name': 'Sunray Advanced Core',
    'version': '1.0',
    'category': 'Security',
    'summary': 'Advanced features for Sunray Zero Trust Access',
    'description': """
Sunray Enterprise Edition
==========================

Advanced features for Sunray Zero Trust Access solution:
* Remote Authentication - Authenticate via mobile device QR code
* Session Management - View and terminate active sessions
* Email notifications for setup tokens
* Advanced analytics and reporting
* Enhanced audit logging
* Custom branding options
* Priority support
    """,
    'author': 'Inouk',
    'website': 'https://sunray-zero-trust.app',
    'depends': ['sunray_core', 'mail', 'inouk_message_queue'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'data/imq_queue.xml',
        'data/ir_cron_worker.xml',
        'data/ir_cron.xml',
        'data/mail_templates.xml',
        'views/sunray_host_views.xml',  # Remote Authentication UI
        'views/res_config_settings_views.xml',
        'wizards/setup_token_wizard_views.xml',
        'wizards/setup_token_bulk_wizard_views.xml',
        'views/sunray_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
