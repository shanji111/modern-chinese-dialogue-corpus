import sqlite3
import unittest
from unittest.mock import patch

import app
import corpus_repository


class GraphShowcaseSampleTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE corpus_entries (
                id INTEGER PRIMARY KEY,
                title TEXT,
                year TEXT,
                source_url TEXT,
                crawl_source TEXT,
                crawl_date TEXT,
                license_note TEXT,
                audio_file TEXT
            );
            CREATE TABLE dialogue_pairs (
                id INTEGER PRIMARY KEY,
                turn_a_id INTEGER,
                turn_b_id INTEGER,
                entry_id INTEGER,
                conversation_key TEXT,
                turn_index_a INTEGER,
                turn_index_b INTEGER,
                speaker_a TEXT,
                speaker_b TEXT,
                text_a TEXT,
                text_b TEXT,
                source TEXT,
                category TEXT,
                dataset_name TEXT,
                shared_terms TEXT,
                markers TEXT,
                has_lexical_echo INTEGER,
                has_pattern_reuse INTEGER,
                has_question_response INTEGER,
                has_negation_turn INTEGER,
                has_repair_repetition INTEGER
            );
            """
        )
        self.conn.execute(
            "INSERT INTO corpus_entries VALUES (1, 'demo', '', '', '', '', '', '')"
        )
        pair_id = 1
        for dataset in corpus_repository.GRAPH_SHOWCASE_DATASETS:
            for is_compact in (True, False):
                text_a = "我们今天去剧院吗" if is_compact else "请你把今天晚上关于剧院演出的具体安排、人物关系和后续计划完整解释一下"
                text_b = "今天去剧院" if is_compact else "我会在认真考虑之后，把所有前因后果、人物关系和后续安排完整地解释给你听"
                self.conn.execute(
                    """
                    INSERT INTO dialogue_pairs VALUES
                    (?, ?, ?, 1, ?, 1, 2, '甲', '乙', ?, ?, '文本对话', '', ?, '[\"剧院\"]', '[]', 1, 0, 1, 0, 0)
                    """,
                    (pair_id, pair_id * 2, pair_id * 2 + 1, f"{dataset}-{pair_id}", text_a, text_b, dataset),
                )
                pair_id += 1
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _query(self, **kwargs):
        with (
            patch.object(corpus_repository, "get_readonly_db_connection", return_value=self.conn),
            patch.object(corpus_repository, "close_connection"),
            patch.object(corpus_repository, "is_postgres", return_value=False),
        ):
            return corpus_repository.query_resonance_page(
                preset="resonance",
                limit=6,
                include_turn_count=False,
                **kwargs,
            )

    def test_showcase_balances_selected_works_and_prefers_compact_turns(self):
        data = self._query(showcase=True)

        self.assertTrue(data["showcase"])
        self.assertFalse(data["has_next"])
        self.assertEqual(
            [item["dataset_name"] for item in data["results"]],
            [
                "雷雨",
                "平凡的世界",
                "骆驼祥子",
                "雷雨",
                "平凡的世界",
                "骆驼祥子",
            ],
        )
        self.assertTrue(all(len(item["turn_a_text"]) <= 90 for item in data["results"][:3]))

    def test_normal_query_order_and_scope_are_unchanged(self):
        data = self._query(showcase=False)

        self.assertFalse(data["showcase"])
        self.assertEqual([item["pair_id"] for item in data["results"]], [6, 5, 4, 3, 2, 1])

    def test_empty_sample_request_enables_showcase_but_keyword_search_does_not(self):
        showcase_response = {"results": [], "has_next": False, "next_cursor": None, "turn_count": 0, "showcase": True}
        regular_response = {"results": [], "has_next": False, "next_cursor": None, "turn_count": 0, "showcase": False}
        with app.app.test_client() as client:
            with patch.object(app, "query_resonance_page", return_value=showcase_response) as query:
                response = client.get("/api/resonance?sample=1")
                self.assertEqual(response.status_code, 200)
                self.assertTrue(query.call_args.kwargs["showcase"])
                self.assertTrue(response.get_json()["presentation_showcase"])
            with patch.object(app, "query_resonance_page", return_value=regular_response) as query:
                response = client.get("/api/resonance?q=剧院")
                self.assertEqual(response.status_code, 200)
                self.assertFalse(query.call_args.kwargs["showcase"])
                self.assertFalse(response.get_json()["presentation_showcase"])


if __name__ == "__main__":
    unittest.main()
