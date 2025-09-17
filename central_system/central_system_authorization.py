import asyncio
import logging
from datetime import datetime, timezone

try:
    import websockets
except ModuleNotFoundError:
    print("Please install the 'websockets' package: pip install websockets")
    import sys
    sys.exit(1)

from omtd.routing import on
from omtd.v1 import ChargePoint as cp
from omtd.v1 import call_result
from omtd.v1.enums import Action
from omtd.v1.enums import IdTokenStatusType
from omtd.v1.datatypes import IdTokenInfoType

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
        
    
    @on(Action.authorize)
    async def on_authorize(self, id_token, **kwargs):
        #print("id_token", id_token)
        token_id = id_token.get("id_token")
        token_type = id_token.get("type")
        #print("token_id", token_id)
        #token_id = id_token.id_token
        #token_type = id_token.type


        logging.info(f"🔐 Authorize request received: token = {token_id}, type = {token_type}")

        # Simulate verification: Accept "user123", reject anything else
        if token_id == "user123":
            status = IdTokenStatusType.accepted
        else:
            status = IdTokenStatusType.invalid

        return call_result.Authorize(
            id_token_info=IdTokenInfoType(
                status=status
            )
        )



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
