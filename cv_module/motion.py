"""
ROI motion / presence trigger — road-camera style.

Real ANPR systems do not OCR every N seconds. They wait for a trigger
(inductive loop, radar, or video motion), capture, read the plate once
per passage, then wait until the lane is clear.
"""

from __future__ import annotations

import cv2
import numpy as np


class RoiMotionTrigger:
    """Frame-diff presence detector on a fixed ROI."""

    def __init__(
        self,
        *,
        diff_threshold: int = 28,
        min_change_ratio: float = 0.035,
        blur_ksize: int = 5,
        ema_alpha: float = 0.15,
    ) -> None:
        self.diff_threshold = diff_threshold
        self.min_change_ratio = min_change_ratio
        self.blur_ksize = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1
        self.ema_alpha = ema_alpha
        self._bg: np.ndarray | None = None
        self._warmup_left = 20
        self.score = 0.0
        self.present = False

    def reset(self) -> None:
        self._bg = None
        self._warmup_left = 20
        self.score = 0.0
        self.present = False

    def update(self, roi_bgr: np.ndarray) -> tuple[bool, float]:
        if roi_bgr.size == 0:
            self.present = False
            self.score = 0.0
            return False, 0.0

        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (self.blur_ksize, self.blur_ksize), 0)
        small = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)

        if self._bg is None:
            self._bg = small.astype(np.float32)
            self._warmup_left = max(self._warmup_left, 1)
            self.present = False
            self.score = 0.0
            return False, 0.0

        if self._warmup_left > 0:
            cv2.accumulateWeighted(small, self._bg, 0.35)
            self._warmup_left -= 1
            self.present = False
            self.score = 0.0
            return False, 0.0

        diff = cv2.absdiff(small, cv2.convertScaleAbs(self._bg))
        _, mask = cv2.threshold(diff, self.diff_threshold, 255, cv2.THRESH_BINARY)
        score = float(np.count_nonzero(mask)) / float(mask.size)
        self.score = score
        self.present = score >= self.min_change_ratio

        # Adapt background slowly when empty; freeze while occupied
        if not self.present:
            cv2.accumulateWeighted(small, self._bg, self.ema_alpha)

        return self.present, score
