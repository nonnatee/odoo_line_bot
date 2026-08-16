# -*- coding: utf-8 -*-
import base64
import logging
from odoo import api, fields, models
from odoo.exceptions import UserError
from ..services.line_api_service import LineApiService

_logger = logging.getLogger(__name__)


class LineRichMenu(models.Model):
    """LINE Official Account Rich Menu configurator."""

    _name = 'line.rich.menu'
    _description = 'LINE Rich Menu'
    _order = 'create_date desc'

    name = fields.Char(string='Menu Name', required=True, default='Main Rich Menu')
    channel_id = fields.Many2one('line.bot.channel', string='LINE Channel', required=True, ondelete='cascade')
    rich_menu_id = fields.Char(string='LINE Rich Menu ID', readonly=True)
    chat_bar_text = fields.Char(string='Chat Bar Label', default='Menu', required=True, help='Text shown at bottom of chat')
    size_type = fields.Selection([
        ('full', 'Full Size (2500 x 1686 px)'),
        ('half', 'Compact Size (2500 x 843 px)'),
    ], default='full', required=True, string='Layout Size')

    image = fields.Binary(string='Menu Image', attachment=True, required=True, help='PNG or JPEG image matching the exact dimensions')
    image_filename = fields.Char(string='Image Filename')
    is_default = fields.Boolean(string='Set as Default Menu', default=True)
    status = fields.Selection([
        ('draft', 'Draft (Not Published)'),
        ('published', 'Active on LINE'),
    ], default='draft', readonly=True)

    area_ids = fields.One2many('line.rich.menu.area', 'rich_menu_id', string='Tap Action Areas')

    def action_publish_to_line(self):
        """Create rich menu on LINE and upload image."""
        self.ensure_one()
        if not self.channel_id.channel_access_token:
            raise UserError('Selected LINE Channel does not have an active Access Token.')
        if not self.image:
            raise UserError('Please upload a Menu Image before publishing.')
        if not self.area_ids:
            raise UserError('Please define at least one tap action area for the rich menu.')

        width = 2500
        height = 1686 if self.size_type == 'full' else 843

        areas = []
        for area in self.area_ids:
            action = {}
            if area.action_type == 'message':
                action = {'type': 'message', 'text': area.action_text or area.name}
            elif area.action_type == 'uri':
                action = {'type': 'uri', 'uri': area.action_uri}
            elif area.action_type == 'postback':
                action = {'type': 'postback', 'data': area.action_data or 'action=click', 'displayText': area.action_text}

            areas.append({
                'bounds': {
                    'x': area.bounds_x,
                    'y': area.bounds_y,
                    'width': area.bounds_width,
                    'height': area.bounds_height,
                },
                'action': action,
            })

        payload = {
            'size': {'width': width, 'height': height},
            'selected': True,
            'name': self.name[:300],
            'chatBarText': self.chat_bar_text[:14],
            'areas': areas,
        }

        api = LineApiService(self.channel_id.channel_access_token)
        menu_id = api.create_rich_menu(payload)
        if not menu_id:
            raise UserError('Failed to create rich menu on LINE. Check server logs.')

        # Upload image
        image_bytes = base64.b64decode(self.image)
        content_type = 'image/png' if (self.image_filename or '').lower().endswith('.png') else 'image/jpeg'
        if not api.upload_rich_menu_image(menu_id, image_bytes, content_type):
            api.delete_rich_menu(menu_id)
            raise UserError('Failed to upload rich menu image to LINE.')

        # Set as default
        if self.is_default:
            api.set_default_rich_menu(menu_id)

        self.write({
            'rich_menu_id': menu_id,
            'status': 'published',
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Rich Menu Published',
                'message': f"Rich menu {self.name} published successfully to LINE!",
                'type': 'success',
            }
        }

    def action_delete_from_line(self):
        """Remove rich menu from LINE."""
        self.ensure_one()
        if self.rich_menu_id and self.channel_id.channel_access_token:
            api = LineApiService(self.channel_id.channel_access_token)
            api.delete_rich_menu(self.rich_menu_id)
        self.write({'rich_menu_id': False, 'status': 'draft'})


class LineRichMenuArea(models.Model):
    """Tap zone within a LINE Rich Menu."""

    _name = 'line.rich.menu.area'
    _description = 'Rich Menu Action Area'
    _order = 'id asc'

    rich_menu_id = fields.Many2one('line.rich.menu', string='Rich Menu', required=True, ondelete='cascade')
    name = fields.Char(string='Area Label', required=True, default='Button')
    bounds_x = fields.Integer(string='X (px)', default=0, required=True)
    bounds_y = fields.Integer(string='Y (px)', default=0, required=True)
    bounds_width = fields.Integer(string='Width (px)', default=833, required=True)
    bounds_height = fields.Integer(string='Height (px)', default=843, required=True)

    action_type = fields.Selection([
        ('message', 'Send Message Text'),
        ('uri', 'Open Web URL'),
        ('postback', 'Trigger Postback Data'),
    ], default='message', required=True, string='Tap Action')

    action_text = fields.Char(string='Message Text / Display')
    action_uri = fields.Char(string='Web URL (https://...)')
    action_data = fields.Char(string='Postback Data')
