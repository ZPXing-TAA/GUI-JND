from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jnd_gui.dataset_parser import scan_scene_folder
from jnd_gui.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_create_new_session_writes_candidate_power_prior_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scene_dir = root / "arbitrary_root" / "device01" / "run" / "natlan_r30_run02"
            scene_dir.mkdir(parents=True)
            (scene_dir / "VeryHigh_60_High_High.mp4").touch()
            (scene_dir / "Medium_30_Low_High.mp4").touch()

            scan_result = scan_scene_folder(scene_dir)
            store = SessionStore(root / "Results")
            bundle = store.create_new_session("S01", scan_result, rng_seed=12345)

            manifest_path = store.candidate_power_prior_manifest_path(bundle.session_dir)
            self.assertTrue(manifest_path.exists())

            manifest = manifest_path.read_text(encoding="utf-8")
            self.assertIn("candidate_power_prior_manifest", manifest_path.name)
            self.assertIn('"power_label_type": "relative_power_prior"', manifest)
            self.assertIn('"video_path"', manifest)

    def test_mark_subject_training_completed_persists_subject_level_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = SessionStore(root / "Results")
            session_dir = store.root_dir / "S01" / "device01" / "run" / "natlan_r30_run02"
            session_dir.mkdir(parents=True)

            self.assertFalse(store.has_subject_completed_training("S01"))

            store.mark_subject_training_completed("S01", session_dir)

            self.assertTrue(store.has_subject_completed_training("S01"))
            state_path = store.subject_training_state_path("S01")
            payload = state_path.read_text(encoding="utf-8")
            self.assertIn('"subject_id": "S01"', payload)
            self.assertIn('"training_completed": true', payload)
            self.assertIn('"source_session_dir"', payload)


if __name__ == "__main__":
    unittest.main()
