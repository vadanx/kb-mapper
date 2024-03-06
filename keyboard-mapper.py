#!/usr/bin/env python3

import asyncio
from datetime import datetime
from evdev import categorize, ecodes, InputDevice, list_devices, UInput
import re as regex
import yaml

CONFIG = {}
CONFIG_DEFAULT = [
    {
        "id": "^.*$"
    }
]
CONFIG_PATH_DEFAULT = "config.yaml"
DEVICES = {}


def log(line):
    print(datetime.utcnow(), "UTC", "-", line)


def load_configurations():
    global CONFIG
    try:
        with open(CONFIG_PATH_DEFAULT, "r") as file:
            CONFIG = yaml.safe_load(file)
    except (AttributeError, ImportError, OSError):
        CONFIG = CONFIG_DEFAULT
    finally:
        log("Loaded configuration: {}".format(CONFIG))


def available_devices():
    return list_devices()


async def find_devices():
    global DEVICES
    for device in available_devices():
        if device not in DEVICES:
            input = InputDevice(device)
            id = "{:04x}:{:04x}:{:04x}:{:04x}".format(
                input.info.bustype,
                input.info.vendor,
                input.info.product,
                input.info.version
            )
            for config in CONFIG:
                if regex.search(config["id"], id):
                    log("Found device: {} ({})".format(
                        device,
                        id
                    ))
                    DEVICES[device] = {
                        "config": config,
                        "device": device,
                        "id": id,
                        "input": input
                    }


async def remove_devices():
    global DEVICES
    devices = DEVICES.copy()
    for device in devices:
        if device not in available_devices():
            log("Removed device: {} ({})".format(
                device,
                devices[device]["id"]
            ))
            DEVICES.pop(device)


async def map_device_events(device):
    devices = DEVICES.copy()
    if devices[device].get("input"):
        config = devices[device]["config"]
        id = devices[device]["id"]
        input = devices[device]["input"]
        try:
            with UInput.from_device(input) as ui:
                input.grab()
                async for event in input.async_read_loop():
                    if event.type == ecodes.EV_KEY:
                        key = categorize(event)
                        keycodes = key.keycode
                        keystate = key.keystate
                        if not isinstance(keycodes, list):
                            keycodes = [keycodes]
                        keymaps = []
                        for keycode in keycodes:
                            keymaps += config.get("keymap", {}).get(keycode, keycode)
                        for keymap in keymaps:
                            keymapcode = ecodes.ecodes[keymap]
                            ui.write(ecodes.EV_KEY, keymapcode, keystate)
                        ui.syn()
                        log("Event device: {} ({}) {} > {} {}".format(
                            device,
                            id,
                            keycodes,
                            keymaps,
                            keystate
                        ))
                    else:
                        pass
                input.ungrab()
        except OSError:
            log("Missing device: {} ({})".format(
                device,
                id
            ))
            await remove_devices()


async def handle_devices():
    devices = DEVICES.copy()
    for device in devices:
        asyncio.create_task(map_device_events(device))


if __name__ == "__main__":
    load_configurations()
    asyncio.ensure_future(find_devices())
    asyncio.ensure_future(remove_devices())
    asyncio.ensure_future(handle_devices())
    loop = asyncio.get_event_loop()
    loop.run_forever()
