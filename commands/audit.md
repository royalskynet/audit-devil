---
description: 叫第二模型當魔鬼代言人做審計＋驗屍，報告回主 session 機械核實後裁決並落地優化
argument-hint: "[diff 範圍｜檔案…] [--incident <錯誤原文檔>] [--model <preset>]"
---

目標：$ARGUMENTS

**審計＋驗屍**任務。你是裁決者，第二模型是魔鬼代言人；它的發現沒被你核實過就不算事實。
沒給範圍就審 `HEAD~1..HEAD`，不先問。CLI＝`audit-devil`（在 PATH 上；沒有就用安裝目錄的 `bin/audit-devil` 絕對路徑）。

## 1. 打包（主 session 做）

```bash
audit-devil bundle --root <repo 絕對路徑> \
  --diff <範圍> [--file <檔>]… [--incident <錯誤原文檔>] \
  --note "<它看不到的上下文：這次要解什麼、已排除什麼、哪裡最可疑>"
```

`--note` 是這一步唯一的槓桿：第二模型看不到本 session 的對話。把目標、已知取捨、你自己的懷疑寫進去。
輸出是 bundle 目錄絕對路徑，記住它。第二模型依序取 `--preset` → `AUDIT_DEVIL_PRESET`／`AUDIT_DEVIL_CMD` → 設定檔
（`audit-devil config` 看目前值）。都沒設會 exit 2：照錯誤訊息用 `audit-devil config --preset <名稱>` 設好再重跑，不要自己猜模型。
臨時換：`--preset builder`（OpenBot，換 agent 用 `OPENBOT_AGENT=<id>`）或 `--preset cmd` 搭 `AUDIT_DEVIL_CMD='<吃 stdin 吐 stdout 的 CLI>'`。

## 2. 送出

```bash
audit-devil send <bundle>
```

`cmd` 類 preset（含 `deepseek`）是同步的：`send` 結束報告就到，直接進第 3 步。
OpenBot 的隊員回覆落在**之後的輪次**，這一輪只回「已派出」，不輪詢、不等。
`collect` 取回報告（還沒答會 exit 1，就先做別的事，稍後再取）：

```bash
audit-devil collect <bundle>
```

## 3. 機械核實（不可跳）

```bash
audit-devil check <bundle>
```

exit 1 ＝有發現的 `evidence:` 指不到真實位置，或報告沒有 `## Verdict` 也沒有發現（無視格式）。有 Verdict 零發現＝乾淨答案，exit 0，仍要讀 Verdict 那行。
`checked.md` 每條附實際程式碼行。核實分兩層，不要混：

- **位置**：`check` 已機械判定。`UNVERIFIED` 的一律駁回並在回報裡點名「第二模型捏造了 N 條」，不替它找補。
- **主張**：`OK` 只證明那幾行存在，不證明 claim 為真。逐條自己讀程式碼判斷真假，必要時跑一條會失敗的指令驗。

## 4. 裁決

填 `<bundle>/verdict.md`，每條 `decision:` 只能是：

- `accept` — 你核實為真，這輪就修。
- `reject` — 你核實為假或位置不存在，寫一句為什麼。
- `defer` — 真的但超出本次範圍，寫清楚留在哪（issue／fixindex／state）。

第二模型的建議修法不照抄：採納的是**問題**，修法由你定（根治原因、不順手重構）。

## 5. 落地＋驗收

accept 的逐條修完，照 `/fix` 的標準：改原因不改表徵，同一改動附一個會失敗的回歸檢查。
驗收貼原始輸出：回歸檢查、`check` 重跑（exit 0）。

## 收尾

- 回報一行結論＋「accept N／reject N／defer N」＋ bundle 絕對路徑＋options。細節留在 bundle 裡。
- 第二模型捏造、或它抓到你這輪漏掉的真缺陷，值得記就跑 `/fi`。
