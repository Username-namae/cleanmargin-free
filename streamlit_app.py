from pathlib import Path
import csv
import json

import streamlit as st

from calculator import (
    CompanySettings,
    JobConditions,
    calculate_quote,
    simulate_offer,
)


# =========================================================
# 基本設定
# =========================================================

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

st.set_page_config(
    page_title="CleanMargin｜清掃利益見積",
    page_icon="🧹",
    layout="wide",
)


# =========================================================
# データ読み込み
# =========================================================

@st.cache_data
def load_services():
    with (
        DATA / "service_master.csv"
    ).open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        row["standard_person_hours"] = float(
            row["standard_person_hours"]
        )

        row["material_cost_yen"] = float(
            row["material_cost_yen"]
        )

        row["public_price_reference_yen"] = float(
            row["public_price_reference_yen"]
        )

    return rows


@st.cache_data
def load_conditions():
    with (
        DATA / "condition_master.json"
    ).open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


services = load_services()
condition_master = load_conditions()


# =========================================================
# タイトル
# =========================================================

st.title("CleanMargin")

st.caption(
    "清掃会社向け｜"
    "原価から「利益が残る見積価格」を逆算する無料計算機"
)


with st.expander(
    "この計算機について",
    expanded=False,
):

    st.write(
        "CleanMarginは、市場相場を断定するツールではありません。"
        "自社の人件費・移動費・材料費・固定費・目標利益率から、"
        "利益を残すための見積価格を計算します。"
    )

    st.warning(
        "標準作業時間と補正係数は、"
        "公開されている清掃料金・作業時間を参考にした"
        "初期モデルです。"
        "実際の案件では現場条件に応じて調整してください。"
    )


# =========================================================
# 1. 自社原価設定
# =========================================================

left, right = st.columns([1, 1])


with left:

    st.subheader("1. 自社の原価設定")

    labor_rate = st.number_input(
        "実質人件費（円 / 人時）",
        min_value=0,
        value=2000,
        step=100,
        help=(
            "給与だけでなく、"
            "自分自身の労働価値や会社負担も含めた"
            "1人1時間あたりの原価を入力してください。"
        ),
    )

    vehicle_rate = st.number_input(
        "車両コスト（円 / km）",
        min_value=0.0,
        value=35.0,
        step=5.0,
        help=(
            "ガソリン代だけでなく、"
            "整備費や車両費を含めて設定できます。"
        ),
    )

    monthly_fixed = st.number_input(
        "月間固定費（円）",
        min_value=0,
        value=60000,
        step=5000,
        help=(
            "通信費、保険、システム費、"
            "事務所費などの固定費です。"
        ),
    )

    monthly_jobs = st.number_input(
        "月間想定案件数",
        min_value=1,
        value=30,
        step=1,
        help=(
            "固定費を1案件あたりへ"
            "配賦するために使用します。"
        ),
    )

    minimum_margin_pct = st.slider(
        "最低利益率",
        min_value=0,
        max_value=60,
        value=15,
        step=1,
        help=(
            "これを下回る価格を"
            "値引き下限として警告します。"
        ),
    )

    target_margin_pct = st.slider(
        "目標利益率",
        min_value=0,
        max_value=70,
        value=30,
        step=1,
        help=(
            "通常の見積価格を"
            "逆算するときに使用します。"
        ),
    )

    minimum_charge = st.number_input(
        "最低受注額（円）",
        min_value=0,
        value=12000,
        step=1000,
        help=(
            "計算結果が小さくても、"
            "この金額より安く受注しない設定です。"
        ),
    )


# =========================================================
# 2. 案件条件
# =========================================================

with right:

    st.subheader("2. 案件条件")

    occupancy = st.selectbox(
        "物件状態",
        list(
            condition_master[
                "occupancy"
            ].keys()
        ),
        index=1,
    )

    dirt = st.selectbox(
        "汚れレベル",
        list(
            condition_master[
                "dirt"
            ].keys()
        ),
        index=1,
    )

    pet = st.checkbox(
        "ペットあり"
    )

    crew_size = st.number_input(
        "作業人数",
        min_value=1,
        max_value=10,
        value=1,
        step=1,
    )

    one_way_minutes = st.number_input(
        "片道移動時間（分）",
        min_value=0,
        value=30,
        step=5,
    )

    one_way_km = st.number_input(
        "片道距離（km）",
        min_value=0.0,
        value=10.0,
        step=1.0,
    )

    parking_cost = st.number_input(
        "駐車費（円）",
        min_value=0,
        value=0,
        step=100,
    )

    subcontract_cost = st.number_input(
        "外注費（円）",
        min_value=0,
        value=0,
        step=1000,
    )

    other_cost = st.number_input(
        "その他変動費（円）",
        min_value=0,
        value=0,
        step=100,
    )


# =========================================================
# 3. 清掃内容
# =========================================================

st.subheader("3. 清掃内容")

st.caption(
    "数量が0のサービスは計算対象外です。"
)


selected = []

cols = st.columns(2)


for index, service in enumerate(services):

    with cols[index % 2]:

        qty = st.number_input(
            (
                f'{service["service_name"]}'
                f'（標準 '
                f'{service["standard_person_hours"]:.2f}'
                f' 人時）'
            ),
            min_value=0,
            max_value=20,
            value=(
                1
                if service["service_name"]
                in [
                    "浴室",
                    "キッチン",
                    "トイレ",
                ]
                else 0
            ),
            step=1,
            key=service["service_id"],
        )

        if qty:

            selected.append(
                {
                    **service,
                    "quantity": qty,
                }
            )


# =========================================================
# マスタにない作業
# =========================================================

with st.expander(
    "マスタにない作業を追加"
):

    custom_hours = st.number_input(
        "追加人時",
        min_value=0.0,
        value=0.0,
        step=0.25,
    )

    custom_material = st.number_input(
        "追加材料費（円）",
        min_value=0,
        value=0,
        step=100,
    )


# =========================================================
# 計算用設定
# =========================================================

settings = CompanySettings(

    labor_cost_per_person_hour=float(
        labor_rate
    ),

    vehicle_cost_per_km=float(
        vehicle_rate
    ),

    monthly_fixed_cost=float(
        monthly_fixed
    ),

    monthly_job_count=float(
        monthly_jobs
    ),

    minimum_margin=(
        minimum_margin_pct / 100.0
    ),

    target_margin=(
        target_margin_pct / 100.0
    ),

    aggressive_markup=0.10,

    minimum_charge=float(
        minimum_charge
    ),
)


conditions = JobConditions(

    occupancy_multiplier=float(
        condition_master[
            "occupancy"
        ][occupancy]
    ),

    dirt_multiplier=float(
        condition_master[
            "dirt"
        ][dirt]
    ),

    pet_additional_person_hours=float(
        condition_master[
            "pet_additional_person_hours"
        ]
        if pet
        else 0.0
    ),

    crew_size=int(
        crew_size
    ),

    one_way_minutes=float(
        one_way_minutes
    ),

    one_way_km=float(
        one_way_km
    ),

    parking_cost=float(
        parking_cost
    ),

    subcontract_cost=float(
        subcontract_cost
    ),

    other_variable_cost=float(
        other_cost
    ),
)


# =========================================================
# 見積計算
# =========================================================

result = calculate_quote(

    selected,

    settings,

    conditions,

    custom_person_hours=float(
        custom_hours
    ),

    custom_material_cost=float(
        custom_material
    ),
)


# =========================================================
# 4. 計算結果
# =========================================================

st.divider()

st.subheader(
    "4. 計算結果"
)


m1, m2, m3, m4 = st.columns(4)


m1.metric(
    "推定総原価",
    f'¥{result["total_cost"]:,.0f}',
)


m2.metric(
    "値引き下限",
    f'¥{result["minimum_price"]:,.0f}',
)


m3.metric(
    "目標価格",
    f'¥{result["target_price"]:,.0f}',
)


m4.metric(
    "強気価格",
    f'¥{result["aggressive_price"]:,.0f}',
)


# =========================================================
# 時間・利益率
# =========================================================

c1, c2, c3 = st.columns(3)


c1.metric(
    "総人時",
    (
        f'{result["total_person_hours"]:.2f}'
        " 人時"
    ),
)


c2.metric(
    "現場作業時間",
    (
        f'{result["onsite_clock_hours"]:.2f}'
        " 時間"
    ),
)


c3.metric(
    "目標価格での利益率",
    f'{result["target_profit_margin"]:.1%}',
)


# =========================================================
# 原価内訳
# =========================================================

with st.expander(
    "原価内訳",
    expanded=True,
):

    st.write(
        {
            "人件費":
                round(
                    result[
                        "labor_cost"
                    ]
                ),

            "材料費":
                round(
                    result[
                        "material_cost"
                    ]
                ),

            "車両費":
                round(
                    result[
                        "vehicle_cost"
                    ]
                ),

            "駐車費":
                round(
                    result[
                        "parking_cost"
                    ]
                ),

            "外注費":
                round(
                    result[
                        "subcontract_cost"
                    ]
                ),

            "その他変動費":
                round(
                    result[
                        "other_variable_cost"
                    ]
                ),

            "固定費配賦":
                round(
                    result[
                        "fixed_cost_allocation"
                    ]
                ),
        }
    )


# =========================================================
# 公開価格参考
# =========================================================

if (
    result[
        "public_price_reference"
    ]
    > 0
):

    st.info(
        (
            "選択サービスの"
            "公開価格参考単純合計："
            f'¥{result["public_price_reference"]:,.0f}'
            "。"
        )
        +
        "これは市場相場を保証するものではなく、"
        "公開されている料金の比較参考です。"
    )


# =========================================================
# 5. 値引きシミュレーター
# =========================================================

st.subheader(
    "5. 値引きシミュレーター"
)


offer = st.number_input(

    "顧客への提示価格（円）",

    min_value=0,

    value=int(
        result[
            "target_price"
        ]
    ),

    step=100,
)


sim = simulate_offer(

    offer,

    result[
        "total_cost"
    ],

    settings.minimum_margin,
)


s1, s2 = st.columns(2)


s1.metric(
    "提示価格での利益",
    f'¥{sim["profit"]:,.0f}',
)


s2.metric(
    "提示価格での利益率",
    f'{sim["margin"]:.1%}',
)


if sim["acceptable"]:

    st.success(
        "設定した最低利益率を満たしています。"
    )

else:

    st.error(
        "設定した最低利益率を下回ります。"
        "値引きまたは原価を再確認してください。"
    )


# =========================================================
# Pro版案内
# =========================================================

st.divider()

st.markdown(
    "## CleanMargin Pro"
)

st.caption(
    "現在開発を検討しています"
)


st.write(
    "無料版では1案件ごとの利益計算ができます。"
    "Pro版では、毎回同じ設定を入力する必要がないように、"
    "清掃会社ごとの設定保存や案件管理を追加する予定です。"
)


pro1, pro2 = st.columns(2)


with pro1:

    st.markdown(
        """
        **Pro版で追加予定**

        - 自社の人件費・利益率を保存
        - 自社の材料費を保存
        - 案件履歴を保存
        - 顧客管理
        - PDF見積書
        """
    )


with pro2:

    st.markdown(
        """
        **将来追加予定**

        - 見積作業時間と実績時間の比較
        - 案件ごとの実利益
        - サービス別平均作業時間
        - 自社実績による標準時間補正
        - 利益分析
        """
    )


st.info(
    "現時点で料金は発生しません。"
    "Pro版についてのご意見を集めています。"
)


# =========================================================
# Googleフォーム
# =========================================================

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSe2vPhTK4t5R6Ui1uQDzSz0sf1BpHmFjDhweEuIpW6hvFpyyg/viewform?usp=publish-editor"


if (
    FORM_URL.startswith(
        "https://"
    )
):

    st.link_button(

        "CleanMargin Proの先行案内・機能希望を送る",

        FORM_URL,

        type="primary",

        use_container_width=True,
    )

else:

    st.warning(
        "現在Pro版の先行登録フォームを準備中です。"
    )


# =========================================================
# フッター
# =========================================================

st.divider()


st.caption(
    "CleanMargin Free"
)


st.caption(
    "無料版では入力した案件情報や"
    "自社設定をサーバーへ保存しません。"
)


st.caption(
    "表示される価格は、入力された原価条件と"
    "初期標準作業時間から算出した参考値です。"
    "実際の見積価格・市場価格を保証するものではありません。"
)
