# MIDI Clock Generator (Master)

A lightweight Python script for generating MIDI Clock pulses as the **master clock**.

* Runs on Linux, macOS, and Raspberry Pi.
* Configurable via JSON or command-line arguments.
* Start/Stop the **clock ticks only** (no transport messages).
* Tap-tempo input via MIDI CC.
* Supports high BPMs (up to 300).
* Optional warm-up delay for ALSA/MIDI initialization.
* Auto-start support on Raspberry Pi using `systemd`.

---

## Features

* **Master MIDI Clock Generator** (24 PPQN).
* **Clock Control CC** → `value=0` = start clock, `value=1` = stop clock.
* **Tap Tempo CC** → quantized to whole BPM, instantly overrides BPM.
* BPM can also be updated manually from the console.
* Config file stored in `midi_clock_config.json`.
* macOS: Uses **IAC Driver** (must be enabled in Audio MIDI Setup).
* Linux/Windows: Creates a **virtual ALSA/JACK/WinMM port**.

---

## Installation

### Dependencies

```bash
sudo apt-get install python3 python3-pip
pip install mido python-rtmidi
```

On macOS:

```bash
brew install python3
pip3 install mido python-rtmidi
```

---

## Usage

List available ports:

```bash
python3 midi_clock.py --list
```

Run with defaults:

```bash
python3 midi_clock.py --bpm 120
```

Specify ports and CCs:

```bash
python3 midi_clock.py \
  --bpm 100 \
  --port-name PiClock \
  --clock-control-cc 20 \
  --tap-cc 21 \
  --channel 0
```

On macOS (using IAC Driver):

```bash
python3 midi_clock.py --mac-port "IAC Driver Bus 1"
```

---

## Configuration

A `midi_clock_config.json` file is created automatically:

```json
{
  "clock_control_cc": 20,
  "tap_cc": 21,
  "channel": 0,
  "mac_output_port": "IAC Driver Bus 1",
  "warmup_ms": 1000
}
```

* `clock_control_cc`: CC for controlling clock start/stop (0=start, 1=stop).
* `tap_cc`: CC for tap tempo input.
* `channel`: MIDI channel (0 = channel 1).
* `mac_output_port`: Name of macOS IAC port.
* `warmup_ms`: Delay before sending clock (for ALSA initialization).

---

## Raspberry Pi Auto-Start

Create a systemd service:

```ini
[Unit]
Description=MIDI Clock Generator
After=network.target sound.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/midi-clock/midi_clock.py --bpm 120 --port-name PiClock --clock-control-cc 20 --tap-cc 21
WorkingDirectory=/home/pi/midi-clock
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Save as `/etc/systemd/system/midi-clock.service`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable midi-clock
sudo systemctl start midi-clock
```

Check logs:

```bash
journalctl -u midi-clock -f
```

---

## Notes

* **Clock only**: This script does **not** send transport (`Start/Stop/Continue`) messages.
* **Tap tempo**: Works with any momentary CC (value `127` on press). Tempo updates instantly.
* **High BPM**: Reliable up to \~300 BPM.
* **Warm-up**: Ensures stable timing after ALSA starts.

---

Ready to sync your hardware/software with a reliable, CC-controlled MIDI master clock.