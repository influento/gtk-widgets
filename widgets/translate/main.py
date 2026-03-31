#!/usr/bin/env python3
"""Ezpick — multi-action text tool using Claude Sonnet via claude CLI."""

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


def claude_ask(prompt, input_text, timeout=30):
    """Send prompt + input to Claude Sonnet via CLI. Returns response text."""
    result = subprocess.run(
        ["claude", "-p", "--model", "sonnet", "--no-session-persistence", prompt],
        input=input_text, capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "claude CLI failed")
    return result.stdout.strip()


def run_translate(text, target_lang="auto", **kwargs):
    """Translate text using Claude CLI."""
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
    return claude_ask(prompt, text)


def run_fix_english(text, **kwargs):
    """Fix English grammar and style."""
    return "(not implemented)"


def run_dictionary(text, **kwargs):
    """Look up dictionary definition."""
    return "(not implemented)"


ACTIONS = [
    {"id": "translate", "label": "Translate", "result_label": "translation", "run": run_translate},
    {"id": "fix-english", "label": "Fix English", "result_label": "corrected text", "run": run_fix_english},
    {"id": "dictionary", "label": "Dictionary", "result_label": "definition", "run": run_dictionary},
]


class EzpickPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.ezpick")
        self._result = ""
        self._active_action = 0
        self._action_buttons = []

    def build_ui(self):
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        container.add_css_class("ezpick-container")

        # Action switcher row
        actions_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        actions_row.add_css_class("ezpick-actions")
        for i, action in enumerate(ACTIONS):
            btn = Gtk.Button(label=action["label"])
            if i == self._active_action:
                btn.add_css_class("ezpick-action-active")
            else:
                btn.add_css_class("ezpick-action")
            btn.connect("clicked", self._on_action_clicked, i)
            actions_row.append(btn)
            self._action_buttons.append(btn)
        container.append(actions_row)

        # Language row (only visible for translate)
        self._lang_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lang_label = Gtk.Label(label="to:")
        lang_label.add_css_class("ezpick-section-label")
        lang_label.set_valign(Gtk.Align.CENTER)
        self._lang_row.append(lang_label)

        self._lang_dropdown = Gtk.DropDown.new_from_strings(
            [name for _, name in LANGUAGES]
        )
        self._lang_dropdown.set_selected(0)
        self._lang_dropdown.add_css_class("ezpick-lang-box")
        self._lang_dropdown.connect("notify::selected", self._on_lang_changed)
        self._lang_row.append(self._lang_dropdown)

        container.append(self._lang_row)

        # Source text
        source_label = Gtk.Label(label="source")
        source_label.add_css_class("ezpick-section-label")
        source_label.set_halign(Gtk.Align.START)
        container.append(source_label)

        self._source_text = Gtk.Label()
        self._source_text.add_css_class("ezpick-source")
        self._source_text.set_wrap(True)
        self._source_text.set_max_width_chars(60)
        self._source_text.set_halign(Gtk.Align.FILL)
        self._source_text.set_xalign(0)
        self._source_text.set_selectable(True)
        container.append(self._source_text)

        separator = Gtk.Separator()
        separator.add_css_class("ezpick-separator")
        container.append(separator)

        # Result
        self._result_label = Gtk.Label(label=ACTIONS[self._active_action]["result_label"])
        self._result_label.add_css_class("ezpick-section-label")
        self._result_label.set_halign(Gtk.Align.START)
        container.append(self._result_label)

        self._result_text = Gtk.Label()
        self._result_text.add_css_class("ezpick-result")
        self._result_text.set_wrap(True)
        self._result_text.set_max_width_chars(60)
        self._result_text.set_halign(Gtk.Align.FILL)
        self._result_text.set_xalign(0)
        self._result_text.set_selectable(True)
        container.append(self._result_text)

        # Status / copy row
        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._status = Gtk.Label()
        self._status.add_css_class("ezpick-status")
        self._status.set_hexpand(True)
        self._status.set_halign(Gtk.Align.START)
        action_row.append(self._status)

        self._copy_btn = Gtk.Button(label="copy")
        self._copy_btn.add_css_class("ezpick-copy-btn")
        self._copy_btn.set_sensitive(False)
        self._copy_btn.connect("clicked", self._on_copy)
        action_row.append(self._copy_btn)

        container.append(action_row)

        # Grab selected text and auto-run default action
        selected = get_selected_text()
        if selected:
            self._source_text.set_text(selected)
            self._run_action(selected)
        else:
            self._source_text.set_text("(no text selected)")
            self._status.set_text("select text before pressing the shortcut")
            self._status.add_css_class("ezpick-error")

        return container

    def _run_action(self, text):
        """Run the active action in a background thread."""
        action = ACTIONS[self._active_action]
        self._status.set_text(f"running {action['label'].lower()}...")
        self._status.remove_css_class("ezpick-error")
        self._copy_btn.set_sensitive(False)
        self._result_text.set_text("")

        kwargs = {}
        if action["id"] == "translate":
            idx = self._lang_dropdown.get_selected()
            kwargs["target_lang"] = LANGUAGES[idx][0]

        def do_run():
            try:
                result = action["run"](text, **kwargs)
                GLib.idle_add(self._on_action_done, result)
            except Exception as e:
                GLib.idle_add(self._on_action_error, str(e))

        thread = threading.Thread(target=do_run, daemon=True)
        thread.start()

    def _on_action_done(self, result):
        self._result = result
        self._result_text.set_text(result)
        self._status.set_text("")
        self._copy_btn.set_sensitive(True)

    def _on_action_error(self, error):
        self._status.set_text(f"error: {error}")
        self._status.add_css_class("ezpick-error")

    def _on_action_clicked(self, _button, index):
        """Switch to a different action."""
        if index == self._active_action:
            return

        # Update button styles
        self._action_buttons[self._active_action].remove_css_class("ezpick-action-active")
        self._action_buttons[self._active_action].add_css_class("ezpick-action")
        self._action_buttons[index].remove_css_class("ezpick-action")
        self._action_buttons[index].add_css_class("ezpick-action-active")

        self._active_action = index

        # Update result section label
        self._result_label.set_text(ACTIONS[index]["result_label"])

        # Show/hide language row
        self._lang_row.set_visible(ACTIONS[index]["id"] == "translate")

        # Re-run if we have input text
        source = self._source_text.get_text()
        if source and source != "(no text selected)":
            self._run_action(source)

    def _on_lang_changed(self, dropdown, _param):
        """Re-run translate when language changes."""
        if ACTIONS[self._active_action]["id"] != "translate":
            return
        source = self._source_text.get_text()
        if source and source != "(no text selected)":
            self._run_action(source)

    def _on_copy(self, _button):
        if self._result:
            subprocess.run(
                ["wl-copy", "--", self._result],
                check=False,
            )
            self._status.set_text("copied!")

    def _on_key(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q):
            self.quit()
            return True
        return False


if __name__ == "__main__":
    EzpickPopup.CSS = CSS
    EzpickPopup().run()
