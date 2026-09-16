import importlib.util
import json
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "harness" / "run_mini_retest.py"
)
SPEC = importlib.util.spec_from_file_location("run_mini_retest", MODULE_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class ProviderAdapterTests(unittest.TestCase):
    def test_default_paths_follow_evaluation_directory_layout(self):
        eval_root = MODULE_PATH.parents[1]

        self.assertEqual(RUNNER.DATASET_PATH.parent, eval_root / "datasets")
        self.assertEqual(RUNNER.PROMPT_PATH.parent, eval_root / "prompts")
        self.assertEqual(RUNNER.BASELINE_PATH.parent, eval_root / "results")
        self.assertEqual(RUNNER.RESULT_PATH.parent, eval_root / "results")
        self.assertEqual(RUNNER.REPORT_PATH.parents[1], eval_root / "reports")

    def test_builds_openai_compatible_request(self):
        payload, headers = RUNNER.build_provider_request(
            protocol="openai",
            api_key="secret",
            model="deepseek-ai/DeepSeek-V3.1",
            system_prompt="只输出 JSON",
            user_message="当前记录：开始跑步",
        )

        self.assertEqual(payload["model"], "deepseek-ai/DeepSeek-V3.1")
        self.assertEqual(payload["messages"][0], {
            "role": "system",
            "content": "只输出 JSON",
        })
        self.assertEqual(headers["Authorization"], "Bearer secret")
        self.assertNotIn("x-api-key", headers)

    def test_normalizes_openai_compatible_response(self):
        response = {
            "choices": [{"message": {"content": '{"operations":[]}'}}],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 5,
                "total_tokens": 17,
            },
        }

        text, usage = RUNNER.parse_provider_response("openai", response)

        self.assertEqual(json.loads(text), {"operations": []})
        self.assertEqual(usage["input_tokens"], 12)
        self.assertEqual(usage["output_tokens"], 5)


if __name__ == "__main__":
    unittest.main()
