"""把测试报告 Markdown 转成单文件 HTML（无外部依赖，双击即可看）。

用法: python md2html.py 测试报告-20261013.md 测试报告-20261013.html
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path


def inline(text: str) -> str:
    """行内标记：图片 / **粗体** / `代码` / _斜体_。"""
    # 图片必须先处理（否则 ![alt](src) 里的 [] () 会被后面的规则吃掉）
    imgs: list[str] = []

    def _stash(m: re.Match) -> str:
        alt, src = m.group(1), m.group(2)
        # ⚠️ 不加 `loading="lazy"`：报告是要**转发**的单文件（邮件/IM/离线预览），
        # 懒加载在部分客户端不生效或未滚动到就不加载 → 收件人看到空白。
        # 全量预加载虽使文件略大，但换来"打开即见"的确定性。
        imgs.append(
            f'<img src="{html.escape(src, quote=True)}" alt="{html.escape(alt)}"/>'
        )
        return f"\x00IMG{len(imgs) - 1}\x00"

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _stash, text)
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", text)
    for i, tag in enumerate(imgs):
        text = text.replace(f"\x00IMG{i}\x00", tag)
    return text


def convert(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    in_code = False
    code_buf: list[str] = []
    in_table = False
    list_type: str | None = None

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            out.append(f"</{list_type}>")
            list_type = None

    def close_table() -> None:
        nonlocal in_table
        if in_table:
            out.append("</tbody></table>")
            in_table = False

    while i < len(lines):
        line = lines[i]

        # 代码块
        if line.strip().startswith("```"):
            if not in_code:
                close_list()
                close_table()
                in_code = True
                code_buf = []
            else:
                in_code = False
                out.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # 表格
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(
            r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]
        ):
            close_list()
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append("<table><thead><tr>")
            for h in header:
                out.append(f"<th>{inline(h)}</th>")
            out.append("</tr></thead><tbody>")
            in_table = True
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>")
                for c in cells:
                    out.append(f"<td>{inline(c)}</td>")
                out.append("</tr>")
                i += 1
            close_table()
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            close_list()
            close_table()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue

        # 分隔线
        if re.match(r"^\s*---+\s*$", line):
            close_list()
            close_table()
            out.append("<hr/>")
            i += 1
            continue

        # 引用
        if line.strip().startswith(">"):
            close_list()
            close_table()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + "<br/>".join(inline(b) for b in buf) + "</blockquote>")
            continue

        # 列表
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            close_table()
            want = "ul" if m.group(2) in ("-", "*") else "ol"
            if list_type != want:
                close_list()
                out.append(f"<{want}>")
                list_type = want
            out.append(f"<li>{inline(m.group(3))}</li>")
            i += 1
            continue

        # 空行 / 段落
        if not line.strip():
            close_list()
            close_table()
            i += 1
            continue

        close_list()
        close_table()
        buf = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|\s*[-*]\s|\s*\d+\.\s|\||>|```|---)", lines[i]
        ):
            buf.append(lines[i])
            i += 1
        out.append("<p>" + "<br/>".join(inline(b) for b in buf) + "</p>")

    close_list()
    close_table()
    return "\n".join(out)


CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  margin: 0 auto; padding: 48px 32px 96px; max-width: 1100px;
  font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
  font-size: 15px; line-height: 1.75; color: #1f2937; background: #fff;
}
h1 { font-size: 28px; border-bottom: 3px solid #2563eb; padding-bottom: 12px; margin-bottom: 28px; }
h2 { font-size: 21px; margin-top: 40px; padding-left: 10px; border-left: 4px solid #2563eb; }
h3 { font-size: 17px; margin-top: 28px; color: #1e40af; }
h4 { font-size: 15px; margin-top: 20px; }
p { margin: 10px 0; }
code {
  background: #f1f5f9; padding: 2px 6px; border-radius: 4px;
  font-family: Consolas, Monaco, monospace; font-size: 13px; color: #be123c;
}
pre {
  background: #0f172a; color: #e2e8f0; padding: 16px 18px; border-radius: 8px;
  overflow-x: auto; font-size: 13px; line-height: 1.6;
}
pre code { background: none; color: inherit; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 14px; table-layout: fixed; }
th, td { border: 1px solid #e2e8f0; padding: 9px 12px; text-align: left; vertical-align: top; word-break: break-word; }
th { background: #f8fafc; font-weight: 600; }
tr:nth-child(even) td { background: #fcfdfe; }
img {
  max-width: 100%; height: auto; border: 1px solid #e2e8f0; border-radius: 6px;
  margin: 6px 0; display: block; box-shadow: 0 1px 3px rgba(0,0,0,.06);
  cursor: zoom-in;              /* 提示可点开 */
  transition: box-shadow .15s, transform .15s;
}
img:hover { box-shadow: 0 4px 14px rgba(37,99,235,.28); transform: translateY(-1px); }
td img { max-height: 260px; width: auto; }

/* ── 灯箱：点击图片放大 ─────────────────────────────────────────────
   纯 CSS + 极简 JS（无外部依赖，保证单文件可转发/离线可用）。
   点图放大、点任意处或按 Esc 关闭；再点图片本身也关闭（避免"点了没反应"）。 */
#lightbox {
  position: fixed; inset: 0; z-index: 9999; display: none;
  background: rgba(15,23,42,.88); backdrop-filter: blur(3px);
  cursor: zoom-out;
}
#lightbox.open { display: flex; align-items: center; justify-content: center; }
#lightbox img {
  max-width: 96vw; max-height: 94vh; width: auto; height: auto;
  border: none; border-radius: 4px; box-shadow: 0 12px 48px rgba(0,0,0,.5);
  cursor: zoom-out; margin: 0; transform: none;
}
#lightbox .hint {
  position: fixed; bottom: 18px; left: 0; right: 0; text-align: center;
  color: #cbd5e1; font-size: 13px; pointer-events: none;
}
@media print { #lightbox { display: none !important; } }
blockquote {
  margin: 14px 0; padding: 10px 16px; background: #f8fafc;
  border-left: 4px solid #94a3b8; color: #475569;
}
ul, ol { padding-left: 26px; margin: 10px 0; }
li { margin: 4px 0; }
hr { border: none; border-top: 1px solid #e2e8f0; margin: 32px 0; }
strong { color: #0f172a; }
"""


def embed_images(doc: str, base_dir: Path) -> str:
    """把 <img src="相对路径"> 转成 base64 内嵌，生成**单文件自包含 HTML**。

    为什么要内嵌：报告要作为**单个文件**转发（邮件/IM），
    外部图片路径在别人机器上打不开、也容易漏发。
    """
    import base64
    import mimetypes

    def repl(m: re.Match) -> str:
        attr, src = m.group(1), m.group(2)
        if src.startswith(("data:", "http://", "https://")):
            return m.group(0)
        p = (base_dir / src).resolve()
        if not p.is_file():
            print(f"  ! 图片缺失: {src}")
            return m.group(0)
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f'{attr}src="data:{mime};base64,{b64}"'

    return re.sub(r'(\s)src="([^"]+)"', repl, doc)


SCRIPT = """
(function () {
  var box = document.getElementById('lightbox');
  var big = box.querySelector('img');
  var hint = box.querySelector('.hint');
  var imgs = document.querySelectorAll('img:not(#lightbox img)');
  var scale = 1;

  function open(src, caption) {
    big.src = src;
    scale = 1;
    big.style.transform = 'scale(1)';
    hint.textContent = (caption ? caption + '　|　' : '') +
      '点击任意处 / 按 Esc 关闭　·　滚轮缩放、拖动平移';
    box.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
  function close() {
    box.classList.remove('open');
    big.src = '';
    scale = 1;
    big.style.transform = 'scale(1)';
    big.style.cursor = 'zoom-out';
    document.body.style.overflow = '';
  }

  imgs.forEach(function (im) {
    var alt = im.getAttribute('alt') || '';
    // 表格里的图无 alt（alt 由 Markdown 空文案给出），退化为空
    if (!alt) {
      var td = im.closest('td');
      if (td) { var n = td.nextElementSibling; if (n) alt = (n.innerText || '').trim(); }
    }
    im.addEventListener('click', function () { open(im.src, alt); });
  });

  box.addEventListener('click', function (e) {
    // 点图片本身也关闭（体验上更符合"再点一下收起来"）
    close();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && box.classList.contains('open')) close();
  });

  // 滚轮缩放（大图查看细节用）
  box.addEventListener('wheel', function (e) {
    if (!box.classList.contains('open')) return;
    e.preventDefault();
    scale = Math.min(6, Math.max(0.3, scale + (e.deltaY < 0 ? 0.15 : -0.15)));
    big.style.transform = 'scale(' + scale + ')';
    big.style.cursor = scale > 1 ? 'grab' : 'zoom-out';
  }, { passive: false });

  // 拖动平移（放大后看局部）
  var dragging = false, sx = 0, sy = 0, ox = 0, oy = 0;
  box.addEventListener('mousedown', function (e) {
    if (!box.classList.contains('open') || scale <= 1) return;
    dragging = true; sx = e.clientX; sy = e.clientY;
    var m = /translate\\(([-\\d.]+)px,\\s*([-\\d.]+)px\\)/.exec(big.style.transform);
    ox = m ? parseFloat(m[1]) : 0; oy = m ? parseFloat(m[2]) : 0;
    e.stopPropagation();
  });
  document.addEventListener('mousemove', function (e) {
    if (!dragging) return;
    var dx = e.clientX - sx, dy = e.clientY - sy;
    big.style.transform = 'scale(' + scale + ') translate(' + (ox + dx / scale) + 'px,' + (oy + dy / scale) + 'px)';
  });
  document.addEventListener('mouseup', function () { dragging = false; });
})();
"""


def main() -> int:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "测试报告-20261013.md")
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else src.with_suffix(".html"))
    md = src.read_text(encoding="utf-8")
    title = next((l.lstrip("# ").strip() for l in md.split("\n") if l.startswith("# ")), "报告")
    body = embed_images(convert(md), src.parent)
    lightbox = (
        '<div id="lightbox"><img alt="放大预览"/>'
        '<div class="hint"></div></div>'
        f"<script>{SCRIPT}</script>"
    )
    doc = (
        "<!DOCTYPE html>\n<html lang='zh-CN'>\n<head>\n<meta charset='UTF-8'>\n"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>\n"
        f"<title>{html.escape(title)}</title>\n<style>{CSS}</style>\n"
        f"</head>\n<body>\n{body}\n{lightbox}\n</body>\n</html>\n"
    )
    dst.write_text(doc, encoding="utf-8")
    print(f"OK {dst}  {dst.stat().st_size / 1024 / 1024:.2f} MB（图片已内嵌，单文件可转发）")
    return 0


if __name__ == "__main__":
    import os

    code = 1
    try:
        code = main()
    except BaseException:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        code = 2
    sys.stdout.flush()
    os._exit(code)
