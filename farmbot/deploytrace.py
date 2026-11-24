"""Save the live deployment frames, calculated candidates, and troop inputs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from farmbot import imagefile
from farmbot.geometry import Point

log = logging.getLogger(__name__)

PINK = (227, 129, 255)
WHITE = (239, 243, 250)
DARK = (18, 22, 30)
SOURCES = {"red line": (132, 240, 107), "building ring": (255, 213, 80), "fixed line": (67, 184, 255)}


@dataclass
class Frame:
    image: np.ndarray
    stage: str
    red_line: dict[str, list[Point]]
    candidates: dict[str, list[Point]]
    sources: dict[str, str]
    inputs: list[dict] = field(default_factory=list)
    response: np.ndarray | None = None

    def overlay(self) -> np.ndarray:
        h = self.image.shape[0]
        out = cv2.copyMakeBorder(self.image, 0, 106, 0, 0, cv2.BORDER_CONSTANT, value=DARK)
        for points in self.red_line.values():
            for point in points:
                cv2.circle(out, point, 3, PINK, -1, cv2.LINE_AA)
        for side, points in self.candidates.items():
            for point in points:
                cv2.circle(out, point, 6, SOURCES[self.sources[side]], 2, cv2.LINE_AA)
        for sent in self.inputs:
            points = sent["frame_points"]
            if sent["gesture"] == "slide":
                cv2.polylines(out, [np.asarray(points, dtype=np.int32)], False, WHITE, 2, cv2.LINE_AA)
            else:
                for point in points:
                    cv2.drawMarker(out, point, DARK, cv2.MARKER_CROSS, 13, 4, cv2.LINE_AA)
                    cv2.drawMarker(out, point, WHITE, cv2.MARKER_CROSS, 13, 2, cv2.LINE_AA)
        labels = (
            (20, 24, f"{self.stage}  |  {len(self.inputs)} troop input batch(es)"),
            (20, 44, "Pink dots: red-line detector output before terrain filtering"),
            (20, 64, "Candidate circles: green red line / cyan building ring / orange fixed line"),
            (20, 84, "White crosses and paths: troop inputs sent to the device"),
        )
        for x, y, label in labels:
            cv2.putText(out, label, (x, h + y), cv2.FONT_HERSHEY_SIMPLEX, .52, WHITE, 1, cv2.LINE_AA)
        return out


class DeployTrace:
    def __init__(self, directory: Path):
        self.directory = directory
        self.frames: list[Frame] = []
        self.active: Frame | None = None

    def frame(self, image: np.ndarray, stage: str, red_line: dict[str, list[Point]],
              candidates: dict[str, list[Point]], sources: dict[str, str], *, track_inputs: bool = True) -> None:
        frame = Frame(image.copy(), stage, red_line, candidates, sources)
        self.frames.append(frame)
        if track_inputs:
            self.active = frame

    def input(self, gesture: str, device_points: list[Point], scale: float) -> None:
        if self.active is not None:
            self.active.inputs.append({
                "gesture": gesture,
                "device_points": device_points,
                "frame_points": [(round(x / scale), round(y / scale)) for x, y in device_points],
            })

    def capture_response(self, image: np.ndarray) -> None:
        """Keep the first screen read after this plan sends a troop input."""
        if self.active is not None and self.active.inputs and self.active.response is None:
            self.active.response = image.copy()

    def save(self) -> None:
        frames, self.frames = self.frames, []
        self.active = None
        if not frames:
            return
        folder = self.directory / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        try:
            folder.mkdir(parents=True)
            for index, frame in enumerate(frames, 1):
                stem = folder / f"{index:02d}"
                if not imagefile.write(stem.with_name(f"{stem.name}-frame.png"), frame.image):
                    raise OSError(f"could not save {stem.name}-frame.png")
                if not imagefile.write(stem.with_suffix(".png"), frame.overlay()):
                    raise OSError(f"could not save {stem.name}.png")
                data = {"stage": frame.stage, "red_line": frame.red_line, "candidates": frame.candidates,
                        "sources": frame.sources, "inputs": frame.inputs}
                if frame.response is not None:
                    response = f"{stem.name}-response.png"
                    if not imagefile.write(folder / response, frame.response):
                        raise OSError(f"could not save {response}")
                    data["response"] = response
                stem.with_suffix(".json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except (OSError, cv2.error) as exc:
            log.warning("Could not save deployment trace in %s: %s", folder, exc)
        else:
            log.info("Deployment trace saved to %s", folder.resolve())
