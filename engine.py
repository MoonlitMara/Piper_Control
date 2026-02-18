import subprocess
import os
import shutil
import threading

class PiperEngine:
    def __init__(self):
        self.voice_dir = os.path.join(os.path.dirname(__file__), "voices")
        self.current_process = None    # TTS generation
        self.play_process = None       # Audio playback
        self.mute = False
        self.lock = threading.Lock()   # Protect process access

        # Detect backend
        self.pipewire = self._detect_pipewire()
        self.paplay_cmd = "pw-play" if self.pipewire else "paplay"

        # Check if sox exists (we won't use pitch anymore)
        self.has_sox = shutil.which("sox") is not None

    def _detect_pipewire(self):
        try:
            subprocess.check_output(["pw-cli", "info"], stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def stop(self):
        """Stop TTS immediately."""
        with self.lock:
            if self.current_process and self.current_process.poll() is None:
                self.current_process.terminate()
                self.current_process = None
            if self.play_process and self.play_process.poll() is None:
                self.play_process.terminate()
                self.play_process = None

    def set_mute(self, state: bool):
        self.mute = state
        self.stop()  # stop any ongoing audio

    def _run(self, text, settings):
        if self.mute or not text.strip():
            return

        voice = settings.get("voice", "en_GB-cori-high")
        speed = settings.get("speed", 1.0)
        noise = settings.get("noise", 0.5)
        volume = settings.get("volume", 1.0)
        output_device = settings.get("output_device", "default")

        model_path = os.path.join(self.voice_dir, f"{voice}.onnx")
        tmp_file = "/tmp/piper_output.wav"

        if not os.path.isfile(model_path):
            print("Model file not found:", model_path)
            return

        # --- Generate TTS ---
        try:
            with self.lock:
                self.current_process = subprocess.Popen(
                    [
                        "piper-tts",
                        "--model", model_path,
                        "--length_scale", str(speed),
                        "--noise_scale", str(noise),
                        "--noise_w", str(noise),
                        "--output_file", tmp_file
                    ],
                    stdin=subprocess.PIPE,
                    text=True
                )
            self.current_process.communicate(input=text)
        except Exception as e:
            print("TTS generation failed:", e)
            return
        finally:
            with self.lock:
                self.current_process = None

        if not os.path.isfile(tmp_file):
            print("ERROR: WAV file was not created!")
            return
# --- Playback ---
        try:
            play_cmd = [self.paplay_cmd, tmp_file]

            if output_device != "default":
                if self.pipewire:
                    # PipeWire: pw-play doesn't have --device; we rely on target node or properties
                    # For specific sink, you may need to set PW_TARGET or use pactl/ wpctl to move stream
                    # Simplest for now: just play to default and let user choose sink via UI / system
                    pass  # ← pw-play ignores --device; remove or ignore
                else:
                    play_cmd += ["--device", output_device]

            if self.has_sox and abs(volume - 1.0) > 0.001:  # avoid tiny float diffs
                # Use sox to adjust volume → output to stdout → pipe to pw-play -
                sox_cmd = [
                    "sox",
                    tmp_file,
                    "-t", "wav",
                    "-",                # output to stdout
                    "vol", str(volume)
                ]

                # Run sox → pipe stdout → pw-play stdin
                with self.lock:
                    sox_proc = subprocess.Popen(sox_cmd, stdout=subprocess.PIPE)
                    self.play_process = subprocess.Popen(
                        play_cmd + ["-"],  # pw-play reads from stdin
                        stdin=sox_proc.stdout
                    )
                    sox_proc.stdout.close()  # allow sox to receive SIGPIPE if needed

                # Wait on the play process (sox will finish first)
                self.play_process.wait()
                sox_proc.wait()  # clean up
            else:
                # Direct playback, no sox
                with self.lock:
                    self.play_process = subprocess.Popen(play_cmd)
                self.play_process.wait()

        except Exception as e:
            print("Playback failed:", e)
        finally:
            with self.lock:
                self.play_process = None

        # Optional: clean up temp file
        try:
            os.unlink(tmp_file)
        except:
            pass