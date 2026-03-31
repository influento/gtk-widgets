#!/usr/bin/env python3
"""ezpick — multi-action text tool using Claude Sonnet via claude CLI."""

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

ACTIONS = ["Translate", "Fix English", "Dictionary"]


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


def call_claude(prompt, text):
    """Run a prompt through claude CLI with input text."""
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


def run_translate(text, target_lang):
    """Translate text."""
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
    return call_claude(prompt, text)


def run_fix_english(text):
    """Fix English grammar and style."""
    prompt = (
        "You are a grammar and style corrector. "
        "First, output the corrected version of the text. "
        "Then output a blank line, followed by a line '---', then a blank line. "
        "Then list each change you made, one per line, starting with '• '. "
        "Each explanation should be concise (one line). "
        "If the text is already correct, output it unchanged and write '• No changes needed.' "
        "Do not add any other commentary."
    )
    return call_claude(prompt, text)


def run_dictionary(text):
    """Look up a word or short phrase."""
    prompt = (
        "You are a dictionary. For the given word or phrase, provide:\n"
        "DEFINITION:\nA clear, concise definition.\n\n"
        "ETYMOLOGY:\nBrief origin of the word.\n\n"
        "EXAMPLES:\n• 2-3 usage examples as bullet points.\n\n"
        "Use exactly these section headers. Be concise. "
        "If the input is not a recognizable word or phrase, say so briefly."
    )
    return call_claude(prompt, text)


class EzpickPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.ezpick")
        self._result_content = ""
        self._active_action = 0  # Translate by default
        self._action_buttons = []

    def build_ui(self):
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        container.add_css_class("translate-container")

        # Action switcher row
        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        action_row.add_css_class("ezpick-action-row")
        for i, name in enumerate(ACTIONS):
            btn = Gtk.Button(label=name)
            btn.add_css_class("ezpick-action-btn")
            if i == 0:
                btn.add_css_class("ezpick-action-active")
            btn.connect("clicked", self._on_action_clicked, i)
            action_row.append(btn)
            self._action_buttons.append(btn)
        container.append(action_row)

        # Language selector (only visible for Translate action)
        self._lang_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lang_label = Gtk.Label(label="to:")
        lang_label.add_css_class("translate-section-label")
        lang_label.set_valign(Gtk.Align.CENTER)
        self._lang_row.append(lang_label)

        self._lang_dropdown = Gtk.DropDown.new_from_strings(
            [name for _, name in LANGUAGES]
        )
        self._lang_dropdown.set_selected(0)
        self._lang_dropdown.add_css_class("translate-lang-box")
        self._lang_dropdown.connect("notify::selected", self._on_lang_changed)
        self._lang_row.append(self._lang_dropdown)
        container.append(self._lang_row)

        # Source section label
        self._source_label = Gtk.Label(label="source")
        self._source_label.add_css_class("translate-section-label")
        self._source_label.set_halign(Gtk.Align.START)
        container.append(self._source_label)

        # Source area — stack with display (label) and input (textview) modes
        self._source_stack = Gtk.Stack()
        self._source_stack.set_transition_type(Gtk.StackTransitionType.NONE)

        # Display mode: read-only label for when text was selected
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

        # Key handler on TextView: Ctrl+Return runs action
        input_key_ctrl = Gtk.EventControllerKey()
        input_key_ctrl.connect("key-pressed", self._on_input_key)
        self._source_input.add_controller(input_key_ctrl)

        separator = Gtk.Separator()
        separator.add_css_class("translate-separator")
        container.append(separator)

        # Result section label
        self._result_label = Gtk.Label(label="result")
        self._result_label.add_css_class("translate-section-label")
        self._result_label.set_halign(Gtk.Align.START)
        container.append(self._result_label)

        # Result text
        self._result_text = Gtk.Label()
        self._result_text.add_css_class("translate-result")
        self._result_text.set_wrap(True)
        self._result_text.set_max_width_chars(60)
        self._result_text.set_halign(Gtk.Align.FILL)
        self._result_text.set_xalign(0)
        self._result_text.set_selectable(True)
        container.append(self._result_text)

        # Status / copy row
        bottom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._status = Gtk.Label()
        self._status.add_css_class("translate-status")
        self._status.set_hexpand(True)
        self._status.set_halign(Gtk.Align.START)
        bottom_row.append(self._status)

        self._copy_btn = Gtk.Button(label="copy")
        self._copy_btn.add_css_class("translate-copy-btn")
        self._copy_btn.set_sensitive(False)
        self._copy_btn.connect("clicked", self._on_copy)
        bottom_row.append(self._copy_btn)

        container.append(bottom_row)

        # Determine mode based on whether text was selected
        selected = get_selected_text()
        if selected:
            self._source_stack.set_visible_child_name("display")
            self._source_text.set_text(selected)
            self._run_action(selected)
        else:
            self._source_stack.set_visible_child_name("input")
            self._status.set_text("type or paste text, then press Ctrl+Enter")
            GLib.idle_add(self._source_input.grab_focus)

        self._update_result_label()

        return container

    def _get_current_text(self):
        if self._source_stack.get_visible_child_name() == "input":
            buf = self._source_input.get_buffer()
            return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()
        return self._source_text.get_text().strip()

    def _on_action_clicked(self, _btn, action_idx):
        """Switch active action and re-run."""
        if action_idx == self._active_action:
            return
        self._active_action = action_idx
        for i, btn in enumerate(self._action_buttons):
            if i == action_idx:
                btn.add_css_class("ezpick-action-active")
            else:
                btn.remove_css_class("ezpick-action-active")

        # Show/hide language selector
        self._lang_row.set_visible(action_idx == 0)
        self._update_result_label()

        text = self._get_current_text()
        if text:
            self._run_action(text)

    def _update_result_label(self):
        """Update the result section label based on active action."""
        labels = ["translation", "corrected text", "definition"]
        self._result_label.set_text(labels[self._active_action])

    def _on_lang_changed(self, dropdown, _param):
        """Re-translate when language changes."""
        if self._active_action != 0:
            return
        text = self._get_current_text()
        if text:
            self._run_action(text)

    def _on_input_key(self, controller, keyval, keycode, state):
        """Handle Ctrl+Return in the input TextView to trigger the active action."""
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            text = self._get_current_text()
            if text:
                self._run_action(text)
            return True
        return False

    def _run_action(self, text):
        """Run the active action in a background thread."""
        action_names = ["translating...", "fixing...", "looking up..."]
        self._status.set_text(action_names[self._active_action])
        self._status.remove_css_class("translate-error")
        self._copy_btn.set_sensitive(False)
        self._result_text.set_text("")

        action_idx = self._active_action
        target_lang = LANGUAGES[self._lang_dropdown.get_selected()][0]

        def do_work():
            try:
                if action_idx == 0:
                    result = run_translate(text, target_lang)
                elif action_idx == 1:
                    result = run_fix_english(text)
                else:
                    result = run_dictionary(text)
                GLib.idle_add(self._on_action_done, result)
            except Exception as e:
                GLib.idle_add(self._on_action_error, str(e))

        thread = threading.Thread(target=do_work, daemon=True)
        thread.start()

    def _on_action_done(self, result):
        self._result_content = result
        self._result_text.set_text(result)
        self._status.set_text("")
        self._copy_btn.set_sensitive(True)

    def _on_action_error(self, error):
        self._status.set_text(f"error: {error}")
        self._status.add_css_class("translate-error")

    def _on_copy(self, _button):
        if self._result_content:
            subprocess.run(
                ["wl-copy", "--", self._result_content],
                check=False,
            )
            self._status.set_text("copied!")

    def _on_key(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        if keyval == Gdk.KEY_q:
            if self._source_stack.get_visible_child_name() == "input":
                return False
            self.quit()
            return True
        return False


if __name__ == "__main__":
    EzpickPopup.CSS = CSS
    EzpickPopup().run()
