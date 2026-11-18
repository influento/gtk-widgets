# Hand-written types for the part of onnxruntime that webcam-effects uses:
# the package ships none. A name only this stub has passes the type check and
# fails at import: run webcam-effects after changing a call.
from collections.abc import Mapping, Sequence
from typing import Any

import numpy.typing as npt

class SessionOptions:
    intra_op_num_threads: int
    def __init__(self) -> None: ...
    def add_session_config_entry(self, key: str, value: str, /) -> None: ...

class InferenceSession:
    def __init__(
        self,
        path_or_bytes: str,
        sess_options: SessionOptions | None = None,
        providers: Sequence[str] | None = None,
    ) -> None: ...
    def run(
        self,
        output_names: Sequence[str] | None,
        input_feed: Mapping[str, npt.NDArray[Any]],
    ) -> list[npt.NDArray[Any]]: ...
