"""What the popup and the popup without libpulse share: glyphs, frame, error box."""

from gtk_widgets.lib.ui.copy_label import copyable
from gtk_widgets.lib.ui.widget_base import Gtk

APP_ID = "dev.dotfiles.audio"  # also application.id of its meter and test streams

ICON = {
    "speaker": "\U000f057e",  # nf-md-volume_high
    "speaker_mute": "\U000f0581",  # nf-md-volume_off
    "mic": "\U000f036c",  # nf-md-microphone
    "mic_mute": "\U000f036d",  # nf-md-microphone_off
    "lock": "\U000f033e",  # nf-md-lock
    "unlock": "\U000f033f",  # nf-md-lock_open
    "expand": "\U000f0142",  # nf-md-chevron_right
    "collapse": "\U000f0140",  # nf-md-chevron_down
    "default": "\U000f04ce",  # nf-md-star
    "not_default": "\U000f04d2",  # nf-md-star_outline
    "card": "\U000f04c3",  # nf-md-speaker
    "bell": "\U000f009a",  # nf-md-bell
    "offline": "\U000f0581",  # nf-md-volume_off
    "kill": "\U000f0156",  # nf-md-close
    "meters": "\U000f0128",  # nf-md-chart_bar
    "record": "\U000f044a",  # nf-md-record
    "stop": "\U000f04db",  # nf-md-stop
}


def popup_frame() -> tuple[Gtk.Box, Gtk.Box]:
    """The popup's container and its header row, which holds the title."""
    container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    container.add_css_class("au-container")
    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    title = Gtk.Label(label="Audio", xalign=0, hexpand=True)
    title.add_css_class("au-title")
    header.append(title)
    container.append(header)
    return container, header


def error_box(message: str, hint: str) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.set_halign(Gtk.Align.CENTER)
    icon = Gtk.Label(label=ICON["offline"])
    icon.add_css_class("au-error-icon")
    box.append(icon)
    msg = Gtk.Label(label=message)
    msg.add_css_class("au-error-msg")
    copyable(msg)
    box.append(msg)
    hint_label = Gtk.Label(label=hint)
    hint_label.add_css_class("au-error-hint")
    box.append(hint_label)
    return box
