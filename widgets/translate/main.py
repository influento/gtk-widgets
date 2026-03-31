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

        # Source text area — stack with display (label) and input (textview) modes
        source_label = Gtk.Label(label="source")
        source_label.add_css_class("translate-section-label")
        source_label.set_halign(Gtk.Align.START)
        container.append(source_label)

        self._source_stack = Gtk.Stack()
        self._source_stack.set_transition_type(Gtk.StackTransitionType.NONE)

        # Display mode: read-only label
        self._source_text = Gtk.Label()
        self._source_text.add_css_class("translate-source")
        self._source_text.set_wrap(True)
        self._source_text.set_max_width_chars(60)
        self._source_text.set_halign(Gtk.Align.FILL)
        self._source_text.set_xalign(0)
        self._source_text.set_selectable(True)
        self._source_stack.add_named(self._source_text, "display")

        # Input mode: editable TextView in a ScrolledWindow
        self._source_input = Gtk.TextView()
        self._source_input.add_css_class("ezpick-input")
        self._source_input.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._source_input.set_accepts_tab(False)

        input_scroll = Gtk.ScrolledWindow()
        input_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        input_scroll.set_min_content_height(60)
        input_scroll.set_max_content_height(100)
        input_scroll.set_child(self._source_input)

        self._source_stack.add_named(input_scroll, "input")
        container.append(self._source_stack)

        # Key handler on TextView: Ctrl+Return runs translation
        input_key_ctrl = Gtk.EventControllerKey()
        input_key_ctrl.connect("key-pressed", self._on_input_key)
        self._source_input.add_controller(input_key_ctrl)

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

        # Choose mode based on whether text was selected
        selected = get_selected_text()
        if selected:
            self._source_stack.set_visible_child_name("display")
            self._source_text.set_text(selected)
            self._run_translation(selected)
        else:
            self._source_stack.set_visible_child_name("input")
            self._status.set_text("type or paste text, then press Ctrl+Enter")
            GLib.idle_add(self._source_input.grab_focus)

        return container

    def _get_current_text(self):
        if self._source_stack.get_visible_child_name() == "input":
            buf = self._source_input.get_buffer()
            return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()
        return self._source_text.get_text().strip()

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
        text = self._get_current_text()
        if text:
            self._run_translation(text)

    def _on_input_key(self, controller, keyval, keycode, state):
        """Handle Ctrl+Return in the input TextView to trigger translation."""
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            text = self._get_current_text()
            if text:
                self._run_translation(text)
            return True
        return False

    def _on_copy(self, _button):
        if self._translation:
            subprocess.run(
                ["wl-copy", "--", self._translation],
                check=False,
            )
            self._status.set_text("copied!")

    def _on_key(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        # Don't close on 'q' when the user is typing in the input TextView
        if keyval == Gdk.KEY_q:
            if self._source_stack.get_visible_child_name() == "input":
                return False
            self.quit()
            return True
        return False


if __name__ == "__main__":
    TranslatePopup.CSS = CSS
    TranslatePopup().run()
