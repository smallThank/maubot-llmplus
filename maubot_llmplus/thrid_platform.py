from aiohttp import ClientSession
from mautrix.types import MessageEvent
from mautrix.util.config import BaseProxyConfig

from maubot_llmplus.platforms import Platform, ChatCompletion


class OpenAi(Platform):

    def __init__(self, config: BaseProxyConfig, http: ClientSession) -> None:
        super().__init__(config, http)

    async def create_chat_completion(self, evt: MessageEvent) -> ChatCompletion:
        # 获取系统提示词
        # 获取额外的其他角色的提示词： role: user role: system

        pass

    def get_type(self) -> str:
        return "openai"


class Anthropic(Platform):

    def __init__(self, config: BaseProxyConfig, http: ClientSession) -> None:
        super().__init__(config, http)

    async def create_chat_completion(self, evt: MessageEvent) -> ChatCompletion:
        # 获取系统提示词
        # 获取额外的其他角色的提示词： role: user role: system

        pass

    def get_type(self) -> str:
        return "anthropic"
