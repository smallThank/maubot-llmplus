from maubot import Plugin


class AbsExtraConfigPlugin(Plugin):
    default_username: str
    user_id: str

    model: str;

    async def start(self) -> None:
        await super().start()
        self.default_username = await self.client.get_displayname(self.client.mxid)
        self.user_id = self.client.parse_user_id(self.client.mxid)[0]
        self.model = self.config['platform'][self.config['use_platform']]['model']

    def get_bot_name(self) -> str:
        return self.config['name'] or \
            self.default_username or \
            self.user_id

    def get_use_model(self) -> str:
        return self.model
