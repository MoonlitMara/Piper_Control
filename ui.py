import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango

import threading
from typing import Dict, Any, List, Tuple

from engine import PiperEngine
from settings import load_settings, save_settings
from utils import list_voices, list_audio_sinks


class PiperUI(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="local.piper.control.portable")
        self.settings: Dict[str, Any] = load_settings()
        self.engine = PiperEngine()
        self.tts_thread: threading.Thread | None = None

        # display_name → real sink name
        self.sink_map: Dict[str, str] = {}

        # History & Favorites
        self.history: List[str] = self.settings.get("history", [])[:10]
        self.favorites: List[str] = self.settings.get("favorites", [])

    def do_activate(self) -> None:
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("Piper TTS Control")
        self.window.set_default_size(700, 720)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)

        # ── Text input ───────────────────────────────────────────────────
        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.text_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR)
        scroll.set_child(self.text_view)
        main_box.append(scroll)

        # ── Audio Settings expander ─────────────────────────────────────
        audio_exp = Gtk.Expander(label="Audio Settings", expanded=False)
        audio_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        audio_box.set_margin_top(12)
        audio_box.set_margin_bottom(12)
        audio_box.set_margin_start(16)
        audio_box.set_margin_end(16)

        # Voice dropdown
        voices = list_voices() or ["No voices found"]
        self.voice_combo = self._create_dropdown(voices, "voice")
        audio_box.append(self._labeled_row("Voice:", self.voice_combo))

        # Output device dropdown
        sinks = list_audio_sinks()
        display_names, self.sink_map = self._build_device_list(sinks)
        self.device_combo = self._create_dropdown(display_names, "output_device")
        audio_box.append(self._labeled_row("Output:", self.device_combo))

        audio_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self._add_slider(audio_box, "Speed",  "speed",  0.7, 1.5, 0.05)
        self._add_slider(audio_box, "Noise",  "noise",  0.0, 1.0,  0.05)
        self._add_slider(audio_box, "Volume", "volume", 0.0, 2.0,  0.05)

        audio_exp.set_child(audio_box)
        main_box.append(audio_exp)

        # ── History & Favorites expander ────────────────────────────────
        hist_exp = Gtk.Expander(label="History & Favorites", expanded=False)
        hist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        hist_box.set_margin_top(12)
        hist_box.set_margin_bottom(12)
        hist_box.set_margin_start(16)
        hist_box.set_margin_end(16)

        # Recent
        hist_box.append(Gtk.Label(label="Recent messages", xalign=0.0))
        self.recent_list = Gtk.ListBox()
        self.recent_list.set_selection_mode(Gtk.SelectionMode.NONE)
        recent_scroll = Gtk.ScrolledWindow()
        recent_scroll.set_child(self.recent_list)
        recent_scroll.set_max_content_height(140)
        hist_box.append(recent_scroll)
        self._refresh_recent()

        hist_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Favorites
        hist_box.append(Gtk.Label(label="Favorites", xalign=0.0))
        self.fav_list = Gtk.ListBox()
        self.fav_list.set_selection_mode(Gtk.SelectionMode.NONE)
        fav_scroll = Gtk.ScrolledWindow()
        fav_scroll.set_child(self.fav_list)
        fav_scroll.set_max_content_height(140)
        hist_box.append(fav_scroll)
        self._refresh_favorites()

        hist_exp.set_child(hist_box)
        main_box.append(hist_exp)

        # ── Buttons ─────────────────────────────────────────────────────
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(12)

        speak = Gtk.Button(label="Speak")
        speak.connect("clicked", self.on_speak)

        stop = Gtk.Button(label="Stop")
        stop.connect("clicked", lambda b: self.engine.stop())

        clear = Gtk.Button(label="Clear")
        clear.connect("clicked", lambda b: self.text_view.get_buffer().set_text(""))

        self.mute_btn = Gtk.ToggleButton(label="Mute")
        muted = self.settings.get("mute", False)
        self.mute_btn.set_active(muted)
        self.mute_btn.connect("toggled", self.on_mute_toggled)
        if muted:
            self.mute_btn.set_label("Unmute")
            self.mute_btn.add_css_class("destructive-action")

        btn_box.append(speak)
        btn_box.append(stop)
        btn_box.append(clear)
        btn_box.append(self.mute_btn)

        main_box.append(btn_box)

        self.window.set_child(main_box)
        self.window.present()

    # ────────────────────────────────────────────────────────────────
    #   Helpers
    # ────────────────────────────────────────────────────────────────

    def _labeled_row(self, text: str, widget: Gtk.Widget) -> Gtk.Box:
        box = Gtk.Box(spacing=12)
        lbl = Gtk.Label(label=text, xalign=0.0)
        lbl.set_width_chars(14)
        box.append(lbl)
        box.append(widget)
        widget.set_hexpand(True)
        return box

    def _create_dropdown(self, items: List[str], key: str) -> Gtk.DropDown:
        model = Gtk.StringList()
        for i in items:
            model.append(i)

        dd = Gtk.DropDown(model=model)
        dd.set_factory(self._create_ellipsizing_factory())

        saved = self.settings.get(key)
        if saved in items:
            dd.set_selected(items.index(saved))
        else:
            dd.set_selected(0)
        return dd

    def _create_ellipsizing_factory(self) -> Gtk.SignalListItemFactory:
        factory = Gtk.SignalListItemFactory()

        def setup(f, item):
            lbl = Gtk.Label(xalign=0.0)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            lbl.set_width_chars(45)
            item.set_child(lbl)

        def bind(f, item):
            lbl = item.get_child()
            lbl.set_text(item.get_item().get_string())

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        return factory

    def _build_device_list(self, sinks: List[str]) -> Tuple[List[str], Dict[str, str]]:
        displays = []
        mapping = {}

        for name in sinks:
            if not name:
                continue

            display = name
            if name == "default":
                display = "Default"
            elif "analog-stereo" in name.lower():
                display = "Analog Stereo"
            elif "easyeffects" in name.lower():
                display = "EasyEffects"
            elif "virtual" in name.lower():
                display = "Virtual"
            else:
                if '.' in name:
                    display = name.split('.')[-1].replace('_', ' ').replace('-', ' ').title()
                if len(display) > 38:
                    display = display[:35] + "…"

            base = display
            i = 1
            while display in mapping:
                display = f"{base} ({i})"
                i += 1

            displays.append(display)
            mapping[display] = name

        if not displays:
            displays = ["Default"]
            mapping["Default"] = "default"

        return displays, mapping

    def _add_slider(self, parent: Gtk.Box, lbl: str, key: str,
                    minv: float, maxv: float, step: float):
        row = Gtk.Box(spacing=12)
        label = Gtk.Label(label=lbl, xalign=0.0)
        label.set_width_chars(14)
        row.append(label)

        val_lbl = Gtk.Label(label=f"{self.settings.get(key, 1.0):.2f}")
        row.append(val_lbl)

        slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, minv, maxv, step)
        slider.set_value(self.settings.get(key, 1.0))
        slider.set_draw_value(False)
        slider.set_hexpand(True)
        slider.set_size_request(180, -1)
        row.append(slider)

        parent.append(row)

        def changed(s, *_):
            v = s.get_value()
            val_lbl.set_text(f"{v:.2f}")
            self.settings[key] = round(v, 3)
            save_settings(self.settings)

        slider.connect("value-changed", changed)

    # ────────────────────────────────────────────────────────────────
    #   History & Favorites
    # ────────────────────────────────────────────────────────────────

    def _refresh_recent(self):
        while c := self.recent_list.get_first_child():
            self.recent_list.remove(c)

        for text in self.history:
            self._append_history_row(self.recent_list, text, favorite=False)

    def _refresh_favorites(self):
        while c := self.fav_list.get_first_child():
            self.fav_list.remove(c)

        for text in self.favorites:
            self._append_history_row(self.fav_list, text, favorite=True)

    def _append_history_row(self, listbox: Gtk.ListBox, text: str, favorite: bool):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(spacing=8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(6)
        box.set_margin_end(6)

        preview = (text[:68] + "…") if len(text) > 68 else text
        lbl = Gtk.Label(label=preview, ellipsize=Pango.EllipsizeMode.END)
        lbl.set_xalign(0.0)
        lbl.set_hexpand(True)
        box.append(lbl)

        use = Gtk.Button(label="Use")
        use.connect("clicked", lambda _, t=text: self.text_view.get_buffer().set_text(t))
        box.append(use)

        if not favorite:
            star = Gtk.Button(label="★")
            star.connect("clicked", lambda _, t=text: self._add_to_fav(t))
            box.append(star)
        else:
            delete = Gtk.Button(label="Delete")
            delete.add_css_class("destructive-action")
            delete.connect("clicked", lambda _, t=text: self._remove_from_fav(t))
            box.append(delete)

        row.set_child(box)
        listbox.append(row)

    def _add_to_fav(self, text: str):
        if text and text not in self.favorites:
            self.favorites.insert(0, text)
            self.settings["favorites"] = self.favorites
            save_settings(self.settings)
            self._refresh_favorites()

    def _remove_from_fav(self, text: str):
        if text in self.favorites:
            self.favorites.remove(text)
            self.settings["favorites"] = self.favorites
            save_settings(self.settings)
            self._refresh_favorites()

    # ────────────────────────────────────────────────────────────────
    #   Actions
    # ────────────────────────────────────────────────────────────────

    def on_speak(self, button):
        buf = self.text_view.get_buffer()
        start, end = buf.get_bounds()
        text = buf.get_text(start, end, False).strip()
        if not text:
            return

        # Voice
        idx = self.voice_combo.get_selected()
        voices = list_voices() or ["en_GB-cori-high"]
        voice = voices[idx] if idx < len(voices) else voices[0]
        self.settings["voice"] = voice

        # Device
        idx = self.device_combo.get_selected()
        device = "default"
        if idx != Gtk.INVALID_LIST_POSITION and self.sink_map:
            disp = self.device_combo.get_selected_item().get_string()
            device = self.sink_map.get(disp, "default")
        self.settings["output_device"] = device

        save_settings(self.settings)

        # Add to history
        if text in self.history:
            self.history.remove(text)
        self.history.insert(0, text)
        self.history = self.history[:10]
        self.settings["history"] = self.history
        save_settings(self.settings)
        self._refresh_recent()

        if self.tts_thread and self.tts_thread.is_alive():
            return

        self.tts_thread = threading.Thread(
            target=self.engine._run,
            args=(text, self.settings),
            daemon=True
        )
        self.tts_thread.start()

    def on_mute_toggled(self, btn: Gtk.ToggleButton):
        muted = btn.get_active()
        self.engine.set_mute(muted)
        self.settings["mute"] = muted
        save_settings(self.settings)

        if muted:
            btn.set_label("Unmute")
            btn.add_css_class("destructive-action")
        else:
            btn.set_label("Mute")
            btn.remove_css_class("destructive-action")


def main():
    app = PiperUI()
    app.run()


if __name__ == "__main__":
    main()