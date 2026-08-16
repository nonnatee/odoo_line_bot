# -*- coding: utf-8 -*-
import json
import logging
import requests

_logger = logging.getLogger(__name__)

LINE_API_BASE = 'https://api.line.me/v2/bot'
LINE_DATA_BASE = 'https://api-data.line.me/v2/bot'


class LineApiService:
    """Low-level client for the LINE Messaging API."""

    def __init__(self, channel_access_token: str):
        self.channel_access_token = (channel_access_token or '').strip()
        self.headers = {
            'Authorization': f'Bearer {self.channel_access_token}',
            'Content-Type': 'application/json',
        }

    # ── Message Delivery ──────────────────────────────────────────────────────

    def reply_message(self, reply_token: str, messages: list | dict, notification_disabled: bool = False) -> bool:
        """
        Send a reply message using a reply token.

        :param reply_token: Token from the webhook event
        :param messages: List of LINE message objects (dict or list of dicts)
        :param notification_disabled: If True, user won't get a push sound
        :return: True on success, False on error
        """
        if not self.channel_access_token or not reply_token or not messages:
            _logger.warning('LineApiService.reply_message: missing token or messages')
            return False

        if isinstance(messages, dict):
            messages = [messages]

        # LINE allows max 5 messages per reply
        messages = messages[:5]

        url = f'{LINE_API_BASE}/message/reply'
        payload = {
            'replyToken': reply_token,
            'messages': messages,
            'notificationDisabled': notification_disabled,
        }

        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                _logger.info('LineApiService: reply sent successfully (replyToken=%.10s...)', reply_token)
                return True
            _logger.error('LineApiService: reply failed (HTTP %s): %s', resp.status_code, resp.text)
            return False
        except requests.RequestException as e:
            _logger.error('LineApiService: network error sending reply — %s', e)
            return False

    def push_message(self, to_user_id: str, messages: list | dict, notification_disabled: bool = False) -> bool:
        """
        Send a push message to a specific LINE user.

        :param to_user_id: LINE user ID ('Uxxxxxxxxx')
        :param messages: List of LINE message objects (dict or list of dicts)
        :param notification_disabled: If True, user won't get a push sound
        :return: True on success, False on error
        """
        if not self.channel_access_token or not to_user_id or not messages:
            _logger.warning('LineApiService.push_message: missing token, user_id, or messages')
            return False

        if isinstance(messages, dict):
            messages = [messages]

        messages = messages[:5]

        url = f'{LINE_API_BASE}/message/push'
        payload = {
            'to': to_user_id,
            'messages': messages,
            'notificationDisabled': notification_disabled,
        }

        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                _logger.info('LineApiService: push sent successfully to %s', to_user_id)
                return True
            _logger.error('LineApiService: push failed (HTTP %s): %s', resp.status_code, resp.text)
            return False
        except requests.RequestException as e:
            _logger.error('LineApiService: network error sending push — %s', e)
            return False

    def multicast_message(self, to_user_ids: list, messages: list | dict) -> bool:
        """Send push message to multiple LINE users (up to 500)."""
        if not self.channel_access_token or not to_user_ids or not messages:
            return False

        if isinstance(messages, dict):
            messages = [messages]

        url = f'{LINE_API_BASE}/message/multicast'
        payload = {
            'to': to_user_ids[:500],
            'messages': messages[:5],
        }

        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=20)
            return resp.status_code == 200
        except requests.RequestException as e:
            _logger.error('LineApiService: multicast error — %s', e)
            return False

    # ── User Profile & Bot Info ────────────────────────────────────────────────

    def get_profile(self, user_id: str) -> dict | None:
        """
        Fetch the user's public LINE profile.

        :return: Dict with displayName, userId, pictureUrl, statusMessage, language
        """
        if not self.channel_access_token or not user_id:
            return None

        url = f'{LINE_API_BASE}/profile/{user_id}'
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            _logger.warning('LineApiService: get_profile failed for %s (HTTP %s)', user_id, resp.status_code)
            return None
        except requests.RequestException as e:
            _logger.error('LineApiService: network error fetching profile — %s', e)
            return None

    def get_bot_info(self) -> dict | None:
        """
        Fetch bot information to validate credentials.

        :return: Dict with userId, basicId, displayName, pictureUrl, chatMode, markAsReadMode
        """
        if not self.channel_access_token:
            return None

        url = f'{LINE_API_BASE}/info'
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            _logger.warning('LineApiService: get_bot_info failed (HTTP %s): %s', resp.status_code, resp.text)
            return None
        except requests.RequestException as e:
            _logger.error('LineApiService: network error fetching bot info — %s', e)
            return None

    def get_message_content(self, message_id: str) -> bytes | None:
        """Download binary content (image, video, audio) of a user message."""
        if not self.channel_access_token or not message_id:
            return None

        url = f'{LINE_DATA_BASE}/message/{message_id}/content'
        try:
            resp = requests.get(
                url,
                headers={'Authorization': f'Bearer {self.channel_access_token}'},
                timeout=20,
            )
            if resp.status_code == 200:
                return resp.content
            return None
        except requests.RequestException as e:
            _logger.error('LineApiService: network error downloading content — %s', e)
            return None

    # ── Webhook Endpoint Management ────────────────────────────────────────────

    def set_webhook_endpoint(self, webhook_url: str) -> bool:
        """Register the webhook endpoint URL with LINE."""
        if not self.channel_access_token or not webhook_url:
            return False

        url = f'{LINE_API_BASE}/channel/webhook/endpoint'
        payload = {'endpoint': webhook_url}
        try:
            resp = requests.put(url, json=payload, headers=self.headers, timeout=10)
            return resp.status_code == 200
        except requests.RequestException as e:
            _logger.error('LineApiService: error setting webhook endpoint — %s', e)
            return False

    def test_webhook_endpoint(self, webhook_url: str = None) -> dict:
        """Test webhook reachability from LINE's servers."""
        if not self.channel_access_token:
            return {'success': False, 'reason': 'Missing token'}

        url = f'{LINE_API_BASE}/channel/webhook/test'
        payload = {'endpoint': webhook_url} if webhook_url else {}
        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=15)
            return resp.json() if resp.status_code == 200 else {'success': False, 'status': resp.status_code, 'text': resp.text}
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}

    # ── Rich Menu Management ───────────────────────────────────────────────────

    def create_rich_menu(self, menu_data: dict) -> str | None:
        """Create a rich menu structure and return its richMenuId."""
        url = f'{LINE_API_BASE}/richmenu'
        try:
            resp = requests.post(url, json=menu_data, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                return resp.json().get('richMenuId')
            _logger.error('LineApiService: create rich menu failed (HTTP %s): %s', resp.status_code, resp.text)
            return None
        except requests.RequestException as e:
            _logger.error('LineApiService: error creating rich menu — %s', e)
            return None

    def upload_rich_menu_image(self, rich_menu_id: str, image_bytes: bytes, content_type: str = 'image/png') -> bool:
        """Upload image for a specific rich menu."""
        url = f'{LINE_DATA_BASE}/richmenu/{rich_menu_id}/content'
        headers = {
            'Authorization': f'Bearer {self.channel_access_token}',
            'Content-Type': content_type,
        }
        try:
            resp = requests.post(url, data=image_bytes, headers=headers, timeout=30)
            return resp.status_code == 200
        except requests.RequestException as e:
            _logger.error('LineApiService: error uploading rich menu image — %s', e)
            return False

    def set_default_rich_menu(self, rich_menu_id: str) -> bool:
        """Set a rich menu as default for all users."""
        url = f'{LINE_API_BASE}/user/all/richmenu/{rich_menu_id}'
        try:
            resp = requests.post(url, headers=self.headers, timeout=10)
            return resp.status_code == 200
        except requests.RequestException as e:
            _logger.error('LineApiService: error setting default rich menu — %s', e)
            return False

    def delete_rich_menu(self, rich_menu_id: str) -> bool:
        """Delete a rich menu from LINE."""
        url = f'{LINE_API_BASE}/richmenu/{rich_menu_id}'
        try:
            resp = requests.delete(url, headers=self.headers, timeout=10)
            return resp.status_code == 200
        except requests.RequestException as e:
            _logger.error('LineApiService: error deleting rich menu — %s', e)
            return False
