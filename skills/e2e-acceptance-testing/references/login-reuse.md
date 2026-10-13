# 登录态复用：原理与两个必踩的坑

> 起因：每个用例都真登录一次 → 连续跑触发**登录限流**（实测：20 次/60s/IP，
> 实际第 5 次左右就开始 429）→ 用例偶发失败。
> 正解：**复用登录态**。但复用本身有两个坑，搞不好会**假通过**。

## 坑 1：`storage_state()` **不含 sessionStorage**

**Playwright 的 `context.storage_state()` 只导出 `localStorage` + cookies。**
如果被测系统把 token 存在 **`sessionStorage`**（很多 SPA 用 pinia 持久化到那里），
直接复用会拿到**没有 token 的空态** → 被打回登录页。

**修法**：额外抓取并回填 sessionStorage。

```python
def snapshot_state(context, page) -> dict:
    state = context.storage_state()
    state["_session_storage"] = page.evaluate(
        "() => Object.fromEntries(Object.entries(window.sessionStorage))"
    )
    return state

def restore_state(browser, state) -> tuple[BrowserContext, Page]:
    sess = state.pop("_session_storage", {})
    ctx = browser.new_context(storage_state=state)
    page = ctx.new_page()
    page.goto(BASE)
    page.evaluate(
        "s => { for (const [k, v] of Object.entries(s)) window.sessionStorage.setItem(k, v); }",
        sess,
    )
    page.reload()
    return ctx, page
```

## 坑 2：**SPA 里"页面能打开" ≠ "token 有效"**

**这是导致"假通过"的元凶。**

前端拿到本地 token 后**直接渲染界面，并不先校验它**。所以 token 早已失效
（WebSession 空闲 TTL 到期）时，页面**照样渲染出输入框和按钮**。

❌ **错误的有效性校验**（只看页面层）：

```python
def is_valid(page):
    return "/login" not in page.url and page.locator(".chat-textarea").count() > 0
    # ← 死 token 也会通过！
```

后果：用例前段"登录成功"，后段断言接口数据时**炸 401** →
表现为**"单跑通过、连跑失败"**的诡异现象。

✅ **正确：两道判据，必须包含"真发一次请求"**

```python
def token_is_live(page) -> bool:
    """真发一次带凭据的请求，以 HTTP 200 为准。"""
    code = page.evaluate("""async () => {
        const raw = window.sessionStorage.getItem('userStore');
        const token = raw ? JSON.parse(raw).user.token : null;
        if (!token) return 0;
        // ⚠️ fetch 绕过 axios 拦截器 → 必须手动带 Authorization
        const r = await fetch('/api/capabilities', {
            headers: {Authorization: 'Bearer ' + token},
        });
        return r.status;
    }""")
    return code == 200

def state_is_valid(page) -> bool:
    return ("/login" not in page.url) and page.locator(".chat-input").count() > 0 \
           and token_is_live(page)          # ← 后端层判据，缺它就会假通过
```

**失效则**：删缓存 → 回退真登录 → 重建缓存。

## 429 的区分与退避

**把"限流"与"密码错/服务不通"分开**，否则排查时方向全错：

```python
class LoginFailed(AssertionError): ...
class LoginRateLimited(LoginFailed): ...   # 子类，便于分别处理
```

```python
def do_real_login(page, user, pwd, retries=3, wait_s=20):
    for i in range(1, retries + 1):
        ...填表并提交...
        if page.url endswith "/login":
            if is_rate_limited(page):        # 页面出现"频繁"/"429"
                if i == retries: raise LoginRateLimited(...)
                time.sleep(wait_s); continue
            raise LoginFailed(...)           # 密码错/服务不通
        return
```

## 缓存策略

| 项 | 建议 |
|---|---|
| 存放位置 | `tests/e2e/artifacts/state/<user>.json` |
| TTL | 短于 WebSession 空闲 TTL（如 TTL 1800s → 缓存 600s） |
| **必须 gitignore** | 🔴 **缓存内含真实 session token，能借此冒充账号** |
| 失效处理 | 校验不过 → 删缓存 → 真登录 → 重建 |

```gitignore
# e2e 测试产物
tests/e2e/artifacts/
```

⚠️ **这条 gitignore 是安全问题**：未忽略时 `git add -A` 会把**凭据**提交进库。

## 用例写法

```python
@pytest.fixture(scope="session")
def logged_in_state(browser):
    """每个账号只真登录一次，后续复用。"""
    cache = {}
    def get(user):
        if user not in cache:
            cache[user] = _login_and_snapshot(browser, user)
        return cache[user]
    yield get
```

**关键**：复用后**仍要跑 `state_is_valid()`**（含 `token_is_live`），
失效自动回退真登录 —— 绝不"相信缓存一定有效"。
