# -*- coding: utf-8 -*-
{
    'name': 'Sunray Dashboard',
    'version': '0.1',
    'category': '',
    'description': "Sunray Dashboard's",
    'author': 'Mathias MANGON',
    'depends': ['base', 'web', 'sunray_core'],
    'data': [
        'data/dashboard_data.xml',
        'security/ir.model.access.csv',
        'views/dashboard_views.xml',
        'menu.xml',
        'data/res_users_set_home_action.xml'
    ],
    'demo_xml': [],
    'auto_install': True,
    'installable': True,
    'license': 'Other proprietary',
    'application': True,
    'assets': {
        'web.assets_backend': [
            ('include', 'web.chartjs_lib'),
            'sunray_dashboard/static/src/js/dashboard.js',
            'sunray_dashboard/static/src/xml/dashboard_templates.xml',
            'sunray_dashboard/static/src/scss/dashboard.scss'
        ]
    }
}
