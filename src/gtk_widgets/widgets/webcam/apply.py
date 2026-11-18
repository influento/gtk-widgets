"""webcam-apply: write the saved camera settings to the camera again (stdlib).
A camera forgets them when unplugged; dotfiles runs this when it comes back."""

import sys

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.widgets.webcam import settings, v4l2
from gtk_widgets.widgets.webcam.parse import Led

LED_MODES = {
    Led.OFF: v4l2.LedMode.OFF,
    Led.ON: v4l2.LedMode.ON,
    Led.AUTO: v4l2.LedMode.AUTO,
}


def main(argv: list[str] | None = None) -> int:
    """Exit 0 applied, 1 no camera, 2 an error."""
    del argv
    device = v4l2.find_camera()
    if device is None:
        print("webcam-apply: no camera", file=sys.stderr)
        return 1
    match settings.load():
        case ParseError() as e:
            print(f"webcam-apply: {e}", file=sys.stderr)
            return 2
        case saved:
            pass
    match v4l2.apply_values(device, saved.controls):
        case v4l2.CameraError() as e:
            print(f"webcam-apply: {device}: {e.strerror}", file=sys.stderr)
            return 2
        case []:
            pass
        case failed:
            print(f"webcam-apply: not applied: {', '.join(failed)}", file=sys.stderr)
    if saved.led is not None and (e := v4l2.set_led(device, LED_MODES[saved.led])):
        print(f"webcam-apply: LED: {e.strerror}", file=sys.stderr)
    return 0
