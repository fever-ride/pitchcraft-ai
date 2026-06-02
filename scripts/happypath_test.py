"""
Happy Path End-to-End Test
Runs the full pipeline: start → 4x HITL confirm → pptx output
Usage: python scripts/happypath_test.py
"""
import asyncio
import json
import time
import urllib.request
import urllib.error

BASE = "http://localhost:8000/api/v1"
CLIENT_ID = "6a1e1f33f3fe0e20287dafdf"  # 可口可乐, seeded in MongoDB

BRIEF = """
可口可乐2026夏季年轻化营销提案

品牌：可口可乐 中国
项目类型：夏季新品（夏日清凉限定罐）上市传播
目标：
- 在18-28岁年轻消费者中建立夏日专属品牌联想
- 拉动线下便利店渠道销售，目标同比增长15%
- 引爆微博/抖音话题，实现5亿+内容曝光

目标受众：Z世代（18-28岁），热爱音乐节、户外运动、潮流文化，
主要活跃在抖音、小红书、微博

预算：约800万人民币（含媒介+创意+活动）
传播周期：2026年6月15日 - 8月31日

竞品动态：百事可乐同期推出"夏日嘻哈"campaign；元气森林主打低卡清爽

核心创意方向（初步）：
"用可口可乐打开夏天" ——以限定罐包装为核心，
联动头部音乐节IP（草莓音乐节/西湖音乐节），
通过抖音挑战赛引爆UGC，小红书种草生活方式，微博话题沉淀声量

特别需求：需要一套完整的整合传播提案PPT，包含策略框架+媒介计划+创意方向+执行节点
""".strip()


def _request(method: str, path: str, data: dict | None = None, token: str | None = None) -> dict:
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"HTTP {e.code} on {method} {path}: {body}")


def banner(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print('='*60)


def step(msg: str):
    print(f"\n[{time.strftime('%H:%M:%S')}] {msg}")


def main():
    banner("Pitchcraft Happy Path Test")

    # 1. Login
    step("Logging in...")
    auth = _request("POST", "/auth/login", {"email": "test@test.com", "password": "test123"})
    token = auth["access_token"]
    print(f"  ✓ Logged in, token: {token[:40]}...")

    # 2. Create project
    step("Creating project...")
    proj = _request("POST", "/projects", {"client_id": CLIENT_ID, "name": "可口可乐2026夏季"}, token)
    project_id = proj["project_id"]
    print(f"  ✓ Project: {project_id}")

    # 3. Start pipeline
    step("Starting pipeline...")
    started = _request("POST", "/pipeline/start", {
        "project_id": project_id,
        "client_id": CLIENT_ID,
        "raw_brief": BRIEF,
        "output_language": "zh",
    }, token)
    pipeline_id = started["pipeline_id"]
    print(f"  ✓ Pipeline started: {pipeline_id}")

    # 4. Poll + confirm HITL loop
    HITL_ORDER = ["hitl_brief", "hitl_strategy", "hitl_structure", "hitl_gallery"]
    confirmed = set()
    max_polls = 300  # ~15 min max
    poll_interval = 3

    banner("Pipeline running — polling every 3s...")

    for i in range(max_polls):
        time.sleep(poll_interval)
        try:
            status = _request("GET", f"/pipeline/{pipeline_id}/status", token=token)
        except Exception as e:
            print(f"  ! Status poll error: {e}")
            continue

        current = status.get("current_node", "unknown")
        st = status.get("status", "unknown")
        print(f"  [{i+1:3d}] status={st:<12} node={current}", end="")

        if st == "completed":
            pptx = status.get("pptx_path", "?")
            print(f"\n\n✓✓✓ PIPELINE COMPLETE!")
            print(f"     pptx_path = {pptx}")
            banner("HAPPY PATH PASSED ✓")
            return

        if st == "error":
            print(f"\n\n✗✗✗ PIPELINE ERROR at node={current}")
            banner("HAPPY PATH FAILED ✗")
            raise SystemExit(1)

        if st == "budget_exceeded":
            print(f"\n\n✗✗✗ BUDGET EXCEEDED")
            banner("HAPPY PATH FAILED ✗")
            raise SystemExit(1)

        if st == "paused" and current in HITL_ORDER and current not in confirmed:
            print(f"  → HITL pause, confirming...")
            try:
                _request("POST", f"/pipeline/{pipeline_id}/confirm", {
                    "node": current,
                    "action": "confirm",
                    "feedback": None,
                }, token)
                confirmed.add(current)
                print(f"  ✓ Confirmed {current} ({len(confirmed)}/{len(HITL_ORDER)})")
            except Exception as e:
                print(f"  ! Confirm failed: {e}")
        else:
            print()  # newline

    banner("TIMEOUT after max polls ✗")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
