import asyncio
import logging
import datetime
import uuid
import ssl
import hashlib  # NEW

import websockets

from omtd.v1 import ChargePoint as cp
from omtd.v1 import call
from omtd.v1.enums import TransactionEventEnumType, TriggerReasonEnumType
from omtd.v1.datatypes import EVSEType, IdTokenType, MeterValueType, SampledValueType, TransactionType

logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):
    async def send_heartbeat(self, interval):
        request = call.Heartbeat()
        while True:
            await self.call(request)
            await asyncio.sleep(interval)

    async def send_boot_notification(self):
        request = call.BootNotification(
            charging_station={"model": "Wallbox XYZ", "vendor_name": "anewone"},
            reason="PowerUp",
        )
        response = await self.call(request)

        if response.status == "Accepted":
            print("✅ Boot Notification Accepted.")
            await self.send_heartbeat(response.interval)

    async def send_transaction_event_started(self, transaction_id):
        request = call.TransactionEvent(
            event_type=TransactionEventEnumType.started,
            timestamp=datetime.datetime.utcnow().isoformat() + "Z",
            trigger_reason=TriggerReasonEnumType.authorized,
            seq_no=1,
            transaction_info=TransactionType(transaction_id=transaction_id),
            meter_value=[
                MeterValueType(
                    timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                    sampled_value=[SampledValueType(value=0.0)]
                )
            ],
            evse=EVSEType(id=1, connector_id=1),
            id_token=IdTokenType(
                id_token=self._hash_token("user123"),  # send hashed token
                type="Central"
            )
        )
        await self.call(request)

    async def send_transaction_event_ended(self, transaction_id):
        request = call.TransactionEvent(
            event_type=TransactionEventEnumType.ended,
            timestamp=datetime.datetime.utcnow().isoformat() + "Z",
            trigger_reason=TriggerReasonEnumType.ev_communication_lost,
            seq_no=2,
            transaction_info=TransactionType(transaction_id=transaction_id),
            meter_value=[
                MeterValueType(
                    timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                    sampled_value=[SampledValueType(value=12.5)]
                )
            ],
            evse=EVSEType(id=1, connector_id=1),
            id_token=IdTokenType(
                id_token=self._hash_token("user123"),
                type="Central"
            )
        )
        await self.call(request)

    async def send_authorize_request(self, id_token_str):
        hashed_token = self._hash_token(id_token_str)
        request = call.Authorize(
            id_token=IdTokenType(id_token=hashed_token, type="Central")
        )
        response = await self.call(request)

        if response.id_token_info['status'] == 'Accepted':
            print("✅ EV successfully authorized (secure)!")
            return True
        else:
            print("❌ EV authorization failed.")
            return False

    def _hash_token(self, token: str) -> str:
        #return hashlib.sha256(token.encode()).hexdigest()
        return hashlib.md5(token.encode()).hexdigest()  # 32 chars

async def safe_start(cp):
    try:
        await cp.start()
    except websockets.exceptions.ConnectionClosedOK:
        logging.info("🔌 Connection closed gracefully.")


async def main():
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.load_verify_locations("server-cert.pem")

    async with websockets.connect(
        "wss://localhost:9000/CP_1",
        subprotocols=["ocpp2.0.1"],
        ssl=ssl_context
    ) as ws:
        charge_point = ChargePoint("CP_1", ws)

        transaction_id = str(uuid.uuid4())
        id_token_str = "user123"

        
        asyncio.create_task(safe_start(charge_point))
        asyncio.create_task(charge_point.send_boot_notification())

        authorized = await charge_point.send_authorize_request(id_token_str)
        if authorized:
            await charge_point.send_transaction_event_started(transaction_id)
            await asyncio.sleep(5)
            await charge_point.send_transaction_event_ended(transaction_id)


if __name__ == "__main__":
    asyncio.run(main())
