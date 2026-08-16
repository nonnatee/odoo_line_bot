# -*- coding: utf-8 -*-
"""
LINE Webhook Controller — Secure endpoint with HMAC-SHA256 signature verification and async worker.
"""
import base64
import hashlib
import hmac
import json
import logging
import threading
from odoo import http
from odoo.http import request
from .line_adapter import LineAdapter

_logger = logging.getLogger(__name__)


class LineWebhookController(http.Controller):
    """Universal Webhook Endpoint for LINE Official Accounts."""

    _adapter = LineAdapter()

    @http.route(
        ['/line/webhook/<int:channel_id>', '/line/webhook'],
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def webhook(self, channel_id: int = None, **kw) -> object:
        """
        Receive LINE Webhook events.
        
        1. Validate X-Line-Signature using Channel Secret.
        2. Normalize payload.
        3. Acknowledge HTTP 200 immediately.
        4. Spawn background thread with isolated database cursor to process events.
        """
        body_bytes = request.httprequest.data or b''
        signature = request.httprequest.headers.get('X-Line-Signature', '')

        # Resolve channel record
        channel_model = request.env['line.bot.channel'].sudo()
        channel = None
        if channel_id:
            channel = channel_model.browse(channel_id)
            if not channel.exists():
                channel = None

        if not channel:
            # Fallback: search for active channels and test signature
            channels = channel_model.search([('status', '=', 'active')])
            if not channels:
                channels = channel_model.search([], limit=1)
            for c in channels:
                if self._verify_signature(c.channel_secret, signature, body_bytes):
                    channel = c
                    break

        if not channel:
            _logger.warning('LineWebhookController: no matching channel found for incoming webhook')
            return self._json_response({'error': 'Channel not found'}, status=404)

        # Verify HMAC-SHA256 signature
        if not self._verify_signature(channel.channel_secret, signature, body_bytes):
            _logger.warning('LineWebhookController: invalid X-Line-Signature for channel %s', channel.name)
            return self._json_response({'error': 'Invalid signature'}, status=401)

        # Parse JSON
        try:
            raw_payload = json.loads(body_bytes.decode('utf-8') or '{}')
        except Exception as exc:
            _logger.error('LineWebhookController: JSON decode error — %s', exc)
            return self._json_response({'error': 'Invalid JSON'}, status=400)

        # Normalize events
        normalized_events = self._adapter.normalize(raw_payload)
        if not normalized_events:
            return self._json_response({'status': 'ok'})

        # Capture environment context for background thread
        env = request.env
        target_channel_id = channel.id

        def _worker():
            """Background processing thread with dedicated database cursor."""
            from ..services.line_bot_service import LineBotService
            try:
                with env.registry.cursor() as new_cr:
                    thread_env = env(cr=new_cr)
                    service = LineBotService(thread_env)
                    ch = thread_env['line.bot.channel'].sudo().browse(target_channel_id)
                    for event in normalized_events:
                        service.process_event(event, ch)
            except Exception as e:
                _logger.exception('LineWebhookController: async background processing failed — %s', e)

        # Start worker thread
        threading.Thread(target=_worker, daemon=True).start()

        # Immediate 200 OK to prevent LINE timeout retries
        return self._json_response({'status': 'ok'})

    @http.route('/line/health', type='http', auth='none', methods=['GET'], csrf=False)
    def health(self, **kw) -> object:
        """Public health check endpoint."""
        return self._json_response({
            'status': 'healthy',
            'gateway': 'Odoo LINE Bot Gateway',
            'version': '19.0.1.0.0',
        })

    @staticmethod
    def _verify_signature(secret: str, signature: str, body: bytes) -> bool:
        """Validate LINE HMAC-SHA256 signature."""
        if not secret or not signature:
            return False
        try:
            hash_val = hmac.new(
                secret.encode('utf-8'),
                body,
                hashlib.sha256,
            ).digest()
            expected_signature = base64.b64encode(hash_val).decode('utf-8')
            return hmac.compare_digest(expected_signature, signature)
        except Exception as exc:
            _logger.debug('Line signature verification error: %s', exc)
            return False

    @staticmethod
    def _json_response(data: dict, status: int = 200) -> object:
        """Make JSON HTTP response."""
        return request.make_response(
            json.dumps(data, ensure_ascii=False),
            headers=[('Content-Type', 'application/json; charset=utf-8')],
            status=status,
        )
