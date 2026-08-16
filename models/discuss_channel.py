# -*- coding: utf-8 -*-
from odoo import fields, models


class DiscussChannel(models.Model):
    """Extension of discuss.channel to support LINE Live Chat bridge."""

    _inherit = 'discuss.channel'

    is_line_channel = fields.Boolean(string='Is LINE Live Chat', default=False, index=True)
    line_conversation_id = fields.Many2one(
        'line.bot.conversation', string='LINE Conversation', ondelete='set null'
    )
