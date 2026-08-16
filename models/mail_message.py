# -*- coding: utf-8 -*-
import logging
import re
from odoo import api, models
from ..services.line_api_service import LineApiService
from ..services.line_flex_builder import build_text_message

_logger = logging.getLogger(__name__)


def clean_html(raw_html: str) -> str:
    """Strip HTML tags to send plain text to LINE."""
    if not raw_html:
        return ''
    clean = re.sub(r'<br\s*/?>', '\n', raw_html)
    clean = re.sub(r'</p>', '\n', clean)
    clean = re.sub(r'<.*?>', '', clean)
    return clean.strip()


class MailMessage(models.Model):
    """Intercept discuss.channel messages from operators and push to LINE."""

    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for msg in records:
            if msg.model == 'discuss.channel' and msg.res_id and msg.message_type == 'comment':
                self._dispatch_to_line(msg)
        return records

    def _dispatch_to_line(self, msg) -> None:
        """Push operator message from Discuss chatter to LINE user."""
        try:
            channel = self.env['discuss.channel'].sudo().browse(msg.res_id)
            if not channel.exists() or not channel.is_line_channel or not channel.line_conversation_id:
                return

            conversation = channel.line_conversation_id
            line_user = conversation.line_user_id
            bot_channel = conversation.channel_id

            # Avoid echo loops: ignore messages posted by the LINE user or root bot
            root_partner_id = self.env.ref('base.partner_root').id
            if msg.author_id.id in (line_user.partner_id.id, root_partner_id):
                return

            # Check if this was an AI bot post (tagged with [AI Bot])
            body_text = clean_html(msg.body)
            if body_text.startswith('[AI Bot]:') or body_text.startswith('[LINE User:'):
                return

            if not body_text:
                return

            # Format operator message
            operator_name = msg.author_id.name or 'Support Agent'
            line_text = f"👤 {operator_name}:\n{body_text}"
            payload = build_text_message(line_text)

            api = LineApiService(bot_channel.channel_access_token)
            if api.push_message(line_user.line_user_id, payload):
                _logger.info('MailMessage: operator reply pushed to LINE user %s', line_user.line_user_id)
                conversation.add_message('operator', body_text)
            else:
                _logger.error('MailMessage: failed to push operator reply to LINE user %s', line_user.line_user_id)

        except Exception as exc:
            _logger.exception('MailMessage: error in _dispatch_to_line — %s', exc)
