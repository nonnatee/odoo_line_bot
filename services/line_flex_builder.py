# -*- coding: utf-8 -*-
"""
Flex Message Builder for Odoo Business Records.
Generates compliant, beautiful LINE Flex Message JSON structures.
"""

def build_quick_reply_items(pills: list) -> dict | None:
    """
    Build quick reply container from a list of action pill definitions.
    
    :param pills: list of dicts [{'label': 'Check Order', 'text': 'My Orders'}, ...]
    :return: LINE quickReply dict or None
    """
    if not pills:
        return None

    items = []
    for pill in pills[:13]:  # LINE allows max 13 quick replies
        label = str(pill.get('label') or pill.get('text', ''))[:20]
        text = str(pill.get('text') or pill.get('label', ''))[:300]
        data = str(pill.get('data') or text)[:300]
        action_type = pill.get('type', 'message')

        if action_type == 'uri' and pill.get('uri'):
            action = {
                'type': 'uri',
                'label': label,
                'uri': pill.get('uri'),
            }
        elif action_type == 'postback':
            action = {
                'type': 'postback',
                'label': label,
                'data': data,
                'displayText': text,
            }
        else:
            action = {
                'type': 'message',
                'label': label,
                'text': text,
            }
        items.append({'type': 'action', 'action': action})

    return {'items': items} if items else None


def build_text_message(text: str, quick_replies: list = None) -> dict:
    """Wrap text in a LINE text message object, optionally with quick replies."""
    msg = {
        'type': 'text',
        'text': (text or '')[:5000],
    }
    qr = build_quick_reply_items(quick_replies)
    if qr:
        msg['quickReply'] = qr
    return msg


def build_sale_order_flex(order, currency_symbol: str = '$', web_base_url: str = '') -> dict:
    """
    Build a rich Sales Order / Quotation Flex Bubble.
    
    :param order: sale.order record or dict with keys
    """
    name = getattr(order, 'name', order.get('name', 'SO000')) if hasattr(order, 'name') or isinstance(order, dict) else 'SO000'
    state = getattr(order, 'state', order.get('state', 'draft')) if hasattr(order, 'state') or isinstance(order, dict) else 'draft'
    amount_total = getattr(order, 'amount_total', order.get('amount_total', 0.0)) if hasattr(order, 'amount_total') or isinstance(order, dict) else 0.0
    date_order = str(getattr(order, 'date_order', order.get('date_order', '')) or '')[:10]
    partner_name = ''
    if hasattr(order, 'partner_id') and order.partner_id:
        partner_name = order.partner_id.name
    elif isinstance(order, dict):
        partner_name = order.get('partner_name', '')

    state_badge_color = '#00B900' if state in ('sale', 'done') else '#F59E0B'
    state_label = 'Confirmed Order' if state in ('sale', 'done') else 'Quotation'

    # Extract up to 4 line items
    lines_contents = []
    order_lines = getattr(order, 'order_line', []) if hasattr(order, 'order_line') else order.get('lines', [])
    for line in list(order_lines)[:4]:
        prod_name = getattr(line, 'name', line.get('name', 'Item')) if hasattr(line, 'name') or isinstance(line, dict) else 'Item'
        qty = getattr(line, 'product_uom_qty', line.get('qty', 1.0)) if hasattr(line, 'product_uom_qty') or isinstance(line, dict) else 1.0
        subtotal = getattr(line, 'price_subtotal', line.get('price_subtotal', 0.0)) if hasattr(line, 'price_subtotal') or isinstance(line, dict) else 0.0
        lines_contents.append({
            'type': 'box',
            'layout': 'horizontal',
            'contents': [
                {'type': 'text', 'text': f'{qty:g}x {prod_name[:20]}', 'size': 'sm', 'color': '#555555', 'flex': 3, 'wrap': False},
                {'type': 'text', 'text': f'{currency_symbol}{subtotal:,.2f}', 'size': 'sm', 'color': '#111111', 'align': 'end', 'flex': 2},
            ],
        })

    bubble = {
        'type': 'bubble',
        'size': 'mega',
        'header': {
            'type': 'box',
            'layout': 'vertical',
            'backgroundColor': '#1E293B',
            'paddingAll': '16px',
            'contents': [
                {
                    'type': 'box',
                    'layout': 'horizontal',
                    'contents': [
                        {'type': 'text', 'text': 'SALES ORDER', 'weight': 'bold', 'color': '#94A3B8', 'size': 'xxs'},
                        {'type': 'text', 'text': state_label, 'weight': 'bold', 'color': state_badge_color, 'size': 'xxs', 'align': 'end'},
                    ],
                },
                {'type': 'text', 'text': name, 'weight': 'bold', 'color': '#FFFFFF', 'size': 'xl', 'margin': 'sm'},
                {'type': 'text', 'text': f'Date: {date_order}' if date_order else 'Odoo ERP', 'color': '#94A3B8', 'size': 'xs', 'margin': 'xs'},
            ],
        },
        'body': {
            'type': 'box',
            'layout': 'vertical',
            'paddingAll': '16px',
            'contents': [
                {
                    'type': 'box',
                    'layout': 'vertical',
                    'margin': 'none',
                    'spacing': 'sm',
                    'contents': lines_contents or [
                        {'type': 'text', 'text': 'Order details logged in ERP', 'size': 'sm', 'color': '#888888'}
                    ],
                },
                {'type': 'separator', 'margin': 'lg'},
                {
                    'type': 'box',
                    'layout': 'horizontal',
                    'margin': 'lg',
                    'contents': [
                        {'type': 'text', 'text': 'Total Amount', 'weight': 'bold', 'size': 'md', 'color': '#1E293B'},
                        {'type': 'text', 'text': f'{currency_symbol}{amount_total:,.2f}', 'weight': 'bold', 'size': 'lg', 'color': '#00B900', 'align': 'end'},
                    ],
                },
            ],
        },
    }

    footer_buttons = []
    order_id = getattr(order, 'id', order.get('id')) if hasattr(order, 'id') or isinstance(order, dict) else None
    if web_base_url and order_id:
        portal_url = f"{web_base_url.rstrip('/')}/my/orders/{order_id}"
        footer_buttons.append({
            'type': 'button',
            'style': 'primary',
            'color': '#00B900',
            'height': 'sm',
            'action': {'type': 'uri', 'label': 'View Order Online', 'uri': portal_url},
        })

    if footer_buttons:
        bubble['footer'] = {
            'type': 'box',
            'layout': 'vertical',
            'spacing': 'sm',
            'paddingAll': '12px',
            'contents': footer_buttons,
        }

    return {
        'type': 'flex',
        'altText': f'Sales Order {name} ({currency_symbol}{amount_total:,.2f})',
        'contents': bubble,
    }


def build_invoice_flex(invoice, currency_symbol: str = '$', web_base_url: str = '') -> dict:
    """Build a rich Invoice & Payment status Flex Bubble."""
    name = getattr(invoice, 'name', invoice.get('name', 'INV/2026/0001')) if hasattr(invoice, 'name') or isinstance(invoice, dict) else 'INV/0001'
    payment_state = getattr(invoice, 'payment_state', invoice.get('payment_state', 'not_paid')) if hasattr(invoice, 'payment_state') or isinstance(invoice, dict) else 'not_paid'
    amount_total = getattr(invoice, 'amount_total', invoice.get('amount_total', 0.0)) if hasattr(invoice, 'amount_total') or isinstance(invoice, dict) else 0.0
    amount_residual = getattr(invoice, 'amount_residual', invoice.get('amount_residual', amount_total)) if hasattr(invoice, 'amount_residual') or isinstance(invoice, dict) else amount_total
    invoice_date_due = str(getattr(invoice, 'invoice_date_due', invoice.get('invoice_date_due', '')) or '')

    is_paid = payment_state in ('paid', 'in_payment')
    status_label = 'PAID' if is_paid else ('PARTIALLY PAID' if payment_state == 'partial' else 'UNPAID')
    status_color = '#00B900' if is_paid else '#EF4444'

    bubble = {
        'type': 'bubble',
        'size': 'mega',
        'header': {
            'type': 'box',
            'layout': 'vertical',
            'backgroundColor': '#0F172A',
            'paddingAll': '16px',
            'contents': [
                {
                    'type': 'box',
                    'layout': 'horizontal',
                    'contents': [
                        {'type': 'text', 'text': 'CUSTOMER INVOICE', 'weight': 'bold', 'color': '#94A3B8', 'size': 'xxs'},
                        {'type': 'text', 'text': status_label, 'weight': 'bold', 'color': status_color, 'size': 'xxs', 'align': 'end'},
                    ],
                },
                {'type': 'text', 'text': name, 'weight': 'bold', 'color': '#FFFFFF', 'size': 'xl', 'margin': 'sm'},
                {'type': 'text', 'text': f'Due Date: {invoice_date_due}' if invoice_date_due else 'Payment Due', 'color': '#94A3B8', 'size': 'xs', 'margin': 'xs'},
            ],
        },
        'body': {
            'type': 'box',
            'layout': 'vertical',
            'paddingAll': '16px',
            'contents': [
                {
                    'type': 'box',
                    'layout': 'horizontal',
                    'contents': [
                        {'type': 'text', 'text': 'Total Invoiced', 'size': 'sm', 'color': '#64748B'},
                        {'type': 'text', 'text': f'{currency_symbol}{amount_total:,.2f}', 'size': 'sm', 'color': '#1E293B', 'align': 'end', 'weight': 'bold'},
                    ],
                },
                {
                    'type': 'box',
                    'layout': 'horizontal',
                    'margin': 'sm',
                    'contents': [
                        {'type': 'text', 'text': 'Balance Due', 'size': 'md', 'color': '#1E293B', 'weight': 'bold'},
                        {'type': 'text', 'text': f'{currency_symbol}{amount_residual:,.2f}', 'size': 'lg', 'color': status_color, 'align': 'end', 'weight': 'bold'},
                    ],
                },
            ],
        },
    }

    inv_id = getattr(invoice, 'id', invoice.get('id')) if hasattr(invoice, 'id') or isinstance(invoice, dict) else None
    if web_base_url and inv_id:
        pay_url = f"{web_base_url.rstrip('/')}/my/invoices/{inv_id}"
        bubble['footer'] = {
            'type': 'box',
            'layout': 'vertical',
            'paddingAll': '12px',
            'contents': [
                {
                    'type': 'button',
                    'style': 'primary',
                    'color': '#00B900',
                    'height': 'sm',
                    'action': {'type': 'uri', 'label': 'Pay Online' if not is_paid else 'View Invoice', 'uri': pay_url},
                }
            ],
        }

    return {
        'type': 'flex',
        'altText': f'Invoice {name} - Balance: {currency_symbol}{amount_residual:,.2f}',
        'contents': bubble,
    }


def build_product_catalog_carousel(products: list, currency_symbol: str = '$', web_base_url: str = '') -> dict:
    """Build a multi-card Product Carousel for eCommerce & inventory display."""
    bubbles = []
    for prod in products[:10]:  # Carousel supports up to 10 bubbles
        name = getattr(prod, 'name', prod.get('name', 'Product')) if hasattr(prod, 'name') or isinstance(prod, dict) else 'Product'
        price = getattr(prod, 'list_price', prod.get('list_price', 0.0)) if hasattr(prod, 'list_price') or isinstance(prod, dict) else 0.0
        code = getattr(prod, 'default_code', prod.get('default_code', '')) if hasattr(prod, 'default_code') or isinstance(prod, dict) else ''
        prod_id = getattr(prod, 'id', prod.get('id', 1)) if hasattr(prod, 'id') or isinstance(prod, dict) else 1

        img_url = f"{web_base_url.rstrip('/')}/web/image/product.template/{prod_id}/image_512" if web_base_url else 'https://via.placeholder.com/400x300.png?text=Product'

        bubble = {
            'type': 'bubble',
            'size': 'kilo',
            'hero': {
                'type': 'image',
                'url': img_url,
                'size': 'full',
                'aspectRatio': '4:3',
                'aspectMode': 'cover',
            },
            'body': {
                'type': 'box',
                'layout': 'vertical',
                'paddingAll': '12px',
                'contents': [
                    {'type': 'text', 'text': name, 'weight': 'bold', 'size': 'sm', 'wrap': True, 'maxLines': 2},
                    {'type': 'text', 'text': f'Code: {code}' if code else 'In Stock', 'size': 'xxs', 'color': '#888888', 'margin': 'xs'},
                    {'type': 'text', 'text': f'{currency_symbol}{price:,.2f}', 'weight': 'bold', 'size': 'md', 'color': '#00B900', 'margin': 'sm'},
                ],
            },
            'footer': {
                'type': 'box',
                'layout': 'vertical',
                'paddingAll': '8px',
                'contents': [
                    {
                        'type': 'button',
                        'style': 'secondary',
                        'height': 'sm',
                        'action': {
                            'type': 'message',
                            'label': 'Inquire / Buy',
                            'text': f'I would like to inquire about {name} (ID: {prod_id})',
                        },
                    }
                ],
            },
        }
        bubbles.append(bubble)

    if not bubbles:
        bubbles.append({
            'type': 'bubble',
            'body': {'type': 'box', 'layout': 'vertical', 'contents': [{'type': 'text', 'text': 'No products found.'}]},
        })

    return {
        'type': 'flex',
        'altText': f'Product Catalog ({len(bubbles)} items)',
        'contents': {
            'type': 'carousel',
            'contents': bubbles,
        },
    }
