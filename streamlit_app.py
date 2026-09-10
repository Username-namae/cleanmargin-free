from pathlib import Path
import csv
import json
import math

import streamlit as st

from calculator import CompanySettings, JobConditions, calculate_quote, simulate_offer


# =============================================================================
# Recurring-cleaning calculator
# =============================================================================
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
    return int(math.ceil(max(0.0, value) / 100.0) * 100)


def yen(value: float) -> str:
    return f"¥{value:,.0f}"


def signed_yen(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}¥{value:,.0f}"


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


# =============================================================================
# App setup / data
# =============================================================================
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

st.set_page_config(
    page_title="CleanMargin｜ビル・定期清掃の積算・見積",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="collapsed",
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


# =============================================================================
# Design system
# =============================================================================
st.markdown(
    """
<style>
:root {
    --cm-ink: #162033;
    --cm-muted: #667085;
    --cm-border: #E5EAF0;
    --cm-bg: #F6F8FB;
    --cm-panel: #FFFFFF;
    --cm-brand: #0F766E;
    --cm-brand-dark: #115E59;
    --cm-brand-soft: #ECFDF5;
    --cm-navy: #0F2747;
    --cm-warning-bg: #FFF8E6;
    --cm-warning-border: #F5D58B;
    --cm-danger-bg: #FEF3F2;
    --cm-danger: #B42318;
}

html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans JP", "Hiragino Sans", "Yu Gothic UI", sans-serif;
}

.stApp {
    background: var(--cm-bg);
    color: var(--cm-ink);
}

.block-container {
    max-width: 1180px;
    padding-top: 2.1rem;
    padding-bottom: 4rem;
}

#MainMenu, footer {visibility: hidden;}
header[data-testid="stHeader"] {background: transparent;}

.cm-top-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin: 0 0 12px;
}
.cm-home-link, .cm-guide-link {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    text-decoration: none !important;
    border-radius: 10px;
    padding: 9px 13px;
    font-size: 13px;
    font-weight: 750;
    line-height: 1.2;
    transition: all .18s ease;
}
.cm-home-link {
    color: var(--cm-navy) !important;
    background: #FFFFFF;
    border: 1px solid var(--cm-border);
    box-shadow: 0 3px 12px rgba(15,39,71,.04);
}
.cm-home-link:hover {
    border-color: #B7E4D8;
    background: #F7FCFA;
    color: var(--cm-brand-dark) !important;
}
.cm-guide-link {
    color: var(--cm-brand-dark) !important;
    background: var(--cm-brand-soft);
    border: 1px solid #B7E4D8;
}
.cm-guide-link:hover {
    background: #DFF7F0;
}
.cm-return-home {
    text-align: center;
    margin: 16px 0 4px;
}
.cm-return-home a {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 42px;
    padding: 10px 16px;
    border: 1px solid var(--cm-border);
    border-radius: 11px;
    background: #FFFFFF;
    color: var(--cm-navy) !important;
    font-size: 13px;
    font-weight: 750;
    text-decoration: none !important;
}
.cm-return-home a:hover {
    border-color: #B7E4D8;
    color: var(--cm-brand-dark) !important;
    background: #F7FCFA;
}

.cm-hero {
    background: linear-gradient(135deg, #0F2747 0%, #123C59 56%, #0F766E 100%);
    border-radius: 22px;
    padding: 34px 38px 32px;
    margin: 0 0 22px;
    box-shadow: 0 14px 38px rgba(15, 39, 71, 0.14);
}
.cm-brand-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 17px;
}
.cm-brand {
    color: #FFFFFF;
    font-size: 18px;
    font-weight: 800;
    letter-spacing: .2px;
}
.cm-badge {
    display: inline-flex;
    align-items: center;
    padding: 5px 10px;
    border-radius: 999px;
    background: rgba(255,255,255,.14);
    border: 1px solid rgba(255,255,255,.2);
    color: #E8FFF8;
    font-size: 12px;
    font-weight: 700;
}
.cm-hero h1 {
    color: #FFFFFF;
    font-size: clamp(28px, 4.2vw, 46px);
    line-height: 1.2;
    letter-spacing: -0.025em;
    margin: 0 0 12px;
}
.cm-hero p {
    color: #D8E5EE;
    font-size: 16px;
    line-height: 1.75;
    max-width: 760px;
    margin: 0;
}
.cm-proof-row {
    display: flex;
    flex-wrap: wrap;
    gap: 9px;
    margin-top: 22px;
}
.cm-proof {
    color: #FFFFFF;
    background: rgba(255,255,255,.10);
    border: 1px solid rgba(255,255,255,.16);
    border-radius: 9px;
    padding: 7px 11px;
    font-size: 12px;
    font-weight: 650;
}

.cm-section-title {
    font-size: 21px;
    font-weight: 800;
    color: var(--cm-navy);
    margin: 4px 0 2px;
    letter-spacing: -0.01em;
}
.cm-section-sub {
    color: var(--cm-muted);
    font-size: 13px;
    margin: 0 0 16px;
}

div[data-testid="stTabs"] button[role="tab"] {
    font-weight: 700;
    padding-top: 10px;
    padding-bottom: 10px;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--cm-border) !important;
    border-radius: 16px !important;
    background: var(--cm-panel);
    box-shadow: 0 4px 18px rgba(15, 39, 71, 0.035);
}

label[data-testid="stWidgetLabel"] p {
    color: #344054;
    font-weight: 650;
}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div {
    border-radius: 10px !important;
}

.cm-result-hero {
    background: #FFFFFF;
    border: 1px solid #DDE6EC;
    border-left: 6px solid var(--cm-brand);
    border-radius: 18px;
    padding: 24px 28px;
    margin: 10px 0 14px;
    box-shadow: 0 8px 28px rgba(15, 39, 71, .07);
}
.cm-result-label {
    color: var(--cm-muted);
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 4px;
}
.cm-result-price {
    color: var(--cm-navy);
    font-size: clamp(38px, 6vw, 58px);
    line-height: 1.05;
    font-weight: 850;
    letter-spacing: -0.04em;
}
.cm-result-note {
    color: var(--cm-muted);
    font-size: 13px;
    margin-top: 9px;
}

.cm-kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0,1fr));
    gap: 12px;
    margin: 0 0 18px;
}
.cm-kpi {
    background: #FFFFFF;
    border: 1px solid var(--cm-border);
    border-radius: 14px;
    padding: 17px 18px;
    min-height: 96px;
}
.cm-kpi-label {
    color: var(--cm-muted);
    font-size: 12px;
    font-weight: 650;
    margin-bottom: 8px;
}
.cm-kpi-value {
    color: var(--cm-navy);
    font-size: 23px;
    font-weight: 800;
    line-height: 1.15;
}

.cm-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    overflow: hidden;
    background: #FFFFFF;
    border: 1px solid var(--cm-border);
    border-radius: 14px;
    font-size: 14px;
}
.cm-table th, .cm-table td {
    padding: 12px 14px;
    border-bottom: 1px solid #EEF1F4;
}
.cm-table tr:last-child td {border-bottom: none;}
.cm-table th {
    text-align: left;
    color: var(--cm-muted);
    background: #F9FAFB;
    font-size: 12px;
    font-weight: 750;
}
.cm-table td:last-child, .cm-table th:last-child {text-align: right;}
.cm-table .total td {
    background: #F7FCFA;
    font-weight: 800;
    color: var(--cm-navy);
}

.cm-callout {
    border-radius: 13px;
    padding: 14px 16px;
    margin: 10px 0;
    font-size: 14px;
    line-height: 1.65;
}
.cm-callout.good {
    background: var(--cm-brand-soft);
    border: 1px solid #B7E4D8;
    color: var(--cm-brand-dark);
}
.cm-callout.warn {
    background: var(--cm-warning-bg);
    border: 1px solid var(--cm-warning-border);
    color: #7A4E00;
}
.cm-callout.bad {
    background: var(--cm-danger-bg);
    border: 1px solid #FECDCA;
    color: var(--cm-danger);
}

.cm-mini-card {
    background: #FFFFFF;
    border: 1px solid var(--cm-border);
    border-radius: 14px;
    padding: 16px 18px;
    height: 100%;
}
.cm-mini-card .label {
    color: var(--cm-muted);
    font-size: 12px;
    font-weight: 650;
}
.cm-mini-card .value {
    color: var(--cm-navy);
    font-size: 24px;
    font-weight: 800;
    margin-top: 4px;
}
.cm-mini-card .delta-up {
    color: var(--cm-danger);
    font-size: 12px;
    font-weight: 700;
    margin-top: 4px;
}

.cm-pro-card {
    background: linear-gradient(135deg, #F0FDFA 0%, #F8FAFC 100%);
    border: 1px solid #B7E4D8;
    border-radius: 16px;
    padding: 20px 22px;
    margin: 18px 0 6px;
}
.cm-pro-eyebrow {
    color: var(--cm-brand-dark);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: .04em;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.cm-pro-title {
    color: var(--cm-navy);
    font-size: 19px;
    font-weight: 800;
    line-height: 1.45;
    margin-bottom: 5px;
}
.cm-pro-copy {
    color: var(--cm-muted);
    font-size: 13px;
    line-height: 1.65;
}

.cm-footer-note {
    color: #7A8699;
    font-size: 12px;
    line-height: 1.7;
    text-align: center;
    margin-top: 26px;
}

/* Tablet / small desktop: keep the two-column form. */
@media (max-width: 900px) {
    .block-container {
        padding-top: .9rem;
        padding-left: 1rem;
        padding-right: 1rem;
        padding-bottom: 2.5rem;
    }
    .cm-hero {padding: 26px 24px 24px; border-radius: 17px; margin-bottom: 14px;}
    .cm-hero h1 {font-size: 30px;}
    .cm-hero p {font-size: 14px;}
    .cm-kpi-grid {grid-template-columns: repeat(2, minmax(0,1fr)); gap: 9px;}
    .cm-kpi {padding: 14px 13px; min-height: 88px;}
    .cm-kpi-value {font-size: 20px;}
}

/* Actual phone width: stack Streamlit columns to one full-width column. */
@media (max-width: 640px) {
    .block-container {
        padding-top: .7rem;
        padding-left: .75rem;
        padding-right: .75rem;
        padding-bottom: 2.3rem;
    }
    .cm-top-nav {margin-bottom: 9px; gap: 8px;}
    .cm-home-link, .cm-guide-link {padding: 8px 10px; font-size: 12px;}
    .cm-hero {padding: 22px 18px 20px; border-radius: 15px;}
    .cm-brand {font-size: 16px;}
    .cm-badge {font-size: 11px; padding: 4px 8px;}
    .cm-hero h1 {font-size: 27px; line-height: 1.25;}
    .cm-hero p {font-size: 14px; line-height: 1.7;}
    .cm-proof-row {gap: 7px; margin-top: 16px;}
    .cm-proof {font-size: 11px; padding: 6px 9px;}

    div[data-testid="stHorizontalBlock"] {
        flex-direction: column !important;
        gap: .7rem !important;
        width: 100% !important;
    }
    div[data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }

    .cm-section-title {font-size: 20px;}
    .cm-section-sub {font-size: 13px; margin-bottom: 12px;}
    .cm-result-hero {padding: 20px 18px; border-left-width: 5px;}
    .cm-result-price {font-size: 40px;}
    .cm-result-note {font-size: 12px; line-height: 1.55;}
    .cm-kpi-grid {grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px;}
    .cm-table {font-size: 13px;}
    .cm-table th, .cm-table td {padding: 10px 9px;}
    .cm-mini-card {padding: 14px 15px;}
    .cm-mini-card .value {font-size: 22px;}
    .cm-pro-card {padding: 17px 16px;}
}
</style>
""",
    unsafe_allow_html=True,
)


# =============================================================================
# Navigation / return to website
# =============================================================================
st.markdown(
    """
<div class="cm-top-nav">
  <a class="cm-home-link" href="https://username-namae.github.io/cleanmargin-site/" target="_blank" rel="noopener noreferrer" aria-label="CleanMarginホームへ戻る">← CleanMargin ホーム</a>
  <a class="cm-guide-link" href="https://username-namae.github.io/cleanmargin-site/#articles" target="_blank" rel="noopener noreferrer">見積ノウハウを見る →</a>
</div>
""",
    unsafe_allow_html=True,
)


# =============================================================================
# Hero
# =============================================================================
st.markdown(
    """
<div class="cm-hero">
  <div class="cm-brand-row">
    <div class="cm-brand">CleanMargin</div>
    <div class="cm-badge">清掃事業者向け・無料</div>
  </div>
  <h1>ビル・定期清掃の見積を、3分で。</h1>
  <p>面積・作業効率・人件費から、必要人工、月間原価、利益を確保した契約価格まで自動計算。勘ではなく、自社原価をもとに見積を組み立てられます。</p>
  <div class="cm-proof-row">
    <div class="cm-proof">登録不要</div>
    <div class="cm-proof">無料で計算</div>
    <div class="cm-proof">入力内容は保存しません</div>
    <div class="cm-proof">スマホ対応</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

with st.expander("計算方法・注意事項を見る", expanded=False):
    st.markdown(
        """
**CleanMarginは市場相場を断定するツールではありません。**  
自社の作業効率、人件費、経費、目標利益率から、赤字を避けるための月額契約価格の目安を計算します。

- 作業効率（㎡/人時）は、建物用途・床材・什器・トイレ数・汚れなどで変わります。
- まずは自社の実績値を入力し、実際の作業時間と比較しながら調整してください。
- 計算結果は見積判断の補助であり、契約価格や利益を保証するものではありません。
"""
    )

main_tab, simple_tab = st.tabs([
    "定期清掃の月額見積",
    "単発清掃の原価・粗利",
])


# =============================================================================
# Main: recurring / commercial cleaning quote
# =============================================================================
with main_tab:
    st.markdown('<div class="cm-section-title">見積条件を入力</div>', unsafe_allow_html=True)
    st.markdown('<div class="cm-section-sub">まずは面積・頻度・自社原価だけで計算できます。入力すると結果は自動更新されます。</div>', unsafe_allow_html=True)

    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        with st.container(border=True):
            st.markdown("#### ① 現場・作業条件")
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
                st.caption(f"月間換算：{monthly_visits:.2f}回")

    with col_right:
        with st.container(border=True):
            st.markdown("#### ② 自社原価・利益")
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

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="cm-section-title">計算結果</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="cm-result-hero">
  <div class="cm-result-label">推奨月額</div>
  <div class="cm-result-price">{yen(result['recommended_price'])}</div>
  <div class="cm-result-note">目標利益率 {target_margin_pct}% を確保するための月額目安　・　総原価 {yen(result['total_cost'])}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
<div class="cm-kpi-grid">
  <div class="cm-kpi"><div class="cm-kpi-label">1回の必要人時</div><div class="cm-kpi-value">{result['person_hours_per_visit']:.2f} 人時</div></div>
  <div class="cm-kpi"><div class="cm-kpi-label">1回の所要時間</div><div class="cm-kpi-value">{result['clock_hours_per_visit']:.2f} 時間</div></div>
  <div class="cm-kpi"><div class="cm-kpi-label">月間人時</div><div class="cm-kpi-value">{result['monthly_person_hours']:.1f} 人時</div></div>
  <div class="cm-kpi"><div class="cm-kpi-label">月間作業回数</div><div class="cm-kpi-value">{result['monthly_visits']:.2f} 回</div></div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.expander("原価・見積の内訳", expanded=True):
        st.markdown(
            f"""
<table class="cm-table">
  <thead><tr><th>項目</th><th>金額</th></tr></thead>
  <tbody>
    <tr><td>月間人件費</td><td>{yen(result['monthly_labor_cost'])}</td></tr>
    <tr><td>洗剤・消耗品</td><td>{yen(result['monthly_material_cost'])}</td></tr>
    <tr><td>交通・車両費</td><td>{yen(result['monthly_transport_cost'])}</td></tr>
    <tr><td>その他直接費</td><td>{yen(result['monthly_other_direct_cost'])}</td></tr>
    <tr><td>直接業務費</td><td>{yen(result['direct_cost'])}</td></tr>
    <tr><td>諸経費</td><td>{yen(result['overhead_cost'])}</td></tr>
    <tr class="total"><td>総原価</td><td>{yen(result['total_cost'])}</td></tr>
    <tr><td>目標利益</td><td>{yen(result['target_profit'])}</td></tr>
    <tr class="total"><td>推奨月額</td><td>{yen(result['recommended_price'])}</td></tr>
  </tbody>
</table>
""",
            unsafe_allow_html=True,
        )
        a, b = st.columns(2)
        with a:
            st.markdown(
                f'<div class="cm-mini-card"><div class="label">1回あたり</div><div class="value">{yen(result["price_per_visit"])}</div></div>',
                unsafe_allow_html=True,
            )
        with b:
            st.markdown(
                f'<div class="cm-mini-card"><div class="label">月額㎡単価</div><div class="value">¥{result["monthly_price_per_sqm"]:,.1f}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="cm-section-title">現在の契約価格を診断</div>', unsafe_allow_html=True)
    st.markdown('<div class="cm-section-sub">既存契約や提示予定額が、目標利益率を満たしているか確認できます。</div>', unsafe_allow_html=True)

    with st.container(border=True):
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
            with q1:
                st.markdown(
                    f'<div class="cm-mini-card"><div class="label">現在価格での利益</div><div class="value">{yen(compare["current_profit"])}</div></div>',
                    unsafe_allow_html=True,
                )
            with q2:
                st.markdown(
                    f'<div class="cm-mini-card"><div class="label">現在価格での利益率</div><div class="value">{compare["current_margin"]:.1%}</div></div>',
                    unsafe_allow_html=True,
                )
            gap = compare["recommended_price"] - current_price
            with q3:
                st.markdown(
                    f'<div class="cm-mini-card"><div class="label">推奨月額との差</div><div class="value">{yen(gap)}</div></div>',
                    unsafe_allow_html=True,
                )

            if compare["current_margin"] < target_margin_pct / 100.0:
                st.markdown(
                    f'<div class="cm-callout warn"><strong>見直し候補です。</strong> 目標利益率 {target_margin_pct}% を下回っています。現在の条件では、月額 <strong>{yen(compare["recommended_price"])}</strong> がひとつの目安です。</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="cm-callout good"><strong>目標利益率を満たしています。</strong> 現在価格での利益率は {compare["current_margin"]:.1%} です。</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("金額を入力すると、利益額・利益率・推奨月額との差を表示します。")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="cm-section-title">人件費上昇の影響を確認</div>', unsafe_allow_html=True)
    st.markdown('<div class="cm-section-sub">賃金改定後も同じ利益率を維持するために必要な月額を計算します。</div>', unsafe_allow_html=True)

    with st.container(border=True):
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
            with f1:
                st.markdown(
                    f'<div class="cm-mini-card"><div class="label">改定後の総原価</div><div class="value">{yen(future["total_cost"])}</div><div class="delta-up">{signed_yen(future["cost_increase"])}</div></div>',
                    unsafe_allow_html=True,
                )
            with f2:
                st.markdown(
                    f'<div class="cm-mini-card"><div class="label">改定後の推奨月額</div><div class="value">{yen(future["recommended_price"])}</div><div class="delta-up">{signed_yen(future["price_increase"])}</div></div>',
                    unsafe_allow_html=True,
                )
            with f3:
                if current_price > 0:
                    st.markdown(
                        f'<div class="cm-mini-card"><div class="label">現在契約との差</div><div class="value">{yen(future["current_contract_gap"])}</div></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="cm-mini-card"><div class="label">時間原価の変化</div><div class="value">{signed_yen(future_labor_rate - labor_rate)}</div></div>',
                        unsafe_allow_html=True,
                    )
        else:
            st.caption("現在の実質人件費と異なる金額を入力すると、改定後の原価と推奨月額を表示します。")

    st.markdown(
        '<div class="cm-callout good"><strong>第一版の考え方：</strong>「面積 × 自社の作業効率」で必要人時を算出します。トイレ数、床材、什器、夜間作業などは現場差が大きいため、まずは自社実績に合わせた作業効率で調整してください。</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="cm-pro-card">
  <div class="cm-pro-eyebrow">CleanMargin Pro</div>
  <div class="cm-pro-title">この見積条件を保存して、次回は入力せずに使いたい方へ</div>
  <div class="cm-pro-copy">案件保存・自社設定保存・見積書PDFなどの業務向け機能を検討しています。先行案内と、必要な機能の希望を受け付けています。</div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.link_button(
        "Pro先行案内・機能希望を送る →",
        "https://docs.google.com/forms/d/e/1FAIpQLSe2vPhTK4t5R6Ui1uQDzSz0sf1BpHmFjDhweEuIpW6hvFpyyg/viewform",
        use_container_width=True,
    )


# =============================================================================
# Existing simple calculator, retained as a secondary tool
# =============================================================================
with simple_tab:
    st.markdown('<div class="cm-section-title">単発清掃の原価・粗利</div>', unsafe_allow_html=True)
    st.markdown('<div class="cm-section-sub">ハウスクリーニングや単発案件の原価・目標価格・値引き余地を確認します。</div>', unsafe_allow_html=True)

    left, right = st.columns(2, gap="large")

    with left:
        with st.container(border=True):
            st.markdown("#### ① 自社の原価設定")
            simple_labor_rate = st.number_input("実質人件費（円/人時）", min_value=0, value=2000, step=100, key="simple_labor")
            vehicle_rate = st.number_input("車両コスト（円/km）", min_value=0.0, value=35.0, step=5.0, key="simple_vehicle")
            monthly_fixed = st.number_input("月間固定費（円）", min_value=0, value=60000, step=5000, key="simple_fixed")
            monthly_jobs = st.number_input("月間想定案件数", min_value=1, value=30, step=1, key="simple_jobs")
            minimum_margin_pct = st.slider("最低利益率", 0, 60, 15, 1, key="simple_min_margin")
            simple_target_margin_pct = st.slider("目標利益率", 0, 70, 30, 1, key="simple_target_margin")
            minimum_charge = st.number_input("最低受注額（円）", min_value=0, value=12000, step=1000, key="simple_min_charge")

    with right:
        with st.container(border=True):
            st.markdown("#### ② 案件条件")
            occupancy = st.selectbox("物件状態", list(condition_master["occupancy"].keys()), index=1, key="simple_occupancy")
            dirt = st.selectbox("汚れレベル", list(condition_master["dirt"].keys()), index=1, key="simple_dirt")
            pet = st.checkbox("ペットあり", key="simple_pet")
            simple_crew_size = st.number_input("作業人数", min_value=1, max_value=10, value=1, step=1, key="simple_crew")
            one_way_minutes = st.number_input("片道移動時間（分）", min_value=0, value=30, step=5, key="simple_minutes")
            one_way_km = st.number_input("片道距離（km）", min_value=0.0, value=10.0, step=1.0, key="simple_km")
            parking_cost = st.number_input("駐車費（円）", min_value=0, value=0, step=100, key="simple_parking")
            subcontract_cost = st.number_input("外注費（円）", min_value=0, value=0, step=1000, key="simple_subcontract")
            other_cost = st.number_input("その他変動費（円）", min_value=0, value=0, step=100, key="simple_other")

    with st.container(border=True):
        st.markdown("#### ③ 清掃内容")
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

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="cm-section-title">計算結果</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="cm-kpi-grid">
  <div class="cm-kpi"><div class="cm-kpi-label">推定総原価</div><div class="cm-kpi-value">{yen(simple_result['total_cost'])}</div></div>
  <div class="cm-kpi"><div class="cm-kpi-label">値引き下限</div><div class="cm-kpi-value">{yen(simple_result['minimum_price'])}</div></div>
  <div class="cm-kpi"><div class="cm-kpi-label">目標価格</div><div class="cm-kpi-value">{yen(simple_result['target_price'])}</div></div>
  <div class="cm-kpi"><div class="cm-kpi-label">強気価格</div><div class="cm-kpi-value">{yen(simple_result['aggressive_price'])}</div></div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.expander("原価内訳", expanded=False):
        st.markdown(
            f"""
<table class="cm-table">
  <thead><tr><th>項目</th><th>金額</th></tr></thead>
  <tbody>
    <tr><td>人件費</td><td>{yen(simple_result['labor_cost'])}</td></tr>
    <tr><td>材料費</td><td>{yen(simple_result['material_cost'])}</td></tr>
    <tr><td>車両費</td><td>{yen(simple_result['vehicle_cost'])}</td></tr>
    <tr><td>駐車費</td><td>{yen(simple_result['parking_cost'])}</td></tr>
    <tr><td>外注費</td><td>{yen(simple_result['subcontract_cost'])}</td></tr>
    <tr><td>その他変動費</td><td>{yen(simple_result['other_variable_cost'])}</td></tr>
    <tr><td>固定費配賦</td><td>{yen(simple_result['fixed_cost_allocation'])}</td></tr>
    <tr class="total"><td>総原価</td><td>{yen(simple_result['total_cost'])}</td></tr>
  </tbody>
</table>
""",
            unsafe_allow_html=True,
        )

    if simple_result["public_price_reference"] > 0:
        st.caption(
            f'公開価格参考の単純合計：{yen(simple_result["public_price_reference"])}。市場相場を保証するものではありません。'
        )

    with st.container(border=True):
        st.markdown("#### 値引きシミュレーター")
        offer = st.number_input(
            "顧客への提示価格（円）",
            min_value=0,
            value=int(simple_result["target_price"]),
            step=100,
            key="simple_offer",
        )
        sim = simulate_offer(offer, simple_result["total_cost"], settings.minimum_margin)
        s1, s2 = st.columns(2)
        with s1:
            st.markdown(
                f'<div class="cm-mini-card"><div class="label">提示価格での利益</div><div class="value">{yen(sim["profit"])}</div></div>',
                unsafe_allow_html=True,
            )
        with s2:
            st.markdown(
                f'<div class="cm-mini-card"><div class="label">提示価格での利益率</div><div class="value">{sim["margin"]:.1%}</div></div>',
                unsafe_allow_html=True,
            )
        if sim["acceptable"]:
            st.markdown('<div class="cm-callout good">設定した最低利益率を満たしています。</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="cm-callout bad">最低利益率を下回っています。値引きまたは原価を再確認してください。</div>', unsafe_allow_html=True)


# =============================================================================
# Product / privacy footer
# =============================================================================
st.markdown("<br>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown("#### Pro版で予定している機能")
    p1, p2, p3 = st.columns(3)
    p1.markdown("**案件を保存**  \n毎回同じ条件を入力せず、過去見積を再利用。")
    p2.markdown("**見積書PDF**  \n計算結果から、そのまま提出用見積へ。")
    p3.markdown("**自社設定を保存**  \n人件費・利益率・ロゴなどを固定。")

st.markdown(
    '<div class="cm-footer-note">CleanMargin 無料版では入力内容をサーバーに保存しません。計算結果は見積判断の補助としてご利用ください。</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="cm-return-home"><a href="https://username-namae.github.io/cleanmargin-site/" target="_blank" rel="noopener noreferrer">← CleanMarginホームページへ戻る</a></div>',
    unsafe_allow_html=True,
)

