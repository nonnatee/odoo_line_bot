# -*- coding: utf-8 -*-
import json
from odoo import fields, models
from ..services.line_api_service import LineApiService


class LineTestChannelWizard(models.TransientModel):
    """Interactive diagnostic wizard to test LINE Bot connection and webhook reachability."""

    _name = 'line.test.channel.wizard'
    _description = 'Test LINE Channel Connection'

    channel_id = fields.Many2one('line.bot.channel', string='LINE Channel', required=True)
    test_type = fields.Selection([
        ('info', 'Verify Credentials & Bot Info'),
        ('webhook', 'Test Webhook Endpoint Reachability'),
    ], default='info', required=True, string='Test Operation')

    result_status = fields.Selection([
        ('pending', 'Pending Test'),
        ('success', 'Passed'),
        ('failed', 'Failed'),
    ], default='pending', readonly=True)
    result_details = fields.Text(string='Diagnostic Details', readonly=True)

    def action_run_test(self):
        """Execute test and display diagnostic output."""
        self.ensure_one()
        api = LineApiService(self.channel_id.channel_access_token)

        if self.test_type == 'info':
            info = api.get_bot_info()
            if info:
                self.write({
                    'result_status': 'success',
                    'result_details': json.dumps(info, indent=2),
                })
            else:
                self.write({
                    'result_status': 'failed',
                    'result_details': 'Failed to connect. Check Channel Access Token.',
                })

        elif self.test_type == 'webhook':
            res = api.test_webhook_endpoint(self.channel_id.webhook_url)
            status = 'success' if res.get('success') else 'failed'
            self.write({
                'result_status': status,
                'result_details': json.dumps(res, indent=2),
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'line.test.channel.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
