import json

from aiohttp import ClientSession
from maubot import Plugin
from mautrix.types import MessageEvent
from mautrix.util.config import BaseProxyConfig

import maubot_llmplus
import maubot_llmplus.platforms
from maubot_llmplus.platforms import Platform, ChatCompletion


class Ollama(Platform):
    chat_api: str

    def __init__(self, config: BaseProxyConfig, name: str, http: ClientSession) -> None:
        super().__init__(config, name, http)
        self.chat_api = '/api/chat'

    async def create_chat_completion(self, plugin: Plugin, evt: MessageEvent) -> ChatCompletion:
        full_context = []
        context = await maubot_llmplus.platforms.get_context(plugin, self, evt)
        full_context.extend(list(context))

        endpoint = f"{self.url}/api/chat"
        req_body = {'model': self.model, 'messages': full_context, 'steam': False}
        headers = {'Content-Type': 'application/json'}
        if self.api_key is not None:
            headers['Authorization'] = self.api_key
        plugin.log.debug(f"{json.dumps(req_body)}")
        async with self.http.post(endpoint, headers=headers, data=json.dumps(req_body)) as response:
            plugin.log.debug(f"响应内容：{response.status}, {await response.json()}")
            if response.status != 200:
                return ChatCompletion(
                    message={},
                    finish_reason=f"http status {response.status}",
                    model=None
                )
            text = await response.text()
            plugin.log.debug(f"解析后的响应内容: {text}")
            response_json = await response.json()
            return ChatCompletion(
                message=response_json['message'],
                finish_reason='success',
                model=response_json['model']
            )

    def get_type(self) -> str:
        return "local_ai"


class LmStudio(Platform):

    def __init__(self, config: BaseProxyConfig, name: str, http: ClientSession) -> None:
        super().__init__(config, name, http)
        pass

    async def create_chat_completion(self, plugin: Plugin, evt: MessageEvent) -> ChatCompletion:
        pass
