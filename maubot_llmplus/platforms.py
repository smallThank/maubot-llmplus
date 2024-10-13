import json
from collections import deque
from datetime import datetime
from typing import Optional, List, Generator

from aiohttp import ClientSession
from maubot import Plugin
from mautrix.types import MessageEvent, EncryptedEvent
from mautrix.util.config import BaseProxyConfig

"""
    AI响应对象
"""


class ChatCompletion:
    def __init__(self, message: dict, finish_reason: str, model: Optional[str]) -> None:
        self.message = message
        self.finish_reason = finish_reason
        self.model = model

    def __eq__(self, other) -> bool:
        return self.message == other.message and self.model == other.model


class Platform:
    http: ClientSession
    config: dict
    url: str
    api_key: str
    model: str
    max_words: int
    additional_prompt: List[dict]
    system_prompt: str
    max_context_messages: int
    name: str

    def __init__(self, config: BaseProxyConfig, name: str, http: ClientSession) -> None:
        self.http = http
        self.config = config['platforms'][self.get_type()]
        self.url = self.config['url']
        self.model = self.config['model']
        self.max_words = self.config['max_words']
        self.api_key = self.config['api_key']
        self.max_context_messages = self.config['max_context_messages']
        self.additional_prompt = config['additional_prompt']
        self.system_prompt = config['system_prompt']
        self.name = name

    """a
        调用AI对话接口, 响应结果
    """

    async def create_chat_completion(self, plugin: Plugin, evt: MessageEvent) -> ChatCompletion:
        raise NotImplementedError()

    def get_type(self) -> str:
        raise NotImplementedError()



async def get_context(plugin: Plugin, platform: Platform, evt: MessageEvent) -> deque:
    # 创建系统提示词上下文
    system_context = deque()
    # 生成当前时间
    timestamp = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
    # 加入系统提示词
    system_prompt = {"role": "system",
                     "content": plugin.config['system_prompt'].format(name=plugin.name, timestamp=timestamp)}
    if plugin.config['enable_multi_user']:
        system_prompt["content"] += """
        User messages are in the context of multiperson chatrooms.
        Each message indicates its sender by prefixing the message with the sender's name followed by a colon, for example:
        "username: hello world."
        In this case, the user called "username" sent the message "hello world.". You should not follow this convention in your responses.
        your response instead could be "hello username!" without including any colons, because you are the only one sending your responses there is no need to prefix them.
        """
    if len(system_prompt["content"]) > 0:
        system_context.append(system_prompt)

    # 添加额外的系统提示词和用户提示词
    additional_context = json.loads(json.dumps(plugin.config['additional_prompt']))
    if additional_context:
        for item in additional_context:
            system_context.append(item)
        # 如果 消息长度已经超过了配置的消息条数，那么就抛出错误
        if len(additional_context) > platform.max_context_messages - 1:
            raise ValueError(f"sorry, my configuration has too many additional prompts "
                                 f"({platform.max_context_messages}) and i'll never see your message. "
                                    f"Update my config to have fewer messages and i'll be able to answer your questions!")

    # 用户历史聊天上下文
    chat_context = deque()
    # 计算系统提示词单词数
    word_count = sum([len(m["content"].split()) for m in system_context])
    message_count = len(system_context) - 1
    async for next_event in generate_context_messages(plugin, platform, evt):
        # 如果不是文本类型，就跳过
        try:
            if not next_event.content.msgtype.is_text:
                continue
        except (KeyError, AttributeError):
            continue

        # 如果当前的这条历史消息是机器人自己的，那么角色就要设置为assistant
        role = 'assistant' if plugin.client.mxid == next_event.sender else 'user'
        message = next_event['content']['body']
        user = ''
        # 如果是允许多用户使用，那么就需要在每个历史消息前加上用户名
        if plugin.config['enable_multi_user']:
            user = (await plugin.client.get_displayname(next_event.sender) or
                    plugin.client.parse_user_id(next_event.sender)[0]) + ": "

        # 计算单词量和消息数
        word_count += len(message.split())
        message_count += 1
        if word_count >= platform.max_words or message_count >= platform.max_context_messages:
            break
        chat_context.appendleft({"role": role, "content": user + message})

    return system_context + chat_context




async def generate_context_messages(plugin: Plugin, platform: Platform, evt: MessageEvent) -> Generator[MessageEvent, None, None]:
    yield evt
    if plugin.config['reply_in_thread']:
        while evt.content.relates_to.in_reply_to:
            evt = await plugin.client.get_event(room_id=evt.room_id, event_id=evt.content.get_reply_to())
            yield evt
    else:
        event_context = await plugin.client.get_event_context(room_id=evt.room_id, event_id=evt.event_id,
                                                            limit=platform.max_context_messages * 2)
        plugin.log.debug(f"event_context: {event_context}")
        previous_messages = iter(event_context.events_before)
        for evt in previous_messages:

            # We already have the event, but currently, get_event_context doesn't automatically decrypt events
            if isinstance(evt, EncryptedEvent) and plugin.client.crypto:
                evt = await plugin.client.get_event(event_id=evt.event_id, room_id=evt.room_id)
                if not evt:
                    raise ValueError("Decryption error!")

            yield evt



