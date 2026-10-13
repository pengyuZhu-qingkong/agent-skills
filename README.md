# Agent Skills

个人维护的 Agent Skill 集合。每个 skill 是独立的目录，放在 `skills/` 下。

## 现有 Skills

| Skill | 用途 |
|---|---|
| [`e2e-acceptance-testing`](skills/e2e-acceptance-testing/) | 用 Playwright + pytest 为待交付的 Web 应用建立端到端功能测试与验收报告 |

---

## 怎么用

### 方式一：整个仓库克隆到 skills 目录（推荐）

```bash
git clone https://github.com/pengyuZhu-qingkong/agent-skills.git
# 把需要的 skill 目录拷进你的 Agent 的 skills 目录
cp -r agent-skills/skills/e2e-acceptance-testing <你的项目>/.agents/skills/
```

**各工具的 skills 目录**：

| 工具 | 目录 |
|---|---|
| OMP / 本项目约定 | `<项目>/.agents/skills/` |
| Claude Code | `~/.claude/skills/` 或 `<项目>/.claude/skills/` |
| 其他 | 看该工具的 skill 加载约定 |

### 方式二：只取一个 skill

把 `skills/<名字>/` 整个目录复制到你的 skills 目录即可 —— 每个 skill 自包含，
无跨目录依赖。

### 方式三：打成 `.skill` 包分发

```bash
python skill-creator/scripts/package_skill.py skills/e2e-acceptance-testing ./dist
# 产出 dist/e2e-acceptance-testing.skill（zip 格式，可直接发送）
```

---

## Skill 结构约定

```
skills/<skill-name>/
├── SKILL.md          # 必需：YAML frontmatter(name/description) + 正文
├── references/       # 可选：按需加载的详细文档
└── scripts/          # 可选：可执行脚本
```

**规范要点**：

- `name` 与目录名一致，kebab-case
- `description` 必须说清**做什么**与**何时用**（这是唯一的触发依据）
- **SKILL.md 正文 < 5k 字**，详细内容放 `references/`（渐进式披露）
- 不写 `README.md` / `CHANGELOG.md` 等辅助文档在 skill 目录内

---

## 贡献

个人仓库。如需修改：

1. 改 `skills/<名字>/` 下的文件
2. 校验：
   ```bash
   python skill-creator/scripts/quick_validate.py skills/<名字>
   ```
3. 提交并推送
