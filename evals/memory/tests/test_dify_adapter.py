import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "harness" / "run_mini_retest.py"
)
DIFY_COMMAND_PATH = (
    Path(__file__).resolve().parents[1] / "harness" / "run-dify-v03.command"
)
SPEC = importlib.util.spec_from_file_location("run_mini_retest_dify", MODULE_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class DifyAdapterTests(unittest.TestCase):
    def test_runner_never_writes_api_key_fingerprint(self):
        runner_source = MODULE_PATH.read_text(encoding="utf-8")

        self.assertNotIn("key_fingerprint", runner_source)

    def test_dify_launcher_uses_frozen_workflow_contract(self):
        command = DIFY_COMMAND_PATH.read_text(encoding="utf-8")

        self.assertIn("dayfold-dify-workflow-api-key", command)
        self.assertIn("https://api.dify.ai/v1/workflows/run", command)
        self.assertIn('DAYFOLD_EVAL_PROTOCOL="dify"', command)
        self.assertIn(
            'DAYFOLD_EVAL_MODEL="deepseek-ai/DeepSeek-V3.1-Terminus"',
            command,
        )
        self.assertIn(
            'DAYFOLD_DIFY_WORKFLOW_VERSION="2026-09-17 14:27"',
            command,
        )
        self.assertIn(
            'DAYFOLD_EVAL_BASELINE="siliconflow-v03-results.json"',
            command,
        )

    def test_builds_frozen_workflow_request(self):
        case = {
            "id": "C01",
            "existing_memories": [
                {
                    "id": "mem-event-shanghai-location",
                    "type": "event",
                    "content": "用户目前居住在上海",
                }
            ],
            "input": "我已经搬到北京，现在会长期住在海淀区。",
        }

        payload, headers = RUNNER.build_dify_workflow_request(
            api_key="app-secret",
            system_prompt="只输出 JSON",
            case=case,
        )

        self.assertEqual(payload["response_mode"], "blocking")
        self.assertEqual(payload["user"], "dayfold-p1-eval")
        self.assertEqual(payload["inputs"]["case_id"], "C01")
        self.assertEqual(
            payload["inputs"]["existing_memories_json"],
            '[{"id":"mem-event-shanghai-location","type":"event",'
            '"content":"用户目前居住在上海"}]',
        )
        self.assertEqual(
            payload["inputs"]["dataset_version"],
            "dayfold-memory-pipeline-v0.3",
        )
        self.assertEqual(headers["Authorization"], "Bearer app-secret")
        self.assertEqual(headers["User-Agent"], "Dayfold-P1-Evaluation/0.3")
        self.assertNotIn("app-secret", str(payload))

    def test_normalizes_workflow_response_and_trace_metadata(self):
        response = {
            "task_id": "task-123",
            "workflow_run_id": "run-456",
            "data": {
                "status": "succeeded",
                "outputs": {"result_json": '{"operations":[]}'},
                "elapsed_time": 1.25,
                "total_tokens": 321,
                "total_price": "0.0042",
                "currency": "USD",
            },
        }

        text, usage, trace = RUNNER.parse_dify_workflow_response(response)

        self.assertEqual(text, '{"operations":[]}')
        self.assertEqual(usage["total_tokens"], 321)
        self.assertEqual(trace["task_id"], "task-123")
        self.assertEqual(trace["workflow_run_id"], "run-456")
        self.assertEqual(trace["workflow_status"], "succeeded")
        self.assertEqual(trace["total_price"], "0.0042")
        self.assertEqual(trace["currency"], "USD")

    def test_rejects_missing_result_json(self):
        with self.assertRaisesRegex(ValueError, "result_json"):
            RUNNER.parse_dify_workflow_response(
                {
                    "task_id": "task-123",
                    "workflow_run_id": "run-456",
                    "data": {
                        "status": "succeeded",
                        "outputs": {},
                    },
                }
            )

    def test_summary_preserves_dify_total_tokens(self):
        dataset = {
            "thresholds": {
                "model_average_score_pass": 90,
                "json_success_rate_pass": 1,
                "critical_case_min_score": 90,
                "deterministic_delete_success_rate_pass": 1,
                "latency_p95_ms_warn": 20000,
                "output_tokens_p95_warn": 400,
            }
        }
        model_results = [
            {
                "case_id": "C01",
                "slice": "conflicting_location",
                "critical": True,
                "http_status": 200,
                "elapsed_ms": 1200,
                "json_ok": True,
                "usage": {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 321,
                },
                "scoring": {"score": 100},
            }
        ]

        summary = RUNNER.summarize(dataset, model_results, [])

        self.assertEqual(summary["tokens"]["total"], 321)

    def test_http_failures_block_and_fail_the_run(self):
        dataset = {
            "thresholds": {
                "model_average_score_pass": 90,
                "json_success_rate_pass": 1,
                "critical_case_min_score": 90,
                "deterministic_delete_success_rate_pass": 1,
                "latency_p95_ms_warn": 20000,
                "output_tokens_p95_warn": 400,
            }
        }
        model_results = [
            {
                "case_id": "C01",
                "slice": "conflicting_location",
                "critical": True,
                "http_status": 403,
                "elapsed_ms": 300,
                "json_ok": False,
                "usage": {},
                "scoring": {"score": 0},
            }
        ]

        summary = RUNNER.summarize(dataset, model_results, [])

        self.assertEqual(summary["http_success_rate"], 0)
        self.assertIn(
            "http_success_rate_below_100_percent",
            summary["blockers"],
        )
        with self.assertRaisesRegex(RuntimeError, "HTTP"):
            RUNNER.assert_request_success(summary)


if __name__ == "__main__":
    unittest.main()
