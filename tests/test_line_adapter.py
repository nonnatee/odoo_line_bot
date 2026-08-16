# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from ..controllers.line_adapter import LineAdapter


class TestLineAdapter(TransactionCase):
    """Test webhook payload normalization and response formatting."""

    def setUp(self):
        super().setUp()
        self.adapter = LineAdapter()

    def test_normalize_text_message(self):
        """Test normalization of standard text message event."""
        payload = {
            'destination': 'U1234567890',
            'events': [
                {
                    'type': 'message',
                    'message': {'type': 'text', 'id': 'msg_001', 'text': 'Check my invoice'},
                    'timestamp': 1620000000000,
                    'source': {'type': 'user', 'userId': 'U_user_99'},
                    'replyToken': 'token_abc123',
                }
            ],
        }

        events = self.adapter.normalize(payload)
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev['type'], 'message')
        self.assertEqual(ev['user_id'], 'U_user_99')
        self.assertEqual(ev['reply_token'], 'token_abc123')
        self.assertEqual(ev['text'], 'Check my invoice')
        self.assertEqual(ev['message_type'], 'text')

    def test_normalize_postback(self):
        """Test normalization of postback click event."""
        payload = {
            'events': [
                {
                    'type': 'postback',
                    'postback': {'data': 'action=handover'},
                    'source': {'type': 'user', 'userId': 'U_user_88'},
                    'replyToken': 'token_pb_123',
                }
            ]
        }

        events = self.adapter.normalize(payload)
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev['type'], 'postback')
        self.assertEqual(ev['postback_data'], 'action=handover')

    def test_format_response_string(self):
        """Test converting string to LINE text object."""
        res = self.adapter.format_response('Hello world!')
        self.assertEqual(res['type'], 'text')
        self.assertEqual(res['text'], 'Hello world!')
