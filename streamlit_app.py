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
    page_title="清掃業の原価計算・見積価格計算｜CleanMargin",
    page_icon="🧹",
    layout="wide",
)


# =========================================================
# デザインCSS
# =========================================================

st.markdown(
    """
    <style>

    .block-container {
        max-width: 1120px;
        padding-top: 1.5rem;
        padding-bottom: 5rem;
    }

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    header {
        background: transparent !important;
    }

    .hero {
        padding: 56px 48px;
        margin-bottom: 28px;
        border-radius: 26px;
        background:
            linear-gradient(
                135deg,
                #0F172A 0%,
                #1D4ED8 100%
            );
        color: white;
        box-shadow:
            0 18px 55px rgba(15, 23, 42, 0.14);
    }

    .hero-badge {
        display: inline-block;
        padding: 7px 13px;
        margin-bottom: 18px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.12);
        color: #DBEAFE;
        font-size: 13px;
        font-weight: 700;
    }

    .hero h1 {
        color: white !important;
        font-size: 46px;
        line-height: 1.25;
        margin: 0 0 16px 0;
        letter-spacing: -0.03em;
    }

    .hero p {
        color: #DBEAFE;
        font-size: 18px;
        line-height: 1.8;
        max-width: 760px;
        margin: 0;
    }

    .intro-card {
        padding: 20px 24px;
        margin: 8px 0 28px 0;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        background: #FFFFFF;
    }

    .step-label {
        color: #2563EB;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 0.08em;
        margin-top: 18px;
        margin-bottom: 4px;
    }

    .price-card {
        text-align: center;
        background: #FFFFFF;
        border: 1px solid #DBEAFE;
        border-radius: 26px;
        padding: 40px 20px;
        margin: 16px 0 24px 0;
        box-shadow:
            0 16px 45px rgba(37, 99, 235, 0.10);
    }

    .price-label {
        color: #64748B;
        font-size: 15px;
        font-weight: 700;
        margin-bottom: 4px;
    }

    .price {
        color: #0F172A;
        font-size: 60px;
        font-weight: 800;
        line-height: 1.15;
        letter-spacing: -0.04em;
        margin: 8px 0;
    }

    .price-sub {
        color: #64748B;
        font-size: 14px;
    }

    .pro-card {
        padding: 34px;
        margin-top: 34px;
        border-radius: 22px;
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
    }

    .pro-card h2 {
        margin-top: 0;
        color: #0F172A;
    }

    .pro-card p {
        color: #475569;
        line-height: 1.8;
    }

    .footer-note {
        text-align: center;
        color: #94A3B8;
        font-size: 13px;
        margin-top: 30px;
        line-height: 1.8;
    }

    @media (max-width: 700px) {

        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .hero {
            padding: 34px 24px;
            border-radius: 20px;
        }

        .hero h1 {
            font-size: 34px;
        }

        .hero p {
            font-size: 16px;
        }

        .price {
            font-size: 46px;
        }

        .pro-card {
            padding: 24px;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# データ読み込み
# =========================================================

@st.cache_data
def load_services():
    with (DATA / "service_master.csv").open(
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
    with (DATA / "condition_master.json").open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


services = load_services()
condition_master = load_conditions()


# =========================================================
# HERO
# =========================================================

st.html(
    """
<div class="hero">
<div class="hero-badge">清掃事業者向け・無料</div>

<h1>
清掃業の見積価格を<br>
「感覚」から「数字」へ。
</h1>

<p>
人件費・移動費・材料費・固定費から、
利益を確保するための見積価格を自動計算。<br>
値引きしても赤字にならない価格も確認できます。
</p>
</div>
"""
)


st.header(
    "清掃業・ハウスクリーニングの原価計算と見積価格計算"
)


st.html(
    """
<div class="intro-card">
CleanMarginは、清掃業者向けの無料見積計算ツールです。<br>
人件費、材料費、移動費、固定費、目標利益率から、
清掃案件の原価と見積価格を計算できます。
</div>
"""
)


with st.expander(
    "この計算機について",
    expanded=False,
):
    st.write(
        "CleanMarginは市場相場を断定するツールではありません。"
        "自社の原価条件と利益率から、"
        "利益を残すための見積価格を計算します。"
    )

    st.warning(
        "標準作業時間と補正係数は、"
        "公開情報を参考にした初期モデルです。"
        "実案件では現場条件に応じて調整してください。"
    )


# =========================================================
# STEP 1 / STEP 2
# =========================================================

left, right = st.columns([1, 1])


with left:

    st.html(
        '<div class="step-label">STEP 1</div>'
    )

    st.subheader(
        "自社の原価設定"
    )

    labor_rate = st.number_input(
        "実質人件費（円 / 人時）",
        min_value=0,
        value=2000,
        step=100,
        help=(
            "給与だけでなく、"
            "自分自身の労働価値や会社負担も含めた"
            "1人1時間あたりの原価です。"
        ),
    )

    vehicle_rate = st.number_input(
        "車両コスト（円 / km）",
        min_value=0.0,
        value=35.0,
        step=5.0,
    )

    monthly_fixed = st.number_input(
        "月間固定費（円）",
        min_value=0,
        value=60000,
        step=5000,
    )

    monthly_jobs = st.number_input(
        "月間想定案件数",
        min_value=1,
        value=30,
        step=1,
    )

    minimum_margin_pct = st.slider(
        "最低利益率",
        0,
        60,
        15,
        1,
    )

    target_margin_pct = st.slider(
        "目標利益率",
        0,
        70,
        30,
        1,
    )

    minimum_charge = st.number_input(
        "最低受注額（円）",
        min_value=0,
        value=12000,
        step=1000,
    )


with right:

    st.html(
        '<div class="step-label">STEP 2</div>'
    )

    st.subheader(
        "今回の案件条件"
    )

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
# STEP 3
# =========================================================

st.html(
    '<div class="step-label">STEP 3</div>'
)

st.subheader(
    "清掃メニュー"
)

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
# 計算設定
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
# RESULT
# =========================================================

st.divider()

st.html(
    '<div class="step-label">RESULT</div>'
)

st.subheader(
    "この案件の見積結果"
)


st.html(
    f"""
<div class="price-card">

<div class="price-label">
推奨見積価格
</div>

<div class="price">
¥{result["target_price"]:,.0f}
</div>

<div class="price-sub">
目標利益率 {settings.target_margin:.0%} を確保する価格
</div>

</div>
"""
)


m1, m2, m3 = st.columns(3)


m1.metric(
    "推定総原価",
    f'¥{result["total_cost"]:,.0f}',
)

m2.metric(
    "値引き下限",
    f'¥{result["minimum_price"]:,.0f}',
)

m3.metric(
    "強気価格",
    f'¥{result["aggressive_price"]:,.0f}',
)


c1, c2, c3 = st.columns(3)


c1.metric(
    "総人時",
    f'{result["total_person_hours"]:.2f} 人時',
)

c2.metric(
    "現場作業時間",
    f'{result["onsite_clock_hours"]:.2f} 時間',
)

c3.metric(
    "目標利益率",
    f'{result["target_profit_margin"]:.1%}',
)


with st.expander(
    "原価内訳を見る",
    expanded=False,
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


if (
    result[
        "public_price_reference"
    ]
    > 0
):

    st.info(
        (
            "選択サービスの公開価格参考単純合計："
            f'¥{result["public_price_reference"]:,.0f}。'
        )
        +
        "これは市場相場を保証するものではなく、"
        "公開されている料金の比較参考です。"
    )


# =========================================================
# STEP 5
# =========================================================

st.divider()

st.html(
    '<div class="step-label">STEP 5</div>'
)

st.subheader(
    "値引きしても利益が残るか確認"
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
        "✓ 設定した最低利益率を満たしています。"
    )

else:

    st.error(
        "最低利益率を下回っています。"
        "値引き価格または原価を再確認してください。"
    )


# =========================================================
# Pro版
# =========================================================

st.html(
    """
<div class="pro-card">

<h2>
CleanMargin Pro
</h2>

<p>
毎回同じ原価設定を入力せず、
清掃会社の日常業務でそのまま使える
Pro版を検討しています。
</p>

</div>
"""
)


pro1, pro2 = st.columns(2)


with pro1:

    st.markdown(
        """
**Pro版で追加予定**

- 自社の人件費・利益率を保存
- 材料費設定を保存
- 案件履歴を保存
- 顧客管理
- PDF見積書
"""
    )


with pro2:

    st.markdown(
        """
**将来追加予定**

- 見積時間と実績時間の比較
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

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSe2vPhTK4t5R6Ui1uQDzSz0sf1BpHmFjDhweEuIpW6hvFpyyg/viewform?usp=dialog"


if FORM_URL.startswith(
    "https://"
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


st.html(
    """
<div class="footer-note">

CleanMargin Free<br><br>

無料版では入力した案件情報や
自社設定をサーバーへ保存しません。<br>

表示価格は入力条件と初期標準作業時間から
算出した参考値です。

</div>
"""
)
