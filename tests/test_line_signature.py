# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
from odoo.tests.common import TransactionCase
from ..controllers.line_webhook_controller import LineWebhookController


class TestLineSignature(TransactionCase):
    """Test HMAC-SHA256 signature verification for LINE webhooks."""

    def setUp(self):
        super().setUp()
        self.secret = 'test_secret_12345'
        self.body = b'{"events":[{"type":"message","text":"hello"}]}'

    def test_valid_signature(self):
        """Verify that a properly signed payload passes verification."""
        hash_val = hmac.new(
            self.secret.encode('utf-8'),
            self.body,
            hashlib.sha256,
        ).digest()
        valid_sig = base64.b64encode(hash_val).decode('utf-8')

        self.assertTrue(
            LineWebhookController._verify_signature(self.secret, valid_sig, self.body),
            'Valid signature should return True',
        )

    def test_tampered_payload_signature(self):
        """Verify that tampering with payload causes verification to fail."""
        hash_val = hmac.new(
            self.secret.encode('utf-8'),
            self.body,
            hashlib.sha256,
        ).digest()
        valid_sig = base64.b64encode(hash_val).decode('utf-8')
        tampered_body = b'{"events":[{"type":"message","text":"hacked"}]}'

        self.assertFalse(
            LineWebhookController._verify_signature(self.secret, valid_sig, tampered_body),
            'Tampered body should fail signature check',
        )

    def test_invalid_secret_signature(self):
        """Verify that mismatching secret fails verification."""
        hash_val = hmac.new(
            'wrong_secret'.encode('utf-8'),
            self.body,
            hashlib.sha256,
        ).digest()
        wrong_sig = base64.b64encode(hash_val).decode('utf-8')

        self.assertFalse(
            LineWebhookController._verify_signature(self.secret, wrong_sig, self.body),
            'Wrong secret signature should return False',
        )
