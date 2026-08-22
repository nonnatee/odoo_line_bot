# -*- coding: utf-8 -*-
"""
LineBotService — Central dispatch, AI routing, Discuss bridge, and handover orchestrator.
"""
import logging
from odoo import fields
from .line_api_service import LineApiService
from .line_flex_builder import (
    build_text_message,
    build_sale_order_flex,
    build_invoice_flex,
    build_product_catalog_carousel,
    build_quick_reply_items,
)
from .line_ai_client import LineAiClient

_logger = logging.getLogger(__name__)

HANDOVER_KEYWORDS = {
    'agent', 'human', 'support', 'help', 'operator',
    'ติดต่อเจ้าหน้าที่', 'เจ้าหน้าที่', 'พนักงาน', 'ช่วยเหลือ', 'แอดมิน'
}


class LineBotService:
    """Orchestrates LINE events, conversational AI, Discuss sync, and human handover."""

    def __init__(self, env):
        self.env = env

    def process_event(self, event: dict, channel) -> bool:
        """
        Process a single normalized LINE event.
        
        :param event: Normalized event dict
        :param channel: line.bot.channel record
        """
        event_type = event.get('type')
        user_id = event.get('user_id')
        reply_token = event.get('reply_token')

        if not user_id:
            _logger.warning('LineBotService: event missing user_id — %s', event)
            return False

        # 1. Resolve or create LINE User profile
        line_user = self.env['line.bot.user'].sudo().get_or_create(channel, user_id)
        api = LineApiService(channel.channel_access_token)

        # Sync profile details if missing
        if not line_user.display_name:
            profile = api.get_profile(user_id)
            if profile:
                line_user.update_from_profile(profile)

        # 2. Resolve Conversation memory
        conversation = self.env['line.bot.conversation'].sudo().get_or_create(channel, line_user)

        # 3. Handle Follow Event
        if event_type == 'follow':
            return self._handle_follow(channel, line_user, conversation, reply_token, api)

        # 4. Handle Unfollow Event
        if event_type == 'unfollow':
            line_user.write({'is_followed': False})
            _logger.info('LineBotService: user %s unfollowed channel %s', user_id, channel.name)
            return True

        # 5. Handle Message Event
        if event_type == 'message':
            return self._handle_message(event, channel, line_user, conversation, reply_token, api)

        # 6. Handle Postback Event
        if event_type == 'postback':
            return self._handle_postback(event, channel, line_user, conversation, reply_token, api)

        return True

    # ── Event Handlers ─────────────────────────────────────────────────────────

    def _handle_follow(self, channel, line_user, conversation, reply_token: str, api: LineApiService) -> bool:
        """Handle new follower subscription."""
        line_user.write({'is_followed': True})
        welcome_text = channel.welcome_message or (
            f"Hello {line_user.display_name or 'there'}! 👋 Welcome to {channel.name}.\n"
            "How can I assist you with your orders, products, or inquiries today?"
        )
        quick_pills = channel.get_quick_replies()
        msg_payload = build_text_message(welcome_text, quick_pills)

        conversation.add_message('assistant', welcome_text)
        if reply_token:
            return api.reply_message(reply_token, msg_payload)
        return api.push_message(line_user.line_user_id, msg_payload)

    def _handle_postback(self, event: dict, channel, line_user, conversation, reply_token: str, api: LineApiService) -> bool:
        """Handle rich menu or button postback clicks."""
        data = event.get('postback_data', '')
        _logger.info('LineBotService: postback received data=%s from user=%s', data, line_user.line_user_id)

        if 'action=handover' in data:
            return self._trigger_handover(channel, line_user, conversation, reply_token, api)

        # Treat postback displayText or data as user message
        text = event.get('text') or data
        event['text'] = text
        return self._handle_message(event, channel, line_user, conversation, reply_token, api)

    def _handle_message(self, event: dict, channel, line_user, conversation, reply_token: str, api: LineApiService) -> bool:
        """Process incoming user message."""
        user_text = (event.get('text') or '').strip()
        msg_type = event.get('message_type', 'text')

        # 1. Log incoming user message
        conversation.add_message('user', user_text or f'[{msg_type} message]')

        # 2. Sync to Odoo Discuss Channel
        discuss_channel = conversation.get_or_create_discuss_channel()
        if discuss_channel and user_text:
            partner = line_user.partner_id
            author_id = partner.id if partner else self.env.ref('base.partner_root').id
            discuss_channel.message_post(
                body=f"<b>[LINE User: {line_user.display_name}]</b><br/>{user_text}",
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=author_id,
            )

        # 3. Check for Handover Request
        lower_text = user_text.lower()
        if any(kw in lower_text for kw in HANDOVER_KEYWORDS):
            return self._trigger_handover(channel, line_user, conversation, reply_token, api)

        # 4. Check if currently in Human Handover Mode
        if conversation.state == 'human':
            _logger.info('LineBotService: conversation %s is in human mode — AI response suppressed', conversation.id)
            if discuss_channel:
                discuss_channel.message_post(
                    body=f"💬 <i>(Operator attention needed)</i> New message from LINE: <b>{user_text}</b>",
                    message_type='notification',
                )
            return True

        # 5. Process in AI Bot Mode
        reply_payload = self._generate_bot_reply(channel, line_user, conversation, user_text)

        # 6. Deliver reply
        success = False
        if reply_token:
            success = api.reply_message(reply_token, reply_payload)
        if not success:
            success = api.push_message(line_user.line_user_id, reply_payload)

        # 7. Log assistant reply in memory & Discuss
        reply_text = reply_payload.get('text') or reply_payload.get('altText') or 'Rich Card Response'
        conversation.add_message('assistant', reply_text)
        if discuss_channel:
            discuss_channel.message_post(
                body=f"🤖 <b>[AI Bot]:</b><br/>{reply_text}",
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=self.env.ref('base.partner_root').id,
            )

        return success

    # ── Handover & Routing ─────────────────────────────────────────────────────

    def _trigger_handover(self, channel, line_user, conversation, reply_token: str, api: LineApiService) -> bool:
        """Switch conversation to human agent mode and notify Discuss."""
        conversation.write({'state': 'human'})
        handover_text = channel.handover_message or (
            "I have transferred your chat to our customer support team. 👤\n"
            "An agent will be with you shortly!"
        )
        discuss_channel = conversation.get_or_create_discuss_channel()
        if discuss_channel:
            discuss_channel.message_post(
                body="🚨 <b>LINE Live Chat Handover Activated:</b> User requested human agent support.",
                message_type='notification',
            )

        msg = build_text_message(handover_text)
        conversation.add_message('assistant', handover_text)
        if reply_token:
            return api.reply_message(reply_token, msg)
        return api.push_message(line_user.line_user_id, msg)

    # ── AI & MCP Generation Engine ─────────────────────────────────────────────

    def _generate_bot_reply(self, channel, line_user, conversation, user_text: str) -> dict:
        """Generate response via MCP Gateway bridge, built-in Flex shortcuts, or direct AI."""
        web_base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        currency = self.env.company.currency_id.symbol or '$'
        partner = line_user.partner_id

        # ── Built-in Quick Shortcuts (Flex UI) ──
        lower = user_text.lower()
        if partner and any(k in lower for k in ('my orders', 'order status', 'orders', 'ใบสั่งซื้อ', 'คำสั่งซื้อ')):
            if 'sale.order' in self.env:
                orders = self.env['sale.order'].sudo().search(
                    [('partner_id', '=', partner.id)], order='date_order desc', limit=1
                )
                if orders:
                    return build_sale_order_flex(orders[0], currency, web_base)

        if partner and any(k in lower for k in ('my invoices', 'invoice', 'balance', 'ใบแจ้งหนี้', 'ยอดค้างชำระ')):
            if 'account.move' in self.env:
                invoices = self.env['account.move'].sudo().search(
                    [('partner_id', '=', partner.id), ('move_type', '=', 'out_invoice')],
                    order='invoice_date desc', limit=1
                )
                if invoices:
                    return build_invoice_flex(invoices[0], currency, web_base)

        if any(k in lower for k in ('products', 'catalog', 'สินค้า', 'แคตตาล็อก')):
            if 'product.template' in self.env:
                products = self.env['product.template'].sudo().search(
                    [('sale_ok', '=', True)], limit=6
                )
                if products:
                    return build_product_catalog_carousel(products, currency, web_base)

        # ── Check MCP Gateway Bridge (odoo_mcp_manager) ──
        if channel.ai_engine_mode in ('mcp', 'auto'):
            mcp_module = self.env['ir.module.module'].sudo().search(
                [('name', '=', 'odoo_mcp_manager'), ('state', '=', 'installed')], limit=1
            )
            if mcp_module:
                try:
                    from ...odoo_mcp_manager.services.bot_gateway_service import BotGatewayService
                    bot_msg = {
                        'platform': 'line',
                        'platform_user_id': line_user.line_user_id,
                        'text': user_text,
                        'attachments': [],
                        'metadata': {'partner_id': partner.id if partner else False},
                    }
                    mcp_resp = BotGatewayService(self.env).process(bot_msg)
                    if mcp_resp and mcp_resp.get('text'):
                        return build_text_message(mcp_resp['text'], channel.get_quick_replies())
                except Exception as exc:
                    _logger.warning('LineBotService: MCP Gateway bridge invocation failed — %s', exc)

        # ── Standalone Direct AI Engine ──
        if channel.ai_provider:
            history = conversation.get_recent_messages(limit=6)
            system_prompt = channel.system_prompt or (
                f"You are a helpful customer service AI for {self.env.company.name} on LINE. "
                "Provide polite, concise, and helpful answers. If the user asks for human help, advise them to type 'agent'."
            )
            try:
                ai_reply = LineAiClient.chat_completion(
                    provider=channel.ai_provider,
                    api_key=channel.ai_api_key,
                    messages=history,
                    model=channel.ai_model,
                    base_url=channel.ai_base_url,
                    system_prompt=system_prompt,
                )
                return build_text_message(ai_reply, channel.get_quick_replies())
            except Exception as exc:
                _logger.exception('LineBotService: Direct AI completion failed — %s', exc)

        # Fallback default response
        return build_text_message(
            f"Thank you for contacting {self.env.company.name}! We have received your message: '{user_text}'. "
            "Type 'agent' to connect with a live representative.",
            channel.get_quick_replies(),
        )
