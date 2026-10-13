# 侦察：写用例前必须摸清的三件事

> **不要跳过这一步。** 跳过侦察直接写用例的代价（实测）：
> 路径猜错（点了不跳转的卡片）→ 用例超时；
> 选择器失效（同一控件有两种文案）→ 用例超时；
> 断言基准错（把不可信来源当真值）→ 断言本身就是错的。

## 一、真实导航路径

**必查三问**：登录后落在哪？目标功能的入口路由是什么？有没有子路由？

### 陷阱：门户页的卡片常常点击无效

很多系统登录后先落在**门户/首页**，上面摆着功能卡片 —— 但那些卡片
**可能只是展示**（无跳转），不是入口。

```python
# ❌ 错：点门户卡片（若不跳转，用例会一直等到超时）
page.get_by_text("<功能名>").click()

# ✅ 对：显式导航到目标路由
page.goto(f"{BASE}{ROUTE_MAIN}")
```

**怎么判断卡片能不能点**：点一下，看 URL 变不变。

**做法**：读前端**路由定义**（`router/index.ts`、`routes.py`、或等价物），确认：
- 登录后落点
- 每个功能的路由路径
- 是否有子路由（如 `/main/detail/:id`）

### 陷阱：关键页面可能藏在子路由里

进入功能页后，真正的操作界面可能在 `/main/detail/<id>`，
而 `/main` 只是列表页。**用例里要显式走到最终页面**，不要假设"进去了就能操作"。

## 二、稳定选择器

**必须实测**，不要凭源码猜 —— 组件库（Element Plus / Ant Design 等）
包装后真实 DOM 与模板写法**不一致**（动态组件、插槽、包装层）。

```python
# 探测脚本：把页面上的 input / button / label 全 dump 出来
page.goto(URL)
for i in range(page.locator("input").count()):
    el = page.locator("input").nth(i)
    print(i, el.get_attribute("type"), el.get_attribute("placeholder"))
for i in range(page.locator("button").count()):
    b = page.locator("button").nth(i)
    print(i, repr((b.inner_text() or "").strip()), b.get_attribute("class"))
```

### 选择器优先级

| 优先级 | 方式 | 说明 |
|---|---|---|
| 1 | `get_by_label("账号")` | 表单标签关联，**最稳** |
| 2 | `get_by_role("button", name="登录")` | 语义 |
| 3 | `get_by_placeholder(...)` / `get_by_text(...)` | 文案 |
| 4 | `.class-name` | 需确认唯一 |
| ❌ | `div:nth-child(3)` | **绝不用** |

### 陷阱：同一控件可能有多种文案

同一张卡片的 `aria-label` / 文案可能有**两种取值**，取决于哪条异步链先到：

| 来源 | 文案 |
|---|---|
| 硬编码兜底 | `<完整场景名>` |
| 接口返回 | `<技能描述>` |

→ **断言必须按"关键词子串"匹配**（取两文案的公共子串），
**不要精确匹配**，否则在一条链上必然超时。

### 陷阱：异步渲染 —— 集合会变

列表类控件常有多条异步链**先后到达并改变集合**（兜底 → 接口A → 接口B）。
**若在中间态读取，会拿到假通过/假失败。**

必须等"**连续若干轮不再变化**"：

```python
def wait_settled(page, getter, quiet_rounds=3, step=300, timeout=15000):
    """等一个集合稳定下来（连续 quiet_rounds 轮不变）。"""
    waited, last, stable = 0, [], 0
    while waited < timeout:
        cur = getter()
        if cur and cur == last:
            stable += 1
            if stable >= quiet_rounds:
                return cur
        else:
            stable = 0
        last = cur
        page.wait_for_timeout(step)
        waited += step
    return getter()
```

**更好的做法**：断言语义性质（如"**没有**越级入口"），而不是硬编码数量 ——
数量受异步链与配置影响，语义性质更稳。

## 三、断言基准（真值）

**必须找到权威来源**，否则断言的期望值本身就是错的。

### 陷阱：同一个数字可能来自两套数据源

实测遇到过：页面显示"当前有 N 个 X"，但 **N 来自两套数据源**：

| 来源 | 内容 | 谁在用 |
|---|---|---|
| **配置/权限树** | 只配了一部分 | 权限判定 |
| **业务库** | 真实全量 | 业务回答 |

**两套不一致** → 界面/回答互相矛盾 → 用户困惑（**不一致本身就是缺陷**）。

**做法**：
1. 找到**业务真值**（直连数据库 / 调权威接口）
2. 断言**优先用业务真值**
3. 顺便记录"两套数据源是否一致"—— 不一致时**记缺陷**

```bash
# 例：直连数据库核实真值
psql -h HOST -U USER -d DB -c "select count(*) from <view> where <条件>"
```

### 陷阱：环境相关的数据会漂移

若真值依赖"当前选中了哪个范围/租户"，**用例必须先把范围钉死**
（显式选择），否则期望值会随"上一次谁改过"而漂移。

## 侦察产出（写进 `TEST_PLAN.md`）

```markdown
## 被测环境
- 前端 / 后端 URL
- 测试账号（角色 / 权限范围）

## 真实路径
- 登录：/login → 成功后落在 <落点>
- 目标功能：必须显式 goto <路由>（门户卡片点击无效）

## 选择器
| 元素 | 选择器 | 实测匹配数 |

## 业务真值
| 维度 | 权威来源 | 值 |
```

## 一次性侦察脚本不要留在测试目录

侦察脚本放**临时目录**（如 `_scratch/`），**不要放 `tests/e2e/`** ——
否则会被 pytest 收集、污染目录；用完即删。
