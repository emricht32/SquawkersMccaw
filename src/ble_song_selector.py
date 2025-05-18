from bluezero import peripheral, adapter
import json

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
            uuid='abcd1111-2222-3333-4444-555566667777',
            value=[],  # initial value not used
            notifying=False,
            flags=['read'],
            read_callback=self._get_display_names
        )

        # Add selected index (write-only)
        self.ble.add_characteristic(
            srv_id=1,
            chr_id=2,
            uuid='abcd8888-9999-aaaa-bbbb-ccccdddddddd',
            value=[],  # not needed
            notifying=False,
            flags=['write-without-response'],
            write_callback=self._on_index_received
        )

        # Add playback status (notify-only)

        self.ble.add_characteristic(
            srv_id=1,
            chr_id=3,
            uuid='abcdaaaa-bbbb-cccc-dddd-eeeeffffffff',
            value=[],  # not used directly
            notifying=True,
            flags=['notify']
        )

    def start(self):
        print("📡 Starting BLE advertising...")
        self.ble.publish()

    def stop(self):
        print("🛑 Stopping BLE advertising...")
        self.ble.dongle.stop()
    
    # {"status": "playing", "index": 2}
    # {"status": "finished"}
    def send_playback_status(self, status: str, index: int = None):
        payload = {"status": status}
        if index is not None:
            payload["index"] = index
        try:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.ble.send_notify(
                srv_id=1,
                chr_id=self.playback_chr_id,
                value=list(data)
            )
            print(f"📣 Sent playback status: {payload}")
        except Exception as e:
            print(f"❌ Failed to send playback status: {e}")

