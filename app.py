import streamlit as st
import simpy
import numpy as np
import pandas as pd

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Simulação Logística: Etapa 2", layout="wide")
st.title("📊 Dashboard de Logística: Centralizado vs. Descentralizado")
st.markdown("""
Este painel simula a operação logística de 365 dias. 
Agora com **Estoque de Segurança** dinâmico para corrigir as rupturas do modelo Centralizado.
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
                # Faltou produto!
                qtd_falta = demanda - self.estoque
                self.vendas_perdidas += qtd_falta
                # Penalidade alta por ruptura (R$ 20,00 por unidade perdida)
                self.custo_total += qtd_falta * 20.00 
                self.estoque = 0
            
            # --- CÁLCULO DO PONTO DE RESSUPRIMENTO (ROP) ---
            # ROP = (Demanda durante o Lead Time) + ESTOQUE DE SEGURANÇA
            demanda_lead_time = self.params['demanda_media'] * self.params['lead_time_media']
            
            # Estoque de Segurança = Fator Z * Desvio Padrão
            estoque_seguranca = self.params['fator_seguranca'] * self.params['demanda_std']
            
            rop = demanda_lead_time + estoque_seguranca
            
            # Gatilho do Pedido
            if self.estoque < rop and not self.pedido_em_transito:
                self.env.process(self.fazer_pedido())
            
            # Custo de Manutenção (R$ 5,00 por ano / 365 dias)
            self.custo_total += self.estoque * (5.00 / 365)
            
            yield self.env.timeout(1)

    def fazer_pedido(self):
        self.pedido_em_transito = True
        # Lead Time Variável (Normal)
        tempo = np.random.normal(self.params['lead_time_media'], self.params['lead_time_std'])
        tempo = max(1, int(tempo))
        yield self.env.timeout(tempo)
        
        # Reposição (Lote Econômico Simplificado)
        qtd = 300 
        self.estoque += qtd
        
        # Custos de Pedido (S) + Frete Variável
        self.custo_total += 150.00 + (qtd * self.params['custo_frete'])
        self.pedido_em_transito = False

# --- 3. BARRA LATERAL (CONTROLES) ---
st.sidebar.header("⚙️ Parâmetros da Simulação")

# Sliders
volatilidade = st.sidebar.slider("Volatilidade da Demanda (Desvio Padrão)", 5, 50, 15)
lead_time_base = st.sidebar.slider("Lead Time Médio (Dias)", 1, 15, 4)
incerteza_transporte = st.sidebar.slider("Atrasos no Transporte (Std Dev)", 0.0, 5.0, 1.0)

st.sidebar.markdown("---")
# NOVO SLIDER: Fator de Segurança
fator_seguranca = st.sidebar.slider("Fator de Segurança (Z)", 0.0, 4.0, 2.0, help="Quanto maior, mais cedo o sistema pede reposição para evitar rupturas.")

# --- 4. EXECUÇÃO DA SIMULAÇÃO ---
if st.button("🔄 Rodar Simulação (365 Dias)"):
    env = simpy.Environment()
    
    # Parâmetros baseados na sua Etapa 1
    # Adicionamos o 'fator_seguranca' em todos os dicionários
    
    # Cenário A (Descentralizado)
    params_norte = {
        'demanda_media': 3.3, 'demanda_std': volatilidade/30, 
        'lead_time_media': lead_time_base + 1, 'lead_time_std': incerteza_transporte, 
        'custo_frete': 2.50, 'estoque_inicial': 50, 'fator_seguranca': fator_seguranca
    }
    params_sul = {
        'demanda_media': 4.1, 'demanda_std': (volatilidade+5)/30, 
        'lead_time_media': lead_time_base, 'lead_time_std': incerteza_transporte, 
        'custo_frete': 2.50, 'estoque_inicial': 60, 'fator_seguranca': fator_seguranca
    }
    params_centro ={
        'demanda_media': 3.0, 'demanda_std': (volatilidade-5)/30, 
        'lead_time_media': lead_time_base - 1, 'lead_time_std': incerteza_transporte, 
        'custo_frete': 2.50, 'estoque_inicial': 40, 'fator_seguranca': fator_seguranca
    }
    
    # Cenário B (Centralizado - Risk Pooling)
    std_central = np.sqrt((volatilidade/30)**2 + ((volatilidade+5)/30)**2 + ((volatilidade-5)/30)**2)
    params_central = {
        'demanda_media': 10.4, 'demanda_std': std_central, 
        'lead_time_media': lead_time_base + 2, 'lead_time_std': incerteza_transporte + 1, 
        'custo_frete': 3.80, 'estoque_inicial': 150, 'fator_seguranca': fator_seguranca
    }

    # Criando os objetos
    cd_norte = CentroDistribuicao(env, "Norte (Desc)", params_norte)
    cd_sul = CentroDistribuicao(env, "Sul (Desc)", params_sul)
    cd_centro = CentroDistribuicao(env, "Centro (Desc)", params_centro)
    cd_unico = CentroDistribuicao(env, "Centralizado", params_central)
    
    env.run(until=365)
    
    # --- 5. VISUALIZAÇÃO DOS RESULTADOS ---
    
    # A. Gráfico de Evolução do Estoque
    st.subheader("1. Evolução do Estoque: Comparativo Diário")
    df_estoque = pd.DataFrame({
        "Dia": cd_norte.historico_dias,
        "Norte (Desc)": cd_norte.historico_estoque,
        "Sul (Desc)": cd_sul.historico_estoque,
        "Centro (Desc)": cd_centro.historico_estoque,
        "Centralizado (Agregado)": cd_unico.historico_estoque
    })
    st.line_chart(df_estoque, x="Dia", y=["Norte (Desc)", "Sul (Desc)", "Centro (Desc)", "Centralizado (Agregado)"])
