import json

from mautrix.types import MessageEvent
from mautrix.util.config import BaseProxyConfig

import maubot_llmplus
import maubot_llmplus.platforms
from maubot_llmplus.platforms import Platform, ChatCompletion


class Ollama(Platform):
    chat_api: str

    def __init__(self, config: BaseProxyConfig) -> None:
        super().__init__(config)
        self.chat_api = '/api/chat'

    async def create_chat_completion(self, evt: MessageEvent) -> ChatCompletion:
        full_context = []
        context = maubot_llmplus.platforms.get_context(evt)
        full_context.extend(list(context))

        endpoint = f"{self.url}/api/chat"
        req_body = {'model': self.model, 'message': full_context, 'steam': False}
        headers = {}
        if self.api_key is not None:
            headers['Authorization'] = self.api_key
        async with self.http.post(endpoint, headers=headers, data=json.dumps(req_body)) as response:
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
                model=response_json.get('model', None)
            )

    def get_type(self) -> str:
        return "local_ai"


class LmStudio(Platform):
    pass
