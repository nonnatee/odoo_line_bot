# -*- coding: utf-8 -*-
from odoo import fields, models


class LineBotMessage(models.Model):
    """Audit log of messages exchanged with LINE users."""

    _name = 'line.bot.message'
    _description = 'LINE Bot Message Record'
    _order = 'create_date asc, id asc'

    conversation_id = fields.Many2one(
        'line.bot.conversation', string='Conversation', required=True, ondelete='cascade', index=True
    )
    role = fields.Selection([
        ('user', 'LINE User'),
        ('assistant', 'AI Bot Assistant'),
        ('operator', 'Human Agent / Operator'),
        ('system', 'System / Handover Notification'),
    ], required=True, string='Sender Role')
    content = fields.Text(string='Message Content', required=True)
    tool_used = fields.Char(string='MCP Tool / Action Invoked')
    raw_payload = fields.Text(string='Raw Payload (JSON)', help='Raw LINE or LLM payload for debugging')
