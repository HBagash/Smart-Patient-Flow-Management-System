import os
import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort

class Tracker:
    def __init__(self):
        # Adjust parameters as needed.
        self.deepsort = DeepSort(
            max_age=7,                      # Frames to keep a lost track alive.
            max_cosine_distance=0.3,        # Tolerance for ReID matching.
            n_init=2,                       # Number of frames required to confirm a track.
            max_iou_distance=0.8,           # IOU threshold for matching.
            embedder_gpu=True,              # Use GPU if available.
            # Note: Do NOT pass model_filename or similar; deep_sort_realtime handles the embedder internally.
        )

    def update(self, frame, detections):
        """
        Update the tracker.
        
        detections: list of detections in the format [x1, y1, x2, y2, confidence]
        Returns a list of tuples: (track_id, bbox) where bbox is [left, top, right, bottom]
        """
        if not detections:
            # When there are no detections, simply update tracks with an empty list.
            self.deepsort.update_tracks([], frame=frame)
            return []

        # Convert detections from [x1,y1,x2,y2,conf] to deep_sort_realtime's expected format:
        # Each detection is [ [x, y, w, h], confidence, class ]
        bboxes = np.array([det[:4] for det in detections])
        bboxes[:, 2:] = bboxes[:, 2:] - bboxes[:, :2]  # convert from xyxy to xywh
        scores = [det[4] for det in detections]

        processed = []
        for i, box in enumerate(bboxes):
            processed.append([box.tolist(), scores[i], 0])  # using dummy class 0

        tracks = self.deepsort.update_tracks(processed, frame=frame)

        output = []
        for t in tracks:
            if not t.is_confirmed() or t.time_since_update > 1:
                continue
            output.append((t.track_id, t.to_ltrb()))
        return output

# Optional: A simple Track class to mirror our output (if needed)
class Track:
    def __init__(self, track_id, bbox):
        self.track_id = track_id
        self.bbox = bbox  # bbox in [left, top, right, bottom] format
