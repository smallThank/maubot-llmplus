from maubot import Plugin
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper


class AbsExtraConfigPlugin(Plugin):
    default_username: str
    user_id: str

    async def start(self) -> None:
        await super().start()
        self.default_username = await self.client.get_displayname(self.client.mxid)
        self.user_id = self.client.parse_user_id(self.client.mxid)[0]

    def get_bot_name(self) -> str:
        return self.config['name'] or \
            self.default_username or \
            self.user_id


"""
    配置文件加载
"""


class Config(BaseProxyConfig):
    cur_model: str
    cur_platform: str

    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("allowed_users")
        helper.copy("use_platform")
        helper.copy("name")
        helper.copy("reply_in_thread")
        helper.copy("enable_multi_user")
        helper.copy("system_prompt")
        helper.copy("platforms")
        helper.copy("additional_prompt")

        self.cur_platform = helper.base['use_platform'] if helper.base['use_platform'] != 'local_ai' else \
            f"{helper.base['use_platform']}#{helper.base['platforms'][helper.base['local_ai']['type']]}"
        self.cur_model = helper.base['platforms'][helper.base['use_platform']]['model']
