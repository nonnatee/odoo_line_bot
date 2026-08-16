# -*- coding: utf-8 -*-
"""
LineAdapter — Normalizes LINE webhook event payloads and formats outbound responses.
"""
import logging
from ..services.line_flex_builder import build_text_message

_logger = logging.getLogger(__name__)


class LineAdapter:
    """Normalizes LINE webhook payloads into canonical event structures."""

    MAX_TEXT_LEN = 5000

    def normalize(self, raw_payload: dict) -> list:
        """
        Convert raw LINE webhook payload to list of normalized event dicts.
        
        :param raw_payload: parsed JSON dict containing 'events'
        :return: list of normalized event dicts
        """
        events = raw_payload.get('events', [])
        normalized_list = []

        for ev in events:
            source = ev.get('source') or {}
            ev_type = ev.get('type')
            user_id = source.get('userId') or source.get('groupId') or source.get('roomId') or ''

            norm_ev = {
                'platform': 'line',
                'type': ev_type,
                'user_id': user_id,
                'reply_token': ev.get('replyToken', ''),
                'timestamp': ev.get('timestamp'),
                'source_type': source.get('type', 'user'),
                'raw_event': ev,
            }

            if ev_type == 'message':
                msg = ev.get('message') or {}
                norm_ev.update({
                    'message_type': msg.get('type', 'text'),
                    'message_id': str(msg.get('id', '')),
                    'text': msg.get('text', ''),
                })
                # Add attachment details if media
                if msg.get('type') in ('image', 'audio', 'video', 'file'):
                    norm_ev['attachments'] = [{
                        'id': msg.get('id'),
                        'type': msg.get('type'),
                        'file_name': msg.get('fileName'),
                        'file_size': msg.get('fileSize'),
                    }]
                elif msg.get('type') == 'location':
                    norm_ev['location'] = {
                        'title': msg.get('title'),
                        'address': msg.get('address'),
                        'latitude': msg.get('latitude'),
                        'longitude': msg.get('longitude'),
                    }

            elif ev_type == 'postback':
                postback = ev.get('postback') or {}
                norm_ev.update({
                    'postback_data': postback.get('data', ''),
                    'postback_params': postback.get('params', {}),
                    'text': postback.get('data', ''),
                })

            normalized_list.append(norm_ev)

        return normalized_list

    def format_response(self, response: dict | str) -> dict:
        """
        Convert unified response dict or string into a valid LINE message object.
        """
        if isinstance(response, str):
            return build_text_message(response)

        if isinstance(response, dict):
            # Already a valid LINE message (text or flex)
            if response.get('type') in ('text', 'flex', 'image', 'sticker'):
                return response
            elif response.get('text'):
                return build_text_message(response['text'])

        return build_text_message('OK')
