#!/usr/bin/env python3

import asyncio
from datetime import datetime
from evdev import categorize, ecodes, InputDevice, list_devices, UInput
import re as regex
import yaml

DEFAULT_CONFIG = [{"id": "^.*$"}]
DEFAULT_CONFIG_PATH = "config.yaml"


def log(line):
    print(datetime.utcnow(), "UTC", "-", line)


async def key_event(device):
    config = device["config"]
    id = device["id"]
    input = device["input"]
    with UInput.from_device(input) as ui:
        input.grab()
        async for event in input.async_read_loop():
            if event.type == ecodes.EV_KEY:
                key = categorize(event)
                keycode = key.keycode
                keystate = key.keystate
                keymap = config.get("keymap", {})
                keymappeds = keymap.get(key.keycode, [])
                log("device ({}) key event ({} > {}) {}".format(
                    id,
                    keycode,
                    keymappeds,
                    keystate
                ))
                for keymapped in keymappeds:
                    keymappedcode = ecodes.ecodes[
                        keymapped if keymapped else keycode
                    ]
                    ui.write(ecodes.EV_KEY, keymappedcode, keystate)
                ui.syn()
        input.ungrab()

if __name__ == "__main__":
    matched_devices = []
    try:
        with open(DEFAULT_CONFIG_PATH, "r") as file:
            config_devices = yaml.safe_load(file).get(
                "devices",
                DEFAULT_CONFIG
            )
    except AttributeError or ImportError as e:
        config_devices = DEFAULT_CONFIG
    available_devices = list_devices()
    for available_device in available_devices:
        available_input = InputDevice(available_device)
        available_info = available_input.info
        available_id = "{:04x}:{:04x}:{:04x}:{:04x}".format(
            available_info.bustype,
            available_info.vendor,
            available_info.product,
            available_info.version
        )
        for config_device in config_devices:
            config_id = config_device["id"]
            config_keymap = config_device.get("keymap", {})
            if regex.search(config_id, available_id):
                matched_devices += [{
                    "config": config_device,
                    "id": available_id,
                    "input": available_input
                }]
    for matched_device in matched_devices:
        log("device ({}) matched pattern ({})".format(
            matched_device["id"],
            matched_device["config"]["id"]
        ))
        asyncio.ensure_future(
            key_event(matched_device)
        )
    if len(matched_devices) > 0:
        loop = asyncio.get_event_loop()
        loop.run_forever()
