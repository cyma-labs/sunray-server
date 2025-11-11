# -*- coding: utf-8 -*-
from odoo import models, fields, tools


class SunrayProtectedHostUserListReport(models.Model):
    """SQL view-backed report model for displaying user statistics per protected host

    This model is backed by a PostgreSQL view that computes real-time statistics
    from the host-user relationship and related tables (passkeys, tokens, sessions).

    The view automatically calculates:
    - User details (username, email, is_active)
    - Passkey count per host
    - Setup token count per host
    - Active session count
    - Last login timestamp

    View name: protected_host_user_list_report
    """
    _name = 'sunray.protected_host_user_list_report'
    _description = 'Protected Host User List Report - Sunray'
    _rec_name = 'user_id'
    _order = 'username'
    _auto = False  # Prevent Odoo from creating a table

    # Relations (computed from view)
    host_id = fields.Many2one(
        'sunray.host',
        string='Host',
        readonly=True
    )
    user_id = fields.Many2one(
        'sunray.user',
        string='User',
        readonly=True
    )
    # User details (from sunray_user table)
    username = fields.Char(
        string='Username',
        readonly=True
    )
    email = fields.Char(
        string='Email',
        readonly=True
    )
    is_active = fields.Boolean(
        string='Is active?',
        readonly=True
    )

    # Host-specific computed statistics (calculated by SQL view)
    passkey_count = fields.Integer(
        string='Passkeys',
        readonly=True,
        help='Number of passkeys for this user on this specific host'
    )
    setup_token_count = fields.Integer(
        string='Setup Tokens',
        readonly=True,
        help='Number of setup tokens for this user on this specific host'
    )
    active_session_count = fields.Integer(
        string='Active Sessions',
        readonly=True,
        help='Number of active sessions for this user on this specific host'
    )
    last_login = fields.Datetime(
        string='Last Login',
        readonly=True,
        help='Most recent login time for this user on this specific host'
    )

    def init(self):
        """Create or replace the PostgreSQL view

        Uses correlated subselects instead of LEFT JOINs for optimal performance.
        Eliminates Cartesian product and leverages composite indexes on related tables.
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW sunray_protected_host_user_list_report AS (
                SELECT
                    -- Generate unique ID (required by Odoo)
                    row_number() OVER (ORDER BY rel.host_id, rel.user_id) as id,

                    -- Relations
                    rel.host_id as host_id,
                    rel.user_id as user_id,

                    -- User details
                    u.username,
                    u.email,
                    u.is_active,

                    -- Statistics: Passkey count for this host
                    -- Uses index: idx_sunray_passkey_user_host_domain
                    (SELECT COUNT(*)
                     FROM sunray_passkey p
                     WHERE p.user_id = rel.user_id
                       AND p.host_domain = h.domain
                    ) as passkey_count,

                    -- Statistics: Setup token count for this host
                    -- Uses index: idx_sunray_setup_token_user_host
                    (SELECT COUNT(*)
                     FROM sunray_setup_token st
                     WHERE st.user_id = rel.user_id
                       AND st.host_id = rel.host_id
                    ) as setup_token_count,

                    -- Statistics: Active session count for this host
                    -- Uses index: idx_sunray_session_user_host_active
                    (SELECT COUNT(*)
                     FROM sunray_session s
                     WHERE s.user_id = rel.user_id
                       AND s.host_id = rel.host_id
                       AND s.is_active = true
                    ) as active_session_count,

                    -- Statistics: Last login time for this host
                    -- Uses index: idx_sunray_session_user_host_created
                    (SELECT MAX(s.created_at)
                     FROM sunray_session s
                     WHERE s.user_id = rel.user_id
                       AND s.host_id = rel.host_id
                    ) as last_login

                FROM sunray_user_host_rel rel

                -- Join host to get domain for passkey matching
                JOIN sunray_host h ON h.id = rel.host_id

                -- Join user details (INNER JOIN - user must exist)
                JOIN sunray_user u ON u.id = rel.user_id
            )
        """)

