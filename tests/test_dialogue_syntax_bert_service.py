import os
import unittest
from unittest.mock import patch

from services.dialogue_syntax_bert_service import (
    LABEL_KEYS,
    get_dialogue_syntax_calibration,
    reset_dialogue_syntax_bert_cache,
)


class DialogueSyntaxBertServiceTests(unittest.TestCase):
    def tearDown(self):
        reset_dialogue_syntax_bert_cache()

    def test_explicit_disable_preserves_rule_only_mode(self):
        with patch.dict(os.environ, {"ENABLE_DIALOGUE_SYNTAX_BERT_CALIBRATION": "0"}):
            payload = get_dialogue_syntax_calibration("你去吗？", "我不去。")
        self.assertFalse(payload["available"])
        self.assertFalse(payload["taxonomy_changed"])
        self.assertEqual(payload["reason"], "disabled")

    def test_local_model_returns_the_original_six_labels(self):
        with patch.dict(os.environ, {"ENABLE_DIALOGUE_SYNTAX_BERT_CALIBRATION": "1"}):
            payload = get_dialogue_syntax_calibration("你为什么不去？", "我不是不去，是没时间。")
        if not payload["available"]:
            self.skipTest(f"Optional local BERT runtime unavailable: {payload['reason']}")
        self.assertEqual([item["key"] for item in payload["labels"]], list(LABEL_KEYS))
        self.assertFalse(payload["taxonomy_changed"])
        for item in payload["labels"]:
            self.assertGreaterEqual(item["probability"], 0)
            self.assertLessEqual(item["probability"], 1)


if __name__ == "__main__":
    unittest.main()
