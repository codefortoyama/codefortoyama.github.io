# Code for Toyama City ウェブサイト

活動の紹介と、初めてのイベント参加を目的にしたGitHub Pages向けサイトです。
表示はHTML / CSS / JavaScriptのみで動作します。イベントとプロジェクトの更新にはPython 3の標準ライブラリを使い、追加パッケージは不要です。

## ローカルで確認する

このフォルダで次のコマンドを実行して、<http://localhost:8000>を開いてください。

```sh
python3 -m http.server 8000
```

`index.html`をブラウザで直接開くこともできます。

## 更新する場所

- `index.html`：団体紹介、取り込んだイベント、活動紹介、FAQ、SNSリンク
- `projects.html`：Code for Toyamaの公開GitHubリポジトリへのリンク集
- `privacy.html`：プライバシーポリシー（アクセス解析・Cookie・外部リンクの情報の取扱い）
- `css/site.css`：新サイトのデザインとスマートフォン対応
- `js/site.js`：モバイルメニューと終了したイベントの表示切り替え
- `assets/img/`：既存の写真・アイコン
- `scripts/update_events.py`：connpass公式Atomフィードの取り込みとHTML生成
- `data/events.json`：最後に正常取得したconnpassイベントと取得日時
- `scripts/update_projects.py`：GitHub APIの取り込み、最新3件と全件のリンク集の生成
- `data/projects.json`：最後に正常取得した公開リポジトリと最新コミット日時
- `data/project_descriptions.json`：README・ソース・ファイル構成を確認して作成した説明文と参照元
- `.github/workflows/pages.yml`：イベント・プロジェクト更新とGitHub Pages公開

旧サイトの`css/style.css`と`js/scripts.js`は、いずれも新サイトでは読み込んでいません。特に`js/scripts.js`は第三者の中継サービスを経由して外部フィードを取得し、その内容をHTML文字列として組み立てる実装だったため、公開面からの除去を目的に削除しました。新サイトでは`css/site.css`と`js/site.js`のみを使用します。

### connpassのイベントを更新する

公式フィード <https://codefortoyama.connpass.com/ja.atom> から取得します。
検索結果を使わず、開催予定を開催日の近い順に最大3件、最近の開催済みイベントを最大3件表示します。
公開時に静的HTMLを生成するため、ブラウザからの外部APIアクセスやCORS対応は不要です。
参加費や募集状況は推測せず、connpassの詳細ページに案内します。

各イベントページの画像情報を取得し、開催予定カードにはアイキャッチ、最近開催したイベントには小さなサムネイルを表示します。画像取得に失敗した場合は前回の画像情報を保持し、画像だけの取得失敗でイベント更新を止めません。表示時に画像を読み込めない場合は`assets/event-placeholder.svg`に切り替えます。

ローカルのHTMLと取得データを更新する場合：

```sh
python3 scripts/update_events.py
```

ネットワークを使わず、保存済みのデータで日付による分類を更新する場合：

```sh
python3 scripts/update_events.py --offline
```

取得日時もイベント欄に表示します。ローカルで取得に失敗した場合は前回のデータを保持し、警告を表示します。
公開用ワークフローは`--require-fresh`を指定し、取得に失敗した場合に古いデータを再公開しません。
GitHub Actionsを有効にすると、デフォルトブランチへのpush、手動実行、3時間ごとの定期実行で取得・公開します。
定期実行には遅延が発生する場合があり、即時反映ではありません。すぐ反映したい場合はActionsから手動実行してください。
GitHubの仕様により、公開リポジトリで60日間活動がないと定期実行が無効になる場合があります。

`CONNPASS_EVENTS_START`から`CONNPASS_EVENTS_END`までのHTMLは自動生成なので、直接編集しないでください。

### 関連イベントを更新する

connpass以外のイベントは`index.html`の「関連イベント」内を手動更新します。
掲載中の10月29日のイベントはCode for Toyama Cityが講師を務め、申し込みは主催者の案内につないでいます。
日付、本文、申し込み先、`data-event-end`（日本時間の終了日時）を一緒に変更してください。
JavaScriptが有効な場合、終了後は「開催終了」と表示します。終了後は手動で記事を整理してください。

### プロジェクトを更新する

GitHubの`codefortoyama`団体にある公開リポジトリを全件取得します（ページ送り対応）。
各リポジトリの標準ブランチにある最新コミットのcommitter日時で並べ、トップページには最新3件、
`projects.html`には全件のリンクを表示します。Issueなどによる更新日時やpush日時では順位を決めません。
GitHub Pagesが有効なリポジトリはPages APIの`html_url`を取得し、公開サイトを主なリンク先にします。
設定APIが公開情報を返さない場合は、GitHub Pagesの公開URLにアクセスし、正常に開けることを確認して採用します。
独自ドメインはAPIの設定または公開URLからのリダイレクトを使います。
homepage欄は、そのプロジェクトのGitHub Pages配下で実際に開けるURLだけ候補にし、フォーク元など別サイトのURLは使いません。
公開サイトがない場合や公開URLが開けない場合はGitHubへリンクします。公開サイトがある場合も、ソースコードへのGitHubリンクを別に残します。
コミットのない空のリポジトリは、トップページとリンク集の両方から除外します。
READMEが空でも、資料やソースがあるリポジトリは掲載します。
フォークやアーカイブもリンク集に含めます。
説明は`data/project_descriptions.json`の確認済み説明文を優先し、未登録のリポジトリはGitHubのdescriptionを使います。

トップページのGitHub Pagesへリンクするカードには、公開サイトの`og:image`、`twitter:image`、メイン画像（classにheroを含む、またはfetchpriorityがhighの画像）の順で、取得できる画像をアイキャッチとして表示します。画像情報はプロジェクト更新時に取得します。画像が未設定、取得できない、または表示時に読み込めない場合は`assets/project-placeholder.svg`を表示します。
作成した説明文は定期更新後も保持されます。内容を見直すときは説明と参照元、確認日を更新してください。

```sh
python3 scripts/update_projects.py
```

GitHub APIの制限やネットワーク障害で取得できない場合、ローカルでは前回の情報を保持して警告を表示します。
ネットワークを使わず生成する場合は`--offline`を指定します。
公開時は`--require-fresh`を指定し、全件の取得に失敗した場合は公開せず、すでに公開済みの内容を維持します。
GitHub Actionsでは組み込みのトークンを環境変数`GH_TOKEN`で渡します。トークンをHTMLやデータには保存しません。
ブラウザからのGitHub APIアクセスは行わず、3時間ごとの公開処理で更新します。リアルタイム反映ではありません。

`GITHUB_FEATURED_START`〜`GITHUB_FEATURED_END`と`GITHUB_REPOSITORIES_START`〜`GITHUB_REPOSITORIES_END`は自動生成です。
手動で生成HTMLを書き換えず、説明文は`data/project_descriptions.json`、リポジトリ名はGitHub側を更新してください。

公開用ファイルをローカルで確認する場合は、イベント更新の後にプロジェクト更新を実行します。

```sh
python3 scripts/update_events.py --offline --output _site
python3 scripts/update_projects.py --offline --output _site
python3 -m http.server 8000 --directory _site
```

### 更新処理を検証する

外部情報の取得は`scripts/safe_http.py`の許可リストで制限しています。
GitHub API、団体のGitHub Pages、connpass、connpassの画像配信元に、HTTPSの443番ポートで接続します。
リダイレクト先も接続前に検証し、DNSが返す全IPが公開アドレスであることを確認してから、そのIPへ直接接続します。
環境変数によるプロキシは使用せず、HTTPSの証明書とホスト名の検証は維持します。
独自ドメインのページや画像を自動取得する場合は、接続先を確認してから`PAGE_HOSTS`または`IMAGE_HOSTS`へ完全なホスト名を追加してください。
許可されていない画像は表示せず、プロジェクトには代替画像を表示します。APIから取得したHTTPSの公開サイトのリンクは保持します。
GitHub APIとconnpassフィードの取得失敗は、従来どおり`--require-fresh`で公開を止めます。

```sh
python3 -m unittest discover -s tests
```

### GitHub Pagesでのセキュリティ設定

主要3ページには、リソースの読み込みより前にHTMLの`meta`でCSPと`strict-origin-when-cross-origin`の参照元ポリシーを設定しています。
Google Analyticsの初期化は`js/analytics.js`へ分離し、CSPでインラインJavaScriptと`eval`を許可していません。
スクリプトは自サイトとGoogleタグ、画像は自サイト・connpassの画像配信元・解析用の配信元に限定しています。
Google Analyticsの通信先は、広告機能を使わない構成の公式資料を基にしています。広告機能を追加する場合は通信先とCSPを見直してください。
イベントやプロジェクトの更新で新しい画像配信元を使う場合は、更新処理の許可リストと3ページのCSPの両方を確認してください。
公開サイトのURLがHTTPの場合は、自動生成するリンクをGitHubへ切り替えます。

GitHub PagesでのHTML変更では、HSTS、`X-Content-Type-Options`、埋め込みを制限する`frame-ancestors`のHTTPヘッダーを設定できません。
`frame-ancestors`や`X-Frame-Options`を`meta`に記載しても対策にならないため、追加していません。
Googleタグは配信内容が更新されるため、固定ハッシュによるSRIは設定せず、CSPで読み込み元を制限しています。
他の団体リポジトリのPagesも同じオリジンを共有するので、CSPの`'self'`はこのリポジトリだけを指すものではありません。
配信基盤や独自ドメインを変更する場合は、これらの制約を含めて再評価してください。

ブラウザでの検証には、Playwrightとインストール済みのChromeを使って`node scripts/check-browser-security.mjs`を実行できます。
Playwrightを別のフォルダへインストールした場合は、環境変数`PLAYWRIGHT_MODULE_PATH`でモジュールの絶対パスを指定します。
先に`--offline --output _site`で両方の更新処理を実行してください。
検証はローカルの公開用ファイルをブラウザ内で本番URLに割り当て、外部のGoogleタグと画像を読み込みます。
メニュー・画像・CSPの拒否動作・参照元情報を確認し、解析の送信リクエストは遮断して本番の計測に混ぜません。

### 活動紹介を更新する

`id="activities"`内の`activity-example`を編集します。
日付、説明、参照先を更新し、開催案内と活動報告を区別して記載してください。
写真は`assets/img/`に追加し、`alt`に写真の内容を記載してください。
現在の集合写真は既存リポジトリの素材を使用し、特定の開催日の写真とは表記していません。

## GitHub Pagesで公開する

GitHubに変更を反映後、リポジトリのSettings → Pages → Sourceで`GitHub Actions`を選択します。
Actionsの`Publish site with latest events and projects`を手動実行すると、最新情報を取得して公開できます。
公開用ディレクトリ`_site/`だけをアップロードし、更新スクリプトやGit管理ファイルは配信しません。
ブランチから直接配信する方式では定期更新は反映されないため、GitHub Actions方式に切り替えてください。
アカウント名とリポジトリ名が現在の想定どおりなら、公開先は
<https://codefortoyama.github.io/>です。
公開URLを変える場合は`index.html`のcanonical、OGP URL、OGP画像URLと`sitemap.xml`も変更してください。
公開時には`sitemap.xml`の`lastmod`を実際の更新日に変更してください。

## 内容の参照元

- 現行サイト：<https://code4toyama.studio.site/>
- イベント募集：<https://codefortoyama.connpass.com/>
- connpass公式フィード：<https://codefortoyama.connpass.com/ja.atom>
- AI開発をやってみよう：<https://codefortoyama.connpass.com/event/409117/>
- 2026年10月29日イベント：<https://sketch.lab.city.toyama.toyama.jp/event/528>
- ハッピーデータとやま！開催案内：<https://sketch.lab.city.toyama.toyama.jp/event/510>
- Facebook：<https://www.facebook.com/codefortoyama/>
- X：<https://x.com/codefortoyama>
- プロジェクト：<https://github.com/codefortoyama>

イベント情報は2026年10月11日に公開情報で確認した内容を掲載しています。
