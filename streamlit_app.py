from pathlib import Path
import csv
import json

import streamlit as st

from calculator import CompanySettings, JobConditions, calculate_quote, simulate_offer

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

st.set_page_config(
    page_title="CleanMargin｜清掃利益見積",
    page_icon="🧹",
    layout="wide",
)

@st.cache_data
def load_services():
    with (DATA / "service_master.csv").open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["standard_person_hours"] = float(r["standard_person_hours"])
        r["material_cost_yen"] = float(r["material_cost_yen"])
        r["public_price_reference_yen"] = float(r["public_price_reference_yen"])
    return rows

@st.cache_data
def load_conditions():
    with (DATA / "condition_master.json").open("r", encoding="utf-8") as f:
        return json.load(f)

services = load_services()
condition_master = load_conditions()
service_by_name = {s["service_name"]: s for s in services}

st.title("CleanMargin")
st.caption("清掃会社向け｜原価から『利益が残る見積価格』を逆算する無料計算機")

with st.expander("この計算機について", expanded=False):
    st.write(
        "市場相場を断定するツールではありません。"
        "自社の人件費・移動・材料・固定費と目標利益率から、"
        "赤字を避けるための目安価格を計算します。"
    )
    st.warning(
        "標準作業時間と補正係数は公開情報をもとにした初期モデルです。"
        "実案件では現場条件に応じて必ず調整してください。"
    )

left, right = st.columns([1, 1])

with left:
    st.subheader("1. 自社の原価設定")
    labor_rate = st.number_input("実質人件費（円/人時）", min_value=0, value=2000, step=100)
    vehicle_rate = st.number_input("車両コスト（円/km）", min_value=0.0, value=35.0, step=5.0)
    monthly_fixed = st.number_input("月間固定費（円）", min_value=0, value=60000, step=5000)
    monthly_jobs = st.number_input("月間想定案件数", min_value=1, value=30, step=1)
    minimum_margin_pct = st.slider("最低利益率", 0, 60, 15, 1)
    target_margin_pct = st.slider("目標利益率", 0, 70, 30, 1)
    minimum_charge = st.number_input("最低受注額（円）", min_value=0, value=12000, step=1000)

with right:
    st.subheader("2. 案件条件")
    occupancy = st.selectbox("物件状態", list(condition_master["occupancy"].keys()), index=1)
    dirt = st.selectbox("汚れレベル", list(condition_master["dirt"].keys()), index=1)
    pet = st.checkbox("ペットあり")
    crew_size = st.number_input("作業人数", min_value=1, max_value=10, value=1, step=1)
    one_way_minutes = st.number_input("片道移動時間（分）", min_value=0, value=30, step=5)
    one_way_km = st.number_input("片道距離（km）", min_value=0.0, value=10.0, step=1.0)
    parking_cost = st.number_input("駐車費（円）", min_value=0, value=0, step=100)
    subcontract_cost = st.number_input("外注費（円）", min_value=0, value=0, step=1000)
    other_cost = st.number_input("その他変動費（円）", min_value=0, value=0, step=100)

st.subheader("3. 清掃内容")
st.caption("数量0のサービスは計算対象外です。")

selected = []
cols = st.columns(2)
for i, service in enumerate(services):
    with cols[i % 2]:
        qty = st.number_input(
            f'{service["service_name"]}（標準 {service["standard_person_hours"]:.2f} 人時）',
            min_value=0,
            max_value=20,
            value=1 if service["service_name"] in ["浴室", "キッチン", "トイレ"] else 0,
            step=1,
            key=service["service_id"],
        )
        if qty:
            selected.append({**service, "quantity": qty})

with st.expander("マスタにない作業を追加"):
    custom_hours = st.number_input("追加人時", min_value=0.0, value=0.0, step=0.25)
    custom_material = st.number_input("追加材料費（円）", min_value=0, value=0, step=100)

settings = CompanySettings(
    labor_cost_per_person_hour=float(labor_rate),
    vehicle_cost_per_km=float(vehicle_rate),
    monthly_fixed_cost=float(monthly_fixed),
    monthly_job_count=float(monthly_jobs),
    minimum_margin=minimum_margin_pct / 100.0,
    target_margin=target_margin_pct / 100.0,
    aggressive_markup=0.10,
    minimum_charge=float(minimum_charge),
)

conditions = JobConditions(
    occupancy_multiplier=float(condition_master["occupancy"][occupancy]),
    dirt_multiplier=float(condition_master["dirt"][dirt]),
    pet_additional_person_hours=float(condition_master["pet_additional_person_hours"] if pet else 0.0),
    crew_size=int(crew_size),
    one_way_minutes=float(one_way_minutes),
    one_way_km=float(one_way_km),
    parking_cost=float(parking_cost),
    subcontract_cost=float(subcontract_cost),
    other_variable_cost=float(other_cost),
)

result = calculate_quote(
    selected,
    settings,
    conditions,
    custom_person_hours=float(custom_hours),
    custom_material_cost=float(custom_material),
)

st.divider()
st.subheader("4. 計算結果")

m1, m2, m3, m4 = st.columns(4)
m1.metric("推定総原価", f'¥{result["total_cost"]:,.0f}')
m2.metric("値引き下限", f'¥{result["minimum_price"]:,.0f}')
m3.metric("目標価格", f'¥{result["target_price"]:,.0f}')
m4.metric("強気価格", f'¥{result["aggressive_price"]:,.0f}')

c1, c2, c3 = st.columns(3)
c1.metric("総人時", f'{result["total_person_hours"]:.2f} 人時')
c2.metric("現場作業時間", f'{result["onsite_clock_hours"]:.2f} 時間')
c3.metric("目標価格での利益率", f'{result["target_profit_margin"]:.1%}')

with st.expander("原価内訳", expanded=True):
    st.write({
        "人件費": round(result["labor_cost"]),
        "材料費": round(result["material_cost"]),
        "車両費": round(result["vehicle_cost"]),
        "駐車費": round(result["parking_cost"]),
        "外注費": round(result["subcontract_cost"]),
        "その他変動費": round(result["other_variable_cost"]),
        "固定費配賦": round(result["fixed_cost_allocation"]),
    })

if result["public_price_reference"] > 0:
    st.info(
        f'選択サービスの公開価格参考単純合計：¥{result["public_price_reference"]:,.0f}。'
        "これは市場相場の保証ではなく、公開料金の比較参考です。"
    )

st.subheader("5. 値引きシミュレーター")
offer = st.number_input(
    "顧客への提示価格（円）",
    min_value=0,
    value=int(result["target_price"]),
    step=100,
)
sim = simulate_offer(offer, result["total_cost"], settings.minimum_margin)
s1, s2 = st.columns(2)
s1.metric("提示価格での利益", f'¥{sim["profit"]:,.0f}')
s2.metric("提示価格での利益率", f'{sim["margin"]:.1%}')
if sim["acceptable"]:
    st.success("設定した最低利益率を満たしています。")
else:
    st.error("設定した最低利益率を下回ります。値引きまたは原価を再確認してください。")

st.divider()
st.markdown("### Pro版で追加予定")
st.write(
    "自社設定の保存 / 案件履歴 / PDF見積書 / 顧客管理 / "
    "見積人時と実績人時の比較 / 自社実績による標準時間の自動補正"
)
st.caption("無料版では入力内容をサーバーに保存しません。")
