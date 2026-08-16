# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """General settings for LINE Bot module."""

    _inherit = 'res.config.settings'

    line_default_channel_id = fields.Many2one(
        'line.bot.channel',
        string='Default LINE Channel',
        config_parameter='line_bot.default_channel_id',
        help='Fallback channel for global pushes or multi-tenant lookups',
    )
    line_webhook_base_url = fields.Char(
        string='LINE Webhook Base URL',
        config_parameter='line_bot.webhook_base_url',
        help='Global HTTPS base URL for LINE webhooks (defaults to web.base.url)',
    )
    line_auto_create_partner = fields.Boolean(
        string='Auto Create Contacts from LINE',
        config_parameter='line_bot.auto_create_partner',
        default=True,
    )
