---
description: codex 先 /wheel 找現成方法再規劃 → 主 session 裁決 → deep 執行 → codex 驗收驗屍 → 裁決後打回的迴圈，gate 機械判定收斂
argument-hint: "<計畫或目標檔> [--repo <路徑>] [--max-rounds N]"
---

目標：$ARGUMENTS

## 1. 角色

- codex：**規劃**（寫工單）與**驗收**。規劃前先跑 wheel 找現成方法與資源，不自造。
- 主 session：裁決工單、裁決審查條目、自己重跑驗收。**不寫產品碼，也不寫工單**（唯一例外：第 4 節連敗 2 次的最後一搏）；工單不合格就退回 codex 重寫並附理由。
- deep：`deep-run <工單.md> <worktree>` 執行（裸名、背景跑）。
- 第二模型：預設 `--preset codex` 的 audit-devil，負責驗收、驗屍、給優化方案。
- `--repo` 未給就問 `git rev-parse --show-toplevel`；`--max-rounds` 預設 6。

## 2. 每輪步驟

1. codex 規劃並寫工單 `.audit-devil/<輪次>.md`（四段：任務／驗收〔每行一條指令、exit 0 才算過〕／不動／禁令；開頭一行「輪子：」＝wheel 輪子卡首行）：
   ```bash
   codex exec --dangerously-bypass-approvals-and-sandbox --disable hooks -C <repo> \
     "先照 ~/dev/wheel/skills/wheel/SKILL.md 跑 wheel（本機已裝工具、官方文件、社群、成熟套件；找不到 SKILL.md 就至少查本機已裝工具與 repo 內既有腳本／測試／CI 清單），把輪子卡寫進工單；再依目標、上輪裁決與 ledger 寫工單 <repo>/.audit-devil/<輪次>.md。只寫工單，不改產品碼。" \
     < /dev/null > /tmp/codex-plan-<輪次>.log 2>&1
   ```
   主 session 只審：輪子卡有沒有查過（不是訓練印象）、驗收能不能失敗、範圍有沒有越界。不合格→附理由叫 codex 重寫（不計輪次）。
2. `deep-lint <工單>`；不通過就改工單，不派。
   - **先裁決才派**：工單碰到鎖、去重、狀態機、故障注入或對外發送，先送規格審查（不計輪次）：
     ```bash
     audit-devil bundle --root <repo> --file <工單> --file <相關現役碼…> --preset codex \
       --note "<只審規格：重複執行、漏寫前提、測試打不打得到分支>" --id spec-<輪次>
     audit-devil send <bundle> && audit-devil check <bundle>
     ```
     逐條填 `verdict.md` 後跑 `audit-devil gate <bundle>`（不帶 `--ledger`，不進收斂統計）。exit 3＝還沒裁決完，**不准進第 3 步**；accept 條目交 codex 改寫進工單，重跑 `deep-lint` 才派。
3. 從 main 開 worktree：`git worktree add <worktree> -b loop/<n> main`。
4. `deep-run <工單.md> <worktree>`，背景跑，結束再收件。
5. 收件後主 session 到 worktree 自己重跑 `wo-verify <工單>`；不過就把失敗輸出交 codex 寫下一張修補工單，回第 1 步。
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
| 10 | 還有 accept | accept 條目交 codex 寫成下一張修補工單，回第 1 步 |
| 3 | 有條目未裁決或缺理由 | 先補 `verdict.md`，再跑 gate |
| 4 | 連續 3 輪 accept 不降 | **停止盲試**：走第 4 節「連敗 2 次」的最後一搏 |

## 4. 硬規則

- 同一條連敗 2 次 → 最後一搏：主 session 親自跑 `/wheel` 找換法，自己改寫工單，派 deep **一次**，主 session 自己重跑驗收。仍失敗 → **停**，寫摘要總結回報（目標、各輪做法與失敗原文、根因判斷、剩餘缺口、建議下一步），不再派任何執行人。
- 修法由 codex 規劃、主 session 裁決；主 session 可退回，不照單全收。
- 驗收不放寬既有斷言。
- 突變驗證：拿掉這輪的修正，對應測試必須 fail。
- `--max-rounds` 到頂就停，回報剩餘條目與最後一輪 ledger。

## 5. 收尾回報

- 一行結論（收斂／到頂／換方法）。
- 每輪 high／accept 走勢：印 `cat <repo>/.audit-devil/loop.tsv`。
- options：剩下的 defer 留哪、要不要再跑一輪。
