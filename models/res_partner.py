# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    """Extension of res.partner with LINE Bot metadata and push actions."""

    _inherit = 'res.partner'

    line_bot_user_ids = fields.One2many('line.bot.user', 'partner_id', string='LINE Profiles')
    line_user_count = fields.Integer(string='LINE Accounts', compute='_compute_line_info')
    line_display_name = fields.Char(string='LINE Name', compute='_compute_line_info')
    line_avatar_url = fields.Char(string='LINE Avatar', compute='_compute_line_info')

    @api.depends('line_bot_user_ids', 'line_bot_user_ids.display_name', 'line_bot_user_ids.picture_url')
    def _compute_line_info(self):
        for rec in self:
            rec.line_user_count = len(rec.line_bot_user_ids)
            if rec.line_bot_user_ids:
                first = rec.line_bot_user_ids[0]
                rec.line_display_name = first.display_name
                rec.line_avatar_url = first.picture_url
            else:
                rec.line_display_name = False
                rec.line_avatar_url = False

    def action_send_line_push(self):
        """Open LINE Push Message composer wizard for this contact."""
        self.ensure_one()
        line_user = self.line_bot_user_ids[:1]
        channel_id = line_user.channel_id.id if line_user else False

        return {
            'type': 'ir.actions.act_window',
            'name': f'Send LINE Message to {self.name}',
            'res_model': 'line.push.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_line_user_id': line_user.id if line_user else False,
                'default_channel_id': channel_id,
            },
        }
