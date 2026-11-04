---
description: 主 session 規劃裁決 → deep 執行 → codex 驗收驗屍 → 裁決後打回的迴圈，gate 機械判定收斂
argument-hint: "<計畫或目標檔> [--repo <路徑>] [--max-rounds N]"
---

目標：$ARGUMENTS

## 1. 角色

- 主 session：只規劃、裁決、驗收。**不寫產品碼。**
- deep：`deep-run <工單.md> <worktree>` 執行（裸名、背景跑）。
- 第二模型：預設 `--preset codex` 的 audit-devil，負責驗收、驗屍、給優化方案。
- `--repo` 未給就問 `git rev-parse --show-toplevel`；`--max-rounds` 預設 6。

## 2. 每輪步驟

1. 寫工單 `.audit-devil/<輪次>.md`（四段：任務／驗收〔每行一條指令、exit 0 才算過〕／不動／禁令）。
2. `deep-lint <工單>`；不通過就改工單，不派。
   - **先裁決才派**：工單碰到鎖、去重、狀態機、故障注入或對外發送，先送規格審查（不計輪次）：
     ```bash
     audit-devil bundle --root <repo> --file <工單> --file <相關現役碼…> --preset codex \
       --note "<只審規格：重複執行、漏寫前提、測試打不打得到分支>" --id spec-<輪次>
     audit-devil send <bundle> && audit-devil check <bundle>
     ```
     逐條填 `verdict.md` 後跑 `audit-devil gate <bundle>`（不帶 `--ledger`，不進收斂統計）。exit 3＝還沒裁決完，**不准進第 3 步**；accept 條目由主 session 改寫進工單，重跑 `deep-lint` 才派。
3. 從 main 開 worktree：`git worktree add <worktree> -b loop/<n> main`。
4. `deep-run <工單.md> <worktree>`，背景跑，結束再收件。
5. 收件後主 session 到 worktree 自己重跑 `wo-verify <工單>`；不過就寫下一張修補工單回第 2 步。
6. 過：`git merge --ff-only` 進主 repo，再在主 repo 重跑 `wo-verify <工單>`。
7. 送審：
   ```bash
   audit-devil bundle --root <repo> --diff <本輪範圍> --preset codex \
     --note "<目標、上輪裁決摘要、要它驗屍前輪必修＋給優化方案>"
   audit-devil send <bundle>
   audit-devil check <bundle>     # exit 1：捏造的條目一律 reject
   ```
8. 逐條填 `<bundle>/verdict.md`（`decision:` = accept／reject／defer；reject／defer 必寫 `reason:`）。
9. `audit-devil gate <bundle> --ledger <repo>/.audit-devil/loop.tsv`，看 exit code 走第 3 節。

## 3. 依 gate exit code

| exit | 意義 | 動作 |
| --- | --- | --- |
| 0 | 收斂，無 accept | 跑最終驗收；commit／push 照使用者指示 |
| 10 | 還有 accept | 把 accept 條目寫成下一張修補工單，回第 2 步 |
| 3 | 有條目未裁決或缺理由 | 先補 `verdict.md`，再跑 gate |
| 4 | 連續 3 輪 accept 不降 | **停止盲試**：換方法（改派 Opus 子代理或重寫計畫）並回報 |

## 4. 硬規則

- 同一條連敗 2 次 → 改派 Opus 子代理，不再原路重試。
- 修法由主 session 定，不照抄第二模型。
- 驗收不放寬既有斷言。
- 突變驗證：拿掉這輪的修正，對應測試必須 fail。
- `--max-rounds` 到頂就停，回報剩餘條目與最後一輪 ledger。

## 5. 收尾回報

- 一行結論（收斂／到頂／換方法）。
- 每輪 high／accept 走勢：印 `cat <repo>/.audit-devil/loop.tsv`。
- options：剩下的 defer 留哪、要不要再跑一輪。
