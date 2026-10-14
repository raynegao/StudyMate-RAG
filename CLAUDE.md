# StudyMate RAG 开发约定（Claude Code 入口）

本目录的协作规则正文在同目录的 `AGENTS.md`，Codex 与 Claude Code 共用同一份；需要修改规则时改 `AGENTS.md`，不要在这里另写一套。

@AGENTS.md

## Claude 侧补充

- 全局规则见 `~/.claude/CLAUDE.md`（与 `~/.codex/AGENTS.md` 内容对应）；项目索引见 `~/Documents/Claude/CLAUDE.md`。
- AGENTS.md 中的 Codex 专属名词按此对应执行：Documents / Spreadsheets / Presentations 插件 → docx / xlsx / pptx skill；`cua_repl`、Codex 电脑控制 → Claude 电脑控制工具；"Codex 随附 Python 运行时" → 本机 `python3` 或项目 `.venv`；`course-mentor` / `course-executor` → 按 AGENTS.md 描述的导师 / 执行两种模式进行；Codex 内置浏览器 → 不用，统一使用本机 Chrome。
