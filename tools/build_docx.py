#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Mermaid 块抽出 -> mmdc 渲染 PNG -> 替换为图片引用 -> pandoc 转 docx
一次性完成 docs/业务需求说明书.md -> docs/HiDevLab-公共流程-业务需求说明书.docx
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(".").resolve()
DOCS = ROOT / "docs"
IMAGES = DOCS / "images"
IMAGES.mkdir(parents=True, exist_ok=True)

SOURCE = DOCS / "业务需求说明书.md"
WORK_MD = DOCS / "_working.md"
OUTPUT = DOCS / "HiDevLab-公共流程-业务需求说明书.docx"

# 给 mermaid 块起名（按出现顺序，名字带业务含义）
MERMAID_NAMES = [
    "er-diagram",
    "main-flow",
]


def which_or_die(name: str) -> str:
    p = shutil.which(name)
    if p is None:
        p = shutil.which(name + ".cmd")
    if p is None:
        sys.stderr.write(f"FATAL: cannot find {name} in PATH\n")
        sys.exit(4)
    return p


def render_mermaid(mmd_path: Path, png_path: Path, width: int = 1600) -> tuple[int, str, str]:
    config = ROOT / "tools" / "puppeteer-config.json"
    cmd = [
        which_or_die("mmdc"),
        "-i", str(mmd_path),
        "-o", str(png_path),
        "-w", str(width),
        "-b", "white",
        "-s", "2",
        "-p", str(config),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")

    pattern = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)

    counter = {"n": 0}
    failures: list[str] = []

    def repl(match: re.Match) -> str:
        counter["n"] += 1
        idx = counter["n"] - 1
        name = MERMAID_NAMES[idx] if idx < len(MERMAID_NAMES) else f"diagram-{counter['n']}"
        mmd_path = IMAGES / f"{name}.mmd"
        png_path = IMAGES / f"{name}.png"
        mmd_path.write_text(match.group(1).rstrip() + "\n", encoding="utf-8")

        rc, out, err = render_mermaid(mmd_path, png_path)
        if rc != 0:
            failures.append(f"{name}: {err.strip() or out.strip()}")
            return match.group(0)

        rel = f"images/{png_path.name}"
        return f"![{name}]({rel})"

    new_text = pattern.sub(repl, text)

    if failures:
        print("FAILURES:")
        for f in failures:
            print(" -", f)
        return 2

    WORK_MD.write_text(new_text, encoding="utf-8")
    print(f"working md -> {WORK_MD}")

    cmd = [
        which_or_die("pandoc"),
        str(WORK_MD.relative_to(ROOT)),
        "-f", "gfm+yaml_metadata_block",
        "-t", "docx",
        "-o", str(OUTPUT.relative_to(ROOT)),
        "--resource-path", str(DOCS.relative_to(ROOT)),
        "--standalone",
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if proc.returncode != 0:
        print("pandoc FAIL:", proc.stderr)
        return 3

    print(f"docx -> {OUTPUT}")
    if proc.stdout:
        print(proc.stdout)

    WORK_MD.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
