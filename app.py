import streamlit as st
import simpy
import numpy as np
import pandas as pd

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Simulação Logística: Etapa 2", layout="wide")
st.title("📊 Dashboard de Logística: Centralizado vs. Descentralizado")
st.markdown("""
Este painel simula a operação logística de 365 dias para comparar a robustez
da rede descentralizada (Cenário A) contra a centralizada (Cenário B) sob incerteza.
""")

# --- 2. CLASSE DE SIMULAÇÃO (O Motor) ---
class CentroDistribuicao:
    def __init__(self, env, nome, params):
        self.env = env
        self.nome = nome
        self.params = params
        self.estoque = params['estoque_inicial']
        self.pedido_em_transito = False
        
        # Coleta de Dados para o Gráfico
        self.historico_dias = []
        self.historico_estoque = []
        self.vendas_perdidas = 0
        self.custo_total = 0
        
        self.processo = env.process(self.rodar_dia_a_dia())

    def rodar_dia_a_dia(self):
        while True:
            # Registro de dados (Snapshot do dia)
            self.historico_dias.append(self.env.now)
            self.historico_estoque.append(self.estoque)
            
            # Demanda Estocástica (Normal)
            demanda = np.random.normal(self.params['demanda_media'], self.params['demanda_std'])
            demanda = max(0, int(demanda))
            
            # Consumo
            if self.estoque >= demanda:
                self.estoque -= demanda
            else:
                self.vendas_perdidas += (demanda - self.estoque)
                self.custo_total += (demanda - self.estoque) * 20.00 # Custo de Ruptura
                self.estoque = 0
            
            # Reposição (ROP)
            rop = self.params['demanda_media'] * self.params['lead_time_media']
            if self.estoque < rop and not self.pedido_em_transito:
                self.env.process(self.fazer_pedido())
            
            # Custo de Manutenção
            self.custo_total += self.estoque * (5.00 / 365)
            
            yield self.env.timeout(1)

    def fazer_pedido(self):
        self.pedido_em_transito = True
        # Lead Time Variável
        tempo = np.random.normal(self.params['lead_time_media'], self.params['lead_time_std'])
        tempo = max(1, int(tempo))
        yield self.env.timeout(tempo)
        
        qtd = 300 # Lote fixo simplificado
        self.estoque += qtd
        self.custo_total += 150.00 + (qtd * self.params['custo_frete'])
        self.pedido_em_transito = False

# --- 3. BARRA LATERAL (CONTROLES) ---
st.sidebar.header("⚙️ Parâmetros da Simulação")

# Sliders para "estressar" o modelo
volatilidade = st.sidebar.slider("Volatilidade da Demanda (Desvio Padrão)", 5, 50, 15)
lead_time_base = st.sidebar.slider("Lead Time Médio (Dias)", 1, 15, 4)
incerteza_transporte = st.sidebar.slider("Atrasos no Transporte (Desvio Pad.)", 0.0, 5.0, 1.0)

# --- 4. EXECUÇÃO DA SIMULAÇÃO ---
if st.button("🔄 Rodar Simulação (365 Dias)"):
    env = simpy.Environment()
    
    # Parâmetros baseados na sua Etapa 1
    # Cenário A (Descentralizado)
    params_norte = {'demanda_media': 3.3, 'demanda_std': volatilidade/30, 'lead_time_media': lead_time_base + 1, 'lead_time_std': incerteza_transporte, 'custo_frete': 2.50, 'estoque_inicial': 50}
    params_sul =   {'demanda_media': 4.1, 'demanda_std': (volatilidade+5)/30, 'lead_time_media': lead_time_base, 'lead_time_std': incerteza_transporte, 'custo_frete': 2.50, 'estoque_inicial': 60}
    params_centro ={'demanda_media': 3.0, 'demanda_std': (volatilidade-5)/30, 'lead_time_media': lead_time_base - 1, 'lead_time_std': incerteza_transporte, 'custo_frete': 2.50, 'estoque_inicial': 40}
    
    # Cenário B (Centralizado - Risk Pooling)
    # Soma das médias, mas raiz da soma dos quadrados dos desvios
    std_central = np.sqrt((volatilidade/30)**2 + ((volatilidade+5)/30)**2 + ((volatilidade-5)/30)**2)
    params_central = {'demanda_media': 10.4, 'demanda_std': std_central, 'lead_time_media': lead_time_base + 2, 'lead_time_std': incerteza_transporte + 1, 'custo_frete': 3.80, 'estoque_inicial': 150}

    # Criando os objetos
    cd_norte = CentroDistribuicao(env, "Norte (Desc)", params_norte)
    cd_sul = CentroDistribuicao(env, "Sul (Desc)", params_sul)
    cd_centro = CentroDistribuicao(env, "Centro (Desc)", params_centro)
    cd_unico = CentroDistribuicao(env, "Centralizado", params_central)
    
    env.run(until=365)
    
    # --- 5. VISUALIZAÇÃO DOS RESULTADOS ---
    
    # A. Gráfico de Evolução do Estoque (Line Chart)
    st.subheader("1. Evolução do Estoque: Comparativo Diário")
    
    # Montando DataFrame para o gráfico
    df_estoque = pd.DataFrame({
        "Dia": cd_norte.historico_dias,
        "Norte (Desc)": cd_norte.historico_estoque,
        "Sul (Desc)": cd_sul.historico_estoque,
        "Centro (Desc)": cd_centro.historico_estoque,
        "Centralizado (Agregado)": cd_unico.historico_estoque
    })
    st.line_chart(df_estoque, x="Dia", y=["Norte (Desc)", "Sul (Desc)", "Centro (Desc)", "Centralizado (Agregado)"])
    
    st.caption("Note como o estoque Centralizado (linha vermelha, usualmente) tende a ser mais estável e sofrer menos 'zeragens' (toques no fundo do gráfico) do que os regionais.")

    # B. Comparativo de Custos e Rupturas (KPIs)
    st.subheader("2. Resultado Financeiro e Nível de Serviço")
    
    col1, col2 = st.columns(2)
    
    # Cálculos Finais
    custo_total_A = cd_norte.custo_total + cd_sul.custo_total + cd_centro.custo_total
    rupturas_A = cd_norte.vendas_perdidas + cd_sul.vendas_perdidas + cd_centro.vendas_perdidas
    
    custo_total_B = cd_unico.custo_total
    rupturas_B = cd_unico.vendas_perdidas
    
    with col1:
        st.metric("Custo Total (Descentralizado)", f"R$ {custo_total_A:,.2f}", delta=f"{rupturas_A:.0f} Rupturas", delta_color="inverse")
    with col2:
        diff_custo = custo_total_B - custo_total_A
        st.metric("Custo Total (Centralizado)", f"R$ {custo_total_B:,.2f}", delta=f"{rupturas_B:.0f} Rupturas", delta_color="inverse")

    # C. Gráfico de Barras Comparativo
    data_custos = pd.DataFrame({
        "Cenário": ["Descentralizado", "Centralizado"],
        "Custo Total (R$)": [custo_total_A, custo_total_B],
        "Vendas Perdidas (Unid)": [rupturas_A, rupturas_B]
    })
    
    st.bar_chart(data_custos, x="Cenário", y="Custo Total (R$)")

    # D. Análise Automática
    if rupturas_A > rupturas_B:
        st.success(f"✅ Conclusão: O Cenário Centralizado evitou {rupturas_A - rupturas_B:.0f} rupturas a mais. O Risk Pooling funcionou!")
    else:
        st.warning("⚠️ Conclusão: A variabilidade foi baixa. O Cenário Descentralizado se manteve mais eficiente.")

else:
    st.info("Ajuste os parâmetros na barra lateral e clique em 'Rodar Simulação' para começar.")