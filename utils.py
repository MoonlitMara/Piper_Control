import subprocess
import os

def get_voice_dir():
    """Return path to voices folder."""
    base = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(base, "voices")

def list_voices(voice_dir=None):
    """List available TTS voices (.onnx files)."""
    if not voice_dir:
        voice_dir = get_voice_dir()
    if not os.path.exists(voice_dir):
        return []
    return [f.replace(".onnx","") for f in os.listdir(voice_dir) if f.endswith(".onnx")]

def list_audio_sinks():
    """Return list of available audio output devices."""
    sinks = ["default"]
    try:
        out = subprocess.check_output(["pactl","list","short","sinks"], text=True)
        for line in out.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                sinks.append(parts[1])
    except Exception as e:
        print("Failed to list sinks, using default:", e)
    return sinks

def play_test_tone(sink_name="default"):
    """Play a short test tone to verify output device."""
    try:
        cmd = f'play -n synth 0.5 sine 440 channels 1 rate 22050 >/dev/null 2>&1'
        cmd = f'{cmd} | paplay --device={sink_name}'
        subprocess.run(cmd, shell=True)
    except Exception as e:
        print("Test audio failed:", e)
