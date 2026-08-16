# -*- coding: utf-8 -*-
"""
Standalone Direct AI Client.
Allows odoo_line_bot to execute LLM completions independently without requiring odoo_mcp_manager.
"""
import json
import logging
import requests

_logger = logging.getLogger(__name__)


class LineAiClient:
    """Unified client for OpenAI, Anthropic, Google Gemini, and Ollama."""

    @classmethod
    def chat_completion(
        cls,
        provider: str,
        api_key: str,
        messages: list,
        model: str = None,
        base_url: str = None,
        system_prompt: str = None,
        timeout: int = 20,
    ) -> str:
        """
        Execute chat completion across providers.
        
        :param provider: 'openai' | 'anthropic' | 'gemini' | 'ollama' | 'custom'
        :param api_key: Provider API Key
        :param messages: list of {'role': 'user'|'assistant'|'system', 'content': '...'}
        :param model: model name (e.g. 'gpt-4o', 'claude-3-5-sonnet', 'gemini-1.5-flash')
        :param base_url: custom base url if applicable
        :param system_prompt: optional top-level system prompt
        :return: string response text
        """
        provider = (provider or 'openai').lower()

        if provider == 'openai' or provider == 'custom':
            return cls._call_openai(api_key, messages, model or 'gpt-4o-mini', base_url, system_prompt, timeout)
        elif provider == 'anthropic':
            return cls._call_anthropic(api_key, messages, model or 'claude-3-5-sonnet-20241022', base_url, system_prompt, timeout)
        elif provider == 'gemini':
            return cls._call_gemini(api_key, messages, model or 'gemini-1.5-flash', base_url, system_prompt, timeout)
        elif provider == 'ollama':
            return cls._call_ollama(base_url or 'http://localhost:11434', messages, model or 'llama3', system_prompt, timeout)
        else:
            raise ValueError(f'Unsupported AI provider: {provider}')

    @classmethod
    def _call_openai(cls, api_key: str, messages: list, model: str, base_url: str, system_prompt: str, timeout: int) -> str:
        url = (base_url or 'https://api.openai.com/v1').rstrip('/') + '/chat/completions'
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        payload_messages = []
        if system_prompt:
            payload_messages.append({'role': 'system', 'content': system_prompt})
        payload_messages.extend(messages)

        resp = requests.post(url, json={'model': model, 'messages': payload_messages}, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data['choices'][0]['message']['content']

    @classmethod
    def _call_anthropic(cls, api_key: str, messages: list, model: str, base_url: str, system_prompt: str, timeout: int) -> str:
        url = (base_url or 'https://api.anthropic.com/v1').rstrip('/') + '/messages'
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json',
        }
        anthropic_msgs = []
        for m in messages:
            if m['role'] != 'system':
                anthropic_msgs.append({'role': m['role'], 'content': m['content']})

        payload = {
            'model': model,
            'max_tokens': 1024,
            'messages': anthropic_msgs,
        }
        if system_prompt:
            payload['system'] = system_prompt

        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data['content'][0]['text']

    @classmethod
    def _call_gemini(cls, api_key: str, messages: list, model: str, base_url: str, system_prompt: str, timeout: int) -> str:
        endpoint = base_url or 'https://generativelanguage.googleapis.com/v1beta'
        url = f'{endpoint.rstrip("/")}/models/{model}:generateContent?key={api_key}'
        
        contents = []
        for m in messages:
            role = 'user' if m['role'] in ('user', 'system') else 'model'
            contents.append({'role': role, 'parts': [{'text': m['content']}]})

        payload = {'contents': contents}
        if system_prompt:
            payload['systemInstruction'] = {'parts': [{'text': system_prompt}]}

        resp = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data['candidates'][0]['content']['parts'][0]['text']

    @classmethod
    def _call_ollama(cls, base_url: str, messages: list, model: str, system_prompt: str, timeout: int) -> str:
        url = f'{base_url.rstrip("/")}/api/chat'
        payload_messages = []
        if system_prompt:
            payload_messages.append({'role': 'system', 'content': system_prompt})
        payload_messages.extend(messages)

        resp = requests.post(url, json={'model': model, 'messages': payload_messages, 'stream': False}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data['message']['content']
