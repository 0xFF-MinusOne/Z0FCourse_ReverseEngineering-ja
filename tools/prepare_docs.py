#!/usr/bin/env python3
"""元の Markdown を .site-src/ にコピーし、パス中の空白を '-' に置き換え、リンクも書き換える。

元のファイルは変更しない。使い方: python tools/prepare_docs.py
"""
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".site-src"
EXCLUDE = {".git", ".github", ".site-src", "site", "tools", "venv", ".venv"}
COPY_SUFFIX = {".md", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


def safe(name: str) -> str:
    return name.replace(" ", "-")


def out_rel(rel: PurePosixPath) -> PurePosixPath:
    return PurePosixPath(*[safe(p) for p in rel.parts])


def collect():
    files = []
    for p in sorted(ROOT.rglob("*")):
        rel = p.relative_to(ROOT)
        if rel.parts[0] in EXCLUDE or not p.is_file():
            continue
        if p.suffix.lower() in COPY_SUFFIX:
            files.append(PurePosixPath(rel.as_posix()))
    return files


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    files = collect()
    fileset = set(files)
    dirs = {}
    for f in files:
        if f.suffix == ".md":
            dirs.setdefault(f.parent, []).append(f)

    link_re = re.compile(r'(\]\(\s*<?)([^)\s>]+)(>?)((?:\s+"[^"]*")?\s*\))')
    src_re = re.compile(r'((?:src|href)=")([^"]+)(")')

    def rewrite_target(target: str, cur: PurePosixPath) -> str:
        if re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*:|#|//)", target):
            return target
        path, sep, frag = target.partition("#")
        if not path:
            return target
        dec = unquote(path)
        # 現在のファイルからの相対パスを、ルート基準に解決
        parts = []
        for seg in (cur.parent / dec).as_posix().split("/"):
            if seg in ("", "."):
                continue
            if seg == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(seg)
        resolved = PurePosixPath(*parts) if parts else PurePosixPath(".")
        if resolved in fileset:
            new = out_rel(resolved)
        elif resolved in dirs:  # ディレクトリへのリンクは、先頭の章ファイルへ向ける
            new = out_rel(sorted(dirs[resolved])[0])
        else:
            new = None
        if new is None:
            # 存在しない先: 空白だけ置き換えて元の形に近いまま残す(警告で報告される)
            return safe(dec).replace("(", "%28").replace(")", "%29") + (sep + frag if sep else "")
        # 出力側の現在ファイルからの相対パスへ
        cur_out = out_rel(cur)
        rel = _relpath(new, cur_out.parent)
        return rel + (sep + frag if sep else "")

    def convert(text: str, cur: PurePosixPath) -> str:
        text = link_re.sub(lambda m: m.group(1) + rewrite_target(m.group(2), cur) + m.group(3) + m.group(4), text)
        text = src_re.sub(lambda m: m.group(1) + rewrite_target(m.group(2), cur) + m.group(3), text)
        return text

    for f in files:
        dst = OUT / out_rel(f).as_posix()
        dst.parent.mkdir(parents=True, exist_ok=True)
        if f.suffix == ".md":
            text = (ROOT / f.as_posix()).read_text(encoding="utf-8")
            dst.write_text(convert(text, f), encoding="utf-8")
        else:
            shutil.copy2(ROOT / f.as_posix(), dst)
    print(f"prepared {len(files)} files into {OUT}")


def _relpath(target: PurePosixPath, start: PurePosixPath) -> str:
    import posixpath
    return posixpath.relpath(target.as_posix(), start.as_posix() if str(start) != "." else ".")


if __name__ == "__main__":
    sys.exit(main())
