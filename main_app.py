import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from config import SystemConfig
from database.connection import get_db_connection
from core.paper_trading import PaperTradingEngine

st.set_page_config(
    page_title="Scanner de Oportunidades Ao Vivo",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        .stApp { padding: 0.5rem; }
        .metric-card {
            background-color: #1e222d;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
            border-left: 4px solid #00e676;
        }
        .grade-a-plus { color: #00e676; font-weight: bold; }
        .grade-a { color: #29b6f6; font-weight: bold; }
        .grade-b { color: #ffca28; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

def utc_to_brt_str(utc_iso_str: str) -> str:
    if not utc_iso_str:
        return "N/A"
    try:
        dt_utc = datetime.fromisoformat(utc_iso_str.replace("Z", "+00:00"))
        dt_brt = dt_utc.astimezone(timezone(timedelta(hours=-3)))
        return dt_brt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return utc_iso_str

st.title("⚽ Live Scanner Mobile")
config = SystemConfig()

now_brt = datetime.now(timezone(timedelta(hours=-3))).strftime("%H:%M:%S")
st.caption(f"📍 Modo: **{config.ENV}** | Fuso: **Horário de Brasília ({now_brt})**")

conn = get_db_connection(config.DB_PATH)
cursor = conn.cursor()
paper_engine = PaperTradingEngine()

tab1, tab2, tab3 = st.tabs(["🔥 Ao Vivo", "📈 Performance", "📜 Histórico"])

with tab1:
    st.subheader("Partidas Ao Vivo")
    cursor.execute("SELECT * FROM raw_fixtures_snapshot WHERE live_eligible = 1")
    live_rows = cursor.fetchall()

    if not live_rows:
        st.info("0 PARTIDAS AO VIVO DE FATO NO MOMENTO.")
    else:
        st.success(f"{len(live_rows)} Partida(s) Válida(s) em Andamento")
        for row in live_rows:
            f_id, league, teams, min_val, score, snapshot_json, coll_at, _ = row
            st.markdown(f"""
                <div class="metric-card">
                    <h4>{teams} ({min_val}')</h4>
                    <p><b>Placar:</b> {score} | <b>Campeonato:</b> {league}</p>
                    <small>Última atualização: {utc_to_brt_str(coll_at)} BRT</small>
                </div>
            """, unsafe_allow_html=True)

with tab2:
    st.subheader("Performance — Paper Trading (Apostas Virtuais)")
    perf = paper_engine.get_performance_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Banca Atual", f"R$ {perf['current_bankroll']:.2f}", delta=f"R$ {perf['net_profit']:.2f}")
    col2.metric("ROI Realizado", f"{perf['roi']:.2f}%")
    col3.metric("Win Rate", f"{perf['win_rate']:.1f}%")
    col4.metric("Max Drawdown", f"{perf['max_drawdown']:.2f}%")

    st.markdown("---")
    st.write("### Desempenho por Graduação de Sinal")
    
    grade_data = []
    for g, metrics in perf["by_grade"].items():
        grade_data.append({
            "Classe": g, "Sinais": metrics["signals"], "Vitórias": metrics["wins"],
            "Derrotas": metrics["losses"], "Win Rate": f"{metrics['win_rate']:.1f}%",
            "Lucro (R$)": f"R$ {metrics['profit']:.2f}", "ROI (%)": f"{metrics['roi']:.2f}%",
            "Odd Média": metrics["avg_odd"], "EV Médio": f"{metrics['avg_ev']:.1f}%"
        })
    st.dataframe(pd.DataFrame(grade_data), use_container_width=True)

with tab3:
    st.subheader("Histórico Auditável de Sinais")
    cursor.execute("SELECT * FROM engine_evaluations ORDER BY id DESC LIMIT 20")
    evals = cursor.fetchall()
    
    if not evals:
        st.info("Nenhum sinal gerado até o momento.")
    else:
        for ev in evals:
            ev_id, f_id, m_name, min_v, p_score, prob_e, odd_v, prob_i, edge_v, ev_v, grade, reasons_json, coll_at = ev
            st.markdown(f"""
                <div class="metric-card">
                    <b>{m_name} ({min_v}')</b> - Classe <span class="grade-a">{grade}</span><br>
                    <b>Odd:</b> {odd_v} | <b>Prob. Estimada:</b> {prob_e}% | <b>Implícita:</b> {prob_i}%<br>
                    <b>Edge:</b> +{edge_v} pp | <b>EV Esperado:</b> +{ev_v}% | <b>Pressão:</b> {p_score}/100<br>
                    <small>Registrado em: {utc_to_brt_str(coll_at)} BRT</small>
                </div>
            """, unsafe_allow_html=True)
