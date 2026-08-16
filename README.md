# Odoo LINE Bot Gateway (`odoo_line_bot`)

An enterprise-grade Odoo 19.0+ module connecting **LINE Official Accounts** (Messaging API) to Odoo ERP with Conversational AI, MCP Tool Calling, Live Chat bridging, and Rich Flex Messages.

---

## Key Features

1. **Dual-Mode AI Engine**:
   - **Standalone Mode**: Direct integration with OpenAI (GPT-4o, GPT-4o-mini), Anthropic (Claude 3.5 Sonnet), and Google Gemini (Gemini 1.5/2.5 Flash).
   - **MCP Gateway Bridged Mode**: Seamlessly integrates with [`odoo_mcp_manager`](file:///C:/Users/nonna/Downloads/odoo_mcp_manager) to allow AI assistants to query and execute live ERP tools (`search_records`, `create_record`, `analyze_records`, etc.).
2. **Discuss Live Chat & Human Handover**:
   - Real-time 2-way synchronization with Odoo Discuss (`discuss.channel`).
   - Automatically pauses AI Bot when an operator takes over or when the customer asks for a live agent ("agent", "human", "ติดต่อเจ้าหน้าที่").
   - Replies typed by backend Odoo operators inside Discuss are pushed directly to the user's LINE screen.
3. **Rich LINE UI & Flex Messages**:
   - Built-in Flex Cards for **Sales Orders / Quotations**, **Customer Invoices & Payments**, **Product Catalogs (Carousel)**, and **Helpdesk Tickets**.
   - One-tap **Quick Reply Action Pills**.
   - Built-in **Rich Menu Manager** to configure and publish persistent navigation menus to LINE.
4. **Partner & Contact Auto-Sync**:
   - Synchronizes LINE user profile (display name, avatar image, status message) with Odoo `res.partner`.
5. **Targeted Push Notification Service**:
   - Interactive wizard to send plain text or Flex cards to individual contacts or broadcast to all active followers.
6. **Resilient Asynchronous Webhooks**:
   - Cryptographically validates `X-Line-Signature` using HMAC-SHA256.
   - Responds with HTTP 200 OK immediately and executes AI processing in background daemon threads with dedicated database cursors to eliminate timeout retries.

---

## Configuration & Setup Guide

### 1. LINE Developers Console Setup
1. Create a Provider and a **Messaging API** channel in the [LINE Developers Console](https://developers.line.biz/).
2. Copy:
   - **Channel ID**
   - **Channel Secret** (under Basic settings)
   - **Channel Access Token (long-lived)** (under Messaging API settings)

### 2. Odoo Configuration
1. In Odoo, navigate to **LINE Bot → Configuration → Channels → New**.
2. Fill in:
   - **Channel Name** (e.g. *Sales LINE OA*)
   - **LINE Channel ID**
   - **LINE Channel Secret**
   - **Channel Access Token**
   - **Routing Mode**: *Hybrid (AI Bot with Live Agent Handover)*
   - **AI Engine Mode**: *Auto-detect* or *Direct AI*
3. Click **Test Connection**. Odoo calls `GET /v2/bot/info` to verify credentials.
4. Set the **Public HTTPS Base URL** (e.g., `https://your-odoo-domain.com` or ngrok URL for local development).
5. Click **Register Webhook** to automatically set the webhook URL on LINE, or copy the generated Webhook URL and paste it into the LINE Developers Console.
6. Enable **Use webhook** in the LINE Developers Console.

---

## File Structure

```
odoo_line_bot/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   ├── line_adapter.py              # Normalizes LINE events & formats responses
│   └── line_webhook_controller.py   # HMAC-SHA256 verification & async worker
├── data/
│   └── default_templates.xml        # System parameters & default configurations
├── models/
│   ├── __init__.py
│   ├── discuss_channel.py           # Discuss Channel extension for LINE
│   ├── line_bot_channel.py          # Channel credentials, AI settings, routing modes
│   ├── line_bot_conversation.py     # Conversation memory & AI/Human handover state
│   ├── line_bot_message.py          # Audit log of messages and tool tracking
│   ├── line_bot_user.py             # LINE user profile linked to res.partner
│   ├── line_rich_menu.py            # Rich menu designer & publisher
│   ├── mail_message.py              # Discuss chatter hook pushing operator replies to LINE
│   ├── res_config_settings.py       # Global settings
│   └── res_partner.py               # Contact extension with LINE actions
├── security/
│   ├── ir.model.access.csv
│   └── res_groups.xml               # Security groups
├── services/
│   ├── __init__.py
│   ├── line_ai_client.py            # Standalone direct AI client (OpenAI/Claude/Gemini)
│   ├── line_api_service.py          # Low-level LINE Messaging API client
│   ├── line_bot_service.py          # Central dispatch & MCP gateway bridge
│   └── line_flex_builder.py         # JSON Flex Message builders for Odoo records
├── static/
│   └── description/
│       └── index.html
├── tests/
│   ├── __init__.py
│   ├── test_discuss_sync.py
│   ├── test_line_adapter.py
│   ├── test_line_flex_builder.py
│   └── test_line_signature.py
├── views/
│   ├── discuss_channel_views.xml
│   ├── line_bot_channel_views.xml
│   ├── line_bot_conversation_views.xml
│   ├── line_bot_user_views.xml
│   ├── line_rich_menu_views.xml
│   ├── menus.xml
│   ├── res_config_settings_views.xml
│   └── res_partner_views.xml
└── wizards/
    ├── __init__.py
    ├── line_push_wizard.py          # Targeted push notification & Flex composer
    ├── line_push_wizard_views.xml
    ├── test_channel_wizard.py       # Connection test & diagnostic wizard
    └── test_channel_wizard_views.xml
```

---

## License
Licensed under LGPL-3.
