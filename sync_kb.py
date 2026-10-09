"""
sync_kb.py —— 飞书知识库同步脚本（离线管线）
================================================================
把飞书知识空间「AI Agent 学习知识库」的最新笔记拉取成本地 Markdown，
覆盖更新 docs/。在本地开发机运行（需要 lark-cli 凭证）；
部署后的 Streamlit 应用只读 docs/，不直接连飞书。

用法：
    python3 sync_kb.py
"""

import os
import re
import subprocess
import sys
import tempfile

SPACE_ID = "7691931235592981705"
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")


def run_json(args: list[str]) -> dict:
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"命令失败：{' '.join(args)}\n{r.stderr[-500:]}")
        sys.exit(1)
    import json
    return json.loads(r.stdout)


def title_to_filename(title: str) -> str:
    """'01 · Agent（智能体）' → '01-01___Agent_智能体_.md'"""
    m = re.match(r"^\s*(\d+)", title)
    num = m.group(1) if m else "00"
    name = re.sub(r"^[\d\s·.\-]+", "", title)          # 去掉开头序号与分隔符
    name = re.sub(r"[^\w一-龥]+", "_", name).strip("_")  # 非文字字符统一成下划线
    return f"{num}-{num}___{name}.md"


def main():
    # 1. 拉知识空间节点列表
    data = run_json([
        "lark-cli", "wiki", "+node-list",
        "--space-id", SPACE_ID, "--as", "user", "--format", "json",
    ])
    nodes = data["data"]["nodes"]
    print(f"知识空间共 {len(nodes)} 篇文档")

    os.makedirs(DOCS_DIR, exist_ok=True)
    ok = fail = 0
    with tempfile.TemporaryDirectory() as tmp:
        for n in nodes:
            title = n["title"]
            token = n["node_token"]
            out_name = title_to_filename(title)
            # 2. 导出 markdown 到临时目录
            r = subprocess.run([
                "lark-cli", "drive", "+export",
                "--doc-type", "wiki", "--file-extension", "markdown",
                "--token", token, "--output-dir", tmp,
                "--overwrite", "--format", "json",
            ], capture_output=True, text=True)
            if r.returncode != 0:
                print(f"  ✗ 导出失败：{title}")
                fail += 1
                continue
            # 3. 找到导出文件，按统一命名写入 docs/
            src = os.path.join(tmp, f"{title}.md")
            if not os.path.exists(src):
                # 兜底：临时目录里找唯一 md
                mds = [f for f in os.listdir(tmp) if f.endswith(".md")]
                if not mds:
                    print(f"  ✗ 导出文件缺失：{title}")
                    fail += 1
                    continue
                src = os.path.join(tmp, mds[0])
            dst = os.path.join(DOCS_DIR, out_name)
            with open(src, encoding="utf-8") as f:
                content = f.read()
            with open(dst, "w", encoding="utf-8") as f:
                f.write(content)
            # 清理临时目录里的导出文件（下一篇不会撞名，但保持干净）
            os.remove(src)
            print(f"  ✓ {out_name}")
            ok += 1

    print(f"\n完成：成功 {ok} / 失败 {fail}，docs/ 已更新")


if __name__ == "__main__":
    main()
