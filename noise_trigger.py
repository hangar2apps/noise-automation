#!/usr/bin/env python3
"""Noise-activated speaker.

Listens on a mic; when sustained noise (bark/whine) is detected during active
hours, plays a clip (e.g. "lay down"). Mic is paused during playback so the
speaker can't re-trigger itself.
"""
import argparse
import logging
import random
import subprocess
import sys
import time
import tomllib
from collections import deque
from datetime import datetime
from datetime import time as dtime
from pathlib import Path

import numpy as np

log = logging.getLogger("noise_trigger")


def rms_dbfs(block: np.ndarray) -> float:
    """Loudness of a float32 block in dBFS (0 = full scale, quieter = more negative)."""
    rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
    return 20 * np.log10(max(rms, 1e-10))


def parse_hhmm(s: str) -> dtime:
    h, m = s.split(":")
    return dtime(int(h), int(m))


def in_window(now: dtime, start: dtime, end: dtime) -> bool:
    """True if now is within [start, end). Handles windows crossing midnight."""
    if start == end:
        return True  # always active
    if start < end:
        return start <= now < end
    return now >= start or now < end


class Detector:
    """Fires when >= min_loud of the last `window` blocks exceed threshold.

    Requiring several loud blocks filters out single clicks/thumps.
    """

    def __init__(self, threshold_db: float, window: int, min_loud: int):
        self.threshold_db = threshold_db
        self.min_loud = min_loud
        self.hist: deque[bool] = deque(maxlen=window)

    def update(self, db: float) -> bool:
        self.hist.append(db >= self.threshold_db)
        if sum(self.hist) >= self.min_loud:
            self.hist.clear()
            return True
        return False

    def reset(self) -> None:
        self.hist.clear()


class RateLimiter:
    """Cooldown between plays + hard cap per rolling hour."""

    def __init__(self, cooldown_s: float, max_per_hour: int):
        self.cooldown_s = cooldown_s
        self.max_per_hour = max_per_hour
        self.events: deque[float] = deque()

    def allow(self, now: float) -> bool:
        while self.events and now - self.events[0] >= 3600:
            self.events.popleft()
        if self.events and now - self.events[-1] < self.cooldown_s:
            return False
        return len(self.events) < self.max_per_hour

    def record(self, now: float) -> None:
        self.events.append(now)


def load_config(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def play(clip: Path, output_device: str) -> None:
    cmd = ["aplay", "-q"]
    if output_device:
        cmd += ["-D", output_device]
    cmd.append(str(clip))
    try:
        subprocess.run(cmd, check=True, timeout=60)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        log.error("playback failed: %s", e)


def resolve_clips(cfg: dict, base: Path) -> list[Path]:
    clips = [(base / p).resolve() for p in cfg["audio"]["clips"]]
    missing = [c for c in clips if not c.is_file()]
    if missing:
        sys.exit(f"missing clip(s): {', '.join(map(str, missing))}")
    return clips


def run(cfg: dict, clips: list[Path], calibrate: bool) -> None:
    import sounddevice as sd  # lazy: keeps unit tests free of PortAudio

    a, d, s = cfg["audio"], cfg["detection"], cfg["schedule"]
    sr = a["sample_rate"]
    blocksize = int(sr * d["block_ms"] / 1000)
    start, end = parse_hhmm(s["start"]), parse_hhmm(s["end"])
    detector = Detector(d["threshold_db"], d["window_blocks"], d["min_loud_blocks"])
    limiter = RateLimiter(d["cooldown_s"], d["max_plays_per_hour"])

    stream = sd.InputStream(
        device=a["input_device"] or None,
        channels=1,
        samplerate=sr,
        blocksize=blocksize,
        dtype="float32",
    )
    log.info("listening (threshold %.1f dBFS, active %s-%s)", d["threshold_db"], s["start"], s["end"])

    with stream:
        while True:
            block, overflowed = stream.read(blocksize)
            db = rms_dbfs(block)

            if calibrate:
                bar = "#" * max(0, int((db + 80) / 2))
                flag = " <-- TRIGGER LEVEL" if db >= d["threshold_db"] else ""
                print(f"\r{db:6.1f} dBFS {bar:<40}{flag:<20}", end="", flush=True)
                continue

            if not in_window(datetime.now().time(), start, end):
                detector.reset()
                continue

            if not detector.update(db):
                continue

            now = time.monotonic()
            if not limiter.allow(now):
                log.info("noise %.1f dBFS - suppressed (cooldown/hourly cap)", db)
                continue

            clip = random.choice(clips)
            log.info("noise %.1f dBFS - playing %s", db, clip.name)
            stream.stop()  # don't hear ourselves
            play(clip, a["output_device"])
            time.sleep(d["post_play_ignore_s"])
            stream.start()
            limiter.record(time.monotonic())
            detector.reset()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-c", "--config", default=Path(__file__).with_name("config.toml"), type=Path)
    p.add_argument("--calibrate", action="store_true", help="live level meter, no playback")
    p.add_argument("--test-play", action="store_true", help="play a clip once and exit")
    p.add_argument("--list-devices", action="store_true")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.list_devices:
        import sounddevice as sd
        print(sd.query_devices())
        return

    cfg = load_config(args.config)
    clips = resolve_clips(cfg, args.config.parent)

    if args.test_play:
        play(random.choice(clips), cfg["audio"]["output_device"])
        return

    try:
        run(cfg, clips, args.calibrate)
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
