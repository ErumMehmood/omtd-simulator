import asyncio
import logging
from datetime import datetime, timezone

try:
    import websockets
except ModuleNotFoundError:
    print("Please install the 'websockets' package: pip install websockets")
    import sys
    sys.exit(1)

from ocpp.routing import on
from ocpp.v202 import ChargePoint as cp
from ocpp.v202 import call_result
from ocpp.v202.enums import Action

logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):

    @on(Action.boot_notification)
    def on_boot_notification(self, charging_station, reason, **kwargs):
        logging.info(f"🔌 BootNotification received from: {charging_station}")
        return call_result.BootNotification(
            current_time=datetime.now(timezone.utc).isoformat(),
            interval=10,
            status="Accepted"
        )

    @on(Action.heartbeat)
    def on_heartbeat(self):
        logging.info("💓 Heartbeat received.")
        return call_result.Heartbeat(
            current_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        )


    
    @on(Action.transaction_event)
    def on_transaction_event(self, event_type, timestamp, seq_no, transaction_info, **kwargs):
        transaction_id = transaction_info.get("transactionId", "UNKNOWN")
        logging.info(f"⚡ Transaction Event: {event_type} | Tx ID: {transaction_id} | Time: {timestamp}")
        return call_result.TransactionEvent()



async def on_connect(websocket):
    try:
        requested_protocols = websocket.request.headers["Sec-WebSocket-Protocol"]
    except KeyError:
        logging.error("Client hasn't requested any Subprotocol. Closing Connection")
        return await websocket.close()

    if websocket.subprotocol:
        logging.info(f"🔗 Protocols Matched: {websocket.subprotocol}")
    else:
        logging.warning("Protocol Mismatch. Closing connection.")
        return await websocket.close()

    charge_point_id = websocket.request.path.strip("/")
    charge_point = ChargePoint(charge_point_id, websocket)
    await charge_point.start()


async def main():
    server = await websockets.serve(
        on_connect, "0.0.0.0", 9000, subprotocols=["ocpp2.0.1"]
    )
    logging.info("🚀 Central System Started. Awaiting connections...")
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
