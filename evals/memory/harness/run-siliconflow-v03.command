#!/bin/bash
set -eo pipefail
set +v
set +x

WORKDIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$WORKDIR/../../.." && pwd)"
LOG="$REPO_ROOT/local/verification/siliconflow-v03-run.log"

finish() {
  local status=$?
  trap - EXIT
  unset DAYFOLD_EVAL_API_KEY
  echo
  if [[ $status -eq 0 ]]; then
    echo "硅基流动 v0.3 baseline 已完成。"
  else
    echo "硅基流动 v0.3 baseline 未完成，退出码：$status"
  fi
  read -r -p "按回车关闭窗口..." _
  exit $status
}
trap finish EXIT

exec > >(tee "$LOG") 2>&1

echo "Dayfold P1 硅基流动 Memory Extraction baseline"
echo "18 次模型请求 + 2 个确定性删除案例"
echo "全部使用人工编写的虚构数据"
echo

DAYFOLD_EVAL_API_KEY="$(
  security find-generic-password \
    -a "$USER" \
    -s "dayfold-siliconflow-api-key" \
    -w 2>/dev/null || true
)"

if [[ -z "$DAYFOLD_EVAL_API_KEY" ]]; then
  echo "请输入硅基流动 API Key。输入时不会显示字符，粘贴后按回车。"
  read -r -s -p "API Key: " DAYFOLD_EVAL_API_KEY
  echo
fi

if [[ -z "$DAYFOLD_EVAL_API_KEY" ]]; then
  echo "API Key 为空，baseline 未开始。"
  exit 2
fi

export DAYFOLD_EVAL_API_KEY
export DAYFOLD_EVAL_PROTOCOL="openai"
export DAYFOLD_EVAL_ENDPOINT="https://api.siliconflow.cn/v1/chat/completions"
export DAYFOLD_EVAL_MODEL="${DAYFOLD_SILICONFLOW_MODEL:-deepseek-ai/DeepSeek-V3.1}"
export DAYFOLD_EVAL_DATASET="mini_retest_cases_v0.3.json"
export DAYFOLD_EVAL_PROMPT="extraction_prompt_v0.3.md"
export DAYFOLD_EVAL_BASELINE="mini-v03-results.json"
export DAYFOLD_EVAL_RESULT="siliconflow-v03-results.json"
export DAYFOLD_EVAL_REPORT_DIR="dayfold-p1-siliconflow-v03-report"
export DAYFOLD_EVAL_REPORT_TITLE="Dayfold P1 硅基流动 v0.3 Baseline"
export DAYFOLD_EVAL_VERSION="siliconflow-v0.3"
export DAYFOLD_EVAL_BASELINE_LABEL="Ark Mini v0.3"

echo "模型：$DAYFOLD_EVAL_MODEL"
echo "开始 baseline，预计需要数分钟，请保持窗口打开..."
python3 "$WORKDIR/run_mini_retest.py"
