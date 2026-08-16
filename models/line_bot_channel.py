# -*- coding: utf-8 -*-
import json
import logging
from odoo import api, fields, models
from odoo.exceptions import UserError
from ..services.line_api_service import LineApiService

_logger = logging.getLogger(__name__)


class LineBotChannel(models.Model):
    """Configuration record for a LINE Official Account (Messaging API)."""

    _name = 'line.bot.channel'
    _description = 'LINE Bot Channel'
    _order = 'name'

    name = fields.Char(string='Channel Name', required=True, default='My LINE Bot')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)

    # ── LINE Credentials ───────────────────────────────────────────────────────
    channel_id = fields.Char(string='LINE Channel ID', required=True, help='From LINE Developers Console')
    channel_secret = fields.Char(
        string='LINE Channel Secret', required=True, help='Used for HMAC-SHA256 signature verification'
    )
    channel_access_token = fields.Char(
        string='Channel Access Token (Long-Lived)', required=True, help='Issue from LINE Developers Messaging API tab'
    )
    basic_id = fields.Char(string='LINE @Basic ID', readonly=True, help='Bot @username registered on LINE')
    bot_display_name = fields.Char(string='Bot Display Name', readonly=True)

    # ── Status & Webhook ───────────────────────────────────────────────────────
    status = fields.Selection([
        ('draft', 'Not Verified'),
        ('active', 'Connected & Active'),
        ('error', 'Connection Error'),
    ], default='draft', readonly=True, tracking=True)
    error_message = fields.Text(string='Last Error', readonly=True)

    custom_webhook_base = fields.Char(
        string='Public HTTPS Base URL',
        help='Override web.base.url for webhook endpoint registration (e.g. https://myodoo.example.com or ngrok URL)',
    )
    webhook_url = fields.Char(string='Webhook URL', compute='_compute_urls')
    bot_link = fields.Char(string='Bot Link', compute='_compute_urls')

    # ── Routing & Mode ─────────────────────────────────────────────────────────
    routing_mode = fields.Selection([
        ('hybrid', 'Hybrid: AI Bot with Live Agent Handover'),
        ('ai_only', 'AI Bot Only'),
        ('human_only', 'Live Agent Only (Discuss Bridge)'),
    ], default='hybrid', required=True, string='Interaction Mode')

    auto_create_partner = fields.Boolean(
        string='Auto-Create Partners', default=True,
        help='Automatically create a new Contact (res.partner) for new LINE followers / callers',
    )

    # ── AI Engine Configuration ────────────────────────────────────────────────
    ai_engine_mode = fields.Selection([
        ('auto', 'Auto-detect (MCP Gateway if installed, else Direct AI)'),
        ('mcp', 'MCP Gateway (odoo_mcp_manager bridge)'),
        ('direct', 'Direct AI API (Standalone)'),
    ], default='auto', required=True, string='AI Engine')

    ai_provider = fields.Selection([
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic (Claude)'),
        ('gemini', 'Google Gemini'),
        ('ollama', 'Ollama / Custom Endpoint'),
    ], default='openai', string='Direct AI Provider')

    ai_api_key = fields.Char(string='AI API Key')
    ai_model = fields.Char(string='AI Model ID', default='gpt-4o-mini')
    ai_base_url = fields.Char(string='AI Base URL (Optional)', help='e.g. http://localhost:11434 for Ollama')
    system_prompt = fields.Text(
        string='Bot Persona / System Prompt',
        default="You are a professional, helpful customer service AI for our company on LINE. Provide clear, polite, and concise answers."
    )

    # ── Messages & Quick Replies ───────────────────────────────────────────────
    welcome_message = fields.Text(
        string='Welcome Greeting',
        default="Hello! 👋 Welcome to our LINE Official Account. How can we help you today with your orders, products, or inquiries?"
    )
    handover_message = fields.Text(
        string='Handover Message',
        default="I am transferring you to a customer service agent. 👤 Please wait a moment while an operator joins the chat!"
    )
    quick_replies_json = fields.Text(
        string='Quick Reply Action Pills (JSON)',
        default='[\n  {"label": "🛍️ Products", "text": "Products"},\n  {"label": "📦 My Orders", "text": "My Orders"},\n  {"label": "📄 My Invoices", "text": "My Invoices"},\n  {"label": "👤 Live Agent", "text": "Agent"}\n]',
        help='JSON list of quick reply pill buttons attached to bot responses',
    )

    # ── Statistics ─────────────────────────────────────────────────────────────
    user_count = fields.Integer(string='LINE Followers', compute='_compute_stats')
    conversation_count = fields.Integer(string='Active Chats', compute='_compute_stats')

    @api.depends('channel_id', 'custom_webhook_base', 'basic_id')
    def _compute_urls(self) -> None:
        params = self.env['ir.config_parameter'].sudo()
        for rec in self:
            base_url = (rec.custom_webhook_base or '').rstrip('/') or \
                       params.get_param('web.base.url', '').rstrip('/')
            if base_url and rec.id:
                rec.webhook_url = f"{base_url}/line/webhook/{rec.id}"
            else:
                rec.webhook_url = f"{base_url}/line/webhook" if base_url else ''

            rec.bot_link = f"https://line.me/R/ti/p/{rec.basic_id}" if rec.basic_id else ''

    def _compute_stats(self) -> None:
        for rec in self:
            rec.user_count = self.env['line.bot.user'].search_count([('channel_id', '=', rec.id)])
            rec.conversation_count = self.env['line.bot.conversation'].search_count([('channel_id', '=', rec.id)])

    def action_test_connection(self):
        """Test credentials against LINE API /v2/bot/info."""
        self.ensure_one()
        if not self.channel_access_token:
            raise UserError('Please fill in the Channel Access Token first.')

        api = LineApiService(self.channel_access_token)
        info = api.get_bot_info()
        if info:
            self.write({
                'status': 'active',
                'basic_id': info.get('basicId') or info.get('userId'),
                'bot_display_name': info.get('displayName'),
                'error_message': False,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'LINE Connection Verified',
                    'message': f"Successfully connected to LINE Bot: {info.get('displayName')} ({info.get('basicId')})",
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            self.write({
                'status': 'error',
                'error_message': 'Failed to authenticate with LINE API. Please verify your Channel Access Token.',
            })
            raise UserError('Failed to connect to LINE API. Please check your Channel Access Token.')

    def action_set_webhook(self):
        """Register Webhook URL with LINE Messaging API."""
        self.ensure_one()
        if not self.webhook_url or not self.webhook_url.startswith('https://'):
            raise UserError(
                'A public HTTPS Webhook URL is required by LINE.\n\n'
                'Please configure the "Public HTTPS Base URL" on this channel or in System Parameters.'
            )
        api = LineApiService(self.channel_access_token)
        if api.set_webhook_endpoint(self.webhook_url):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Webhook Registered',
                    'message': f"Webhook URL {self.webhook_url} was successfully registered with LINE!",
                    'type': 'success',
                }
            }
        raise UserError('LINE API rejected the webhook endpoint registration.')

    def get_quick_replies(self) -> list:
        """Parse JSON quick reply pills."""
        self.ensure_one()
        if not self.quick_replies_json:
            return []
        try:
            pills = json.loads(self.quick_replies_json)
            return pills if isinstance(pills, list) else []
        except Exception:
            return []
