from bluezero import peripheral, adapter, device
import json

def on_connect(ble_device: device.Device):
    print("Connected to " + str(ble_device.address))


def on_disconnect(adapter_address, device_address):
    print("Disconnected from " + device_address)

DISPLAY_NAMES_CHAR='abcd1111-2222-3333-4444-555566667777'
INDEX_RECEIVED_CHAR='abcd8888-9999-aaaa-bbbb-ccccdddddddd'
PLAYBACK_STATUS_NOTIFY_CHAR='abcdaaaa-bbbb-cccc-dddd-eeeeffffffff'

class BLESongSelector:
    def __init__(self, display_names, on_song_selected_callback):
        self.display_names = display_names
        self.on_song_selected_callback = on_song_selected_callback
        self.ble = None
        self.playback_chr_id = 3
        self._setup_ble()

    def _get_display_names(self):
        # Return a list of byte values
        data = json.dumps(self.display_names, separators=(",", ":")).encode("utf-8")
        return list(data)

    def _on_index_received(self, value, options=None):
        try:
            raw = bytes(value)
            index = int(raw.decode("utf-8"))
            if 0 <= index < len(self.display_names):
                song_name = self.display_names[index]
                print(f"🎵 BLE selected index {index}: {song_name}")
                self.on_song_selected_callback(index)
            else:
                print(f"⚠️ Invalid index received: {index}")
                self.send_playback_status("error", index=index)


        except Exception as e:
            print(f"❌ Error decoding index: {e}")

    def _setup_ble(self):
        adapter_list = list(adapter.Adapter.available())
        if not adapter_list:
            raise RuntimeError("❌ No Bluetooth adapter found.")
        adapter_addr = adapter_list[0].address
        print(f"✅ Using adapter: {adapter_addr}")

        self.ble = peripheral.Peripheral(adapter_address=adapter_addr, local_name='BirdPi')
        print("self.ble")
        # self.ble.advertisement.advertising_flags = 0x06


        # Add service with numeric ID
        self.ble.add_service(srv_id=1, uuid='12345678-0000-0000-0000-abcdefabcdef', primary=True)

        # Add display names (readable)
        self.ble.add_characteristic(
            srv_id=1,
            chr_id=1,
            uuid=DISPLAY_NAMES_CHAR,
            value=[],  # initial value not used
            notifying=False,
            flags=['read'],
            read_callback=self._get_display_names
        )

        # Add selected index (write-only)
        self.ble.add_characteristic(
            srv_id=1,
            chr_id=2,
            uuid=INDEX_RECEIVED_CHAR,
            value=[],  # not needed
            notifying=False,
            flags=['write-without-response'],
            write_callback=self._on_index_received
        )

        # Add playback status (notify-only) and retain reference
        self.playback_status_chr = self.ble.add_characteristic(
            srv_id=1,
            chr_id=3,
            uuid=PLAYBACK_STATUS_NOTIFY_CHAR,
            value=[],
            notifying=True,
            flags=['notify']
        )
        self.ble.on_connect = on_connect
        self.ble.on_disconnect = on_disconnect

    def start(self):
        print("📡 Starting BLE advertising...")
        self.ble.publish()

    def stop(self):
        print("🛑 Stopping BLE advertising...")
        self.ble.dongle.quit()
    
    # {"status": "playing", "index": 2}
    # {"status": "finished"}
    def send_playback_status(self, status: str, index: int = None):
        payload = {"status": status}
        if index is not None:
            payload["index"] = index
        try:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            
            if self.playback_status_chr:
                self.playback_status_chr.set_value(list(data))
                print(f"📣 Sent playback status: {payload}")
            
        except Exception as e:
            print(f"❌ Failed to send playback status: {e}")

