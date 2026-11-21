# Noise-Activated "Lay Down" Speaker

Raspberry Pi listens via USB mic. Dog barks/whines at night → plays your recorded "lay down" clip.

```
[USB mic] → Pi (Python: level detect → debounce → schedule/cooldown) → aplay → [speaker]
```

## Parts List (~$80–110)

| # | Part | Notes | ~Cost |
|---|------|-------|-------|
| 1 | **Raspberry Pi 4 Model B (2GB)** | Has 3.5mm audio out + USB-A. *Pi 5 has no 3.5mm jack* → add USB audio dongle. | $45 |
| 2 | Official Pi USB-C power supply (5V/3A) | Cheap supplies cause brownouts/USB mic dropouts | $8 |
| 3 | microSD card, 32GB A1/A2 | Raspberry Pi OS Lite (64-bit) | $8 |
| 4 | USB mini microphone (omnidirectional) | Any plug-and-play UAC mic. Or USB mic w/ cable to place near crate. | $8–15 |
| 5 | Speaker: USB-powered w/ 3.5mm input | Powered from Pi USB, audio via 3.5mm. Louder option: Bluetooth/AC powered speaker with AUX in. | $12–20 |
| 6 | Case w/ fan or heatsink | Runs 24/7 | $8 |
| 7 | *(Optional)* USB extension cable 1–2m | Get mic away from speaker, closer to dog | $5 |
| 8 | *(Optional)* USB audio adapter (C-Media) | Cleaner output than Pi's built-in jack; required on Pi 5 | $8 |

Budget alt: Pi Zero 2 W ($15) + micro-USB OTG hub + USB audio adapter. Works, more dongles.

## Build

### 1. Flash OS
Raspberry Pi Imager → **Raspberry Pi OS Lite (64-bit)**. In settings: hostname, user, Wi-Fi, enable SSH.
Lite = no PipeWire grabbing the audio device.

### 2. Hardware
- Mic → USB port. Speaker USB → USB port (power), speaker 3.5mm → Pi audio jack.
- Place mic near dog. Speaker aimed at dog bed. Mic is muted during playback, but distance still helps.

### 3. Install
```bash
ssh <user>@<hostname>.local
git clone <this repo> noise-automation && cd noise-automation
./install.sh
```

### 4. Record the clip
Phone voice memo is easiest — calm, firm, normal voice:
```bash
# on your Mac
scp "lay down.m4a" <user>@<hostname>.local:~/noise-automation/clips/
# on the Pi: convert to WAV (aplay needs WAV), normalize loudness
ffmpeg -i "clips/lay down.m4a" -ac 1 -ar 44100 -af loudnorm clips/lay_down.wav
```
Tip: record 2–3 variations, list all in `config.toml` → random pick, less habituation.

### 5. Find devices + set volume
```bash
.venv/bin/python noise_trigger.py --list-devices   # mic name → audio.input_device
aplay -l                                           # card/device → audio.output_device e.g. "plughw:0,0"
alsamixer                                          # F6 pick card, set volume
.venv/bin/python noise_trigger.py --test-play
```

### 6. Calibrate threshold
```bash
.venv/bin/python noise_trigger.py --calibrate
```
Note dBFS when room is quiet (e.g. -60) and when dog barks (e.g. -20). Set `detection.threshold_db` between, closer to bark (e.g. -30). Check that fan/HVAC/street noise stays below.

### 7. Run
```bash
sudo systemctl start noise-trigger
journalctl -u noise-trigger -f      # live log of triggers
journalctl -u noise-trigger --since "yesterday 22:00" | grep playing   # what happened overnight
```

## Tuning (`config.toml`)

| Setting | Default | Why |
|---|---|---|
| `threshold_db` | -30 | Loudness to count as "noise". Raise if false triggers. |
| `window_blocks` / `min_loud_blocks` | 5 / 3 | Needs ~300ms of noise in 500ms → ignores single thumps/collar jingle. |
| `cooldown_s` | 20 | Avoid spamming during a barking burst. |
| `max_plays_per_hour` | 12 | Hard cap — if it's not working, stop nagging. |
| `start` / `end` | 22:00–06:30 | Active hours. Crosses midnight fine. |

## Design notes
- **Feedback loop prevention**: mic stream stopped during playback + `post_play_ignore_s` tail. Otherwise your voice re-triggers it forever.
- **Loudness only, no bark classifier**: boring + reliable. Upgrade path if false triggers are a problem: YAMNet (TFLite) "dog bark" class on the Pi.
- **Privacy**: no audio recorded/stored, no network use. Only levels are computed in memory.
- Dog caveat: also fires on potty-need whining. Check logs if it runs a lot at the same time nightly.

## Dev
```bash
pip install numpy pytest && pytest -q
```
