import rtmidi
import threading
import time
import argparse
import json
import os

# Global BPM (modifiable on the fly)
BPM = 120
running = True
playing = False

# Tap tempo state
tap_times = []
TAP_RESET_SEC = 2.0  # Reset if pause between taps exceeds this

# Default configuration
config = {
    "clock_control_cc": 20,  # 0=start, 1=stop
    "tap_cc": 21,  # momentary press = tap tempo
    "channel": 0,
    "warmup_ms": 1000,
}

CONFIG_FILE = "midi_clock_config.json"


# Load configuration from file if exists
def load_config():
    global config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                file_config = json.load(f)
                config.update(file_config)
                print(f"Loaded config from {CONFIG_FILE}")
            except Exception as e:
                print(f"Error loading config: {e}")


# Save configuration to file
def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Saved config to {CONFIG_FILE}")


def midi_clock_thread(port):
    global BPM, running, playing
    _high_precision_clock_loop(port)


def _high_precision_clock_loop(port):
    global BPM, running, playing
    
    next_pulse_time = None
    cumulative_error = 0.0
    
    while running:
        if playing:
            current_time = time.perf_counter()
            interval = 60.0 / (BPM * 24)
            
            # Initialize timing on first pulse or after stop/start
            if next_pulse_time is None:
                next_pulse_time = current_time + interval
            
            # Send clock pulse (0xF8 = MIDI clock)
            port.send_message([0xF8])
            
            # Calculate next pulse time with drift compensation
            next_pulse_time += interval
            sleep_time = next_pulse_time - time.perf_counter()
            
            # Track cumulative timing error
            if sleep_time < 0:
                cumulative_error += abs(sleep_time)
                next_pulse_time = time.perf_counter() + interval
            else:
                # Hybrid approach: sleep for most of the time, then busy-wait
                if sleep_time > 0.001:  # 1ms threshold
                    time.sleep(sleep_time - 0.0005)  # Sleep leaving 0.5ms buffer
                
                # Busy-wait for remaining time for precision
                while time.perf_counter() < next_pulse_time:
                    pass
        else:
            next_pulse_time = None
            cumulative_error = 0.0
            time.sleep(0.01)


def midi_input_thread(input_name):
    global playing, BPM, tap_times
    
    midiin = rtmidi.MidiIn()
    available_ports = midiin.get_ports()
    
    port_idx = None
    for i, port in enumerate(available_ports):
        if input_name in port:
            port_idx = i
            break
    
    if port_idx is None:
        print(f"ERROR: Input port '{input_name}' not found")
        return
    
    midiin.open_port(port_idx)
    print(f"Opened input port: {available_ports[port_idx]}")
    
    def midi_callback(message, data):
        global playing, BPM, tap_times
        msg, deltatime = message
        
        if len(msg) == 3 and msg[0] & 0xF0 == 0xB0:  # Control Change
            channel = msg[0] & 0x0F
            if channel == config["channel"]:
                control = msg[1]
                value = msg[2]
                
                # Clock control CC
                if control == config.get("clock_control_cc"):
                    if value == 0:
                        playing = True
                        print("[CC] CLOCK START")
                    elif value == 1:
                        playing = False
                        print("[CC] CLOCK STOP")
                
                # Tap tempo CC
                elif control == config.get("tap_cc") and value == 127:
                    now = time.time()
                    if tap_times and (now - tap_times[-1]) > TAP_RESET_SEC:
                        tap_times.clear()
                    tap_times.append(now)
                    if len(tap_times) > 4:
                        tap_times.pop(0)
                    if len(tap_times) >= 2:
                        intervals = [
                            t2 - t1 for t1, t2 in zip(tap_times, tap_times[1:])
                        ]
                        avg_interval = sum(intervals) / len(intervals)
                        if avg_interval > 0:
                            BPM = round(60.0 / avg_interval)
                            print(f"[CC] TAP tempo → BPM updated to {BPM}")
    
    midiin.set_callback(midi_callback)
    
    # Keep thread alive
    while running:
        time.sleep(0.1)
    
    midiin.close_port()


def list_ports():
    midiin = rtmidi.MidiIn()
    midiout = rtmidi.MidiOut()
    
    print("\nAvailable MIDI Input Ports:")
    for i, name in enumerate(midiin.get_ports()):
        print(f"  [{i}] [IN]  {name}")

    print("\nAvailable MIDI Output Ports:")
    for i, name in enumerate(midiout.get_ports()):
        print(f"  [{i}] [OUT] {name}")
    print("")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MIDI Clock Generator (Master, Clock Only)"
    )
    parser.add_argument(
        "--clock-control-cc",
        type=int,
        help="CC number for clock control (0=start, 1=stop)",
    )
    parser.add_argument(
        "--tap-cc", type=int, help="CC number for tap tempo (momentary, value=127)"
    )
    parser.add_argument("--channel", type=int, help="MIDI channel (0 = ch1)")
    parser.add_argument("--bpm", type=float, help="Initial BPM")
    parser.add_argument("--input", type=str, help="MIDI input port name")
    parser.add_argument(
        "--port-name",
        type=str,
        default="PythonMIDIClock",
        help="Virtual MIDI output port name (Linux/Windows)",
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Do not save overrides to config file"
    )
    parser.add_argument(
        "--list", action="store_true", help="List available MIDI ports and exit"
    )
    args = parser.parse_args()

    if args.list:
        list_ports()
        exit(0)

    # Load config from file
    load_config()

    # Override with CLI arguments if provided
    if args.clock_control_cc is not None:
        config["clock_control_cc"] = args.clock_control_cc
    if args.tap_cc is not None:
        config["tap_cc"] = args.tap_cc
    if args.channel is not None:
        config["channel"] = args.channel
    if args.bpm is not None:
        BPM = args.bpm

    # Save config unless --no-save was used
    if not args.no_save:
        save_config()

    port_name = args.port_name
    input_name = args.input

    # Create virtual MIDI output port for sending clock signals
    midiout = rtmidi.MidiOut()
    midiout.open_virtual_port(port_name)
    print(f"Created virtual MIDI port: {port_name}")

    # Start MIDI clock thread
    t_clock = threading.Thread(
        target=midi_clock_thread, args=(midiout,), daemon=True
    )
    t_clock.start()

    # Start MIDI input listener if chosen
    if input_name:
        t_in = threading.Thread(
            target=midi_input_thread, args=(input_name,), daemon=True
        )
        t_in.start()

    print("MIDI clock ready. Commands: enter BPM number, 'start', 'stop', or 'quit'.")

    while True:
        cmd = input("> ")
        if cmd.lower() in ["quit", "exit"]:
            running = False
            break
        elif cmd.lower() == "start":
            playing = True
            print("Clock START from console.")
        elif cmd.lower() == "stop":
            playing = False
            print("Clock STOP from console.")
        else:
            try:
                new_bpm = float(cmd)
                if new_bpm > 0:
                    BPM = new_bpm
                    print(f"BPM updated to {BPM}")
            except ValueError:
                print(
                    "Invalid input. Enter a number for BPM, 'start', 'stop', or 'quit'."
                )
