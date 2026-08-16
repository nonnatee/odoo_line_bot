# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestDiscussSync(TransactionCase):
    """Test Discuss channel creation, user linking, and conversation memory."""

    def setUp(self):
        super().setUp()
        self.channel = self.env['line.bot.channel'].create({
            'name': 'Test LINE Channel',
            'channel_id': '1234567890',
            'channel_secret': 'secret_xyz',
            'channel_access_token': 'token_xyz',
            'routing_mode': 'hybrid',
        })
        self.line_user = self.env['line.bot.user'].get_or_create(self.channel, 'U_test_user_007')

    def test_user_and_partner_creation(self):
        """Verify LINE user creates linked res.partner automatically."""
        self.assertTrue(self.line_user.partner_id, 'Partner should be auto-created')
        self.assertIn(self.line_user.partner_id, self.env['res.partner'].search([]))

    def test_conversation_and_discuss_channel(self):
        """Verify conversation creates and links discuss.channel."""
        conv = self.env['line.bot.conversation'].get_or_create(self.channel, self.line_user)
        self.assertEqual(conv.state, 'bot')

        discuss_chan = conv.get_or_create_discuss_channel()
        self.assertTrue(discuss_chan.is_line_channel)
        self.assertEqual(discuss_chan.line_conversation_id, conv)

    def test_handover_state_transition(self):
        """Verify switching between AI bot and live agent mode."""
        conv = self.env['line.bot.conversation'].get_or_create(self.channel, self.line_user)
        self.assertEqual(conv.state, 'bot')

        conv.action_switch_to_human()
        self.assertEqual(conv.state, 'human')

        conv.action_switch_to_bot()
        self.assertEqual(conv.state, 'bot')
