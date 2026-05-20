# -*- coding: utf-8 -*-
"""Regression tests for the email OTP template config parameter.

The parameter ``sunray.email_otp_template_id`` must hold a numeric DB id
(not an XML ID string) so the controller resolves it via
``mail.template.browse(int(...))``. Storing an XML ID crashed ``env.ref()``
with "not enough values to unpack" once an admin saved General Settings
(the res.config.settings Many2one stores a numeric id). See module 18.0.1.3.0.
"""
import importlib.util
import os

from odoo.tests.common import TransactionCase


def _load_post_migrate():
    """Import the 18.0.1.3.0 post-migrate script.

    Its path (version dir + hyphenated file) is not a valid module name,
    so it cannot be imported with a plain ``import`` statement.
    """
    path = os.path.join(
        os.path.dirname(__file__), '..', 'migrations', '18.0.1.3.0', 'post-migrate.py'
    )
    spec = importlib.util.spec_from_file_location('sunray_otp_post_migrate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestEmailOtpTemplate(TransactionCase):
    """Guards the numeric-id format of sunray.email_otp_template_id."""

    PARAM_KEY = 'sunray.email_otp_template_id'

    def setUp(self):
        super().setUp()
        self.icp = self.env['ir.config_parameter'].sudo()
        self.default_template = self.env.ref(
            'sunray_core.mail_template_email_otp_default'
        )

    def test_installed_param_is_numeric_template_id(self):
        """The data file installs the parameter as a numeric DB id."""
        value = self.icp.get_param(self.PARAM_KEY)
        self.assertTrue(value, "OTP template parameter must be set after install")
        self.assertTrue(
            value.isdigit(),
            f"Parameter must be a numeric DB id, got {value!r}",
        )
        template = self.env['mail.template'].browse(int(value)).exists()
        self.assertEqual(
            template, self.default_template,
            "Parameter must resolve to the default OTP template",
        )

    def test_migration_converts_legacy_xml_id(self):
        """A legacy XML ID value is normalized to the numeric id."""
        self.icp.set_param(
            self.PARAM_KEY, 'sunray_core.mail_template_email_otp_default'
        )
        _load_post_migrate().migrate(self.env.cr, None)
        self.assertEqual(
            self.icp.get_param(self.PARAM_KEY), str(self.default_template.id)
        )

    def test_migration_preserves_admin_numeric_choice(self):
        """An existing numeric value (admin-selected template) is kept as-is."""
        custom_template = self.env['mail.template'].create({
            'name': 'Custom OTP Template',
            'model_id': self.env['ir.model']._get('sunray.host').id,
        })
        self.icp.set_param(self.PARAM_KEY, str(custom_template.id))
        _load_post_migrate().migrate(self.env.cr, None)
        self.assertEqual(
            self.icp.get_param(self.PARAM_KEY), str(custom_template.id),
            "Migration must preserve an admin-selected numeric template id",
        )

    def test_migration_recovers_from_empty_value(self):
        """An empty value falls back to the default OTP template."""
        self.icp.set_param(self.PARAM_KEY, '')
        _load_post_migrate().migrate(self.env.cr, None)
        self.assertEqual(
            self.icp.get_param(self.PARAM_KEY), str(self.default_template.id)
        )

    def test_migration_recovers_from_stale_numeric_id(self):
        """A numeric id pointing to a deleted template falls back to default."""
        self.icp.set_param(self.PARAM_KEY, '999999999')
        _load_post_migrate().migrate(self.env.cr, None)
        self.assertEqual(
            self.icp.get_param(self.PARAM_KEY), str(self.default_template.id)
        )
