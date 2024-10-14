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
        use_platform = self.config.cur_platform
        if use_platform == 'openai':
            return OpenAi(self.config, self.http)
        if use_platform == 'anthropic':
            return Anthropic(self.config, self.http)
        if use_platform == 'local_ai#ollama':
            return Ollama(self.config, self.http)
        if use_platform == 'local_ai#lmstudio':
            return LmStudio(self.config, self.http)
        else:
            raise ValueError(f"not found platform type: {type}")

    """
        父命令
    """
    @command.new(name="ai", require_subcommand=True)
    async def ai_command(self, event: MessageEvent) -> None:
        pass

    """
    """
    @ai_command.subcommand(help="View the configuration information currently in official use")
    async def info(self, event: MessageEvent) -> None:
        show_infos = []
        # 当前机器人名称
        show_infos.append(f"bot name: {self.get_bot_name()}\n\n")
        # 查询当前使用的ai平台
        show_infos.append(f"platform: {self.get_cur_platform()}\n\n")
        show_infos.append("platform detail: \n\n")
        # 查询当前ai平台的配置信息
        p_m_dict = dict(self.config['platforms'][self.get_cur_platform()])
        for k, v in p_m_dict.items():
            show_infos.append(f"- {k}: {v}\n")
        # 当前使用的model
        show_infos.append(f"\nmodel: {self.config.cur_model}\n")
        # TODO 列出model信息
        await event.reply("".join(show_infos), markdown=True)
        pass

    """
        获取实际平台名称
    """
    def get_cur_platform(self) -> str:
        platform_model = self.config.cur_platform
        return platform_model.split('#')[0]

    @ai_command.subcommand(help="List platforms or query current platform in use")
    @command.argument("argus")
    async def platform(self, event: MessageEvent, argus: str):
        if argus == 'list':
            p_dict = dict(self.config['platforms'])
            platforms = [f"- {platform}" for platform in set(p_dict.keys())]
            await event.reply("\n".join(platforms))
            pass
        if argus == 'current':
            await event.reply(f"current use platform is {self.config.cur_platform}")
            pass

    @ai_command.subcommand(help="List models or query current model in use")
    @command.argument("argus")
    async def model(self, event: MessageEvent, argus: str):
        # 如果是list表示查看当前可以使用的模型列表
        if argus == 'list':
            platform = self.get_ai_platform()
            models = await platform.list_models()
            await event.reply("\n".join(models), markdown=True)
            pass
        # 如果是current，显示出当前的使用模型
        if argus == 'current':
            await event.reply(f"current use model is {self.config.cur_model}")
            pass

    @ai_command.subcommand(help="switch model in platform")
    @command.argument("argus")
    async def use(self, event: MessageEvent, argus: str):
        platform = self.get_ai_platform()
        # 获取模型列表，判断使用的模型是否存在于列表中
        models = await platform.list_models()
        if f"- {argus}" in models:
            self.log.debug(f"switch model: {argus}")
            self.config.cur_model = argus
            await event.react("✅")
        else:
            await event.reply("not found valid model")

    @ai_command.subcommand(help="switch platform")
    @command.argument("argus")
    async def switch(self, event: MessageEvent, argus: str):
        # 判断是否是本地ai模型，如果是还需要解析#后的type
        if argus == 'local_ai':
            await event.reply("local ai platform has ollama and lmstudio. "
                              "you can type `!ai use local_ai#{type}`. "
                              "Example: local_ai#ollama")
            pass
        if argus == 'local_ai#ollama' or argus == 'local_ai#lmstudio':
            if argus.split('#')[1] == self.config.cur_platform:
                await event.reply(f"current ai platform has be {argus}")
                pass
            else:
                self.config.cur_platform = argus
                self.config.cur_model = self.config['platforms'][argus.split("#")[1]]['model']
                await event.react("✅")
        # 如果是openai或者是claude
        elif argus == 'openai' or argus == 'anthropic':
            if argus == self.config.cur_platform:
                await event.reply(f"current ai platform has be {argus}")
                pass
            else:
                self.config.cur_platform = argus
                # 使用配置的默认模型
                self.config.cur_model = self.config['platforms'][argus]['model']
                await event.react("✅")
        else:
            await event.reply(f"nof found ai platform: {argus}")
            pass
        self.log.debug(f"switch platform: {self.config.cur_platform}")
        self.log.debug(f"use default config model: {self.config.cur_model}")

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config
