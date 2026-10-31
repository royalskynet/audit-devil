[English](README.md)

讓第二個模型對你的變更扮演魔鬼代言人（審計 + 事後檢討），要求每一項發現都引用 `path:line`，並在你相信它之前，機械式查核每一個引用。

## 為什麼

審自己的變更，等於用自己的盲點在審。第二個模型有不同的盲點，所以能抓到你看漏的地方——但它也可能捏造一個指向空無的引用。`check` 把第二意見變成可查核的第二意見：若引用的行不存在，執行會以 1 結束，而不是默默把虛構內容交到你手上。

## 安裝

```bash
git clone https://github.com/royalskynet/audit-devil
cd audit-devil
ln -s "$PWD/bin/audit-devil" ~/.local/bin/
```

Claude Code 斜線指令（英文）：

```bash
ln -s "$PWD/commands/audit.en.md" ~/.claude/commands/audit.md
```

中文指令請改為連結 `commands/audit.md`。

需求：Python 3.9+ 與 git，其他都不需要。

## 選擇你的第二個模型

沒有內建的預設模型。audit-devil 依下列順序決定第二模型：

1. 命令列的 `--preset <名稱>`
2. 環境變數 `AUDIT_DEVIL_PRESET`／`AUDIT_DEVIL_CMD`
3. 設定檔 `~/.config/audit-devil/config`（會遵守 `$XDG_CONFIG_HOME`；`AUDIT_DEVIL_CONFIG` 可改路徑）
4. 都沒設、且你在終端機前，它會詢問你，並問要不要存成預設
5. 其他情況（CI、代理程式、管線）以 exit 2 停下，並告訴你怎麼設定

內建 preset：`deepseek`（opencode＋DeepSeek V4 Pro）、`builder`（OpenBot Builder）、`cmd`（任何你指定的 CLI）。

```bash
audit-devil config                        # 顯示目前設定與每項的來源
audit-devil config --ask                  # 互動選擇
audit-devil config --preset deepseek      # 存成預設
audit-devil config --preset cmd --cmd 'llm -m gpt-4o-mini'
```

`cmd` 的指令從 stdin 讀取提示詞，並把報告寫到 stdout。指令裡的 `{material}` 會換成 bundle 的材料目錄。請依你安裝的 CLI 版本調整；作者實測過 OpenBot 與下方 opencode＋DeepSeek 那一行，其餘是未實測的範例。

```bash
# 建議：simonw/llm（Apache-2.0；外掛涵蓋 OpenRouter/Ollama/Gemini/Anthropic）
AUDIT_DEVIL_PRESET=cmd AUDIT_DEVIL_CMD='llm -m gpt-4o-mini'

# 2026-10-31 實測：opencode 跑 DeepSeek，唯讀 agent，在材料目錄內執行
AUDIT_DEVIL_PRESET=deepseek   # = opencode run -m opencode-go/deepseek-v4-pro --agent plan --dir {material}

# 透過 llm 外掛使用任何 OpenRouter 模型
AUDIT_DEVIL_PRESET=cmd AUDIT_DEVIL_CMD='llm -m openrouter/<model>'

# 其他接受 stdin 提示詞、輸出到 stdout 的 CLI
AUDIT_DEVIL_PRESET=cmd AUDIT_DEVIL_CMD='codex exec -'
AUDIT_DEVIL_PRESET=cmd AUDIT_DEVIL_CMD='gemini -p ""'
AUDIT_DEVIL_PRESET=cmd AUDIT_DEVIL_CMD='ollama run qwen2.5-coder'
AUDIT_DEVIL_PRESET=cmd AUDIT_DEVIL_CMD='claude -p --model claude-sonnet-5-5'
```

`builder` preset 會與 OpenBot（本機代理程式）的 Builder agent 對話。它需要 send-to-openbot 技能（`OPENBOT_SKILL_DIR`）；設定 `OPENBOT_AGENT=<id>` 可改用其他 agent。它的回覆會在之後的回合才送達，因此你必須執行 `collect`。

## 快速開始

```bash
audit-devil bundle --root . --diff HEAD~1..HEAD --note "what this change is for"
audit-devil send <bundle>
audit-devil collect <bundle>   # OpenBot only; skip for cmd
audit-devil check <bundle>
# read checked.md, then fill in verdict.md
```

一個 bundle 目錄包含 `task.md`（提示詞）、`material/`（diff 與變更後的完整檔案）、`meta.json`、`report.md`（第二個模型的回答）、`checked.md`（每個引用都已用實際行號查核），以及 `verdict.md`（你的裁決）。

## 報告格式

提示詞是 `bin/audit-devil` 中的 `SPEC` 常數，以下逐字照錄：

```
You are the devil's advocate on this change. Your job is to find what is wrong
with it and to explain why nobody caught it. You are not here to approve it.

Two halves, both required:

AUDIT — defects in the material itself: wrong logic, unhandled failure, unsafe
input, race, silent fallback, dead or speculative code, a simpler correct form.
POST-MORTEM — for each defect answer: where else does this pattern appear in the
material, which layer should have stopped it (test, type, guard, hook, review),
and under what conditions it gets written again.

Rules:
- Every finding must cite real locations from the material as `path:line` or
  `path:line-line`. Paths are relative to the material root. A finding you
  cannot locate in the material does not go in the report.
- No praise, no summary of what the code does, no restating the task.
- If you believe the change is sound, say so in `## Verdict` and report only the
  findings you can actually evidence. An empty findings list is a valid answer.
- Rank findings highest severity first.
- Do a full pass before answering; do not stop at the first valid finding.
- Do not report style, formatting, lint or type-check issues, and no generic
  advice such as "add more tests". Only what genuinely matters.

Output format, exactly this, nothing before or after:

## Verdict
<one or two sentences: ship / fix first / cannot tell, and why>

### F1 <short title>
severity: high|medium|low
kind: audit|postmortem
action: auto-fix|ask-user|no-op
evidence: <path:line>[, <path:line-line> ...]
claim: <what is wrong, one or two sentences>
why-not-caught: <which layer was missing>
fix: <smallest change that fixes the cause, not the symptom>

action: auto-fix = correctness, error handling, security, performance — fixable
without discussing intent. ask-user = product behaviour or the author's deliberate
intent; when in doubt, ask-user. no-op = informational.

### F2 ...
```

## `check` 的運作方式

對每一個 `evidence:` 項目，`check` 會以 material 根目錄為基準解析引用，並回報下列其中一種狀態：

- `OK` — 檔案與行號都存在；實際的原始碼行會被引用出來。
- `MISSING` — 該路徑不存在於 material 中，或無法解析（例如 symlink 迴圈）。
- `OUTOFRANGE` — 路徑存在，但引用的行號落在檔案範圍之外。
- `OUTSIDE` — 該路徑逃出了 material 根目錄。
- `BADFORM` — 引用不是 `path:line` 或 `path:line-line` 的形式。

路徑可以是 material 相對路徑（`files/x`）或 repo 相對路徑（`x`），兩者都會解析。結束碼 0 表示每個引用都查核通過。結束碼 1 表示至少有一個引用是 `UNVERIFIED`，或報告既沒有 `## Verdict` 也沒有任何發現區塊（模型無視格式）。有 `## Verdict` 但零發現是合法的乾淨答案，結束碼 0。結束碼 2 表示用法錯誤。

`OK` 只證明那些行存在，並不證明該主張為真。裁決仍須由你閱讀程式碼後自行做出。

## 裁決

填寫 `verdict.md`。每個 `decision:` 是下列之一：

- `accept` — 你已查核為真，並會在這一輪修正。
- `reject` — 你已查核為假，或該位置不存在；用一句話說明原因。
- `defer` — 確實存在但超出範圍；記錄它被保存在何處（issue / fixindex / state）。

## 環境變數

| 變數 | 意義 | 預設值 |
| --- | --- | --- |
| `AUDIT_DEVIL_PRESET` | 第二模型 preset：`deepseek`、`builder` 或 `cmd` | 設定檔，否則詢問 |
| `AUDIT_DEVIL_CMD` | `cmd` preset 使用的 CLI（stdin 到 stdout，`{material}`＝材料目錄） | 設定檔 |
| `AUDIT_DEVIL_OUT` | bundle 的上層目錄 | `./.audit-devil`；`builder` 為 `~/OpenBot/Shared/audit-devil` |
| `AUDIT_DEVIL_LANG` | 報告敘述使用的語言 | `zh-TW`（設為 `en` 則用英文） |
| `AUDIT_DEVIL_CONFIG` | 設定檔路徑 | `~/.config/audit-devil/config` |

設定檔用 `key=value` 逐行存 `preset`、`cmd`、`out`、`lang`。同一項有環境變數時，環境變數優先。
| `OPENBOT_SKILL_DIR` | send-to-openbot 技能所在目錄 | `~/.claude/skills/send-to-openbot` |
| `OPENBOT_AGENT` | OpenBot agent id，會覆寫 builder agent | Builder agent |
| `OPENBOT_TIMEOUT` | OpenBot 可花費的時間上限 | `45m` |

## 限制

- `cmd` preset 會把材料全文加行號內嵌進 stdin，沒有讀檔工具的純模型也能引用精確行號。會自己跑工具的 agent 型 CLI（例如 build 模式的 `opencode run`）可能去執行程式後沒給最終答案就結束；優先用純模型呼叫。

`check` 只查核位置，從不查核主張的真偽。使用 `--diff` 時，變更後的完整檔案會自動納入；超過 512 KB 的檔案與已刪除的檔案會被略過。不會自動修正任何東西。也不做任何機密處理：bundle 的內容會被送到第二個模型，因此在對敏感 repo 執行前請自行判斷。

## 前例／致謝

審查規則借用 kunchenguid/grok-ship 對抗式審查技能（MIT）。建議以 simonw/llm 作為第二模型的連接方式。BeehiveInnovations/pal-mcp-server 提供類似的多模型程式碼審查；本工具的重點在於引用查核。

## 測試

```bash
python3 -I tests/test_audit_devil.py
```

測試可離線執行，且從不呼叫模型。

## 授權

MIT。
