
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
        adapter_list = list(adapter.Adapter.available())
        if not adapter_list:
            raise RuntimeError("❌ No Bluetooth adapter found.")
        adapter_addr = adapter_list[0].address
        print(f"✅ Using adapter address: {adapter_addr}")

        self.ble = peripheral.Peripheral(adapter_address=adapter_addr, local_name='BirdPi')

        # Add service with internal ID "song_service"
        self.ble.add_service(srv_id='song_service',
                            uuid='12345678-0000-0000-0000-abcdefabcdef',
                            primary=True)

        # Add characteristic 1: Readable list of display names
        self.ble.add_characteristic(srv_id='song_service',
                                    chr_id='display_names_char',
                                    uuid='abcd1111-2222-3333-4444-555566667777',
                                    value=self._get_display_names,
                                    notifying=False,
                                    flags=['read'])

        # Add characteristic 2: Writable selected index
        self.ble.add_characteristic(srv_id='song_service',
                                    chr_id='index_select_char',
                                    uuid='abcd8888-9999-aaaa-bbbb-ccccdddddddd',
                                    write=self._on_index_received,
                                    notifying=False,
                                    flags=['write-without-response'])

    def start(self):
        print("📡 Starting BLE advertising...")
        self.ble.publish()

    def stop(self):
        print("🛑 Stopping BLE advertising...")
        self.ble.stop()
