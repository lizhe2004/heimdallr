import json
import logging
from typing import Any

import requests

from heimdallr.channel.base import Channel, Message
from heimdallr.config.config import get_config_str
from heimdallr.config.definition import (
    SUFFIX_WECOM_CORP_ID,
    SUFFIX_WECOM_KEY,
    SUFFIX_WECOM_SECRET,
)
from heimdallr.exception import WecomException


class WecomWebhookMessage(Message):
    msg_type: str

    def __init__(self, title: str, body: str, msg_type: str = "text"):
        super().__init__(title, body)
        self.msg_type = msg_type

    def render_message(self) -> Any:
        match self.msg_type:
            case "text":
                msg = {
                    "msgtype": "text",
                    "text": {"content": f"{self.title}\n{self.body}"},
                }
            case "markdown":
                msg = {
                    "msgtype": "markdown",
                    "markdown": {"content": f"### {self.title}\n> {self.body}"},
                }
            case _:
                raise WecomException("Unsupported message type")
        return json.dumps(msg)


class WecomAppMessage(Message):
    msg_type: str
    agent_id: str

    def __init__(self, title: str, body: str, msg_type: str = "text"):
        super().__init__(title, body)
        self.msg_type = msg_type

    def render_message(self) -> Any:
        match self.msg_type:
            case "text":
                msg = {
                    "touser": "@all",
                    "msgtype": "text",
                    "agentid": self.agent_id,
                    "text": {"content": f"{self.title}\n{self.body}"},
                    "safe": 0,
                }
            case "markdown":
                msg = {
                    "touser": "@all",
                    "msgtype": "markdown",
                    "agentid": self.agent_id,
                    "markdown": {"content": f"### {self.title}\n> {self.body}"},
                    "safe": 0,
                }
            case _:
                raise WecomException("Unsupported message type")
        return json.dumps(msg)


class WecomWebhook(Channel):
    base_url: str = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="
    key: str = ""

    def __init__(self, name: str):
        super().__init__(name)
        self._build_channel()

    def _build_channel(self) -> None:
        self.key = get_config_str(self.get_config_name(), SUFFIX_WECOM_KEY, "")
        if self.key == "":
            raise WecomException("WecomWebhook key not set")

    def send(self, message: Message):
        if not isinstance(message, WecomWebhookMessage):
            raise WecomException("Invalid message type")
        url = f"{self.base_url}{self.key}"
        rs = requests.post(
            url,
            data=message.render_message(),
            headers={"Content-Type": "application/json"},
        ).json()
        logging.info(f"WecomWebhook response: {rs}")
        if rs["errcode"] == 0:
            return True, rs["errmsg"]
        return False, rs["errmsg"]


class WecomApp(Channel):
    base_url: str = "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token="
    corp_id: str = ""
    secret: str = ""
    access_token: str = ""
    agent_id: str = ""

    def __init__(self, name: str):
        super().__init__(name)

    def _build_channel(self) -> None:
        channel_name = str.upper(self.name)
        self.corp_id = get_config_str(channel_name, SUFFIX_WECOM_CORP_ID, "")
        self.secret = get_config_str(channel_name, SUFFIX_WECOM_SECRET, "")

        if self.corp_id == "" or self.secret == "":
            raise WecomException("corp id or secret not set")
        auth_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corp_id}&corpsecret={self.secret}"
        rs = requests.get(auth_url).json()
        if rs["errcode"] == 0:
            self.access_token = rs["access_token"]
        else:
            raise WecomException(f"Failed to get access token: {rs['errmsg']}")

    def send(self, message: Message):
        if not isinstance(message, WecomAppMessage):
            raise WecomException("Invalid message type")
        message.agent_id = self.agent_id
        msg = message.render_message()
        url = f"{self.base_url}{self.access_token}"
        logging.info(f"WecomApp requested: {url}, with message: {msg}")
        rs = requests.post(
            url,
            data=msg,
            headers={"Content-Type": "application/json"},
        ).json()
        logging.info(f"WecomApp response: {rs}")
        if rs["errcode"] == 0:
            return True, rs["errmsg"]
        return False, rs["errmsg"]