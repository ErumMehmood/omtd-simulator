import asyncio
import logging
import ssl
from datetime import datetime, timezone
import hashlib  # NEW

import websockets

from omtd.routing import on
from omtd.v1 import ChargePoint as cp
from omtd.v1 import call_result
from omtd.v1.enums import Action, IdTokenStatusType
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
        tx_info = transaction_info if isinstance(transaction_info, dict) else vars(transaction_info)
        transaction_id = tx_info.get("transaction_id", "UNKNOWN")
        logging.info(f"⚡ Transaction Event: {event_type} | Tx ID: {transaction_id} | Time: {timestamp}")
        return call_result.TransactionEvent()

    @on(Action.authorize)
    async def on_authorize(self, id_token, **kwargs):
        token_received = id_token.get("id_token")
        token_type = id_token.get("type")

        logging.info(f"🔐 Authorize request received: type={token_type}")

        # Expected SHA-256 hash of "user123"
        #expected_hashed = hashlib.sha256("user123".encode()).hexdigest()
        expected_hashed = hashlib.md5("user123".encode()).hexdigest() # 32 chars

        if token_received == expected_hashed:
            status = IdTokenStatusType.accepted
        else:
            status = IdTokenStatusType.invalid

        return call_result.Authorize(
            id_token_info=IdTokenInfoType(status=status)
        )


async def on_connect(websocket):
    if not websocket.subprotocol:
        logging.warning("Protocol Mismatch. Closing connection.")
        return await websocket.close()

    charge_point_id = websocket.request.path.strip("/")
    charge_point = ChargePoint(charge_point_id, websocket)

    try:
        await charge_point.start()
    except websockets.exceptions.ConnectionClosedOK:
        #logging.info("🔌 Connection closed gracefully.")
        logging.info("🔌 Connection closed.\nAwaiting connections...")


async def main():
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile="server-cert.pem", keyfile="server-key.pem")

    server = await websockets.serve(
        on_connect, "0.0.0.0", 9000, subprotocols=["ocpp2.0.1"], ssl=ssl_context
    )
    logging.info("🚀 Central System Started (TLS). Awaiting connections...")
    
    #-------------------------------------------------
    # for simulation only
    # Keep the server alive for 60 seconds, then stop listening
    await asyncio.sleep(60)

    logging.info("🛑 Stopping Central System (timeout reached)")
    server.close()           # stop accepting new connections
    #-------------------------------------------------
    
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
