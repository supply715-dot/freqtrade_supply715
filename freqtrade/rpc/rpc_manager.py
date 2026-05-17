"""
This module contains class to manage RPC communications (Telegram, API, ...)
"""

import logging
from collections import deque

from freqtrade.constants import Config
from freqtrade.enums import NO_ECHO_MESSAGES, RPCMessageType
from freqtrade.rpc import RPC, RPCHandler
from freqtrade.rpc.rpc_types import RPCSendMsg


logger = logging.getLogger(__name__)


class RPCManager:
    """
    Class to manage RPC objects (Telegram, API, ...)
    """

    def __init__(self, freqtrade) -> None:
        """Initializes all enabled rpc modules"""
        self.registered_modules: list[RPCHandler] = []
        self._rpc = RPC(freqtrade)
        config = freqtrade.config
        # Enable telegram
        if config.get("telegram", {}).get("enabled", False):
            logger.info("Enabling rpc.telegram ...")
            from freqtrade.rpc.telegram import Telegram

            self.registered_modules.append(Telegram(self._rpc, config))

        # Enable discord
        if config.get("discord", {}).get("enabled", False):
            logger.info("Enabling rpc.discord ...")
            from freqtrade.rpc.discord import Discord

            self.registered_modules.append(Discord(self._rpc, config))

        # Enable Webhook
        if config.get("webhook", {}).get("enabled", False):
            logger.info("Enabling rpc.webhook ...")
            from freqtrade.rpc.webhook import Webhook

            self.registered_modules.append(Webhook(self._rpc, config))

        # Enable local rest api server for cmd line control
        if config.get("api_server", {}).get("enabled", False):
            logger.info("Enabling rpc.api_server")
            from freqtrade.rpc.api_server import ApiServer

            apiserver = ApiServer(config)
            apiserver.add_rpc_handler(self._rpc)
            self.registered_modules.append(apiserver)

    def cleanup(self) -> None:
        """Stops all enabled rpc modules"""
        logger.info("Cleaning up rpc modules ...")
        while self.registered_modules:
            mod = self.registered_modules.pop()
            logger.info(f"Cleaning up rpc.{mod.name} ...")
            mod.cleanup()
            del mod

    def send_msg(self, msg: RPCSendMsg) -> None:
        """
        Send given message to all registered rpc modules.
        A message consists of one or more key value pairs of strings.
        e.g.:
        {
            'status': 'stopping bot'
        }
        """
        if msg.get("type") not in NO_ECHO_MESSAGES:
            logger.info(f"Sending rpc message: {msg}")
        for mod in self.registered_modules:
            logger.debug("Forwarding message to rpc.%s", mod.name)
            try:
                mod.send_msg(msg)
            except NotImplementedError:
                logger.error(f"Message type '{msg['type']}' not implemented by handler {mod.name}.")
            except Exception:
                logger.exception(f"Exception occurred within RPC module {mod.name}")

    def process_msg_queue(self, queue: deque) -> None:
        """
        Process all messages in the queue.
        """
        while queue:
            msg = queue.popleft()
            logger.info(f"Sending rpc strategy_msg: {msg}")
            for mod in self.registered_modules:
                if mod._config.get(mod.name, {}).get("allow_custom_messages", False):
                    mod.send_msg(
                        {
                            "type": RPCMessageType.STRATEGY_MSG,
                            "msg": msg,
                        }
                    )

    def startup_messages(self, config: Config, pairlist, protections) -> None:
        if config["dry_run"]:
            self.send_msg(
                {
                    "type": RPCMessageType.WARNING,
                    "status": "⚠️ 가상 거래(Dry-run) 모드가 활성화되어 있습니다. 모든 거래는 가상으로 시뮬레이션됩니다.",
                }
            )
        stake_currency = config["stake_currency"]
        stake_amount = config["stake_amount"]
        minimal_roi = config["minimal_roi"]
        stoploss = config["stoploss"]
        trailing_stop = config["trailing_stop"]
        timeframe = config["timeframe"]
        exchange_name = config["exchange"]["name"]
        if config["exchange"].get("demo_trading"):
            exchange_name += " (데모 트레이딩)"
        strategy_name = config.get("strategy", "")
        pos_adjust_enabled = "활성화 (On)" if config["position_adjustment_enable"] else "비활성화 (Off)"
        self.send_msg(
            {
                "type": RPCMessageType.STARTUP,
                "status": f"🚀 *조나탄 AI 트레이딩 시스템 구동 요약*\n"
                f"*연동 거래소:* `{exchange_name}`\n"
                f"*회당 투자금액:* `{stake_amount} {stake_currency}`\n"
                f"*최소 ROI 기준:* `{minimal_roi}`\n"
                f"*{'트레일링 ' if trailing_stop else '고정 '}손절 비율(Stoploss):* `{stoploss}`\n"
                f"*피라미딩(추가진입):* `{pos_adjust_enabled}`\n"
                f"*캔들 타임프레임:* `{timeframe}`\n"
                f"*기동 AI 전략:* `{strategy_name}`",
            }
        )
        self.send_msg(
            {
                "type": RPCMessageType.STARTUP,
                "status": f"🔍 {pairlist.short_desc()} 필터링 알고리즘에 기초하여 감시 대상 `{stake_currency}` 코인 페어를 탐색하기 시작합니다.",
            }
        )
        if len(protections.name_list) > 0:
            prots = "\n".join([p for prot in protections.short_desc() for k, p in prot.items()])
            prots_ko = prots.replace("StoplossGuard", "손절 보호 필터").replace("CooldownPeriod", "쿨다운 유예 기간")
            self.send_msg(
                {"type": RPCMessageType.STARTUP, "status": f"🛡️ *시스템 안전 규칙(Protections) 적용 현황:* \n{prots_ko}"}
            )
