#!/bin/bash
set -eo pipefail
set +v
set +x

WORKDIR="$(cd "$(dirname "$0")" && pwd)"
REPORT="$WORKDIR/benchmark-results.json"
LOG="$WORKDIR/benchmark-run.log"

finish() {
  local status=$?
  trap - EXIT
  unset DAYFOLD_ARK_API_KEY
  echo
  if [[ $status -eq 0 ]]; then
    echo "模型对照测试进程已完成。"
  else
    echo "模型对照测试未完成，退出码：$status"
  fi
  read -r -p "按回车关闭窗口..." _
  exit $status
}
trap finish EXIT

exec > >(tee "$LOG") 2>&1

echo "Dayfold P1 Memory Extraction 模型对照测试"
echo "模型：Doubao-Seed-2.1-Turbo vs Doubao-Seed-2.0-Mini"
echo "数据：12 组人工编写的虚构案例，共 24 次请求"
echo "并发：2；单次超时：60 秒；不使用真实用户数据"
echo

DAYFOLD_ARK_API_KEY="$(
  security find-generic-password -a "$USER" -s "dayfold-ark-api-key" -w 2>/dev/null || true
)"

if [[ -z "$DAYFOLD_ARK_API_KEY" ]]; then
  echo "请输入 Agent Plan API Key。输入时不会显示字符，粘贴后按回车。"
  read -r -s -p "API Key: " DAYFOLD_ARK_API_KEY
  echo
fi

if [[ -z "$DAYFOLD_ARK_API_KEY" ]]; then
  echo "API Key 为空，测试未开始。"
  exit 2
fi

export DAYFOLD_ARK_API_KEY

echo "开始运行，预计需要数分钟。请保持窗口打开..."

python3 - "$WORKDIR" "$REPORT" <<'PY'
import concurrent.futures
import hashlib
import json
import math
import os
import random
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

workdir = Path(sys.argv[1])
report_path = Path(sys.argv[2])
api_key = os.environ["DAYFOLD_ARK_API_KEY"].strip()
endpoint = "https://ark.cn-beijing.volces.com/api/plan/v1/messages"
models = [
    "doubao-seed-2-1-turbo",
    "doubao-seed-2-0-mini",
]

dataset = json.loads((workdir / "benchmark_cases.json").read_text(encoding="utf-8"))
system_prompt = (workdir / "extraction_prompt_v0.1.md").read_text(encoding="utf-8")
cases = dataset["cases"]
thresholds = dataset["thresholds"]
print_lock = threading.Lock()


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def parse_json_text(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def valid_memory(memory):
    if not isinstance(memory, dict):
        return False
    if memory.get("type") not in {"event", "interest", "goal"}:
        return False
    if not isinstance(memory.get("content"), str) or not memory["content"].strip():
        return False
    confidence = memory.get("confidence")
    return isinstance(confidence, (int, float)) and 0 <= confidence <= 1


def score_case(case, parsed):
    structure_ok = (
        isinstance(parsed, dict)
        and parsed.get("action") in {"upsert", "delete", "none"}
        and isinstance(parsed.get("memories"), list)
        and all(valid_memory(item) for item in parsed.get("memories", []))
    )
    if not structure_ok:
        return {
            "score": 0,
            "structure_ok": False,
            "action_ok": False,
            "type_f1": 0,
            "term_recall": 0,
            "count_ok": False,
        }

    memories = parsed["memories"]
    action_ok = parsed["action"] == case["expected_action"]
    expected_types = set(case["expected_types"])
    actual_types = {item["type"] for item in memories}

    if not expected_types and not actual_types:
        type_f1 = 1.0
    elif not expected_types or not actual_types:
        type_f1 = 0.0
    else:
        tp = len(expected_types & actual_types)
        precision = tp / len(actual_types)
        recall = tp / len(expected_types)
        type_f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

    combined_content = " ".join(item["content"] for item in memories)
    groups = case["required_term_groups"]
    if not groups:
        term_recall = 1.0
    else:
        matched = sum(
            1 for group in groups if any(term in combined_content for term in group)
        )
        term_recall = matched / len(groups)

    count_ok = case["min_memories"] <= len(memories) <= case["max_memories"]
    score = (
        20
        + (20 if action_ok else 0)
        + 25 * type_f1
        + 25 * term_recall
        + (10 if count_ok else 0)
    )
    return {
        "score": round(score, 2),
        "structure_ok": True,
        "action_ok": action_ok,
        "type_f1": round(type_f1, 4),
        "term_recall": round(term_recall, 4),
        "count_ok": count_ok,
    }


def call_model(model, case):
    user_content = []
    if case["context"]:
        user_content.append(case["context"])
    user_content.append("当前记录：" + case["input"])
    payload = {
        "model": model,
        "max_tokens": 300,
        "temperature": 0,
        "system": system_prompt,
        "messages": [{"role": "user", "content": "\n".join(user_content)}],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "Authorization": f"Bearer {api_key}",
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    started = time.perf_counter()
    result = {
        "case_id": case["id"],
        "slice": case["slice"],
        "critical": case["critical"],
        "model": model,
    }
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            text = "".join(
                item.get("text", "")
                for item in data.get("content", [])
                if isinstance(item, dict) and item.get("type") == "text"
            )
            result.update(
                {
                    "http_status": response.status,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000),
                    "usage": data.get("usage", {}),
                    "raw_output": text,
                }
            )
            try:
                parsed = parse_json_text(text)
                result["parsed_output"] = parsed
                result["json_ok"] = True
                result["scoring"] = score_case(case, parsed)
            except Exception as exc:
                result["json_ok"] = False
                result["parse_error"] = repr(exc)
                result["scoring"] = {
                    "score": 0,
                    "structure_ok": False,
                    "action_ok": False,
                    "type_f1": 0,
                    "term_recall": 0,
                    "count_ok": False,
                }
    except urllib.error.HTTPError as exc:
        error = exc.read().decode("utf-8", errors="replace").replace(
            api_key, "[REDACTED_KEY]"
        )
        result.update(
            {
                "http_status": exc.code,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "error": error[:1000],
                "json_ok": False,
                "scoring": {"score": 0, "structure_ok": False},
            }
        )
    except Exception as exc:
        result.update(
            {
                "http_status": None,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "error": repr(exc).replace(api_key, "[REDACTED_KEY]")[:1000],
                "json_ok": False,
                "scoring": {"score": 0, "structure_ok": False},
            }
        )
    with print_lock:
        print(
            f"[{model}] {case['id']} "
            f"score={result['scoring'].get('score', 0)} "
            f"latency={result.get('elapsed_ms')}ms"
        )
    return result


def summarize_model(model, rows):
    model_rows = [row for row in rows if row["model"] == model]
    scores = [row["scoring"].get("score", 0) for row in model_rows]
    latencies = [row["elapsed_ms"] for row in model_rows if row.get("elapsed_ms")]
    output_tokens = [
        row.get("usage", {}).get("output_tokens", 0)
        for row in model_rows
        if isinstance(row.get("usage", {}).get("output_tokens", 0), (int, float))
    ]
    input_tokens = [
        row.get("usage", {}).get("input_tokens", 0)
        for row in model_rows
        if isinstance(row.get("usage", {}).get("input_tokens", 0), (int, float))
    ]
    json_rate = sum(1 for row in model_rows if row.get("json_ok")) / len(model_rows)
    critical_rows = [row for row in model_rows if row["critical"]]
    critical_pass = all(
        row["scoring"].get("score", 0) >= thresholds["critical_case_min_score"]
        for row in critical_rows
    )
    average_score = statistics.mean(scores)
    latency_p95 = percentile(latencies, 0.95)
    output_p95 = percentile(output_tokens, 0.95)

    blockers = []
    warnings = []
    if average_score < thresholds["average_score_warn"]:
        blockers.append("average_score_below_80")
    elif average_score < thresholds["average_score_pass"]:
        warnings.append("average_score_below_85")
    if json_rate < thresholds["json_success_rate_pass"]:
        blockers.append("json_success_rate_below_95_percent")
    if not critical_pass:
        blockers.append("critical_case_failed")
    if latency_p95 and latency_p95 > thresholds["latency_p95_ms_warn"]:
        warnings.append("latency_p95_above_30s")
    if output_p95 and output_p95 > thresholds["output_tokens_p95_warn"]:
        warnings.append("output_tokens_p95_above_400")

    verdict = "block" if blockers else ("warn" if warnings else "pass")
    return {
        "model": model,
        "case_count": len(model_rows),
        "average_score": round(average_score, 2),
        "json_success_rate": round(json_rate, 4),
        "critical_cases_passed": critical_pass,
        "latency_ms": {
            "p50": round(percentile(latencies, 0.50), 2),
            "p95": round(latency_p95, 2),
            "max": max(latencies),
        },
        "tokens": {
            "input_total": sum(input_tokens),
            "output_total": sum(output_tokens),
            "output_p95": round(output_p95, 2),
        },
        "verdict": verdict,
        "blockers": blockers,
        "warnings": warnings,
        "failed_cases": [
            {
                "case_id": row["case_id"],
                "slice": row["slice"],
                "score": row["scoring"].get("score", 0),
            }
            for row in model_rows
            if row["scoring"].get("score", 0) < 85
        ],
    }


jobs = [(model, case) for case in cases for model in models]
random.Random(20260915).shuffle(jobs)
results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    future_map = {
        executor.submit(call_model, model, case): (model, case["id"])
        for model, case in jobs
    }
    for future in concurrent.futures.as_completed(future_map):
        results.append(future.result())

results.sort(key=lambda row: (row["case_id"], row["model"]))
summaries = [summarize_model(model, results) for model in models]

eligible = [summary for summary in summaries if summary["verdict"] != "block"]
selection = {
    "recommended_model": None,
    "rule": "先满足阻断门槛；平均分差距不超过 3 分时，选择输出 Token 更少者；否则选择平均分更高者。",
    "reason": "",
}
if not eligible:
    selection["reason"] = "两个模型都未达到最低门槛，需要调整 Prompt 或模型配置后重测。"
elif len(eligible) == 1:
    selection["recommended_model"] = eligible[0]["model"]
    selection["reason"] = "只有该模型通过最低门槛。"
else:
    ranked = sorted(eligible, key=lambda item: item["average_score"], reverse=True)
    best, other = ranked[0], ranked[1]
    if best["average_score"] - other["average_score"] <= 3:
        recommended = min(
            eligible,
            key=lambda item: (
                item["tokens"]["output_total"],
                item["latency_ms"]["p95"],
            ),
        )
        selection["recommended_model"] = recommended["model"]
        selection["reason"] = "质量差距不超过 3 分，按更低输出 Token 与尾延迟选择。"
    else:
        selection["recommended_model"] = best["model"]
        selection["reason"] = "平均质量分领先超过 3 分。"

report = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "dataset": {
        "id": dataset["dataset_id"],
        "case_count": len(cases),
        "data_class": dataset["data_class"],
        "sha256": hashlib.sha256(
            (workdir / "benchmark_cases.json").read_bytes()
        ).hexdigest(),
    },
    "prompt": {
        "version": "extraction_prompt_v0.1",
        "sha256": hashlib.sha256(
            (workdir / "extraction_prompt_v0.1.md").read_bytes()
        ).hexdigest(),
    },
    "endpoint_protocol": "anthropic-compatible",
    "key_fingerprint": hashlib.sha256(api_key.encode()).hexdigest()[:8],
    "models": models,
    "run_config": {
        "temperature": 0,
        "max_tokens": 300,
        "concurrency": 2,
        "timeout_seconds": 60,
        "random_seed": 20260915,
    },
    "thresholds": thresholds,
    "summaries": summaries,
    "selection": selection,
    "results": results,
    "secret_written_to_report": False,
}

report_path.write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print()
print("对照测试完成。")
for summary in summaries:
    print(
        summary["model"],
        "平均分=", summary["average_score"],
        "JSON成功率=", summary["json_success_rate"],
        "p95延迟=", summary["latency_ms"]["p95"],
        "输出Token=", summary["tokens"]["output_total"],
        "结论=", summary["verdict"],
    )
print("推荐：", selection["recommended_model"] or "暂无")
print("脱敏结果：", report_path)
PY
