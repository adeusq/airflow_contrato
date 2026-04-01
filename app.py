import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Anomalias — Contratos Ceará",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 Painel de Anomalias — Contratos Públicos do Ceará")
st.caption(f"Atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# ─────────────────────────────────────────────────────────────────────────────
# CONEXÃO COM SUPABASE
# ─────────────────────────────────────────────────────────────────────────────

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

# ─────────────────────────────────────────────────────────────────────────────
# MÉTRICAS DO TOPO
# ─────────────────────────────────────────────────────────────────────────────

resumo = df["nivel_risco"].value_counts().to_dict()
alto  = resumo.get("ALTO", 0)
medio = resumo.get("MEDIO", 0)
baixo = resumo.get("BAIXO", 0)
total = len(df)

col1, col2, col3, col4 = st.columns(4)
col1.metric("🔴 ALTO",   alto)
col2.metric("🟡 MÉDIO",  medio)
col3.metric("🟢 BAIXO",  baixo)
col4.metric("📋 Total",  total)

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# FILTROS
# ─────────────────────────────────────────────────────────────────────────────

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

# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICOS
# ─────────────────────────────────────────────────────────────────────────────

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

# ─────────────────────────────────────────────────────────────────────────────
# DISPERSÃO: VALOR x PRAZO
# ─────────────────────────────────────────────────────────────────────────────

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

# ─────────────────────────────────────────────────────────────────────────────
# TABELA DETALHADA
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Detalhamento das Anomalias")

df_exibir = df_filtrado[[
    "isn_sic", "nivel_risco", "percentil_risco", "score_anomalia",
    "valor_global", "prazo_vigencia_dias", "fornecedor_nome",
    "orgao_nome", "objeto", "data_assinatura"
]].rename(columns={
    "isn_sic":             "ISN SIC",
    "nivel_risco":         "Risco",
    "percentil_risco":     "Percentil",
    "score_anomalia":      "Score",
    "valor_global":        "Valor (R$)",
    "prazo_vigencia_dias": "Prazo (dias)",
    "fornecedor_nome":     "Fornecedor",
    "orgao_nome":          "Órgão",
    "objeto":              "Objeto",
    "data_assinatura":     "Assinatura",
})

st.dataframe(
    df_exibir.style.apply(
        lambda row: [
            "background-color: #fde8e8" if row["Risco"] == "ALTO"
            else "background-color: #fef9e7" if row["Risco"] == "MEDIO"
            else ""
        ] * len(row),
        axis=1,
    ),
    use_container_width=True,
    height=500,
)
