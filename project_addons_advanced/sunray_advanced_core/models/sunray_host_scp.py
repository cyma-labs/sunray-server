# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SunrayHostSCP(models.Model):
    """Extend sunray.host with SCP (Sunray Configuration Proxy) management fields."""

    _inherit = 'sunray.host'

    scp_id = fields.Many2one(
        'sunray.configuration_proxy',
        string='Configuration Proxy (SCP)',
        ondelete='set null',
        help='SCP managing this host configuration. Auto-register sets this automatically; '
             'manually assign to enable SCP synchronization for manually-created hosts. '
             'Ensure the SCP knows about this host\'s FQDN.'
    )
    scp_sync_enabled = fields.Boolean(
        string='Enable SCP Sync',
        default=False,
        help='Enable synchronization with the assigned SCP. Auto-register sets this to True. '
             'Manually enable for manually-created hosts that should be synced. '
             'When disabled, the host is unaffected by SCP changes.'
    )
    scp_hash = fields.Char(
        string='SCP Hash',
        help='Last hash received from SCP for this host. Used for change detection.'
    )
    scp_last_sync_ts = fields.Datetime(
        string='Last SCP Sync',
        readonly=True,
        help='Timestamp of last successful SCP synchronization for this host'
    )
    scp_setup_in_progress = fields.Boolean(
        string='Setup in Progress',
        default=False,
        help='True while async auto-register setup is running. Worker will show setup page.'
    )
