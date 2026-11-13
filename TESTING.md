# 🧪 Testing session-graph · 测试清单

## Test data · 测试数据

```bash
bash tests/make_testbed.sh            # creates ../session-graph-testbed
```

一个虚构的 todo app 项目，里面有 8 个真实的 Claude Code session（用 Haiku 生成，提问是英文，每个只回答一句话，花费很少）。

| # | 位置 | 内容 | 测什么 |
|---|---|---|---|
| S1 | `main` | data model → JSON storage → which directory (3 prompts) | 主线；被 fork 之后自己继续往下聊 |
| S2 | `main` | **fork of S1**: SQLite instead | fork 识别 |
| S7 | `main` | **fork of S2**: ORM vs plain SQL | 多层 fork，应挂在 S2 下，而不是 S1 |
| S8 | `feature/auth` | **2nd fork of S1**: add userId | 兄弟 fork、跨分支的 fork |
| S3, S4 | `feature/auth` | login: cookies vs JWT; login tests | 按分支分组 + 时间顺序 |
| S5 | `.worktrees/ui`（`experiment/ui`） | new UI: cards or table | worktree 分组 |
| S6 | `main` 下的 `docs/` | README contents | 子文件夹分组 |

## How to test · 怎么测

1. 在 Claude 里打开一个 session，文件夹选 `session-graph-testbed`。
2. 输入 `/session-graph`。
3. 对照下面的清单逐条检查。

## Checklist · 检查清单

- [ ] **语言**：网页默认英文，点右上角"中文"能切换（`--lang zh` 直接生成中文版）
- [ ] **触发**：`/session-graph` 能被识别，Claude 按步骤跑完并打开网页
- [ ] **范围**：只出现这个项目的 session，没有其他项目的
- [ ] **分组**：4 组：`main`、`feature/auth`、`experiment/ui @ ui`、`main @ docs`
- [ ] **fork**：橙色箭头为 S1→S2、S2→S7、S1→S8；S2 和 S8 之间**没有**箭头
- [ ] **分叉点**：点开 S2 能看到"fork 自 S1，在『OK. In one sentence: is a JSON file fine for storage to start with?』之后分出"
- [ ] **标题**：每个节点的名字能看出它在做什么，原 session 和 fork 能区分开
- [ ] **时间**：能看到开始和最后活跃时间；同组里的虚线箭头方向是从早到晚
- [ ] **一句话摘要**：摘要准确；fork 的摘要说的是分叉之后做了什么不同的事
- [ ] **是否在运行**：你正在用的 session 显示绿色，其余显示蓝色
- [ ] **context 占用**：显示 token 数，圆点大小反映差别
- [ ] **是否已归档**：在 Claude app 里归档一个 session，重新运行后它显示为灰色；勾选"隐藏已归档"后它会消失
- [ ] **只看图**：Claude 没有修改、归档或删除任何 session
- [ ] **最终目标**：看完图，能说清楚各个 session 之间的关系，以及下一步该回到哪个 session

## Known limits · 已知限制

- 用 `claude -p` 或 CLI 开的 session 在 desktop app 里看不到，所以归档状态显示为"未知"。
- desktop app 用 `start_session` 开出来的子 session（"由谁启动"）还没有画出来。
- 网页需要联网加载 vis-network；断网时只有右侧列表能用。

## Clean up · 清理测试数据

```bash
rm -rf ../session-graph-testbed ~/.claude/projects/*session-graph-testbed ~/.claude/session-graph/*session-graph-testbed
```
