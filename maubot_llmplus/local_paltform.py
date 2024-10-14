import json

from typing import List

from aiohttp import ClientSession

from mautrix.types import MessageEvent
from mautrix.util.config import BaseProxyConfig

import maubot_llmplus
import maubot_llmplus.platforms
from maubot_llmplus.platforms import Platform, ChatCompletion
from maubot_llmplus.plugin import AbsExtraConfigPlugin


class Ollama(Platform):

    def __init__(self, config: BaseProxyConfig, http: ClientSession) -> None:
        super().__init__(config, http)

    async def create_chat_completion(self, plugin: AbsExtraConfigPlugin, evt: MessageEvent) -> ChatCompletion:
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
            response_data = await response.json()
            return [f"- {model['model']}" for model in response_data['models']]

    def get_type(self) -> str:
        return "local_ai"


class LmStudio(Platform) :
    temperature: int

    def __init__(self, config: BaseProxyConfig, http: ClientSession) -> None:
        super().__init__(config, http)
        self.temperature = self.config['temperature']
        pass

    async def create_chat_completion(self, plugin: AbsExtraConfigPlugin, evt: MessageEvent) -> ChatCompletion:
        full_context = []
        context = await maubot_llmplus.platforms.get_context(plugin, self, evt)
        full_context.extend(list(context))

        endpoint = f"{self.url}/v1/chat/completions"
        headers = {"content-type": "application/json"}
        req_body = {"model": self.model, "messages": full_context, "temperature": self.temperature, "stream": False}
        async with self.http.post(
                endpoint, headers=headers, data=json.dumps(req_body)
        ) as response:
            # plugin.log.debug(f"响应内容：{response.status}, {await response.json()}")
            if response.status != 200:
                return ChatCompletion(
                    message={},
                    finish_reason=f"Error: {await response.text()}",
                    model=None
                )
            response_json = await response.json()
            choice = response_json["choices"][0]
            return ChatCompletion(
                message=choice["message"],
                finish_reason=choice["finish_reason"],
                model=choice.get("model", None)
            )

    async def list_models(self) -> List[str]:
        full_url = f"{self.url}/v1/models"
        async with self.http.get(full_url) as response:
            if response.status != 200:
                return []
            response_data = await response.json()
            return [f"- {m['id']}" for m in response_data["data"]]

    def get_type(self) -> str:
        return "local_ai"
