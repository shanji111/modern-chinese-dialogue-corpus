import unittest
from unittest.mock import patch

import app


class DiagraphOldTaxonomyTests(unittest.TestCase):
    def test_payload_keeps_vertical_grid_and_adds_non_authoritative_calibration(self):
        pair = {
            "id": 17,
            "text_a": "你为什么不去？",
            "text_b": "我不是不去，是没时间。",
            "shared_terms": '["不去"]',
            "markers": '["为什么", "不是"]',
        }
        turns = [
            {"turn_index": 1, "speaker_label": "A", "turn_text": pair["text_a"]},
            {"turn_index": 2, "speaker_label": "B", "turn_text": pair["text_b"]},
        ]
        calibration = {
            "available": True,
            "enabled": True,
            "taxonomy_changed": False,
            "notice": "test",
            "labels": [
                {
                    "key": key,
                    "label": app.DIAGRAPH_BERT_LABEL_NAMES[key],
                    "probability": 0.8 if key == "contrast" else 0.1,
                    "threshold": 0.5,
                    "suggested": key == "contrast",
                }
                for key in app.DIAGRAPH_BERT_LABEL_KEYS
            ],
        }
        with patch.object(app, "get_dialogue_syntax_calibration", return_value=calibration):
            payload = app.build_diagraph_payload(pair, turns, "pair")

        self.assertEqual(payload["pair_id"], 17)
        self.assertTrue(payload["columns"])
        self.assertEqual(len(payload["grid"]), 2)
        self.assertTrue(any(item["relation"] == "否定回应" for item in payload["affordances"]))
        self.assertEqual(
            [item["key"] for item in payload["mechanism_summary"]],
            list(app.DIAGRAPH_BERT_LABEL_KEYS),
        )
        contrast = next(item for item in payload["mechanism_summary"] if item["key"] == "contrast")
        self.assertEqual(contrast["support_state"], "joint")
        self.assertFalse(payload["bert_calibration"]["taxonomy_changed"])


if __name__ == "__main__":
    unittest.main()
