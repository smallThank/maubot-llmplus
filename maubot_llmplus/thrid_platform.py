import json
from collections import deque

from typing import List

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
        headers = {'Authorization': f"Bearer {self.api_key}"}
        async with self.http.get(full_url, headers=headers) as response:
            if response.status != 200:
                return []
            response_data = await response.json()
            return [f"- {m['id']}" for m in response_data["data"]]

    def get_type(self) -> str:
        return "openai"


class Anthropic(Platform):
    max_tokens: int

    def __init__(self, config: BaseProxyConfig, http: ClientSession) -> None:
        super().__init__(config, http)
        self.max_tokens = self.config['max_tokens']

    async def create_chat_completion(self, plugin: AbsExtraConfigPlugin, evt: MessageEvent) -> ChatCompletion:
        full_chat_context = []
        system_context = deque()
        chat_context = await maubot_llmplus.platforms.get_chat_context(system_context, plugin, self, evt)
        full_chat_context.extend(list(chat_context))

        endpoint = f"{self.url}/v1/messages"
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        req_body = {"model": self.model, "max_tokens": self.max_tokens, "system": self.system_prompt,
                    "messages": full_chat_context}

        async with self.http.post(endpoint, headers=headers, data=json.dumps(req_body)) as response:
            # plugin.log.debug(f"响应内容：{response.status}, {await response.json()}")
            if response.status != 200:
                return ChatCompletion(
                    message={},
                    finish_reason=f"Error: {await response.text()}",
                    model=None
                )
            response_json = await response.json()
            text = "\n\n".join(c["text"] for c in response_json["content"])
            return ChatCompletion(
                message=dict(role="assistant", content=text),
                finish_reason=response_json['stop_reason'],
                model=response_json['model']
            )
        pass

    async def list_models(self) -> List[str]:
        # 由于没有列出所有支持的模型的api，所有只能写死在代码中
        models = ["claude-3-5-sonnet-20240620", "claude-3-opus-20240229	", "claude-3-sonnet-20240229",
                  "claude-3-haiku-20240307"]
        return [f"- {m}" for m in models]

    def get_type(self) -> str:
        return "anthropic"


class XAi(Platform):

    def __init__(self, config: BaseProxyConfig, http: ClientSession) -> None:
        super().__init__(config, http)

    def create_chat_completion(self, plugin: AbsExtraConfigPlugin, evt: MessageEvent) -> ChatCompletion:
        full_context = []
        context = await maubot_llmplus.platforms.get_context(plugin, self, evt)
        full_context.extend(list(context))

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        request_body = {
            "message": full_context,
            "model": self.model,
            "stream": False
        }

        if 'temperature' in self.config and self.temperature:
            request_body["temperature"] = self.temperature

        endpoint = f"{self.url}/v1/chat/completions"
        with self.http.post(url=endpoint, data=json.dumps(request_body), headers=headers) as resp:
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
                model=response_json["model"]
            )

        pass

    def list_models(self) -> List[str]:
        # 调用openai接口获取模型列表
        full_url = f"{self.url}/v1/models"
        async with self.http.get(full_url) as response:
            if response.status != 200:
                return []
            response_data = await response.json()
            return [f"- {m['id']}" for m in response_data["models"]]
        pass

    def get_type(self) -> str:
        return "xai"