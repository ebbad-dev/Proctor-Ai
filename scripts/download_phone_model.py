from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_URL = "https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5n.onnx"
DEFAULT_OUTPUT = ROOT / "models" / "phone_detector.onnx"


def download(url: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".download")
    print(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=60) as response:
        total = int(response.headers.get("Content-Length") or 0)
        with tmp.open("wb") as handle:
            copied = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                copied += len(chunk)
                if total:
                    pct = copied * 100 / total
                    print(f"\r{pct:5.1f}% ({copied // 1024} KB)", end="")
    if total:
        print()
    if tmp.stat().st_size < 1024 * 1024:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("Downloaded file is too small to be a valid ONNX model.")
    tmp.replace(output)
    print(f"Saved {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the ProctorAI phone/object ONNX model.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    try:
        download(args.url, Path(args.output))
    except Exception as exc:
        print(f"Model download failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
