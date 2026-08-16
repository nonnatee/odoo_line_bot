# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class LineBotConversation(models.Model):
    """Tracks chat memory and AI/Human handover state per LINE user."""

    _name = 'line.bot.conversation'
    _description = 'LINE Conversation Session'
    _order = 'last_message_date desc, id desc'
    _rec_name = 'display_name'

    name = fields.Char(string='Session Title', compute='_compute_name', store=True)
    channel_id = fields.Many2one('line.bot.channel', string='LINE Channel', required=True, ondelete='cascade')
    line_user_id = fields.Many2one('line.bot.user', string='LINE User', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', related='line_user_id.partner_id', string='Contact', readonly=True)
    discuss_channel_id = fields.Many2one('discuss.channel', string='Odoo Discuss Channel', ondelete='set null')

    state = fields.Selection([
        ('bot', 'AI Bot Active'),
        ('human', 'Live Agent Handover'),
    ], default='bot', required=True, string='Conversation Mode')

    operator_id = fields.Many2one('res.users', string='Assigned Operator')
    message_ids = fields.One2many('line.bot.message', 'conversation_id', string='Messages')
    message_count = fields.Integer(string='Messages', compute='_compute_message_count')
    last_message_date = fields.Datetime(string='Last Message', default=fields.Datetime.now, index=True)
    active = fields.Boolean(default=True)

    @api.depends('line_user_id.display_name', 'channel_id.name')
    def _compute_name(self):
        for rec in self:
            user_name = rec.line_user_id.display_name or 'Unknown User'
            rec.name = f"[LINE] {user_name} ({rec.channel_id.name})"

    @api.depends('message_ids')
    def _compute_message_count(self):
        for rec in self:
            rec.message_count = len(rec.message_ids)

    @api.model
    def get_or_create(self, channel, line_user) -> 'LineBotConversation':
        """Get or create active conversation session for this user."""
        conv = self.search([
            ('channel_id', '=', channel.id),
            ('line_user_id', '=', line_user.id),
        ], limit=1)

        if not conv:
            conv = self.create({
                'channel_id': channel.id,
                'line_user_id': line_user.id,
            })
            _logger.info('LineBotConversation: created session %s', conv.name)

        return conv

    def get_or_create_discuss_channel(self) -> object:
        """Find or create dedicated discuss.channel for live chat bridge."""
        self.ensure_one()
        if self.discuss_channel_id and self.discuss_channel_id.active:
            return self.discuss_channel_id

        user_name = self.line_user_id.display_name or 'LINE User'
        channel_name = f"LINE: {user_name}"

        # Create discuss channel
        partner_ids = [self.env.user.partner_id.id]
        if self.partner_id:
            partner_ids.append(self.partner_id.id)

        discuss_chan = self.env['discuss.channel'].sudo().create({
            'name': channel_name,
            'channel_type': 'group',
            'is_line_channel': True,
            'line_conversation_id': self.id,
            'channel_member_ids': [(0, 0, {'partner_id': pid}) for pid in partner_ids],
        })
        self.write({'discuss_channel_id': discuss_chan.id})
        return discuss_chan

    def get_recent_messages(self, limit: int = 10) -> list:
        """Return last messages formatted for LLM context."""
        self.ensure_one()
        msgs = self.message_ids.sorted(lambda m: (m.create_date or fields.Datetime.now(), m.id), reverse=True)[:limit]
        return [{'role': m.role, 'content': m.content} for m in reversed(msgs)]

    def add_message(self, role: str, content: str, tool_used: str = None) -> None:
        """Append message to session and touch last_message_date."""
        self.ensure_one()
        self.env['line.bot.message'].create({
            'conversation_id': self.id,
            'role': role,
            'content': content,
            'tool_used': tool_used or False,
        })
        self.write({'last_message_date': fields.Datetime.now()})

    def action_switch_to_human(self):
        """Switch to live agent mode."""
        self.ensure_one()
        self.write({'state': 'human', 'operator_id': self.env.user.id})
        disc = self.get_or_create_discuss_channel()
        if disc:
            disc.message_post(
                body=f"👤 <b>Operator {self.env.user.name} took over the chat.</b> AI Bot is now paused.",
                message_type='notification',
            )

    def action_switch_to_bot(self):
        """Resume AI bot mode."""
        self.ensure_one()
        self.write({'state': 'bot', 'operator_id': False})
        disc = self.get_or_create_discuss_channel()
        if disc:
            disc.message_post(
                body="🤖 <b>AI Bot mode resumed.</b> Bot will now automatically respond to LINE messages.",
                message_type='notification',
            )
