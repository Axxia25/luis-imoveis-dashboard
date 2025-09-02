"""
DASHBOARD STREAMLIT - LUIS IMÓVEIS
Sistema expandido de análise de leads - VERSÃO CORRIGIDA
Deploy: Streamlit Cloud
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import gspread
from google.oauth2.service_account import Credentials
import json
import os
from datetime import datetime, timedelta
import pytz

# Configuração da página
st.set_page_config(
    page_title="Dashboard Luis Imóveis",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configurações
PLANILHA_ID = "1xtn9-jreUtGPRh_ZQUaeNHq253iztZwXJ8uSmDc2_gc"
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

@st.cache_data(ttl=300)  # Cache por 5 minutos
def get_data_from_sheets():
    """Carrega dados da planilha Google - MÉTODO MELHORADO"""
    try:
        # Configurar credenciais
        creds_dict = dict(st.secrets['GOOGLE_CREDENTIALS'])
        
        # Criar credenciais e cliente
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(PLANILHA_ID)
        
        # Busca por abas existentes
        worksheet_names = ['Leads_Todos_Imoveis', 'Leads_Lancamentos', 'Sheet1']
        worksheet = None
        
        for name in worksheet_names:
            try:
                worksheet = sheet.worksheet(name)
                break
            except:
                continue
        
        if not worksheet:
            st.error("Nenhuma aba encontrada na planilha")
            return pd.DataFrame()
        
        # CORREÇÃO: Usar get_all_values() ao invés de get_all_records()
        # para garantir que todas as linhas sejam capturadas
        all_values = worksheet.get_all_values()
        
        if not all_values or len(all_values) < 2:
            st.warning("Planilha encontrada, mas sem dados suficientes")
            return pd.DataFrame()
        
        # Separar cabeçalho da primeira linha
        headers = all_values[0]
        data_rows = all_values[1:]
        
        # Filtrar linhas completamente vazias
        data_rows = [row for row in data_rows if any(cell.strip() for cell in row)]
        
        if not data_rows:
            st.warning("Nenhuma linha de dados encontrada")
            return pd.DataFrame()
        
        # Criar DataFrame garantindo que todas as colunas tenham o mesmo tamanho
        max_cols = len(headers)
        processed_rows = []
        
        for row in data_rows:
            # Preencher colunas faltantes com string vazia
            while len(row) < max_cols:
                row.append('')
            # Truncar se houver colunas extras
            row = row[:max_cols]
            processed_rows.append(row)
        
        df = pd.DataFrame(processed_rows, columns=headers)
        
        # Remover linhas onde todas as colunas essenciais estão vazias
        essential_cols = ['Data/Hora', 'Nome', 'Telefone']
        mask = df[essential_cols].apply(lambda x: x.str.strip() if x.dtype == 'object' else x, axis=0)
        mask = mask.apply(lambda row: any(row != ''), axis=1)
        df = df[mask]
        
        if df.empty:
            st.warning("Nenhum dado válido encontrado após limpeza")
            return df
        
        # Processamento dos dados
        df['Data/Hora'] = pd.to_datetime(df['Data/Hora'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        
        # Tratar coluna de interesse (pode vir como TRUE/sim/true/yes)
        if 'Interesse Visita' in df.columns:
            df['Interesse_Bool'] = df['Interesse Visita'].astype(str).str.lower().isin(['true', 'sim', 'yes', '1'])
        else:
            df['Interesse_Bool'] = False
        
        # Identifica tipo do imóvel se não existe a coluna ou está vazia
        if 'Tipo Imóvel' not in df.columns or df['Tipo Imóvel'].isna().all() or (df['Tipo Imóvel'] == '').all():
            df['Tipo Imóvel'] = df['Imóvel/Referência'].apply(identify_property_type)
        
        # Garantir que Status existe
        if 'Status' not in df.columns:
            df['Status'] = 'Novo'
        
        st.info(f"✅ Dados carregados: {len(df)} leads encontrados (incluindo linha {len(all_values)-1})")
        
        return df
        
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

def identify_property_type(reference):
    """Identifica tipo do imóvel pela referência"""
    if pd.isna(reference) or reference == '':
        return 'Indefinido'
    
    ref = str(reference).upper().strip()
    
    if ref.startswith('CA'):
        return 'Casa'
    elif ref.startswith('AP'):
        return 'Apartamento'
    elif ref.startswith('TR'):
        return 'Terreno'
    elif ref.startswith('CO'):
        return 'Comercial'
    elif ref in ['WIND OCEANICA', 'TRESOR CAMBOINHAS']:
        return 'Lançamento'
    
    # Busca por palavras-chave
    if 'CASA' in ref:
        return 'Casa'
    elif any(word in ref for word in ['APARTAMENTO', 'APT']):
        return 'Apartamento'
    elif 'TERRENO' in ref:
        return 'Terreno'
    elif any(word in ref for word in ['COMERCIAL', 'LOJA', 'SALA']):
        return 'Comercial'
    elif any(word in ref for word in ['LANÇAMENTO', 'LANCAMENTO']):
        return 'Lançamento'
    
    return 'Outros'

def create_metrics_cards(df):
    """Cria cards de métricas principais"""
    if df.empty:
        st.warning("Nenhum dado encontrado")
        return
    
    total_leads = len(df)
    interesse_leads = df['Interesse_Bool'].sum()
    taxa_interesse = (interesse_leads / total_leads * 100) if total_leads > 0 else 0
    
    # Contadores por tipo
    tipos_count = df['Tipo Imóvel'].value_counts().to_dict()
    
    # Lançamentos específicos para compatibilidade
    wind_count = len(df[df['Imóvel/Referência'] == 'Wind Oceanica'])
    tresor_count = len(df[df['Imóvel/Referência'] == 'Tresor Camboinhas'])
    
    # Exibir métricas com mais detalhes
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Leads", total_leads)
        st.metric("Taxa de Interesse", f"{taxa_interesse:.1f}%")
    
    with col2:
        st.metric("Interesse em Visita", interesse_leads)
        st.metric("Sem Interesse", total_leads - interesse_leads)
    
    with col3:
        st.metric("Lançamentos", tipos_count.get('Lançamento', 0))
        st.metric("Wind Oceanica", wind_count)
    
    with col4:
        st.metric("Tresor Camboinhas", tresor_count)
        st.metric("Imóveis Gerais", total_leads - wind_count - tresor_count)

def create_property_type_chart(df):
    """Gráfico de distribuição por tipo de imóvel - MELHORADO"""
    if df.empty:
        return
    
    tipos_count = df['Tipo Imóvel'].value_counts()
    
    # Cores personalizadas para cada tipo
    cores_tipos = {
        'Casa': '#3498db',
        'Apartamento': '#2ecc71', 
        'Lançamento': '#f39c12',
        'Terreno': '#9b59b6',
        'Comercial': '#e74c3c',
        'Outros': '#95a5a6'
    }
    
    colors = [cores_tipos.get(tipo, '#95a5a6') for tipo in tipos_count.index]
    
    fig = px.pie(
        values=tipos_count.values,
        names=tipos_count.index,
        title="Distribuição por Tipo de Imóvel",
        color_discrete_sequence=colors
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(height=400, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

def create_interest_analysis(df):
    """Análise de interesse por tipo - MELHORADO"""
    if df.empty:
        return
    
    interesse_por_tipo = df.groupby('Tipo Imóvel').agg({
        'Interesse_Bool': ['count', 'sum']
    }).round(2)
    
    interesse_por_tipo.columns = ['Total', 'Com_Interesse']
    interesse_por_tipo['Taxa_Interesse'] = (
        interesse_por_tipo['Com_Interesse'] / interesse_por_tipo['Total'] * 100
    ).round(1)
    interesse_por_tipo = interesse_por_tipo.reset_index()
    
    # Gráfico de barras melhorado
    fig = px.bar(
        interesse_por_tipo,
        x='Tipo Imóvel',
        y=['Total', 'Com_Interesse'],
        title="Interesse por Tipo de Imóvel",
        barmode='group',
        color_discrete_sequence=['#3498db', '#2ecc71'],
        text_auto=True
    )
    
    fig.update_layout(height=400, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    
    # Tabela de detalhes melhorada
    st.subheader("Detalhes por Tipo")
    
    # Adicionar coluna de performance
    interesse_por_tipo['Performance'] = interesse_por_tipo['Taxa_Interesse'].apply(
        lambda x: '🔥 Excelente' if x >= 80 else '👍 Boa' if x >= 60 else '⚠️ Regular' if x >= 40 else '🔴 Baixa'
    )
    
    # Tentar usar background_gradient se matplotlib estiver disponível
    try:
        import matplotlib
        styled_df = interesse_por_tipo.style.format({
            'Taxa_Interesse': '{:.1f}%'
        }).background_gradient(subset=['Taxa_Interesse'], cmap='RdYlGn')
        st.dataframe(styled_df, use_container_width=True)
    except ImportError:
        # Fallback sem background_gradient
        styled_df = interesse_por_tipo.style.format({
            'Taxa_Interesse': '{:.1f}%'
        })
        st.dataframe(styled_df, use_container_width=True)

def create_timeline_chart(df):
    """Gráfico de evolução temporal - MELHORADO"""
    if df.empty or df['Data/Hora'].isna().all():
        return
    
    # Agrupa por dia
    df_daily = df.set_index('Data/Hora').resample('D').agg({
        'Nome': 'count',
        'Interesse_Bool': 'sum'
    }).reset_index()
    
    df_daily.columns = ['Data', 'Total_Leads', 'Com_Interesse']
    df_daily = df_daily[df_daily['Total_Leads'] > 0]  # Remove dias sem leads
    
    if df_daily.empty:
        st.warning("Dados insuficientes para análise temporal")
        return
    
    # Calcular média móvel
    if len(df_daily) >= 3:
        df_daily['Media_Movel'] = df_daily['Total_Leads'].rolling(window=3, center=True).mean()
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Leads totais
    fig.add_trace(
        go.Scatter(
            x=df_daily['Data'],
            y=df_daily['Total_Leads'],
            mode='lines+markers',
            name='Total Leads',
            line=dict(color='#3498db', width=3),
            hovertemplate='<b>%{x}</b><br>Total Leads: %{y}<extra></extra>'
        ),
        secondary_y=False,
    )
    
    # Leads com interesse
    fig.add_trace(
        go.Scatter(
            x=df_daily['Data'],
            y=df_daily['Com_Interesse'],
            mode='lines+markers',
            name='Com Interesse',
            line=dict(color='#2ecc71', width=2),
            hovertemplate='<b>%{x}</b><br>Com Interesse: %{y}<extra></extra>'
        ),
        secondary_y=False,
    )
    
    # Média móvel (se disponível)
    if 'Media_Movel' in df_daily.columns:
        fig.add_trace(
            go.Scatter(
                x=df_daily['Data'],
                y=df_daily['Media_Movel'],
                mode='lines',
                name='Tendência (3 dias)',
                line=dict(color='#f39c12', width=1, dash='dash'),
                hovertemplate='<b>%{x}</b><br>Média Móvel: %{y:.1f}<extra></extra>'
            ),
            secondary_y=False,
        )
    
    fig.update_xaxes(title_text="Data")
    fig.update_yaxes(title_text="Número de Leads", secondary_y=False)
    fig.update_layout(
        title_text="Evolução de Leads ao Longo do Tempo", 
        height=400,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_referencia_analysis(df):
    """Análise das referências mais populares - MELHORADO"""
    if df.empty:
        return
    
    ref_count = df['Imóvel/Referência'].value_counts().head(10)
    
    if ref_count.empty:
        st.warning("Nenhuma referência encontrada")
        return
    
    # Adicionar informação de interesse para cada referência
    ref_with_interest = []
    for ref in ref_count.index:
        total = ref_count[ref]
        interesse = df[df['Imóvel/Referência'] == ref]['Interesse_Bool'].sum()
        taxa = (interesse / total * 100) if total > 0 else 0
        ref_with_interest.append({
            'Referência': ref,
            'Total': total,
            'Com_Interesse': interesse,
            'Taxa_Interesse': taxa
        })
    
    ref_df = pd.DataFrame(ref_with_interest)
    
    fig = px.bar(
        ref_df,
        x='Total',
        y='Referência',
        orientation='h',
        title="Top 10 Referências Mais Procuradas",
        color='Taxa_Interesse',
        color_continuous_scale='viridis',
        text='Total',
        hover_data=['Com_Interesse', 'Taxa_Interesse']
    )
    
    fig.update_layout(height=400)
    fig.update_traces(texttemplate='%{text}', textposition='outside')
    st.plotly_chart(fig, use_container_width=True)

def create_hourly_analysis(df):
    """Análise por horário - MELHORADO"""
    if df.empty or df['Data/Hora'].isna().all():
        return
    
    df_hourly = df.copy()
    df_hourly['Hora'] = df_hourly['Data/Hora'].dt.hour
    
    hourly_stats = df_hourly.groupby('Hora').agg({
        'Nome': 'count',
        'Interesse_Bool': 'sum'
    }).reset_index()
    
    hourly_stats.columns = ['Hora', 'Total', 'Com_Interesse']
    hourly_stats['Taxa_Interesse'] = (
        hourly_stats['Com_Interesse'] / hourly_stats['Total'] * 100
    ).round(1)
    
    # Identificar horários de pico
    pico_leads = hourly_stats['Total'].max()
    horarios_pico = hourly_stats[hourly_stats['Total'] == pico_leads]['Hora'].tolist()
    
    fig = px.line(
        hourly_stats,
        x='Hora',
        y=['Total', 'Com_Interesse'],
        title=f"Distribuição de Leads por Horário (Pico: {pico_leads} leads às {', '.join(map(str, horarios_pico))}h)",
        markers=True
    )
    
    fig.update_layout(height=400, xaxis_tickmode='linear')
    st.plotly_chart(fig, use_container_width=True)
    
    # Insights dos melhores horários
    if len(hourly_stats) > 0:
        melhor_horario = hourly_stats.loc[hourly_stats['Taxa_Interesse'].idxmax()]
        st.info(f"💡 **Melhor horário para conversão**: {melhor_horario['Hora']}:00h com {melhor_horario['Taxa_Interesse']:.1f}% de interesse")

def create_advanced_analysis(df):
    """Análises avançadas adicionais"""
    if df.empty:
        return
    
    st.subheader("📊 Análises Avançadas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Análise de fontes/origem
        if 'Origem' in df.columns:
            origem_stats = df['Origem'].value_counts()
            fig_origem = px.pie(
                values=origem_stats.values,
                names=origem_stats.index,
                title="Distribuição por Origem",
            )
            st.plotly_chart(fig_origem, use_container_width=True)
    
    with col2:
        # Análise de status
        if 'Status' in df.columns:
            status_stats = df['Status'].value_counts()
            fig_status = px.bar(
                x=status_stats.index,
                y=status_stats.values,
                title="Distribuição por Status",
                color=status_stats.values,
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig_status, use_container_width=True)

def main():
    """Função principal do dashboard"""
    
    # Header melhorado
    st.title("🏠 Dashboard Luis Imóveis")
    st.subheader("Sistema Expandido de Gestão de Leads - v2.1")
    
    # Sidebar com filtros
    st.sidebar.title("🎛️ Filtros")
    
    # Carrega dados
    with st.spinner("Carregando dados da planilha..."):
        df = get_data_from_sheets()
    
    if df.empty:
        st.error("Não foi possível carregar os dados da planilha")
        st.stop()
    
    # Filtros na sidebar
    tipos_disponiveis = ['Todos'] + list(df['Tipo Imóvel'].unique())
    tipo_selecionado = st.sidebar.selectbox("Filtrar por Tipo:", tipos_disponiveis)
    
    # Filtro de período
    if not df['Data/Hora'].isna().all():
        data_min = df['Data/Hora'].min().date()
        data_max = df['Data/Hora'].max().date()
        
        # Calcular período padrão baseado nos dados disponíveis
        periodo_padrao_inicio = max(data_min, data_max - timedelta(days=30))
        
        periodo = st.sidebar.date_input(
            "Período:",
            value=(periodo_padrao_inicio, data_max),
            min_value=data_min,
            max_value=data_max
        )
        
        # Aplicar filtro de período
        if len(periodo) == 2:
            mask = (df['Data/Hora'].dt.date >= periodo[0]) & (df['Data/Hora'].dt.date <= periodo[1])
            df = df[mask]
    
    # Filtro de interesse
    filtro_interesse = st.sidebar.radio(
        "Interesse em Visita:",
        ["Todos", "Apenas com interesse", "Apenas sem interesse"]
    )
    
    if filtro_interesse == "Apenas com interesse":
        df = df[df['Interesse_Bool'] == True]
    elif filtro_interesse == "Apenas sem interesse":
        df = df[df['Interesse_Bool'] == False]
    
    # Aplicar filtro de tipo
    if tipo_selecionado != 'Todos':
        df = df[df['Tipo Imóvel'] == tipo_selecionado]
    
    # Status do sistema
    st.success(f"✅ Sistema funcionando - {len(df)} leads encontrados")
    
    # Cards de métricas
    create_metrics_cards(df)
    
    # Layout em colunas
    col1, col2 = st.columns(2)
    
    with col1:
        create_property_type_chart(df)
        create_timeline_chart(df)
    
    with col2:
        create_interest_analysis(df)
        create_referencia_analysis(df)
    
    # Análise horária
    st.subheader("⏰ Análise por Horário")
    create_hourly_analysis(df)
    
    # Análises avançadas
    create_advanced_analysis(df)
    
    # Tabela de dados
    st.subheader("📋 Dados Detalhados")
    
    if not df.empty:
        # Preparar dados para exibição
        colunas_exibir = [
            'Data/Hora', 'Nome', 'Telefone', 'Imóvel/Referência',
            'Interesse Visita', 'Tipo Imóvel', 'Status'
        ]
        
        # Verificar quais colunas existem
        colunas_disponiveis = [col for col in colunas_exibir if col in df.columns]
        df_display = df[colunas_disponiveis].copy()
        
        # Formatar data
        if 'Data/Hora' in df_display.columns and not df_display['Data/Hora'].isna().all():
            df_display['Data/Hora'] = df_display['Data/Hora'].dt.strftime('%d/%m/%Y %H:%M')
        
        # Mostrar número total de registros
        st.info(f"📊 Mostrando {len(df_display)} registros de {len(get_data_from_sheets())} total")
        
        st.dataframe(df_display, use_container_width=True, height=400)
        
        # Botão de download
        csv = df_display.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f'leads_luis_imoveis_{datetime.now().strftime("%Y%m%d_%H%M")}.csv',
            mime='text/csv'
        )
    
    # Footer com informações
    st.markdown("---")
    st.markdown(
        f"**Sistema Expandido v2.1** | "
        f"Última atualização: {datetime.now(pytz.timezone('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M:%S')} | "
        f"Dados em tempo real da planilha Google | "
        f"🔄 Cache de 5 minutos"
    )

if __name__ == "__main__":
    main()
