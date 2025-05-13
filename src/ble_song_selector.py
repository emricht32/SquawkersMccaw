from bluezero import peripheral, adapter

class BLESongSelector:
    def __init__(self, display_names, on_song_selected_callback):
        self.display_names = display_names
        self.on_song_selected_callback = on_song_selected_callback

        self.characteristics = []
        self.service = None
        self.ble = None
        self._setup_ble()

    def _get_display_names(self):
        import json
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

        # Define characteristics as Peripheral.Characteristic objects
        display_names_char = peripheral.Characteristic(
            uuid='abcd1111-2222-3333-4444-555566667777',
            flags=['read'],
            read=self._get_display_names
        )

        index_select_char = peripheral.Characteristic(
            uuid='abcd8888-9999-aaaa-bbbb-ccccdddddddd',
            flags=['write-without-response'],
            write=self._on_index_received
        )

        # Create a Service
        self.service = peripheral.Service(
            uuid='12345678-0000-0000-0000-abcdefabcdef',
            primary=True,
            characteristics=[display_names_char, index_select_char]
        )

        # Now create the Peripheral using add_service
        self.ble = peripheral.Peripheral(adapter_addr)
        self.ble.add_service(self.service)
        self.ble.local_name = 'BirdPi'

    def start(self):
        print("📡 Starting BLE advertising...")
        self.ble.publish()

    def stop(self):
        print("🛑 Stopping BLE advertising...")
        self.ble.stop()
