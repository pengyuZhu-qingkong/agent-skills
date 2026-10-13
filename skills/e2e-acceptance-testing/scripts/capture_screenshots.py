"""证据截图脚本模板（按功能域截图 + 生成索引）。

## 用法

1. 改配置区（BASE / API / 账号 / 选择器）
2. 按被测系统调整 `main()` 里的截图步骤
3. 运行：`python capture_screenshots.py`

## 为什么需要单独跑一遍

测试套件的自动截图**只在失败时触发**，而交付时通常全绿 → 没有图可给。
验收报告需要**主动**截"成功 + 异常"两类场景的证据图。

## 原则

- 截**真实界面**（真登录、真发请求、真结果），不做假图
- 每张图配一句**它证明什么**
- **异常/拒绝场景的图最有价值**（证明"系统在异常下表现正确"）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 配置区（按被测系统改）──────────────────────────────────────────────
BASE = "http://127.0.0.1:9999"
PASSWORD = "12345678"
#: 账号 → (角色名, 期望的范围描述)；范围描述为 None 表示可跨范围
ACCOUNTS: dict[str, tuple[str, str | None]] = {
    "admin": ("管理员", None),
    "user_a": ("受限角色A", "某学院"),
}
#: 登录页选择器
SEL_USER = "#username"
SEL_PWD = "#password"
SEL_SUBMIT = ".submit-btn"
#: 登录成功后的落点（URL 片段）
URL_AFTER_LOGIN = "/home"
#: 功能入口路由（**不是门户页** —— 门户卡片常常点击无效）
ROUTE_MAIN = "/main"
#: 主界面选择器
SEL_INPUT = "textarea.chat-input"
SEL_CARD = ".scene-tag"           # 功能入口卡片
SEL_CARD_LABEL = ".scene-tag-label"
# ──────────────────────────────────────────────────────────────────────

OUT = Path(__file__).resolve().parent / "screenshots"
captured: list[tuple[str, str]] = []


def shot(page, name: str, note: str, *, full: bool = True) -> None:  # noqa: ANN001
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
        captured.append((f"{name}.png", note))
        print(f"  ✔ {name}.png  — {note}")
    except Exception as exc:  # noqa: BLE001
        print(f"  ✘ {name}: {exc}")


def login(page, user: str) -> bool:  # noqa: ANN001
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(1200)
    page.locator(SEL_USER).fill(user)
    page.locator(SEL_PWD).fill(PASSWORD)
    page.locator(SEL_SUBMIT).click()
    try:
        page.wait_for_url(f"**{URL_AFTER_LOGIN}", timeout=30000)
        return True
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ① 登录页 + 登录失败（**异常场景必须截**）
        print("\n[①] 登录")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.goto(f"{BASE}/login", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        shot(page, "A1-登录页", "登录入口")
        page.locator(SEL_USER).fill(next(iter(ACCOUNTS)))
        page.locator(SEL_PWD).fill("wrong-password")
        page.locator(SEL_SUBMIT).click()
        page.wait_for_timeout(2500)
        shot(page, "A2-密码错误被拒", "错误凭据被拒：留在登录页且有提示")
        ctx.close()

        # ② 每个角色：范围显示 + 功能入口
        print("\n[②] 角色与权限")
        for user, (role, expect) in ACCOUNTS.items():
            ctx = browser.new_context(viewport={"width": 1600, "height": 950}, locale="zh-CN")
            page = ctx.new_page()
            if not login(page, user):
                print(f"  ! {user} 登录失败，跳过")
                ctx.close()
                continue
            page.wait_for_timeout(2500)
            shot(page, f"B-{role}-范围", f"{role} 的范围显示"
                 + ("（可跨范围切换）" if expect is None else f"（锁定：{expect}）"))
            page.goto(f"{BASE}{ROUTE_MAIN}", wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            labels = [t.strip() for t in page.locator(SEL_CARD_LABEL).all_inner_texts()]
            shot(page, f"C-{role}-功能入口",
                 f"{role} 的可用功能入口 {page.locator(SEL_CARD).count()} 个：{'、'.join(labels)}")
            ctx.close()

        # ③ 异常/拒绝场景（**最有价值的一类证据**）
        print("\n[③] 异常/拒绝场景")
        # 示例：用受限角色请求越界对象
        # 按实际系统改写：发消息 / 调接口后等待结论，再截图
        # ctx = browser.new_context(...); page = ctx.new_page()
        # if login(page, "user_a"):
        #     page.goto(f"{BASE}{ROUTE_MAIN}"); ...
        #     shot(page, "D-越权被拒", "越界请求被拒绝，且未产出数据（对应缺陷回归）")

        browser.close()

    OUT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 测试证据截图索引", "",
        f"共 {len(captured)} 张。均为真实界面实拍（真登录 / 真请求 / 真结果）。", "",
        "| 文件 | 它证明什么 |", "|---|---|",
    ]
    lines += [f"| `{n}` | {note} |" for n, note in captured]
    (OUT / "index.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n共 {len(captured)} 张 → {OUT}")
    return 0


if __name__ == "__main__":
    import os

    code = 0
    try:
        code = main()
    except BaseException:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        code = 2
    sys.stdout.flush()
    os._exit(code)
