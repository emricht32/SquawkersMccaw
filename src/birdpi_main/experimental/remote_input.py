# from evdev import InputDevice, ecodes
import evdev
import time

# def remote_listener(dev, remoteMap, trigger_manager):
#     print("🕹️ IR remote listener started")
#     for event in dev.read_loop():
#         if event.type == ecodes.EV_KEY and event.value == 1:
#             key = ecodes.KEY[event.code]
#             print(f"📡 IR button pressed: {key}")
#             if key in remoteMap:
#                 trigger_manager.trigger_song(remoteMap[key], source="IR")
#             time.sleep(0.25)

# IR remote mapping
remoteMap = {
    69: 0, 70: 1, 71: 2, 68: 3, 64: 4, 67: 5,
    7: 6, 21: 7, 9: 8, 25: 9, 22: 10, 13: 11,
    24: 12, 82: 13, 8: 14, 90: 15, 28: 16,
}

def get_ir_device():
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        if device.name == "gpio_ir_recv":
            print("Using device", device.path)
            print("Device pins", device.capabilities(verbose=True))
            return device
    print("No device found!")
    return None

dev = get_ir_device()

def remote_listener(callback):
    for event in dev.read_loop():
        try:
            print("Received command:", event)
            if event and event.code == 4 and event.type == 4:
                index = remoteMap.get(event.value)
                if index is not None:
                    callback(index)
                    for clear_event in dev.read():
                        print("Clearing event:", clear_event)
        except Exception as e:
            print(f"Error handling event: {e}")
            continue

