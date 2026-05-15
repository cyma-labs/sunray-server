# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


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

    def action_retry_scp_setup(self):
        """Re-enqueue the async setup_host_from_scp IMQ job for a stuck stub host.

        Used to recover from a failed initial setup (e.g. wrong SCP URL at the
        time of the first auto-register call). Requires the host to have an
        assigned SCP and a worker, and to still be flagged scp_setup_in_progress.
        """
        self.ensure_one()
        if not self.scp_setup_in_progress:
            raise UserError(
                "This host is not a stub (scp_setup_in_progress is False). "
                "Nothing to retry."
            )
        if not self.scp_id:
            raise UserError(
                "Cannot retry setup: no SCP assigned to this host."
            )
        if not self.sunray_worker_id:
            raise UserError(
                "Cannot retry setup: no worker assigned to this host."
            )

        sunray_api_user = self.env.ref('sunray_advanced_core.user_sunray_api')
        scp_for_imq = self.scp_id.with_user(sunray_api_user)
        result = scp_for_imq.setup_host_from_scp.run_async(
            scp_for_imq,
            self.domain,
            self.sunray_worker_id.id,
        )

        imq_message_id = result.get('id') if isinstance(result, dict) else None
        if imq_message_id:
            self.env.user.ik_notify_with_link(
                'success',
                'Setup retry enqueued',
                f'Async setup job re-enqueued for {self.domain}. '
                f'Open the IMQ message to follow execution.',
                model='imq.message',
                res_id=imq_message_id,
                button_name='Open IMQ Message',
            )
        else:
            self.env.user.ik_notify(
                'warning',
                'Setup retry enqueued (no IMQ id)',
                f'Setup job re-enqueued for {self.domain} but no IMQ message id '
                f'was returned: {result}',
            )

    def action_scp_sync_now(self):
        """Relay: trigger the parent SCP's action_sync_now from the host form.

        Reuses the existing SCP-level sync logic (which iterates over all hosts
        managed by this SCP). Defined here so a button on sunray.host can call
        it directly without needing a different button type.
        """
        self.ensure_one()
        if not self.scp_id:
            raise UserError("Cannot sync: no SCP assigned to this host.")
        return self.scp_id.action_sync_now()
