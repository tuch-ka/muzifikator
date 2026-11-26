"""Подпроцесс синтеза NNSVS: изолирует chdir и падения вендоренного пайплайна."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3:
        print("usage: worker <ust> <out.wav> <vendor_dir>", file=sys.stderr)
        return 2
    ust_path, out_path, vendor = args
    if not hasattr(os, "startfile"):
        os.startfile = lambda _path: None  # type: ignore[attr-defined]

    sys.path.insert(0, vendor)

    import torch

    _original_load = torch.load

    def _load(*load_args: Any, **load_kwargs: Any) -> Any:
        load_kwargs.setdefault("weights_only", False)
        return _original_load(*load_args, **load_kwargs)

    torch.load = _load

    import enunu_steps

    enunu_steps.main(str(Path(ust_path).resolve()), str(Path(out_path).resolve()), play_wav=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
