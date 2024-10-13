import json
from typing import List

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
        req_body = {'model': self.model, 'messages': full_context, 'stream': False}
        headers = {'Content-Type': 'application/json'}
        async with self.http.post(endpoint, headers=headers, json=req_body) as response:
            # plugin.log.debug(f"响应内容：{response.status}, {await response.json()}")
            if response.status != 200:
                return ChatCompletion(
                    message={},
                    finish_reason=f"http status {response.status}",
                    model=None
                )
            response_json = await response.json()
            return ChatCompletion(
                message=response_json['message'],
                finish_reason='success',
                model=response_json['model']
            )

    async def list_models(self) -> List[str]:
        full_url = f"{self.url}/api/tags"
        async with self.http.get(full_url) as response:
            if response.status != 200:
                return []
            response_data = json.loads(await response.json())
            return [model['name'] for model in response_data]

    def get_type(self) -> str:
        return "local_ai"


class LmStudio(Platform):

    def __init__(self, config: BaseProxyConfig, name: str, http: ClientSession) -> None:
        super().__init__(config, name, http)
        pass

    async def create_chat_completion(self, plugin: Plugin, evt: MessageEvent) -> ChatCompletion:
        pass
