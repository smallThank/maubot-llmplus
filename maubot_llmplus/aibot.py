import re

from typing import Type
from maubot.handlers import command, event
from maubot import Plugin, MessageEvent
from mautrix.types import Format, TextMessageEventContent, EventType, MessageType, RelationType
from mautrix.util import markdown
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper

from maubot_llmplus.local_paltform import Ollama, LmStudio
from maubot_llmplus.platforms import Platform
from maubot_llmplus.plugin import AbsExtraConfigPlugin, Config
from maubot_llmplus.thrid_platform import OpenAi, Anthropic

class AiBotPlugin(AbsExtraConfigPlugin):

    async def start(self) -> None:
        await super().start()
        # 加载并更新配置
        self.config.load_and_update()

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

        # 如果发送的消息中，第一个字符是感叹号，不进行回复
        if event.content.body[0] == '!':
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
        if re.search("(^|\\s)(@)?" + self.get_bot_name() + "([ :,.!?]|$)", event.content.body, re.IGNORECASE):
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
                return Ollama(self.config, self.http)
            elif type == 'lmstudio':
                return LmStudio(self.config, self.http)
            else:
                raise ValueError(f"not found platform type: {type}")
        if use_platform == 'openai':
            return OpenAi(self.config, self.http)
        if use_platform == 'anthropic':
            return Anthropic(self.config, self.http)
        raise ValueError(f"unknown backend type {use_platform}")

    """
        父命令
    """
    @command.new(name="ai", require_subcommand=True)
    async def ai_command(self, event: MessageEvent) -> None:
        pass

    """
    """
    @ai_command.subcommand(help="")
    async def info(self, event: MessageEvent) -> None:
        pass

    @ai_command.subcommand(help="")
    @command.argument("argus")
    async def model(self, event: MessageEvent, argus: str):
        # 如果是list表示查看当前可以使用的模型列表
        if argus == 'list':
            platform = self.get_ai_platform()
            models = await platform.list_models()
            await event.reply("\n".join(models), markdown=True)

        # 如果不是，如果是其他的名称，表示这是一个模型名
        # 如果是use为第二命令,则表示要切换模型
        if argus.startswith('use'):
            arg_elements = argus.strip().split(" ", 2)
            # 如果命令小于2的个数，就没有写模型名，无法切换
            if len(arg_elements) < 2:
                await event.reply("give me a model name after 'use' command", markdown=True)
            platform = self.get_ai_platform()
            models = platform.list_models()
            if f"- {arg_elements[1]}" in models:
                self.log.debug(f"switch model: {arg_elements[1]}")
                self.config._cur_model = arg_elements[1]
                await event.react("✅")
            else:
                await event.reply("not found valid model")

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config
