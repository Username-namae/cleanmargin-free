from pathlib import Path
import csv
import json

import streamlit as st

from calculator import CompanySettings, JobConditions, calculate_quote, simulate_offer


# 定期清掃用の計算はこのファイル内で完結させます。
# calculator.py が旧版でも新版でも動作するようにするためです。
FREQUENCY_TO_MONTHLY_VISITS = {
    "月1回": 1.0,
    "月2回": 2.0,
    "週1回": 52.0 / 12.0,
    "週2回": 2.0 * 52.0 / 12.0,
    "週3回": 3.0 * 52.0 / 12.0,
    "週5回": 5.0 * 52.0 / 12.0,
    "週6回": 6.0 * 52.0 / 12.0,
    "毎日": 365.0 / 12.0,
}


def _round_up_100(value: float) -> int:
    import math
    return int(math.ceil(max(0.0, value) / 100.0) * 100)


def recurring_cleaning_quote(
    *,
    area_sqm,
    productivity_sqm_per_person_hour,
    crew_size,
    monthly_visits,
    labor_cost_per_person_hour,
    monthly_material_cost,
    monthly_transport_cost,
    monthly_other_direct_cost,
    overhead_rate,
    target_margin,
    current_contract_price=0.0,
    future_labor_cost_per_person_hour=None,
):
    area_sqm = max(0.0, float(area_sqm))
    productivity = max(0.000001, float(productivity_sqm_per_person_hour))
    crew_size = max(1, int(crew_size))
    monthly_visits = max(0.0, float(monthly_visits))
    labor_rate = max(0.0, float(labor_cost_per_person_hour))
    materials = max(0.0, float(monthly_material_cost))
    transport = max(0.0, float(monthly_transport_cost))
    other_direct = max(0.0, float(monthly_other_direct_cost))
    overhead_rate = min(max(float(overhead_rate), 0.0), 5.0)
    target_margin = min(max(float(target_margin), 0.0), 0.95)
    current_contract_price = max(0.0, float(current_contract_price))

    person_hours_per_visit = area_sqm / productivity
    clock_hours_per_visit = person_hours_per_visit / crew_size
    monthly_person_hours = person_hours_per_visit * monthly_visits
    monthly_labor_cost = monthly_person_hours * labor_rate
    direct_cost = monthly_labor_cost + materials + transport + other_direct
    overhead_cost = direct_cost * overhead_rate
    total_cost = direct_cost + overhead_cost
    recommended_price = _round_up_100(total_cost / (1.0 - target_margin))
    target_profit = recommended_price - total_cost
    price_per_visit = recommended_price / monthly_visits if monthly_visits > 0 else 0.0
    monthly_price_per_sqm = recommended_price / area_sqm if area_sqm > 0 else 0.0

    current_profit = current_contract_price - total_cost if current_contract_price > 0 else None
    current_margin = current_profit / current_contract_price if current_contract_price > 0 else None

    future = None
    if future_labor_cost_per_person_hour is not None:
        future_labor_rate = max(0.0, float(future_labor_cost_per_person_hour))
        future_labor_cost = monthly_person_hours * future_labor_rate
        future_direct_cost = future_labor_cost + materials + transport + other_direct
        future_overhead_cost = future_direct_cost * overhead_rate
        future_total_cost = future_direct_cost + future_overhead_cost
        future_recommended_price = _round_up_100(future_total_cost / (1.0 - target_margin))
        future = {
            "labor_rate": future_labor_rate,
            "labor_cost": future_labor_cost,
            "total_cost": future_total_cost,
            "recommended_price": future_recommended_price,
            "cost_increase": future_total_cost - total_cost,
            "price_increase": future_recommended_price - recommended_price,
            "current_contract_gap": (
                future_recommended_price - current_contract_price
                if current_contract_price > 0 else None
            ),
        }

    return {
        "person_hours_per_visit": person_hours_per_visit,
        "clock_hours_per_visit": clock_hours_per_visit,
        "monthly_visits": monthly_visits,
        "monthly_person_hours": monthly_person_hours,
        "monthly_labor_cost": monthly_labor_cost,
        "monthly_material_cost": materials,
        "monthly_transport_cost": transport,
        "monthly_other_direct_cost": other_direct,
        "direct_cost": direct_cost,
        "overhead_cost": overhead_cost,
        "total_cost": total_cost,
        "recommended_price": recommended_price,
        "target_profit": target_profit,
        "target_profit_margin": target_profit / recommended_price if recommended_price else 0.0,
        "price_per_visit": price_per_visit,
        "monthly_price_per_sqm": monthly_price_per_sqm,
        "current_contract_price": current_contract_price,
        "current_profit": current_profit,
        "current_margin": current_margin,
        "future": future,
    }

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

st.set_page_config(
    page_title="CleanMargin｜ビル・定期清掃の積算・見積",
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

st.title("CleanMargin")
st.caption("ビル・定期清掃の見積を、必要人工・原価・目標利益率から自動計算")

with st.expander("この計算機について", expanded=False):
    st.write(
        "CleanMarginは市場相場を断定するツールではありません。"
        "自社の作業効率・人件費・経費・目標利益率から、"
        "赤字を避けるための月額契約価格の目安を計算します。"
    )
    st.warning(
        "作業効率（㎡/人時）は建物用途・床材・什器・トイレ数・汚れなどで変わります。"
        "第一版では自社の実績値を入力して調整してください。"
    )

main_tab, simple_tab = st.tabs([
    "🏢 定期清掃 見積シミュレーター",
    "🧮 簡易原価・粗利計算（従来版）",
])


# =============================================================================
# Main: recurring / commercial cleaning quote
# =============================================================================
with main_tab:
    st.subheader("ビル・日常清掃の月額見積")
    st.caption("面積と作業条件から、必要人工 → 月間原価 → 推奨契約額まで計算します。")

    left, right = st.columns(2)

    with left:
        st.markdown("#### 1. 現場・作業条件")
        area_sqm = st.number_input(
            "清掃対象面積（㎡）",
            min_value=1.0,
            value=1000.0,
            step=50.0,
            help="実際に日常清掃の対象となる概算面積を入力してください。",
        )
        productivity = st.number_input(
            "作業効率（㎡ / 人時）",
            min_value=1.0,
            value=250.0,
            step=10.0,
            help="1人が1時間で清掃できる面積。自社実績に合わせて変更してください。",
        )
        crew_size = st.number_input(
            "1回の作業人数",
            min_value=1,
            max_value=50,
            value=2,
            step=1,
        )

        frequency_options = list(FREQUENCY_TO_MONTHLY_VISITS.keys()) + ["回数を直接入力"]
        frequency = st.selectbox("清掃頻度", frequency_options, index=5)
        if frequency == "回数を直接入力":
            monthly_visits = st.number_input(
                "月間作業回数",
                min_value=0.0,
                value=20.0,
                step=1.0,
            )
        else:
            monthly_visits = FREQUENCY_TO_MONTHLY_VISITS[frequency]
            st.caption(f"月間換算：約 {monthly_visits:.2f} 回")

    with right:
        st.markdown("#### 2. 自社原価・利益設定")
        labor_rate = st.number_input(
            "実質人件費（円 / 人時）",
            min_value=0,
            value=1800,
            step=100,
            help="給与だけでなく、会社負担の社会保険・採用教育費なども含めた時間原価を推奨します。",
        )
        material_cost = st.number_input("洗剤・消耗品（円 / 月）", min_value=0, value=10000, step=1000)
        transport_cost = st.number_input("交通・車両費（円 / 月）", min_value=0, value=8000, step=1000)
        other_direct_cost = st.number_input("その他直接費（円 / 月）", min_value=0, value=5000, step=1000)
        overhead_rate_pct = st.slider("諸経費率", 0, 100, 15, 1)
        target_margin_pct = st.slider("目標利益率", 0, 70, 20, 1)

    result = recurring_cleaning_quote(
        area_sqm=area_sqm,
        productivity_sqm_per_person_hour=productivity,
        crew_size=int(crew_size),
        monthly_visits=monthly_visits,
        labor_cost_per_person_hour=labor_rate,
        monthly_material_cost=material_cost,
        monthly_transport_cost=transport_cost,
        monthly_other_direct_cost=other_direct_cost,
        overhead_rate=overhead_rate_pct / 100.0,
        target_margin=target_margin_pct / 100.0,
    )

    st.divider()
    st.markdown("### 計算結果")

    st.metric(
        "推奨月額",
        f'¥{result["recommended_price"]:,.0f}',
        help="総原価から、設定した目標利益率を売価ベースで確保するための月額です。",
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("1回の必要人工", f'{result["person_hours_per_visit"]:.2f} 人時')
    m2.metric("1回の所要時間", f'{result["clock_hours_per_visit"]:.2f} 時間')
    m3.metric("月間必要人工", f'{result["monthly_person_hours"]:.1f} 人時')
    m4.metric("月間作業回数", f'{result["monthly_visits"]:.2f} 回')

    with st.expander("原価・見積の内訳", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.write({
                "月間人件費": round(result["monthly_labor_cost"]),
                "洗剤・消耗品": round(result["monthly_material_cost"]),
                "交通・車両費": round(result["monthly_transport_cost"]),
                "その他直接費": round(result["monthly_other_direct_cost"]),
                "直接業務費": round(result["direct_cost"]),
                "諸経費": round(result["overhead_cost"]),
                "総原価": round(result["total_cost"]),
            })
        with c2:
            st.write({
                "目標利益": round(result["target_profit"]),
                "推奨月額": round(result["recommended_price"]),
                "1回あたり": round(result["price_per_visit"]),
                "月額㎡単価": round(result["monthly_price_per_sqm"], 1),
            })

    st.divider()
    st.markdown("### 現在・提示予定の契約価格と比較")
    current_price = st.number_input(
        "現在の契約額 / 提示予定額（円 / 月）",
        min_value=0,
        value=0,
        step=5000,
        help="0円のままなら比較を行いません。",
    )

    if current_price > 0:
        compare = recurring_cleaning_quote(
            area_sqm=area_sqm,
            productivity_sqm_per_person_hour=productivity,
            crew_size=int(crew_size),
            monthly_visits=monthly_visits,
            labor_cost_per_person_hour=labor_rate,
            monthly_material_cost=material_cost,
            monthly_transport_cost=transport_cost,
            monthly_other_direct_cost=other_direct_cost,
            overhead_rate=overhead_rate_pct / 100.0,
            target_margin=target_margin_pct / 100.0,
            current_contract_price=current_price,
        )
        q1, q2, q3 = st.columns(3)
        q1.metric("現在価格での利益", f'¥{compare["current_profit"]:,.0f}')
        q2.metric("現在価格での利益率", f'{compare["current_margin"]:.1%}')
        gap = compare["recommended_price"] - current_price
        q3.metric("推奨月額との差", f'¥{gap:,.0f}')

        if compare["current_margin"] < target_margin_pct / 100.0:
            st.warning(
                f"目標利益率 {target_margin_pct}% を下回っています。"
                f"設定条件では月額約 ¥{compare['recommended_price']:,.0f} が目安です。"
            )
        else:
            st.success(f"目標利益率 {target_margin_pct}% を満たしています。")

    st.divider()
    st.markdown("### 人件費が上がった場合")
    future_labor_rate = st.number_input(
        "改定後の実質人件費（円 / 人時）",
        min_value=0,
        value=int(labor_rate),
        step=100,
    )

    if future_labor_rate != labor_rate:
        future_result = recurring_cleaning_quote(
            area_sqm=area_sqm,
            productivity_sqm_per_person_hour=productivity,
            crew_size=int(crew_size),
            monthly_visits=monthly_visits,
            labor_cost_per_person_hour=labor_rate,
            monthly_material_cost=material_cost,
            monthly_transport_cost=transport_cost,
            monthly_other_direct_cost=other_direct_cost,
            overhead_rate=overhead_rate_pct / 100.0,
            target_margin=target_margin_pct / 100.0,
            current_contract_price=current_price,
            future_labor_cost_per_person_hour=future_labor_rate,
        )
        future = future_result["future"]
        f1, f2, f3 = st.columns(3)
        f1.metric("改定後の総原価", f'¥{future["total_cost"]:,.0f}', delta=f'¥{future["cost_increase"]:,.0f}')
        f2.metric("改定後の推奨月額", f'¥{future["recommended_price"]:,.0f}', delta=f'¥{future["price_increase"]:,.0f}')
        if current_price > 0:
            f3.metric("現在契約との差", f'¥{future["current_contract_gap"]:,.0f}')

    st.info(
        "第一版は『面積 × 自社の作業効率』で必要人工を求めるシンプルな積算です。"
        "トイレ数・床材・什器・夜間作業などの詳細条件は、利用データを見て第二版で追加します。"
    )


# =============================================================================
# Existing simple calculator, retained as a secondary tool
# =============================================================================
with simple_tab:
    st.subheader("簡易原価・粗利計算")
    st.caption("従来のハウスクリーニング／単発案件向け計算機です。")

    left, right = st.columns([1, 1])

    with left:
        st.markdown("#### 1. 自社の原価設定")
        simple_labor_rate = st.number_input("実質人件費（円/人時）", min_value=0, value=2000, step=100, key="simple_labor")
        vehicle_rate = st.number_input("車両コスト（円/km）", min_value=0.0, value=35.0, step=5.0, key="simple_vehicle")
        monthly_fixed = st.number_input("月間固定費（円）", min_value=0, value=60000, step=5000, key="simple_fixed")
        monthly_jobs = st.number_input("月間想定案件数", min_value=1, value=30, step=1, key="simple_jobs")
        minimum_margin_pct = st.slider("最低利益率", 0, 60, 15, 1, key="simple_min_margin")
        simple_target_margin_pct = st.slider("目標利益率", 0, 70, 30, 1, key="simple_target_margin")
        minimum_charge = st.number_input("最低受注額（円）", min_value=0, value=12000, step=1000, key="simple_min_charge")

    with right:
        st.markdown("#### 2. 案件条件")
        occupancy = st.selectbox("物件状態", list(condition_master["occupancy"].keys()), index=1, key="simple_occupancy")
        dirt = st.selectbox("汚れレベル", list(condition_master["dirt"].keys()), index=1, key="simple_dirt")
        pet = st.checkbox("ペットあり", key="simple_pet")
        simple_crew_size = st.number_input("作業人数", min_value=1, max_value=10, value=1, step=1, key="simple_crew")
        one_way_minutes = st.number_input("片道移動時間（分）", min_value=0, value=30, step=5, key="simple_minutes")
        one_way_km = st.number_input("片道距離（km）", min_value=0.0, value=10.0, step=1.0, key="simple_km")
        parking_cost = st.number_input("駐車費（円）", min_value=0, value=0, step=100, key="simple_parking")
        subcontract_cost = st.number_input("外注費（円）", min_value=0, value=0, step=1000, key="simple_subcontract")
        other_cost = st.number_input("その他変動費（円）", min_value=0, value=0, step=100, key="simple_other")

    st.markdown("#### 3. 清掃内容")
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
                key=f'simple_{service["service_id"]}',
            )
            if qty:
                selected.append({**service, "quantity": qty})

    with st.expander("マスタにない作業を追加"):
        custom_hours = st.number_input("追加人時", min_value=0.0, value=0.0, step=0.25, key="simple_custom_hours")
        custom_material = st.number_input("追加材料費（円）", min_value=0, value=0, step=100, key="simple_custom_material")

    settings = CompanySettings(
        labor_cost_per_person_hour=float(simple_labor_rate),
        vehicle_cost_per_km=float(vehicle_rate),
        monthly_fixed_cost=float(monthly_fixed),
        monthly_job_count=float(monthly_jobs),
        minimum_margin=minimum_margin_pct / 100.0,
        target_margin=simple_target_margin_pct / 100.0,
        aggressive_markup=0.10,
        minimum_charge=float(minimum_charge),
    )

    conditions = JobConditions(
        occupancy_multiplier=float(condition_master["occupancy"][occupancy]),
        dirt_multiplier=float(condition_master["dirt"][dirt]),
        pet_additional_person_hours=float(condition_master["pet_additional_person_hours"] if pet else 0.0),
        crew_size=int(simple_crew_size),
        one_way_minutes=float(one_way_minutes),
        one_way_km=float(one_way_km),
        parking_cost=float(parking_cost),
        subcontract_cost=float(subcontract_cost),
        other_variable_cost=float(other_cost),
    )

    simple_result = calculate_quote(
        selected,
        settings,
        conditions,
        custom_person_hours=float(custom_hours),
        custom_material_cost=float(custom_material),
    )

    st.divider()
    st.markdown("#### 4. 計算結果")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("推定総原価", f'¥{simple_result["total_cost"]:,.0f}')
    m2.metric("値引き下限", f'¥{simple_result["minimum_price"]:,.0f}')
    m3.metric("目標価格", f'¥{simple_result["target_price"]:,.0f}')
    m4.metric("強気価格", f'¥{simple_result["aggressive_price"]:,.0f}')

    c1, c2, c3 = st.columns(3)
    c1.metric("総人時", f'{simple_result["total_person_hours"]:.2f} 人時')
    c2.metric("現場作業時間", f'{simple_result["onsite_clock_hours"]:.2f} 時間')
    c3.metric("目標価格での利益率", f'{simple_result["target_profit_margin"]:.1%}')

    with st.expander("原価内訳", expanded=True):
        st.write({
            "人件費": round(simple_result["labor_cost"]),
            "材料費": round(simple_result["material_cost"]),
            "車両費": round(simple_result["vehicle_cost"]),
            "駐車費": round(simple_result["parking_cost"]),
            "外注費": round(simple_result["subcontract_cost"]),
            "その他変動費": round(simple_result["other_variable_cost"]),
            "固定費配賦": round(simple_result["fixed_cost_allocation"]),
        })

    if simple_result["public_price_reference"] > 0:
        st.info(
            f'選択サービスの公開価格参考単純合計：¥{simple_result["public_price_reference"]:,.0f}。'
            "これは市場相場の保証ではなく、公開料金の比較参考です。"
        )

    st.markdown("#### 5. 値引きシミュレーター")
    offer = st.number_input(
        "顧客への提示価格（円）",
        min_value=0,
        value=int(simple_result["target_price"]),
        step=100,
        key="simple_offer",
    )
    sim = simulate_offer(offer, simple_result["total_cost"], settings.minimum_margin)
    s1, s2 = st.columns(2)
    s1.metric("提示価格での利益", f'¥{sim["profit"]:,.0f}')
    s2.metric("提示価格での利益率", f'{sim["margin"]:.1%}')
    if sim["acceptable"]:
        st.success("設定した最低利益率を満たしています。")
    else:
        st.error("設定した最低利益率を下回ります。値引きまたは原価を再確認してください。")

st.divider()
st.markdown("### Pro版で追加予定")
st.write("自社設定保存 / 案件保存 / 見積書PDF / 自社ロゴ / 過去見積の複製・比較")
st.caption("無料版では入力内容をサーバーに保存しません。")
