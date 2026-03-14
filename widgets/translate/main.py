#!/usr/bin/env python3
"""Translation popup — GTK4 widget using Claude Sonnet via claude CLI."""

import os, subprocess, sys, threading
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))

from lib.widget_base import Gdk, Gtk, WidgetPopup, load_css

from gi.repository import GLib

CSS = load_css(os.path.join(_DIR, "style.css"))

LANGUAGES = [
    ("auto", "Auto"),
    ("en", "English"),
    ("ru", "Russian"),
    ("de", "German"),
    ("fr", "French"),
    ("es", "Spanish"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("zh", "Chinese"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("ar", "Arabic"),
    ("tr", "Turkish"),
    ("pl", "Polish"),
    ("nl", "Dutch"),
    ("uk", "Ukrainian"),
]


def get_selected_text():
    """Get the currently selected text via primary selection."""
    try:
        result = subprocess.run(
            ["wl-paste", "-p", "-n"],
            capture_output=True, text=True, timeout=2,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def translate(text, target_lang):
    """Translate text using claude CLI."""
    if target_lang == "auto":
        lang_instruction = (
            "Auto-detect the source language. "
            "If the text is in Russian, translate to English. "
            "If the text is in English, translate to Russian. "
            "For any other language, translate to English."
        )
    else:
        lang_name = dict(LANGUAGES).get(target_lang, target_lang)
        lang_instruction = f"Translate the text to {lang_name}."

    prompt = (
        f"{lang_instruction} "
        "Output ONLY the translation, nothing else. "
        "No explanations, no quotes, no prefixes."
    )

    result = subprocess.run(
        [
            "claude", "-p",
            "--model", "sonnet",
            "--no-session-persistence",
            prompt,
        ],
        input=text,
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "claude CLI failed")
    return result.stdout.strip()


class TranslatePopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.translate")
        self._translation = ""

    def build_ui(self):
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        container.add_css_class("translate-container")

        # Title row with language selector
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="Translate")
        title.add_css_class("translate-title")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        title_row.append(title)

        lang_label = Gtk.Label(label="to:")
        lang_label.add_css_class("translate-section-label")
        lang_label.set_valign(Gtk.Align.CENTER)
        title_row.append(lang_label)

        self._lang_dropdown = Gtk.DropDown.new_from_strings(
            [name for _, name in LANGUAGES]
        )
        self._lang_dropdown.set_selected(0)  # Auto
        self._lang_dropdown.add_css_class("translate-lang-box")
        self._lang_dropdown.connect("notify::selected", self._on_lang_changed)
        title_row.append(self._lang_dropdown)

        container.append(title_row)

        # Source text
        source_label = Gtk.Label(label="source")
        source_label.add_css_class("translate-section-label")
        source_label.set_halign(Gtk.Align.START)
        container.append(source_label)

        self._source_text = Gtk.Label()
        self._source_text.add_css_class("translate-source")
        self._source_text.set_wrap(True)
        self._source_text.set_max_width_chars(60)
        self._source_text.set_halign(Gtk.Align.FILL)
        self._source_text.set_xalign(0)
        self._source_text.set_selectable(True)
        container.append(self._source_text)

        separator = Gtk.Separator()
        separator.add_css_class("translate-separator")
        container.append(separator)

        # Translation result
        result_label = Gtk.Label(label="translation")
        result_label.add_css_class("translate-section-label")
        result_label.set_halign(Gtk.Align.START)
        container.append(result_label)

        self._result_text = Gtk.Label()
        self._result_text.add_css_class("translate-result")
        self._result_text.set_wrap(True)
        self._result_text.set_max_width_chars(60)
        self._result_text.set_halign(Gtk.Align.FILL)
        self._result_text.set_xalign(0)
        self._result_text.set_selectable(True)
        container.append(self._result_text)

        # Status / copy row
        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._status = Gtk.Label()
        self._status.add_css_class("translate-status")
        self._status.set_hexpand(True)
        self._status.set_halign(Gtk.Align.START)
        action_row.append(self._status)

        self._copy_btn = Gtk.Button(label="copy")
        self._copy_btn.add_css_class("translate-copy-btn")
        self._copy_btn.set_sensitive(False)
        self._copy_btn.connect("clicked", self._on_copy)
        action_row.append(self._copy_btn)

        container.append(action_row)

        # Grab selected text and start translating
        selected = get_selected_text()
        if selected:
            self._source_text.set_text(selected)
            self._run_translation(selected)
        else:
            self._source_text.set_text("(no text selected)")
            self._status.set_text("select text before pressing the shortcut")
            self._status.add_css_class("translate-error")

        return container

    def _run_translation(self, text):
        """Run translation in background thread."""
        self._status.set_text("translating...")
        self._status.remove_css_class("translate-error")
        self._copy_btn.set_sensitive(False)
        self._result_text.set_text("")

        idx = self._lang_dropdown.get_selected()
        target = LANGUAGES[idx][0]

        def do_translate():
            try:
                result = translate(text, target)
                GLib.idle_add(self._on_translate_done, result)
            except Exception as e:
                GLib.idle_add(self._on_translate_error, str(e))

        thread = threading.Thread(target=do_translate, daemon=True)
        thread.start()

    def _on_translate_done(self, result):
        self._translation = result
        self._result_text.set_text(result)
        self._status.set_text("")
        self._copy_btn.set_sensitive(True)

    def _on_translate_error(self, error):
        self._status.set_text(f"error: {error}")
        self._status.add_css_class("translate-error")

    def _on_lang_changed(self, dropdown, _param):
        """Re-translate when language changes."""
        source = self._source_text.get_text()
        if source and source != "(no text selected)":
            self._run_translation(source)

    def _on_copy(self, _button):
        if self._translation:
            subprocess.run(
                ["wl-copy", "--", self._translation],
                check=False,
            )
            self._status.set_text("copied!")

    def _on_key(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q):
            self.quit()
            return True
        return False


if __name__ == "__main__":
    TranslatePopup.CSS = CSS
    TranslatePopup().run()
