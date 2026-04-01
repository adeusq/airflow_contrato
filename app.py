import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import datetime

st.set_page_config(
    page_title="Anomalias — Contratos Ceará",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 Painel de Anomalias — Contratos Públicos do Ceará")
st.caption(f"Atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")


@st.cache_data(ttl=300)
def carregar_anomalias():
    try:
        conn = psycopg2.connect(
            host=st.secrets["db_host"],
            port=st.secrets["db_port"],
            database=st.secrets["db_name"],
            user=st.secrets["db_user"],
            password=st.secrets["db_password"],
        )
        df = pd.read_sql("""
            SELECT
                isn_sic,
                objeto,
                fornecedor_nome,
                orgao_nome,
                valor_global,
                prazo_vigencia_dias,
                score_anomalia,
                percentil_risco,
                nivel_risco,
                data_assinatura,
                detectado_em
            FROM anomalias_contratos
            ORDER BY score_anomalia ASC
        """, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Erro ao conectar no banco: {e}")
        return pd.DataFrame()


df = carregar_anomalias()

if df.empty:
    st.warning("Nenhuma anomalia encontrada ou banco ainda sem dados.")
    st.stop()

# ─── MÉTRICAS ─────────────────────────────────────────────────────────────────

resumo = df["nivel_risco"].value_counts().to_dict()
alto  = resumo.get("ALTO", 0)
medio = resumo.get("MEDIO", 0)
baixo = resumo.get("BAIXO", 0)
total = len(df)

col1, col2, col3, col4 = st.columns(4)
col1.metric("🔴 ALTO",  alto)
col2.metric("🟡 MÉDIO", medio)
col3.metric("🟢 BAIXO", baixo)
col4.metric("📋 Total", total)

st.divider()

# ─── FILTROS ──────────────────────────────────────────────────────────────────

col_f1, col_f2 = st.columns(2)

with col_f1:
    niveis = st.multiselect(
        "Filtrar por nível de risco",
        options=["ALTO", "MEDIO", "BAIXO"],
        default=["ALTO", "MEDIO", "BAIXO"],
    )

with col_f2:
    orgaos = st.multiselect(
        "Filtrar por órgão",
        options=sorted(df["orgao_nome"].dropna().unique()),
        default=[],
    )

df_filtrado = df[df["nivel_risco"].isin(niveis)]
if orgaos:
    df_filtrado = df_filtrado[df_filtrado["orgao_nome"].isin(orgaos)]

st.caption(f"{len(df_filtrado)} registros exibidos")

# ─── GRÁFICOS ─────────────────────────────────────────────────────────────────

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("Anomalias por nível de risco")
    fig_pizza = px.pie(
        df_filtrado,
        names="nivel_risco",
        color="nivel_risco",
        color_discrete_map={"ALTO": "#e74c3c", "MEDIO": "#f39c12", "BAIXO": "#2ecc71"},
        hole=0.4,
    )
    st.plotly_chart(fig_pizza, use_container_width=True)

with col_g2:
    st.subheader("Top 10 órgãos com mais anomalias")
    top_orgaos = (
        df_filtrado["orgao_nome"]
        .value_counts()
        .head(10)
        .reset_index()
        .rename(columns={"orgao_nome": "Orgao", "count": "Qtd"})
    )
    fig_bar = px.bar(
        top_orgaos,
        x="Qtd",
        y="Orgao",
        orientation="h",
        color="Qtd",
        color_continuous_scale="Reds",
    )
    fig_bar.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_bar, use_container_width=True)

# ─── DISPERSÃO ────────────────────────────────────────────────────────────────

st.subheader("Distribuição: Valor Global x Prazo de Vigência")
fig_scatter = px.scatter(
    df_filtrado,
    x="prazo_vigencia_dias",
    y="valor_global",
    color="nivel_risco",
    color_discrete_map={"ALTO": "#e74c3c", "MEDIO": "#f39c12", "BAIXO": "#2ecc71"},
    hover_data=["fornecedor_nome", "orgao_nome", "objeto"],
    labels={
        "prazo_vigencia_dias": "Prazo (dias)",
        "valor_global": "Valor Global (R$)",
        "nivel_risco": "Nível de Risco",
    },
)
st.plotly_chart(fig_scatter, use_container_width=True)

# ─── TABELA ───────────────────────────────────────────────────────────────────

st.subheader("Detalhamento das Anomalias")

# Formata valor em R$
df_filtrado = df_filtrado.copy()
df_filtrado["valor_fmt"] = df_filtrado["valor_global"].apply(
    lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(v) else "-"
)

# Badge de risco colorido
def badge_risco(risco):
    cores = {"ALTO": "🔴", "MEDIO": "🟡", "BAIXO": "🟢"}
    return f"{cores.get(risco, '')} {risco}"

df_filtrado["risco_fmt"] = df_filtrado["nivel_risco"].apply(badge_risco)

df_exibir = df_filtrado[[
    "isn_sic", "risco_fmt", "percentil_risco",
    "valor_fmt", "prazo_vigencia_dias",
    "fornecedor_nome", "orgao_nome", "objeto", "data_assinatura"
]].rename(columns={
    "isn_sic":             "ISN SIC",
    "risco_fmt":           "Risco",
    "percentil_risco":     "Percentil",
    "valor_fmt":           "Valor",
    "prazo_vigencia_dias": "Prazo (dias)",
    "fornecedor_nome":     "Fornecedor",
    "orgao_nome":          "Órgão",
    "objeto":              "Objeto",
    "data_assinatura":     "Assinatura",
})

# Cor de fundo por nível de risco
def colorir_linha(row):
    if "ALTO" in str(row["Risco"]):
        return ["background-color: #fde8e8; color: #333"] * len(row)
    elif "MEDIO" in str(row["Risco"]):
        return ["background-color: #fef9e7; color: #333"] * len(row)
    return ["background-color: #f0faf4; color: #333"] * len(row)

st.dataframe(
    df_exibir.style.apply(colorir_linha, axis=1),
    use_container_width=True,
    height=500,
    column_config={
        "ISN SIC":     st.column_config.NumberColumn(width="small"),
        "Risco":       st.column_config.TextColumn(width="small"),
        "Percentil":   st.column_config.ProgressColumn(min_value=0, max_value=100, width="small"),
        "Valor":       st.column_config.TextColumn(width="medium"),
        "Prazo (dias)":st.column_config.NumberColumn(width="small"),
        "Fornecedor":  st.column_config.TextColumn(width="large"),
        "Órgão":       st.column_config.TextColumn(width="small"),
        "Objeto":      st.column_config.TextColumn(width="large"),
        "Assinatura":  st.column_config.DateColumn(width="small"),
    }
)
