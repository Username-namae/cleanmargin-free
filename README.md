# CleanMargin Free v1

清掃会社向けに、案件の作業量と自社原価から「利益が残る見積価格」を逆算する無料MVPです。

## 無料版の役割
- ログインなし
- サーバー保存なし
- 1案件ごとの原価・価格計算
- 値引きシミュレーション
- 公開価格の参考表示

## 有料版に残す機能
- 自社設定の永続保存
- 顧客・案件履歴
- PDF見積書
- 実績作業時間
- 実績原価
- 自社平均による標準時間補正
- CSV出力・分析

## ローカル起動
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run streamlit_app.py
```

## ファイル構成
- `streamlit_app.py` : 無料Webアプリ
- `calculator.py` : 計算ロジック
- `data/service_master.csv` : サービス標準時間・材料費・公開価格参考
- `data/condition_master.json` : 物件状態・汚れ補正
- `data/source_research.csv` : 公開情報の根拠
- `data/sample_cases.csv` : テスト用ケース
- `tests/test_calculator.py` : 計算ロジックのテスト
- `CleanMargin_v1.xlsx` : Excel版計算機
- `DEPLOY_STREAMLIT.md` : 無料公開手順
- `PRODUCT_ROADMAP.md` : 有料版までの開発順
- `MARKETING_FLOW.md` : 集客・販売導線

## 注意
標準作業時間・補正係数は初期仮説です。実案件データが貯まった段階で、自社実績を優先する設計へ移行します。
