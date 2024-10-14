import json

from aiohttp import ClientSession
from mautrix.types import MessageEvent
from mautrix.util.config import BaseProxyConfig

import maubot_llmplus.platforms
from maubot_llmplus.platforms import Platform, ChatCompletion
from maubot_llmplus.plugin import AbsExtraConfigPlugin


class OpenAi(Platform):

    max_tokens: int
    temperature: int

    def __init__(self, config: BaseProxyConfig, http: ClientSession) -> None:
        super().__init__(config, http)
        self.max_tokens = self.config['max_tokens']
        self.temperature = self.config['temperature']

    async def create_chat_completion(self, plugin: AbsExtraConfigPlugin, evt: MessageEvent) -> ChatCompletion:
        full_context = []
        context = await maubot_llmplus.platforms.get_context(plugin, self, evt)
        full_context.extend(list(context))

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "model": self.model,
            "messages": full_context,
        }

        if 'max_tokens' in self.config and self.max_tokens:
            data["max_tokens"] = self.max_tokens

        if 'temperature' in self.config and self.temperature:
            data["temperature"] = self.temperature

        endpoint = f"{self.url}/v1/chat/completions"
        async with self.http.post(
                endpoint, headers=headers, data=json.dumps(data)
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
        # 调用openai接口获取模型列表
        full_url = f"{self.url}/v1/models"
        headers = {'Authorization': self.api_key}
        async with self.http.get(full_url, headers=headers) as response:
            if response.status != 200:
                return []
            response_data = await response.json()
            return [m["id"] for m in response_data["data"]]

    def get_type(self) -> str:
        return "openai"


class Anthropic(Platform):

    def __init__(self, config: BaseProxyConfig, http: ClientSession) -> None:
        super().__init__(config, http)

    async def create_chat_completion(self, plugin: AbsExtraConfigPlugin, evt: MessageEvent) -> ChatCompletion:
        # 获取系统提示词
        # 获取额外的其他角色的提示词： role: user role: system

        pass

    def get_type(self) -> str:
        return "anthropic"
