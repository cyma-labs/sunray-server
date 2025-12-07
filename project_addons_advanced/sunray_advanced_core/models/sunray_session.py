# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)


class SunraySession(models.Model):
    """
    Extends sunray.session model with Remote Authentication features.
    This is a PAID feature available only in Sunray Advanced Core.
    """
    _inherit = 'sunray.session'

    # Remote Authentication fields
    session_type = fields.Selection([
        ('normal', 'Normal'),
        ('remote', 'Remote')
    ], string='Session Type', default='normal',
       help='Normal: Regular passkey authentication. Remote: Authenticated via mobile device')

    created_via = fields.Text(
        string='Created Via',
        help='JSON metadata about device that created the session (User-Agent, IP, etc.)'
    )

    def get_device_info(self):
        """
        Parse and return device information from created_via JSON.
        Used for session management UI.
        """
        if not self.created_via:
            return {}
        try:
            return json.loads(self.created_via)
        except (json.JSONDecodeError, TypeError):
            _logger.warning(f"Failed to parse device info for session {self.session_id}")
            return {}

    @api.model
    def create_remote_session(self, session_data):
        """
        Create a remote authentication session with proper audit logging.

        :param session_data: Dictionary containing session information
        :return: Created session record
        """
        # Ensure session_type is set to remote
        session_data['session_type'] = 'remote'

        # Create the session
        session = self.create(session_data)

        # Audit log is handled by the controller
        _logger.info(f"Remote session created: {session.session_id} for user {session.user_id.username}")

        return session