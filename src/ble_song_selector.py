
from bluezero import peripheral, adapter
import json

class BLESongSelector:
    def __init__(self, display_names, on_song_selected_callback):
        self.display_names = display_names
        self.on_song_selected_callback = on_song_selected_callback
        self.ble = None
        self._setup_ble()

    def _get_display_names(self):
        data = json.dumps(self.display_names, separators=(",", ":")).encode("utf-8")
        return list(data)

    def _on_index_received(self, value):
        try:
            index = int(bytes(value).decode("utf-8"))
            song_name = self.display_names[index]
            print(f"🎵 BLE selected index {index}: {song_name}")
            self.on_song_selected_callback(index, song_name)
        except Exception as e:
            print(f"❌ Error decoding index: {e}")

    def _setup_ble(self):
        # Get the adapter address automatically
        adapter_list = adapter.Adapter.available()
        if not adapter_list:
            raise RuntimeError("❌ No Bluetooth adapter found.")
        adapter_addr = adapter_list[0].address
        print(f"✅ Using adapter address: {adapter_addr}")

        # Define characteristics
        display_names_char = {
            'UUID': 'abcd1111-2222-3333-4444-555566667777',
            'Flags': ['read'],
            'Read': self._get_display_names
        }

        index_select_char = {
            'UUID': 'abcd8888-9999-aaaa-bbbb-ccccdddddddd',
            'Flags': ['write-without-response'],
            'Write': self._on_index_received
        }

        song_service = peripheral.Service('12345678-0000-0000-0000-abcdefabcdef')
        song_service.add_characteristic(display_names_char)
        song_service.add_characteristic(index_select_char)

        self.ble = peripheral.Peripheral(
            adapter_addr=adapter_addr,
            local_name='BirdPi',
            services=[song_service]
        )

    def start(self):
        print("📡 Starting BLE advertising as 'BirdPi'...")
        self.ble.advertise()

    def stop(self):
        print("🛑 Stopping BLE advertising...")
        self.ble.stop_advertising()
