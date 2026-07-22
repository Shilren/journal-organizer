import importlib.util
import json
import os
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KnowledgeRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("LARK_PROFILE", "test-profile")
        cls.knowledge = load_module(
            "knowledge_handler",
            ROOT / "knowledge-bot" / "templates" / "handler.py",
        )

    def test_split_markdown_removes_original_callout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "2026-07-22.md"
            path.write_text(
                "# day\n\n## 21:10 · title\n\nclean body\n\n"
                "> [!note]- 原始记录\n> raw body\n\n---\n",
                encoding="utf-8",
            )
            chunks = self.knowledge.split_markdown(str(path), "信念/2026-07-22.md")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["category"], "信念")
        self.assertIn("clean body", chunks[0]["text"])
        self.assertNotIn("raw body", chunks[0]["text"])

    def test_weekly_review_is_secondary_except_for_trend_questions(self):
        settings = {
            "weekly_category": "周复盘",
            "category_meta": {},
            "exclude_dirs": set(),
            "max_chunks": 10,
        }
        chunk = {
            "category": "周复盘",
            "rel": "周复盘/2026-07-14_07-20.md",
            "title": "本周复盘",
            "text": "主体性变化",
        }
        terms = {"主体性"}
        normal = self.knowledge.chunk_score(chunk, terms, [], False, settings)
        trend = self.knowledge.chunk_score(chunk, terms, [], True, settings)
        self.assertGreater(trend, normal)

    def test_category_keywords_route_questions(self):
        settings = {
            "category_meta": {
                "创作灵感": {"desc": "", "keywords": ["口播", "选题"]},
                "工作与职业": {"desc": "", "keywords": ["面试"]},
            }
        }
        self.assertEqual(
            self.knowledge.preferred_categories("给我几个口播选题", settings),
            ["创作灵感"],
        )


class ConfigurationTests(unittest.TestCase):
    def test_example_config_is_valid_json(self):
        with open(ROOT / "config.example.json", encoding="utf-8") as handle:
            config = json.load(handle)
        self.assertTrue(config["vault"])
        self.assertGreaterEqual(len(config["categories"]), 3)
        self.assertIn("knowledge", config)

    def test_organize_schema_is_valid_json(self):
        with open(
            ROOT / "feishu-bot" / "templates" / "organize_schema.json",
            encoding="utf-8",
        ) as handle:
            schema = json.load(handle)
        self.assertEqual(schema["type"], "object")
        self.assertEqual(set(schema["required"]), {"category", "title", "body"})


class WeeklyIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.weekly = load_module(
            "weekly_review",
            ROOT / "feishu-bot" / "templates" / "weekly_review.py",
        )

    def test_tombstone_removes_entry_from_weekly_review(self):
        monday = self.weekly.datetime.date(2026, 7, 20)
        sunday = monday + self.weekly.datetime.timedelta(days=6)
        with tempfile.TemporaryDirectory() as directory:
            index_path = pathlib.Path(directory) / "weekly_entries.jsonl"
            rows = [
                {
                    "type": "entry",
                    "id": "m1",
                    "date": "2026-07-22",
                    "category": "信念与原则",
                    "title": "保留",
                    "body": "正文一",
                },
                {
                    "type": "entry",
                    "id": "m2",
                    "date": "2026-07-22",
                    "category": "生活记录",
                    "title": "删除",
                    "body": "正文二",
                },
                {"type": "delete", "id": "m2"},
            ]
            index_path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
            old_path = self.weekly.WEEKLY_INDEX_FILE
            self.weekly.WEEKLY_INDEX_FILE = str(index_path)
            try:
                entries = self.weekly.collect_from_index(monday, sunday)
            finally:
                self.weekly.WEEKLY_INDEX_FILE = old_path
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][2], "保留")


if __name__ == "__main__":
    unittest.main()
