# -*- coding: utf-8 -*-
import json
import logging
from odoo import api, fields, models
from odoo.exceptions import UserError
from ..services.line_api_service import LineApiService
from ..services.line_flex_builder import (
    build_text_message,
    build_sale_order_flex,
    build_invoice_flex,
    build_product_catalog_carousel,
)

_logger = logging.getLogger(__name__)


class LinePushWizard(models.TransientModel):
    """Composer wizard for targeted and broadcast LINE Push messages."""

    _name = 'line.push.wizard'
    _description = 'Send LINE Push Message'

    channel_id = fields.Many2one('line.bot.channel', string='LINE Channel', required=True)
    target_type = fields.Selection([
        ('single', 'Specific LINE User'),
        ('partner', 'Odoo Contact (res.partner)'),
        ('broadcast', 'All Active Channel Followers'),
    ], default='single', required=True, string='Recipient Target')

    line_user_id = fields.Many2one('line.bot.user', string='LINE Recipient')
    partner_id = fields.Many2one('res.partner', string='Contact')

    message_type = fields.Selection([
        ('text', 'Plain Text Message'),
        ('sale_order', 'Sales Order / Quotation Flex Card'),
        ('invoice', 'Invoice & Payment Flex Card'),
        ('product', 'Product Catalog Carousel'),
        ('custom_flex', 'Custom Flex JSON Payload'),
    ], default='text', required=True, string='Message Content Type')

    text_message = fields.Text(string='Message Text', default='Hello! We have an update regarding your account.')
    sale_order_id = fields.Many2one('sale.order', string='Select Sales Order')
    invoice_id = fields.Many2one('account.move', string='Select Invoice', domain="[('move_type', '=', 'out_invoice')]")
    product_ids = fields.Many2many('product.template', string='Select Products (up to 10)', domain="[('sale_ok', '=', True)]")
    custom_flex_json = fields.Text(string='Custom Flex JSON', help='Raw Flex JSON bubble/carousel')

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id and self.partner_id.line_bot_user_ids:
            self.line_user_id = self.partner_id.line_bot_user_ids[0]
            self.channel_id = self.line_user_id.channel_id

    @api.onchange('line_user_id')
    def _onchange_line_user_id(self):
        if self.line_user_id:
            self.channel_id = self.line_user_id.channel_id
            if self.line_user_id.partner_id:
                self.partner_id = self.line_user_id.partner_id

    def action_send_push(self):
        """Build message payload and dispatch via LINE Messaging API."""
        self.ensure_one()
        if not self.channel_id.channel_access_token:
            raise UserError('Selected LINE Channel does not have an active Access Token.')

        api = LineApiService(self.channel_id.channel_access_token)
        web_base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        currency = self.env.company.currency_id.symbol or '$'

        # 1. Build Payload
        if self.message_type == 'text':
            if not self.text_message:
                raise UserError('Please enter a message text.')
            payload = build_text_message(self.text_message)

        elif self.message_type == 'sale_order':
            if not self.sale_order_id:
                raise UserError('Please select a Sales Order.')
            payload = build_sale_order_flex(self.sale_order_id, currency, web_base)

        elif self.message_type == 'invoice':
            if not self.invoice_id:
                raise UserError('Please select an Invoice.')
            payload = build_invoice_flex(self.invoice_id, currency, web_base)

        elif self.message_type == 'product':
            if not self.product_ids:
                raise UserError('Please select at least one product.')
            payload = build_product_catalog_carousel(self.product_ids, currency, web_base)

        elif self.message_type == 'custom_flex':
            try:
                flex_dict = json.loads(self.custom_flex_json)
                payload = {'type': 'flex', 'altText': 'Notification', 'contents': flex_dict}
            except Exception as e:
                raise UserError(f'Invalid Flex JSON: {e}')
        else:
            raise UserError('Unsupported message type.')

        # 2. Resolve Recipients
        recipients = []
        if self.target_type == 'single':
            if not self.line_user_id:
                raise UserError('Please select a LINE User recipient.')
            recipients.append(self.line_user_id.line_user_id)

        elif self.target_type == 'partner':
            if not self.partner_id or not self.partner_id.line_bot_user_ids:
                raise UserError('Selected contact does not have a linked LINE profile.')
            recipients.append(self.partner_id.line_bot_user_ids[0].line_user_id)

        elif self.target_type == 'broadcast':
            users = self.env['line.bot.user'].search([
                ('channel_id', '=', self.channel_id.id),
                ('is_followed', '=', True),
            ])
            recipients = [u.line_user_id for u in users if u.line_user_id]
            if not recipients:
                raise UserError('No active followers found on this channel.')

        # 3. Dispatch
        if len(recipients) == 1:
            success = api.push_message(recipients[0], payload)
        else:
            success = api.multicast_message(recipients, payload)

        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Push Message Sent',
                    'message': f"Successfully sent LINE message to {len(recipients)} recipient(s)!",
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise UserError('Failed to send LINE Push Message. Check server logs for details.')
