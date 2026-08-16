# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models
from ..services.line_api_service import LineApiService

_logger = logging.getLogger(__name__)


class LineBotUser(models.Model):
    """LINE User Profile linked to Odoo Contact (res.partner)."""

    _name = 'line.bot.user'
    _description = 'LINE User Profile'
    _order = 'last_interaction_date desc, id desc'
    _rec_name = 'display_name'

    line_user_id = fields.Char(string='LINE User ID', required=True, index=True)
    channel_id = fields.Many2one('line.bot.channel', string='LINE Channel', required=True, ondelete='cascade')
    display_name = fields.Char(string='LINE Display Name')
    picture_url = fields.Char(string='Avatar URL')
    status_message = fields.Text(string='Status Message')
    language = fields.Char(string='Language')
    is_followed = fields.Boolean(string='Follower Active', default=True)

    partner_id = fields.Many2one(
        'res.partner', string='Linked Contact', ondelete='set null',
        help='Odoo Customer/Vendor record associated with this LINE profile'
    )
    conversation_ids = fields.One2many('line.bot.conversation', 'line_user_id', string='Conversations')
    first_interaction_date = fields.Datetime(string='First Seen', default=fields.Datetime.now, readonly=True)
    last_interaction_date = fields.Datetime(string='Last Active', default=fields.Datetime.now)

    _sql_constraints = [
        ('line_user_channel_uniq', 'unique(channel_id, line_user_id)', 'A user record already exists for this channel and LINE ID!'),
    ]

    @api.model
    def get_or_create(self, channel, line_user_id: str) -> 'LineBotUser':
        """Resolve existing LINE user or create a new profile record."""
        user = self.search([
            ('channel_id', '=', channel.id),
            ('line_user_id', '=', line_user_id),
        ], limit=1)

        if not user:
            user = self.create({
                'channel_id': channel.id,
                'line_user_id': line_user_id,
                'display_name': f'LINE User ({line_user_id[:8]})',
            })
            _logger.info('LineBotUser: created new profile for %s on channel %s', line_user_id, channel.name)

            # Auto-create Contact if channel is configured
            if channel.auto_create_partner:
                partner = self.env['res.partner'].sudo().create({
                    'name': user.display_name,
                    'comment': f'Created automatically via LINE Bot Channel: {channel.name} (ID: {line_user_id})',
                })
                user.write({'partner_id': partner.id})

        user.write({'last_interaction_date': fields.Datetime.now()})
        return user

    def update_from_profile(self, profile: dict) -> None:
        """Update fields from LINE Profile API response."""
        self.ensure_one()
        updates = {
            'display_name': profile.get('displayName') or self.display_name,
            'picture_url': profile.get('pictureUrl') or self.picture_url,
            'status_message': profile.get('statusMessage') or self.status_message,
            'language': profile.get('language') or self.language,
        }
        self.write(updates)

        # Update partner name if it was a placeholder
        if self.partner_id and self.partner_id.name.startswith('LINE User ('):
            self.partner_id.write({'name': updates['display_name']})

    def action_refresh_profile(self):
        """Fetch latest profile info from LINE."""
        self.ensure_one()
        api = LineApiService(self.channel_id.channel_access_token)
        profile = api.get_profile(self.line_user_id)
        if profile:
            self.update_from_profile(profile)

    def action_send_push(self):
        """Open push wizard for this user."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Send Push to {self.display_name}',
            'res_model': 'line.push.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_channel_id': self.channel_id.id,
                'default_line_user_id': self.id,
            },
        }
