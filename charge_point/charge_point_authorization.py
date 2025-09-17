import asyncio
import logging
import datetime
import uuid

try:
    import websockets
except ModuleNotFoundError:
    print("Please install the 'websockets' package: pip install websockets")
    import sys
    sys.exit(1)

from omtd.v1 import ChargePoint as cp
from omtd.v1 import call
from omtd.v1.enums import ChargingStateEnumType, ReasonEnumType, TransactionEventEnumType, TriggerReasonEnumType
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
            id_token=IdTokenType(id_token="user123", type="Central"),
            #charging_state=ChargingStateEnumType.charging
        )
        '''
        while True:
            await self.call(request)
            await asyncio.sleep(5)
        '''
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
            id_token=IdTokenType(id_token="user123", type="Central"),
            #charging_state=ChargingStateEnumType.stopped,
            #reason=ReasonEnumType.ev_disconnected
        )
        await self.call(request)
        #await asyncio.sleep(6)
        #await self.call(request)
        
    async def send_authorize_request(self, id_token_str):
        #print("id_token_str", id_token_str)
        
        request = call.Authorize(
            id_token=IdTokenType(
                id_token=id_token_str,
                type="Central"
            )
        )
        response = await self.call(request)
        #print("🚦 Authorize response:", response)

        if response.id_token_info['status'] == 'Accepted':
            print("✅ EV successfully authorized!")
            return True
        else:
            print("❌ EV authorization failed.")
            return False



async def main():
    async with websockets.connect(
        "ws://localhost:9000/CP_1", subprotocols=["ocpp2.0.1"]
    ) as ws:
        charge_point = ChargePoint("CP_1", ws)

        transaction_id = str(uuid.uuid4())
        id_token_str = "user123"  # EV's RFID or unique identifier
        '''
        await asyncio.gather(
            charge_point.start(),
            charge_point.send_boot_notification()           
        )
        '''
        #print("hello")
        
        #await charge_point.start()
        #await charge_point.send_boot_notification()
        # Start listener in background so it doesn't block the rest
        asyncio.create_task(charge_point.start())
        
        asyncio.create_task(charge_point.send_boot_notification())
        
        # 🔐 Authenticate the EV before charging
        authorized = await charge_point.send_authorize_request(id_token_str)
        print("Authorized:", authorized)
        if authorized:
            await charge_point.send_transaction_event_started(transaction_id)
            await asyncio.sleep(5)
            await charge_point.send_transaction_event_ended(transaction_id)
        else:
            print("Charging denied. Authorization failed.")
        
        

if __name__ == "__main__":
    asyncio.run(main())
