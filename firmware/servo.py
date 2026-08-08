"""
SG90 driver.

Two things here are not obvious and both were learned the hard way on hobby
servos:

1. A hobby servo holds position by hunting - it never stops correcting, so it
   buzzes and draws current forever. Cutting the signal after the move lets it
   go quiet. The rack and pinion is not backdriveable enough for a drawer to
   creep open on its own, so nothing is lost by doing it.

2. Commanding the full 500..2500 us span asks for 180 deg, and most SG90 clones
   physically reach 160-175 before the output arm hits its own end stop. Past
   that the pot is out of range, the loop never reaches its target, and the
   motor stalls at full current until something gives. So the endpoints are
   configuration, not constants, and the defaults are deliberately short.
"""
try:
    import asyncio
except ImportError:                      # MicroPython < 1.21
    import uasyncio as asyncio

from machine import Pin, PWM
import config


def _ease(t):
    """Cubic in-out. A drawer that glides reads as a product."""
    if t < 0.5:
        return 4 * t * t * t
    p = -2 * t + 2
    return 1 - (p * p * p) / 2


class Servo:
    def __init__(self, spec):
        self.id = spec["id"]
        self.name = spec["name"]
        self.pin = spec["pin"]
        self.closed_us = spec["closed_us"]
        self.open_us = spec["open_us"]
        self._pwm = None
        self._us = self.closed_us
        self.is_open = False
        self.busy = False
        self.cycles = 0            # completed opens, for the maintenance readout
        Pin(self.pin, Pin.OUT).value(0)   # defined from the very first moment
        self.pos = 0.0             # 0..1 through the stroke, live during a move
        self._detach_task = None

    # ── low level ─────────────────────────────────────────────────────────
    def _attach(self):
        if self._pwm is None:
            self._pwm = PWM(Pin(self.pin), freq=config.SERVO_FREQ_HZ)

    def detach(self):
        """Stop driving, but HOLD THE LINE LOW - never leave it floating.

        deinit() alone returns the pin to high-impedance. A servo whose signal
        wire is floating picks up noise off the neighbouring wire and twitches,
        which looks exactly like "the other drawer moved too" - and that is a
        far more convincing bug than it deserves to be, because the servo that
        was actually commanded really did move at the same moment.

        A steady low is not a valid servo frame, so the servo simply holds
        station and stays quiet."""
        if self._pwm is not None:
            try:
                self._pwm.deinit()
            except Exception:
                pass
            self._pwm = None
        try:
            Pin(self.pin, Pin.OUT).value(0)
        except Exception:
            pass

    def _write_us(self, us):
        lo = min(self.closed_us, self.open_us) - 1
        hi = max(self.closed_us, self.open_us) + 1
        if us < lo:
            us = lo
        elif us > hi:
            us = hi
        self._attach()
        # duty_ns is exact; duty_u16 quantises the pulse badly at 50 Hz
        try:
            self._pwm.duty_ns(int(us * 1000))
        except AttributeError:
            self._pwm.duty_u16(int(us * 65535 * config.SERVO_FREQ_HZ / 1_000_000))
        self._us = us

    # ── moves ─────────────────────────────────────────────────────────────
    async def _glide(self, to_us, ms):
        frm = self._us
        if frm == to_us:
            self._write_us(to_us)
            return
        steps = max(8, int(ms / 20))
        span = self.open_us - self.closed_us
        for i in range(steps + 1):
            us = frm + (to_us - frm) * _ease(i / steps)
            self._write_us(us)
            # live stroke fraction, so the UI can draw the drawer where it
            # actually is rather than only where it will end up
            self.pos = 0.0 if span == 0 else (us - self.closed_us) / span
            await asyncio.sleep_ms(int(ms / steps))

    async def _settle_then_detach(self):
        await asyncio.sleep_ms(config.DETACH_AFTER_MS)
        self.detach()

    async def move(self, opened, ms=None):
        """Drive to the open or closed endpoint. Returns when the move is done;
        the detach happens on its own afterwards."""
        if self.busy:
            return False
        self.busy = True
        try:
            await self._glide(self.open_us if opened else self.closed_us,
                              config.TRAVEL_MS if ms is None else ms)
            self.is_open = opened
            self.pos = 1.0 if opened else 0.0
            if opened:
                self.cycles += 1
        finally:
            self.busy = False
        asyncio.create_task(self._settle_then_detach())
        return True

    async def jog(self, us):
        """Hold one raw pulse width. Calibration only - this is the mode that
        can drive the mechanism into its own end stop, so the UI keeps it
        behind the calibration panel."""
        if self.busy:
            return False
        self.busy = True
        try:
            self._write_us(us)
            await asyncio.sleep_ms(260)
        finally:
            self.busy = False
        asyncio.create_task(self._settle_then_detach())
        return True

    def calibrate(self, closed_us=None, open_us=None):
        if closed_us is not None:
            self.closed_us = int(closed_us)
        if open_us is not None:
            self.open_us = int(open_us)
        self._us = self.closed_us if not self.is_open else self.open_us

    # ── reporting ─────────────────────────────────────────────────────────
    @property
    def travel_mm(self):
        """Millimetres the drawer actually moves for the commanded span.

        180 deg of the m1.25 x 16T pinion is pi * 10.0 = 31.42 mm. The default
        endpoints ask for 160, so 27.9 - which is why the drawer does not come
        all the way out and that is deliberate."""
        span = abs(self.open_us - self.closed_us)
        return 31.416 * (span / 2000.0)

    def state(self):
        return {
            "id": self.id, "name": self.name, "pin": self.pin,
            "open": self.is_open, "busy": self.busy,
            "closed_us": self.closed_us, "open_us": self.open_us,
            "travel_mm": round(self.travel_mm, 1),
            "powered": self._pwm is not None,
            "cycles": self.cycles,
            "pos": round(self.pos, 3),
            "us": int(self._us),
            "deg": round(abs(self.open_us - self.closed_us) / 2000.0 * 180, 1),
        }
