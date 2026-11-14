# pulsectl (vendored)

ctypes bindings to libpulse, vendored from
[mk-fg/python-pulse-control](https://github.com/mk-fg/python-pulse-control) at commit
`c994e9ad55844cbe556d472943f2bc4148a51f0d` (2024-12-26, release 24.12.0) so the `audio`
widget does not depend on the AUR package. MIT licensed, see `COPYING`.

Local changes against upstream:

- `_pulsectl.py`: load `libpulse.so.0` directly. Upstream calls
  `ctypes.util.find_library('libpulse')`, which never resolves and costs ~100 ms of
  gcc/ld probing before falling back to the same soname.
- `pulsectl.py`, `__init__.py`: removed `connect_to_cli()` (pidfile read + `SIGUSR2`,
  unused here). `lookup.py` is not vendored.
- `_pulsectl.py`, `pulsectl.py`: added `sink_input_kill(index)` and
  `source_output_kill(index)` (upstream binds only the C function for source outputs
  and exposes neither).
- `_pulsectl.py`, `pulsectl.py`: `pa_stream_peek()` takes `size_t *nbytes`; upstream binds
  it as `POINTER(c_int)`, so libpulse writes 8 bytes into a 4-byte `c_int`. Bound as
  `POINTER(c_size_t)` and `get_peak_sample()` passes a `c_size_t`.
- `_pulsectl.py`: added `pa_stream_get_state()` and the `PA_STREAM_*` state constants
  (the audio meters must not disconnect a stream that is still being created).

Upstream quirk kept as is: `Pulse.connect(timeout=...)` always waits the full timeout, so
callers connect without one.
