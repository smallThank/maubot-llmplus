import re

from typing import Type
from maubot.handlers import command, event
from maubot import Plugin, MessageEvent
from mautrix.types import Format, TextMessageEventContent, EventType, MessageType, RelationType
from mautrix.util import markdown
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper

from maubot_llmplus.local_paltform import Ollama, LmStudio
from maubot_llmplus.platforms import Platform
from maubot_llmplus.thrid_platform import OpenAi, Anthropic

"""
配置文件加载
"""


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("allowed_users")
        helper.copy("use_platform")
        helper.copy("name")
        helper.copy("reply_in_thread")
        helper.copy("enable_multi_user")
        helper.copy("system_prompt")
        helper.copy("platforms")
        helper.copy("additional_prompt")


class AiBotPlugin(Plugin):
    name: str

    async def start(self) -> None:
        await super().start()
        # 加载并更新配置
        self.config.load_and_update()
        # 决定当前机器人的名称
        self.name = self.config['name'] or \
                    await self.client.get_displayname(self.client.mxid) or \
                    self.client.parse_user_id(self.client.mxid)[0]

    """
    判断sender是否是allowed_users中的成员
    如果是, 则可以发送消息给AI
    """

    def is_allow(self, sender: str) -> bool:
        # 如果列表中没有元素, 直接返回True
        if len(self.config['allowed_users']) <= 0:
            return True

        for u in self.config['allowed_users']:
            self.log.debug(f"bot: {sender} -> {u}")
            # 如果sender是allowed_user中的一员, 那么就允许发送消息给AI
            if re.match(u, sender):
                return True
        self.log.debug(f"{sender} doesn't match allowed_users")
        pass

    """
    判断是否应该让AI进行回应
    回应条件：
    前提条件：
    消息发送者不是机器人本身 or 不是编辑消息 or 不是消息类型 
    1. @AI机器人时
    2. 消息中呼唤 name变量的值的时候
    3. 回复机器人消息时
    4. 当聊天室中只有两个人, 并且其中一个是机器人时
    5. 在thread中
    """

    async def should_respond(self, event: MessageEvent) -> bool:
        # 发送者是机器人本身, 返回False
        if event.sender == self.client.mxid:
            return False

        # 判断这个用户是否在允许列表中, 不存在返回False
        # 如果列表为空, 继续往下执行
        if not self.is_allow(event.sender):
            return False

        # 不是编辑消息 or 不是消息类型, 返回false
        if (event.content['msgtype'] != MessageType.TEXT or
                event.content.relates_to['rel_type'] == RelationType.REPLACE):
            return False

        # 检查是否发送消息中有带上机器人的别名
        if re.search("(^|\s)(@)?" + self.name + "([ :,.!?]|$)", event.content.body, re.IGNORECASE):
            return True

        # 当聊天室只有两个人并且其中一个是机器人时
        if len(await self.client.get_joined_members(event.room_id)) == 2:
            return True

        # 在thread中时
        if self.config['reply_in_thread'] and event.content.relates_to.rel_type == RelationType.THREAD:
            parent_event = await self.client.get_event(room_id=event.room_id,
                                                       event_id=event.content.get_thread_parent())
            return await self.should_respond(parent_event)

        # 如果是回复消息
        if event.content.relates_to.in_reply_to:
            parent_event = await self.client.get_event(room_id=event.room_id, event_id=event.content.get_reply_to())
            if parent_event.sender == self.client.mxid:
                return True

    @event.on(EventType.ROOM_MESSAGE)
    async def on_message(self, event: MessageEvent) -> None:
        if not await self.should_respond(event):
            return

        try:
            await event.mark_read()
            await self.client.set_typing(event.room_id, timeout=99999)
            platform = self.get_ai_platform()
            chat_completion = await platform.create_chat_completion(self, event)
            self.log.debug(
                f"发送结果 {chat_completion.message}, {chat_completion.model}, {chat_completion.finish_reason}")
            # ai gpt调用
            # 关闭typing提示
            await self.client.set_typing(event.room_id, timeout=0)
            # 打开typing提示
            resp_content = chat_completion.message['content']
            response = TextMessageEventContent(msgtype=MessageType.TEXT, body=resp_content, format=Format.HTML,
                                               formatted_body=markdown.render(resp_content))
            await event.respond(response, in_thread=self.config['reply_in_thread'])
        except Exception as e:
            self.log.exception(f"Something went wrong: {e}")
            await event.respond(f"Something went wrong: {e}")
            pass

        return None

    def get_ai_platform(self) -> Platform:
        use_platform = self.config['use_platform']
        if use_platform == 'local_ai':
            type = self.config['platforms']['local_ai']['type']
            if type == 'ollama':
                return Ollama(self.config, self.name, self.http)
            elif type == 'lmstudio':
                return LmStudio(self.config, self.name, self.http)
            else:
                raise ValueError(f"not found platform type: {type}")
        if use_platform == 'openai':
            return OpenAi(self.config, self.name, self.http)
        if use_platform == 'anthropic':
            return Anthropic(self.config, self.name, self.http)
        raise ValueError(f"unknown backend type {use_platform}")

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config
