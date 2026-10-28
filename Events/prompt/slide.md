---
marp: true
theme: default
paginate: true
header: 'とつげき！隣のプロンプト in 富山'
footer: 'Code for Toyama City'
style: |
  section {
    --ink: #212529;
    --accent: #0b7285;
    --accent-light: #99e9f2;
    --accent-pale: #e3fafc;
    --muted: #868e96;
    font-family: "Hiragino Kaku Gothic ProN", "Noto Sans JP", sans-serif;
    font-size: 27px;
    line-height: 1.55;
    color: var(--ink);
    padding: 68px 80px;
  }
  h1 {
    color: var(--accent);
    font-size: 2.6em;
    line-height: 1.15;
    letter-spacing: -0.02em;
  }
  h2 {
    color: var(--accent);
    font-size: 1.75em;
    line-height: 1.2;
    border-bottom: 4px solid var(--accent-light);
    padding-bottom: 0.22em;
    margin-bottom: 0.7em;
  }
  h3 { color: var(--accent); }
  strong { color: var(--accent); font-weight: 800; }
  ul, ol { padding-left: 1.3em; }
  li { margin: 0.35em 0; }
  li::marker { color: var(--accent); font-weight: 800; }
  blockquote {
    margin: 0.9em 0 0;
    padding: 0.6em 0.9em;
    border-left: 6px solid var(--accent);
    background: var(--accent-pale);
    color: #0b3d47;
    font-size: 1.05em;
  }
  .kicker {
    display: block;
    font-size: 0.45em;
    letter-spacing: 0.2em;
    font-weight: 800;
    color: var(--accent);
    opacity: 0.65;
    margin-bottom: 0.3em;
  }
  section.lead {
    justify-content: center;
    text-align: center;
  }
  section.lead h1 { font-size: 2.6em; }
  section.lead h2 {
    border: none;
    font-size: 1.2em;
    font-weight: 400;
    color: #495057;
    margin-top: 0.4em;
  }
  section.lead p { color: var(--muted); }
  section.statement {
    justify-content: center;
    text-align: center;
  }
  section.statement h2 {
    border: none;
    font-size: 2.7em;
  }
  section.statement p { font-size: 1.15em; }
  section.invert {
    --header-footer-color: rgba(255, 255, 255, 0.66);
    --paginate-color: rgba(255, 255, 255, 0.66);
    background: #0b3d47;
    color: #f1f3f5;
  }
  section.invert h1, section.invert h2, section.invert strong { color: var(--accent-light); }
  section.invert blockquote {
    background: rgba(255, 255, 255, 0.08);
    color: #f1f3f5;
    border-color: var(--accent-light);
  }
  section.invert .kicker { color: var(--accent-light); opacity: 1; }
  .big {
    display: inline-block;
    font-size: 2.4em;
    font-weight: 800;
    color: var(--accent);
    line-height: 1.1;
  }
  section.invert .big { color: var(--accent-light); }
  .note { margin-top: 1.2em; font-size: 0.9em; color: var(--muted); }
---

<!-- _class: lead -->

# とつげき！隣のプロンプト in 富山
## 〜あなたのChatGPT、ちょっと見せてもらっていいですか？〜

Code for Toyama City × LLM観察ワークショップ

---

## <span class="kicker">GOAL</span>今日のゴール

1. 隣の人のAI履歴を**覗かせてもらう**
2. 「へえ、そんな使い方！」を**1つ見つける**
3. **明日マネしたい**プロンプトを1つ持ち帰る

> 上手いプロンプト自慢は禁止！ **生活感あるやつがMVP**です。

---

## <span class="kicker">FLOW</span>今日の流れ（60分）

1. **お約束の確認**（5分）
2. **見せてもらう履歴を選ぶ**（5分）
3. **隣のAI履歴を覗いて「へえ、そんな使い方！」探し**（15分）
4. **代表発表「隣のMVPプロンプト」**（15分）
5. **明日マネしたいことを宣言＆投票・振り返り**（10分）

---

## <span class="kicker">RULE</span>お約束は、4つだけ。

- 📵 画面の**撮影・録画・SNS投稿は禁止**
- 🙅 見せたくないものは**出さなくてOK**
- 👀 見るのは**相手が選んだ範囲だけ**。全スクロール禁止
- 💻 プロジェクターへの**直映しなし**。グループ内だけで見る

---

## <span class="kicker">NG</span>見せちゃダメなもの

- 氏名・住所・電話・メール・顔写真・子どもの情報
- 顧客名・社外秘・庁内検討中の文書
- 位置情報・カレンダー連携の中身
- 本人が恥ずかしいと思う相談・下ネタ

> 迷ったら、**出さない。** 持ち込み1本 or その場実演に切替！

---

## <span class="kicker">HOW TO 01</span>履歴の見方：ChatGPT

- **左サイドバー**のスレッド一覧が履歴です
- キーワード検索もできます
- **一時チャットは保存されない**ので掘れません
- 「メモリ」と「履歴」は別物。今日見るのは**スレッド一覧だけ**

選ぶときは3件だけ候補にして、見せるものを決めよう。

---

## <span class="kicker">HOW TO 02</span>履歴の見方：Gemini

- `gemini.google.com` 左の「チャット」が履歴です
- Google「アクティビティ」が**OFF／自動削除**だと古いのは消えています
- **My Activityまでは開かないで！** 検索履歴まで見えちゃいます

→ **左ペインだけ**見せるのが安全です。

---

## <span class="kicker">HOW TO 03</span>履歴の見方：Copilot

- `copilot.microsoft.com` / Edgeサイドバー / Windowsアプリで**出方が違います**
- **アカウント設定で保存OFF**にもできます（掘れないのが正常）
- 商用版は**保護設定で残らない**こともあります

→ **WebかEdgeの履歴パネルだけ**見せてもらおう。

---

<!-- _class: invert -->

## <span class="kicker">SELECT</span>セレクトタイム

<span class="big">5分！</span>

**見せていい3件を候補に → 見せるものを決めて開いて待機**

- 履歴OFFの人：事前メモ・コピペ持ち込みでOK
- 見せられるものがない人：この後「その場で1問実演」チームへ
- タイマースタート！

---

## <span class="kicker">WORK</span>グループで突撃プロンプト

1. 3〜4人グループになる
2. 1人3分で「この人のAIとの付き合い方」を紹介
   - 例：「レシピ全部AIに聞いてる」「富山弁に翻訳させてるw」
3. 順番に交代する
4. グループのMVPを1つ決める

**ツッコミ大歓迎。でも否定はなしで！**

---

## <span class="kicker">SHARE</span>代表発表：隣のMVPプロンプト

- 3〜4グループだけ前に出て1分紹介
- フォーマット：
  > 隣の○○さんは、AIに「××」と聞いていました。
  > 面白ポイントは「△△」です！

- 本人の補足一言もOK
- プロジェクターに映す場合はコピペのテキストのみ。ログイン画面は映さない。

---

<!-- _class: invert -->

## <span class="kicker">EXPERIMENT</span>その場で再現実験！

選ばれたMVPプロンプトを、別のAIに入れたらどうなる？

- ChatGPTのやつ → Gemini / Copilotに入れてみる
- 同じ質問でも答えが違う＝AIのクセが見える！

みんなで違いを観察しよう。

---

## <span class="kicker">WRAP UP</span>投票＆振り返り

**今日のMVPプロンプトはどれ？** 拍手or挙手で投票！

振り返りトーク：
- 履歴ON派？OFF派？なぜ？
- 記録されないAIとの付き合い方って？
- 富山の暮らしでAIが使えそうな場面は？

---

<!-- _class: invert -->

# おつかれさまでした！

- 今日の気づきを一言ずつどうぞ
- 写真撮影OKなのはこのスライドと集合写真だけです
- 次回もやる？ネタ持ち込み大歓迎！

`#とつげき隣のプロンプト` で感想ポストしてね（個別のプロンプト内容は書かないでね）
