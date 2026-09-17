import unittest
from pathlib import Path


PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "prompts"
    / "extraction_prompt_v0.4.md"
)
HARNESS_PATH = Path(__file__).resolve().parents[1] / "harness"


class PromptV04ContractTests(unittest.TestCase):
    def test_upsert_confidence_is_an_explicit_hard_requirement(self):
        prompt = PROMPT_PATH.read_text(encoding="utf-8")

        self.assertIn("字段完整性是最高优先级约束", prompt)
        self.assertIn("每一个 `upsert` operation", prompt)
        self.assertIn("`confidence` 是必填字段", prompt)
        self.assertIn("0.0 到 1.0 之间的数字", prompt)
        self.assertIn("任何情况下都不能省略", prompt)

    def test_goal_replacement_example_contains_confidence(self):
        prompt = PROMPT_PATH.read_text(encoding="utf-8")

        self.assertIn('"target_memory_id":"mem-old-goal"', prompt)
        self.assertIn(
            '"content":"毕业后直接找市场研究相关的工作"',
            prompt,
        )
        self.assertIn('"confidence":0.95', prompt)

    def test_v04_launchers_use_v04_prompt_and_separate_results(self):
        siliconflow = (
            HARNESS_PATH / "run-siliconflow-v04.command"
        ).read_text(encoding="utf-8")
        dify = (HARNESS_PATH / "run-dify-v04.command").read_text(
            encoding="utf-8"
        )

        self.assertIn('DAYFOLD_EVAL_PROMPT="extraction_prompt_v0.4.md"', siliconflow)
        self.assertIn('DAYFOLD_EVAL_RESULT="siliconflow-v04-results.json"', siliconflow)
        self.assertIn('DAYFOLD_EVAL_PROMPT="extraction_prompt_v0.4.md"', dify)
        self.assertIn('DAYFOLD_EVAL_RESULT="dify-v04-results.json"', dify)
        self.assertIn('DAYFOLD_EVAL_BASELINE="siliconflow-v04-results.json"', dify)


if __name__ == "__main__":
    unittest.main()
