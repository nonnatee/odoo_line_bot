# -*- coding: utf-8 -*-
{
    'name': 'Odoo LINE Bot Gateway',
    'version': '19.0.1.0.0',
    'category': 'Productivity/AI/Social',
    'summary': 'Unified LINE Messaging API, AI Assistant & Discuss Live Chat Gateway for Odoo',
    'description': """
Odoo LINE Bot Gateway
=====================
Enterprise turnkey solution connecting LINE Official Accounts (Messaging API) to Odoo 19.

Key Features:
-------------
* **Conversational AI & Tool Calling**: Direct LLM integration (OpenAI, Anthropic, Gemini) with seamless bridge to MCP Gateway (`odoo_mcp_manager`).
* **Live Chat / Discuss 2-Way Sync**: Dedicated Discuss channel per LINE user with real-time operator chat and AI-to-Human handover.
* **Rich Flex Messages**: Beautiful interactive cards for Quotations, Invoices, Products, and Support Tickets.
* **Profile & Partner Auto-Sync**: Automatically synchronizes LINE user profiles with `res.partner`.
* **Push Notification Service**: Targeted push messages and Flex cards for sales, marketing, and notifications.
* **Rich Menu Designer**: Configure and publish persistent navigation menus directly to LINE.
    """,
    'author': 'Nonnatee Kanjana',
    'website': 'https://github.com/nonnatee/odoo_line_bot',
    'depends': [
        'base',
        'mail',
        'web',
    ],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'data/default_templates.xml',
        'wizards/line_push_wizard_views.xml',
        'wizards/test_channel_wizard_views.xml',
        'views/line_bot_channel_views.xml',
        'views/line_bot_user_views.xml',
        'views/line_bot_conversation_views.xml',
        'views/line_rich_menu_views.xml',
        'views/discuss_channel_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'external_dependencies': {
        'python': ['requests', 'cryptography'],
    },
    'images': ['static/description/banner.png'],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
