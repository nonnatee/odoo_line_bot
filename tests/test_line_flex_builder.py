# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from ..services.line_flex_builder import (
    build_text_message,
    build_sale_order_flex,
    build_invoice_flex,
    build_product_catalog_carousel,
    build_quick_reply_items,
)


class TestLineFlexBuilder(TransactionCase):
    """Test Flex Message JSON structure compliance."""

    def test_build_quick_reply_items(self):
        pills = [
            {'label': 'Products', 'text': 'Show Products'},
            {'label': 'Website', 'type': 'uri', 'uri': 'https://example.com'},
        ]
        qr = build_quick_reply_items(pills)
        self.assertIsNotNone(qr)
        self.assertEqual(len(qr['items']), 2)
        self.assertEqual(qr['items'][0]['action']['type'], 'message')
        self.assertEqual(qr['items'][1]['action']['type'], 'uri')

    def test_build_text_message_with_quick_reply(self):
        pills = [{'label': 'Help', 'text': 'Help'}]
        msg = build_text_message('Welcome!', pills)
        self.assertEqual(msg['type'], 'text')
        self.assertEqual(msg['text'], 'Welcome!')
        self.assertIn('quickReply', msg)

    def test_build_sale_order_flex_mock(self):
        order_dict = {
            'name': 'SO001',
            'state': 'sale',
            'amount_total': 1500.00,
            'date_order': '2026-08-17',
            'lines': [{'name': 'Laptop Stand', 'qty': 2, 'price_subtotal': 500.00}],
        }
        flex = build_sale_order_flex(order_dict, '$', 'https://odoo.example.com')
        self.assertEqual(flex['type'], 'flex')
        self.assertEqual(flex['contents']['type'], 'bubble')
        self.assertIn('SO001', flex['altText'])

    def test_build_invoice_flex_mock(self):
        inv_dict = {
            'name': 'INV/2026/001',
            'payment_state': 'not_paid',
            'amount_total': 2500.00,
            'amount_residual': 2500.00,
            'invoice_date_due': '2026-09-01',
        }
        flex = build_invoice_flex(inv_dict, '$', 'https://odoo.example.com')
        self.assertEqual(flex['type'], 'flex')
        self.assertEqual(flex['contents']['type'], 'bubble')

    def test_build_product_catalog_carousel_mock(self):
        products = [
            {'name': 'Desk Lamp', 'list_price': 45.00, 'default_code': 'LMP01', 'id': 1},
            {'name': 'Ergo Chair', 'list_price': 250.00, 'default_code': 'CHR01', 'id': 2},
        ]
        flex = build_product_catalog_carousel(products, '$', 'https://odoo.example.com')
        self.assertEqual(flex['type'], 'flex')
        self.assertEqual(flex['contents']['type'], 'carousel')
        self.assertEqual(len(flex['contents']['contents']), 2)
