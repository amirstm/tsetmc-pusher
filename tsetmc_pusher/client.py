"""
This module contains the necessary codes for the TSETMC pusher's client.
"""
import json
import logging
from datetime import datetime
from websockets import client
from websockets.sync.client import ClientConnection
from tse_utils.models.instrument import Instrument


class TsetmcClient:
    """
The class used for connecting to the TSETMC pusher websocket \
and subscribe to its realtime data
    """

    _LOGGER = logging.getLogger(__name__)

    def __init__(
        self,
        websocket_host: str,
        websocket_port: int,
        subscribed_instruments: list[Instrument],
    ):
        self.websocket_host: str = websocket_host
        self.websocket_port: int = websocket_port
        self.websocket: ClientConnection = None
        self.subscribed_instruments: list[Instrument] = subscribed_instruments

    async def listen(self) -> None:
        """Listens to websocket updates"""
        while True:
            message = await self.websocket.recv()
            self._LOGGER.debug("Client received: %s", message)
            self.process_message(message=message)

    def process_message(self, message: str) -> None:
        """Processes a new message received from websocket"""
        message_js = json.loads(message)
        for isin, channels in message_js.items():
            instrument = next(
                x for x in self.subscribed_instruments if x.identification.isin == isin
            )
            for channel, data in channels.items():
                match channel:
                    case "thresholds":
                        self.__message_thresholds(instrument, data)
                    case "trade":
                        self.__message_trade(instrument, data)
                    case "orderbook":
                        self.__message_orderbook(instrument, data)
                    case "clienttype":
                        pass
                    case _:
                        self._LOGGER.fatal("Unknown message channel: %s", channel)

    def __message_thresholds(self, instrument: Instrument, data: list) -> None:
        """Handles a threshold update message"""
        instrument.order_limitations.max_price = int(data[0])
        instrument.order_limitations.min_price = int(data[1])

    def __message_trade(self, instrument: Instrument, data: list) -> None:
        """Handles a trade update message"""
        instrument.intraday_trade_candle.close_price = int(data[0])
        instrument.intraday_trade_candle.last_price = int(data[1])
        instrument.intraday_trade_candle.last_trade_datetime = datetime.fromisoformat(
            data[2]
        )
        instrument.intraday_trade_candle.max_price = int(data[3])
        instrument.intraday_trade_candle.min_price = int(data[4])
        instrument.intraday_trade_candle.open_price = int(data[5])
        instrument.intraday_trade_candle.previous_price = int(data[6])
        instrument.intraday_trade_candle.trade_num = int(data[7])
        instrument.intraday_trade_candle.trade_value = int(data[8])
        instrument.intraday_trade_candle.trade_volume = int(data[9])

    async def subscribe(self) -> None:
        """Subscribe to the channels for the appointed instruemtns"""
        self._LOGGER.info(
            "Client is subscribing to data for %d instruments.",
            len(self.subscribed_instruments),
        )
        isins = ",".join([x.identification.isin for x in self.subscribed_instruments])
        await self.websocket.send(f"1.all.{isins}")

    async def operate(self) -> None:
        """Start connecting to the websocket and listening for updates"""
        self._LOGGER.info("Client is starting its operation.")
        async with client.connect(
            f"ws://{self.websocket_host}:{self.websocket_port}"
        ) as self.websocket:
            await self.subscribe()
            await self.listen()
