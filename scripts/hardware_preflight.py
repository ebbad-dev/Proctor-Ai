from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check ProctorAI camera, microphone, and phone model readiness.")
    parser.add_argument("--require-camera", action="store_true")
    parser.add_argument("--require-microphone", action="store_true")
    args = parser.parse_args()

    from input.audio_capture import AudioCapture
    from input.webcam_capture import WebcamCapture
    from run_proctor_engine import OptionalPhoneDetector

    camera = WebcamCapture(label="preflight")
    microphone = AudioCapture()
    result = {
        "camera": {"started": False, "running": False, "frame_available": False},
        "microphone": {"started": False, "available": False},
        "phone_detection": {"available": False, "reason": "not_checked"},
    }

    try:
        result["camera"]["started"] = bool(camera.start_camera())
        microphone.start_microphone()
        result["microphone"]["started"] = True
        time.sleep(2)
        frame = camera.get_frame()
        result["camera"].update({
            "running": bool(camera.is_running),
            "frame_available": frame is not None,
            "resolution": "x".join(str(value) for value in camera.resolution),
            "fps": camera.fps,
        })
        result["microphone"].update({
            "available": bool(microphone.is_available),
            "level": float(microphone.audio_level),
        })
        detector = OptionalPhoneDetector()
        result["phone_detection"] = {
            "available": bool(detector.available),
            "reason": detector.reason,
            "labels": len(detector.labels),
        }
    finally:
        camera.stop_camera()
        microphone.stop_microphone()

    print(json.dumps(result, indent=2, sort_keys=True))
    if args.require_camera and not (result["camera"]["running"] and result["camera"]["frame_available"]):
        return 2
    if args.require_microphone and not result["microphone"]["available"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
