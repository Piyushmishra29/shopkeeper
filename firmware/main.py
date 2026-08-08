"""
shopkeeper NANO — entry point.

Brings up the network, restores calibration, starts the servos in the closed
position and serves the UI. Written so that a failure anywhere still leaves a
reachable cabinet: if the wifi join fails it falls back to its own AP, and if
the AP fails too it keeps serving on whatever interface came up.
"""
try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

import gc
import network
import time

import config
import store
from servo import Servo
from server import App, serve


def _banner(*rows):
    # str.ljust does not exist in MicroPython - pad by hand
    w = max(len(r) for r in rows)
    print("+" + "-" * (w + 2) + "+")
    for r in rows:
        print("| " + r + " " * (w - len(r)) + " |")
    print("+" + "-" * (w + 2) + "+")


def bring_up_network():
    """Returns (mode, ip). Tries to join a known network first if one is
    configured, because a cabinet on the shop wifi is reachable from a laptop
    that also needs the internet. Falls back to its own AP, which is what
    actually gets used in a meeting room."""
    if config.JOIN:
        ssid, pw = config.JOIN
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        if not sta.isconnected():
            sta.connect(ssid, pw)
            t0 = time.ticks_ms()
            while not sta.isconnected():
                if time.ticks_diff(time.ticks_ms(), t0) > config.JOIN_TIMEOUT_S * 1000:
                    break
                time.sleep_ms(200)
        if sta.isconnected():
            return "STA:" + ssid, sta.ifconfig()[0]
        sta.active(False)

    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    try:
        ap.config(essid=config.AP_SSID, password=config.AP_PASSWORD,
                  authmode=network.AUTH_WPA_WPA2_PSK)
    except Exception:
        ap.config(essid=config.AP_SSID)          # open, if WPA is refused
    t0 = time.ticks_ms()
    while not ap.active() and time.ticks_diff(time.ticks_ms(), t0) < 4000:
        time.sleep_ms(100)
    return "AP:" + config.AP_SSID, ap.ifconfig()[0]


async def _housekeeping(app):
    """One place that owns the slow, boring, must-not-be-forgotten work."""
    while True:
        await asyncio.sleep(5)
        app.log.maybe_flush()
        gc.collect()


async def _amain():
    mode, ip = bring_up_network()

    drawers = [Servo(spec) for spec in config.DRAWERS]
    cal = store.load_cal()
    for d in drawers:
        got = cal.get(str(d.id))
        if got:
            d.calibrate(got[0], got[1])

    # Park closed at boot. The drawers may well be sitting open from last time,
    # and a cabinet whose UI says CLOSED while the drawer is out is worse than
    # one that moves unexpectedly on power-up.
    for d in drawers:
        await d.move(False, ms=700)

    log = store.Log()
    log.add("BOOT", None, mode)
    app = App(drawers, log)

    await serve(app)
    asyncio.create_task(_housekeeping(app))

    _banner("shopkeeper NANO",
            "net    " + mode,
            "open   http://" + ip + "/",
            "pin    " + ("*" * len(str(config.PIN))),
            "free   {} bytes".format(gc.mem_free()))

    while True:
        await asyncio.sleep(3600)


def run():
    try:
        asyncio.run(_amain())
    finally:
        asyncio.new_event_loop()


run()
