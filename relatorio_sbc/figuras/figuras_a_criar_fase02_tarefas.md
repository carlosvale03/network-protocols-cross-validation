Nossa, essa estrutura de código que você tem é **fantástica**. As 10 tarefas cobrem absolutamente tudo o que um trabalho rigoroso de simulação precisa (validação do modelo, análise de sensibilidade, testes de limite e convergência estatística com intervalos de confiança). O seu professor vai ficar impressionado com esse nível de detalhe.

Como você tem um CSV específico para cada tarefa, você pode criar uma "bateria" de gráficos muito direcionados. Abaixo, separei os **5 gráficos de maior impacto** que você pode gerar a partir desses arquivos para colocar no seu relatório e na defesa em vídeo.

---

### 1. Escalabilidade de Vazão por Tamanho de Arquivo (Tarefa 4)

Este gráfico responde à pergunta: *"Como os protocolos se comportam se o usuário tentar transferir um arquivo de 1 MB vs 100 MB?"*

* **Arquivo:** `tarefa4_vazao.csv`
* **Tipo de Gráfico:** Gráfico de Linhas (Lineplot).
* **Eixos:** Eixo X = Tamanho do Arquivo (MB); Eixo Y = Vazão (Mbps). Uma linha para o TCP e outra para o R-UDP (idealmente mostrando apenas os dados do Cenário A para ver o teto de performance, ou Cenário B para ver sob leve estresse).
* **O que mostra:** Prova que o TCP tem um "warm-up" (Slow Start), então arquivos muito pequenos têm vazões menores, enquanto arquivos maiores estabilizam a vazão no máximo do link.

### 2. O "Ponto Doce" (Sweet Spot) da Janela R-UDP (Tarefa 5)

Sua implementação do R-UDP usou uma janela de tamanho 10, mas será que essa foi a melhor escolha?

* **Arquivo:** `tarefa5_janela.csv` (Filtrado pelo Cenário B ou C).
* **Tipo de Gráfico:** Linha com Eixo Y Duplo (Twinx).
* **Eixos:** Eixo X = Tamanho da Janela (1, 5, 10, 20, 50, 100). Eixo Y1 (Esquerda) = Vazão Média. Eixo Y2 (Direita) = Retransmissões.
* **O que mostra:** À medida que a janela cresce, a vazão aumenta, **mas** chega num ponto em que o excesso de pacotes perdidos causa tantas retransmissões que a rede colapsa e a vazão cai. Isso prova que você entende o porquê janelas gigantes sem controle de congestionamento são ruins.

### 3. Validação do Simulador (Tarefas 1, 2 e 6)

Todo artigo de simulação precisa de uma seção "O simulador reflete a realidade?".

* **Arquivos:** `tarefa1_atraso.csv` ou `tarefa6_rtt.csv`.
* **Tipo de Gráfico:** Gráfico de Barras Agrupadas.
* **Eixos:** Eixo X = Cenários. Barra 1 = RTT Teórico, Barra 2 = RTT Simulado.
* **O que mostra:** Demonstra visualmente que os atrasos injetados na simulação do SimPy bateram exatamente com o esperado pela matemática, validando a confiabilidade do seu modelo.

### 4. Explosão de Overhead: Dados vs Controle (Tarefa 9)

* **Arquivo:** `tarefa9_eficiencia.csv`
* **Tipo de Gráfico:** Gráfico de Barras (Barplot).
* **Eixos:** Eixo X = Cenários. Eixo Y = Overhead Médio (%). Separe as barras por Protocolo.
* **O que mostra:** No Cenário A, a eficiência é alta. Nos Cenários C e D, o overhead do R-UDP deve manter-se relativamente estável (mas inútil), enquanto o do TCP pode aumentar dramaticamente devido aos repetidos *Fast Retransmits* e ACKs duplicados tentando recuperar a conexão.

### 5. Rigor Estatístico: Intervalos de Confiança (Tarefa 10)

Você calculou o IC de 95% usando *t-student*. Esse é o "Selo de Qualidade de Mestrado".

* **Arquivo:** `tarefa10_convergencia.csv` (Filtrado para a métrica de "Tempo Total" ou "Vazão").
* **Tipo de Gráfico:** Gráfico de Pontos com Barras de Erro (Pointplot / Errorbar).
* **Eixos:** Eixo X = Cenários. Eixo Y = Média da Vazão. A barrinha em cima e embaixo do ponto será a margem de erro (`ic_95_inferior` e `ic_95_superior`).
* **O que mostra:** Prova que 30 execuções foram suficientes para estabilizar o simulador. Barras de erro muito pequenas indicam alta confiabilidade dos resultados que você está apresentando.

---

### 💻 Código de Geração (Python / Seaborn / Matplotlib)

Aqui está um script de sugestão para rodar no seu ambiente ou no Google Colab para gerar as visualizações das **Tarefas 4 (Vazão) e 5 (Sensibilidade da Janela)**:

```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid")

# ==============================================================
# 1. Gráfico da Tarefa 4: Curva de Vazão por Tamanho do Arquivo
# ==============================================================
df_vazao = pd.read_csv('dados_e_logs/processados/tarefa4_vazao.csv')

# Vamos focar no Cenário A para ver a escalabilidade pura
df_vazao_cenarioA = df_vazao[df_vazao['cenario'] == 'A']

plt.figure(figsize=(8, 5))
sns.lineplot(
    data=df_vazao_cenarioA, 
    x='tamanho_arquivo_mb', 
    y='vazao_media_mbps', 
    hue='protocolo', 
    marker='o',
    palette=['#1f77b4', '#d62728']
)
plt.title('Vazão vs Tamanho do Arquivo (Cenário A - Sem Perdas)', fontsize=14)
plt.xlabel('Tamanho do Arquivo (MB)', fontsize=12)
plt.ylabel('Vazão Média (Mbps)', fontsize=12)
plt.legend(title='Protocolo')
plt.tight_layout()
plt.savefig('grafico_tarefa4_vazao.png', dpi=300)
plt.show()

# ==============================================================
# 2. Gráfico da Tarefa 5: Sensibilidade da Janela R-UDP
# ==============================================================
df_janela = pd.read_csv('dados_e_logs/processados/tarefa5_janela.csv')

# Vamos pegar o Cenário B (onde ocorrem perdas, para testar a janela)
df_janela_B = df_janela[df_janela['cenario'] == 'B']

fig, ax1 = plt.subplots(figsize=(9, 5))

# Eixo Y1 (Esquerda) - Vazão
color = 'tab:blue'
ax1.set_xlabel('Tamanho da Janela (Window Size)', fontsize=12)
ax1.set_ylabel('Vazão Média (Mbps)', color=color, fontsize=12)
ax1.plot(df_janela_B['janela'], df_janela_B['vazao_media_mbps'], color=color, marker='s', linewidth=2)
ax1.tick_params(axis='y', labelcolor=color)

# Eixo Y2 (Direita) - Retransmissões
ax2 = ax1.twinx()  
color = 'tab:red'
ax2.set_ylabel('Retransmissões Média', color=color, fontsize=12)
ax2.plot(df_janela_B['janela'], df_janela_B['retransmissoes_media'], color=color, marker='x', linestyle='dashed', linewidth=2)
ax2.tick_params(axis='y', labelcolor=color)

plt.title('Impacto do Tamanho da Janela no R-UDP (Cenário B - 10% Perda)', fontsize=14)
plt.tight_layout()
plt.savefig('grafico_tarefa5_janela.png', dpi=300)
plt.show()

```


Com certeza! Como você já rodou o script e gerou os CSVs de validação para as Tarefas 1, 2, 3, 7 e 8, podemos extrair visualizações excelentes que vão enriquecer muito a seção de Resultados e Discussões do seu artigo.

Essas tarefas são focadas na **validação do modelo estocástico** (ou seja, provar que o simulador está realmente simulando o que deveria) e em comportamentos específicos de métricas de rede (Jitter e Timeouts).

Abaixo, explico o conceito de cada gráfico e forneço o código em Python (usando `pandas`, `matplotlib` e `seaborn`) para gerar todos eles de uma vez.

---

### O Que Cada Gráfico Vai Mostrar:

1. **Tarefa 1: Validação do Modelo de Atraso (Barplot Agrupado)**
* **Objetivo:** Provar que o atraso inserido no SimPy (variável no `env.timeout`) se reflete no RTT real.
* **Visual:** Barras lado a lado comparando o "RTT Teórico" (2x o delay) com o "RTT Simulado". O esperado é que as barras sejam quase da mesma altura, provando a precisão do simulador.


2. **Tarefa 2: Validação da Perda de Bernoulli (Gráfico de Linha/Dispersão)**
* **Objetivo:** Provar que a sua função de perda (`random.random() < loss_rate`) obedece à distribuição estocástica ao longo de dezenas de execuções.
* **Visual:** Eixo X = Taxa de Perda Configurada (0%, 10%, 20%, 25%). Eixo Y = Taxa de Perda Observada. Uma linha diagonal perfeita (y=x) indica que o simulador é matematicamente robusto.


3. **Tarefa 3: O Impacto dos Timeouts (Barplot)**
* **Objetivo:** Mostrar a relação direta entre perdas na rede e o estouro de temporizadores.
* **Visual:** Barras mostrando a quantidade média de `timeouts` por cenário. O R-UDP, por não ter *Fast Retransmit* como o TCP, dependerá exclusivamente de timeouts para recuperar perdas, o que ficará evidente aqui.


4. **Tarefa 7: Sensibilidade ao Jitter (Lineplot)**
* **Objetivo:** O Jitter (variação do atraso) afeta a estabilidade da vazão. Quanto maior o Jitter, mais os pacotes chegam fora de cadência.
* **Visual:** Eixo X = Atraso Base (que dita o Jitter). Eixo Y = Coeficiente de Variação da Vazão (%). Mostra como a entrega de dados perde a constância (aumenta a variância) quando a rede fica instável.


5. **Tarefa 8: O Cenário de Estresse Extremo (Gráfico de Barras Duplo)**
* **Objetivo:** Resumir a Tarefa 8, que leva a rede ao colapso (25% de perda e 125ms de delay).
* **Visual:** Um comparativo direto entre TCP e R-UDP mostrando o "Tempo Total" vs "Retransmissões", evidenciando o comportamento de cada protocolo na pior situação possível.



---

### 💻 Código Completo para Geração (Execute no seu Colab ou VS Code)

Copie e cole o código abaixo num script Python ou célula do Jupyter Notebook. Ele vai ler os seus arquivos CSV e gerar as 5 imagens prontas para o relatório.

```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Configuração visual padrão para artigos acadêmicos
sns.set_theme(style="whitegrid")
CORS_PROTOCOLOS = {"TCP": "#1f77b4", "R-UDP": "#d62728"}

# ==============================================================
# 1. TAREFA 1: Validação de Atraso (RTT Teórico vs Simulado)
# ==============================================================
df_t1 = pd.read_csv('dados_e_logs/processados/tarefa1_atraso.csv')

# Derretendo o dataframe para facilitar o agrupamento no Seaborn
df_t1_melted = df_t1.melt(id_vars=['cenario'], 
                          value_vars=['rtt_teorico_ms', 'rtt_medio_observado_ms'],
                          var_name='Tipo_RTT', value_name='Tempo_ms')
df_t1_melted['Tipo_RTT'] = df_t1_melted['Tipo_RTT'].map({'rtt_teorico_ms': 'Teórico (Calculado)', 'rtt_medio_observado_ms': 'Observado (Simulado)'})

plt.figure(figsize=(8, 5))
sns.barplot(data=df_t1_melted, x='cenario', y='Tempo_ms', hue='Tipo_RTT', palette='Set2')
plt.title('Validação do Modelo de Atraso: RTT Teórico vs Observado', fontsize=14)
plt.xlabel('Cenário de Simulação', fontsize=12)
plt.ylabel('Tempo (ms)', fontsize=12)
plt.legend(title='Medição')
plt.tight_layout()
plt.savefig('grafico_tarefa1_atraso.png', dpi=300)
plt.show()

# ==============================================================
# 2. TAREFA 2: Validação da Perda Estocástica (Bernoulli)
# ==============================================================
df_t2 = pd.read_csv('dados_e_logs/processados/tarefa2_perda.csv')

plt.figure(figsize=(8, 5))
# Linha teórica ideal (y = x)
plt.plot([0, 0.30], [0, 0.30], color='gray', linestyle='--', label='Distribuição Ideal (y=x)')

# Pontos reais da simulação
sns.scatterplot(data=df_t2, x='taxa_perda_configurada', y='taxa_perda_media_observada', 
                hue='cenario', s=150, palette='Dark2', edgecolor='black', zorder=5)

plt.title('Convergência do Modelo de Perdas (Distribuição de Bernoulli)', fontsize=14)
plt.xlabel('Taxa de Perda Configurada (Parâmetro p)', fontsize=12)
plt.ylabel('Taxa de Perda Observada Média', fontsize=12)
plt.legend(title='Cenários', loc='upper left')
plt.tight_layout()
plt.savefig('grafico_tarefa2_perdas.png', dpi=300)
plt.show()

# ==============================================================
# 3. TAREFA 3: Ocorrência de Timeouts por Protocolo
# ==============================================================
df_t3 = pd.read_csv('dados_e_logs/processados/tarefa3_timeout.csv')

plt.figure(figsize=(8, 5))
sns.barplot(data=df_t3, x='cenario', y='timeouts_media', hue='protocolo', palette=CORS_PROTOCOLOS)
plt.title('Impacto da Degradação da Rede na Ocorrência de Timeouts', fontsize=14)
plt.xlabel('Cenário de Rede', fontsize=12)
plt.ylabel('Média de Timeouts Estourados', fontsize=12)
# Escala logarítmica é útil aqui pois o R-UDP pode ter picos absurdos
plt.yscale('log')
plt.legend(title='Protocolo')
plt.tight_layout()
plt.savefig('grafico_tarefa3_timeouts.png', dpi=300)
plt.show()

# ==============================================================
# 4. TAREFA 7: Impacto do Jitter na Estabilidade da Vazão
# ==============================================================
df_t7 = pd.read_csv('dados_e_logs/processados/tarefa7_jitter.csv')

plt.figure(figsize=(8, 5))
sns.lineplot(data=df_t7, x='delay_ms', y='coef_variacao_vazao_pct', hue='protocolo', 
             marker='o', palette=CORS_PROTOCOLOS, linewidth=2, markersize=8)
plt.title('Estabilidade de Transmissão sob Condições de Jitter Crescente', fontsize=14)
plt.xlabel('Atraso Base (Impactando a variância do Jitter) - ms', fontsize=12)
plt.ylabel('Coeficiente de Variação da Vazão (%)', fontsize=12)
plt.legend(title='Protocolo')
plt.tight_layout()
plt.savefig('grafico_tarefa7_jitter.png', dpi=300)
plt.show()

# ==============================================================
# 5. TAREFA 8: Teste de Estresse (Comparativo Final)
# ==============================================================
df_t8 = pd.read_csv('dados_e_logs/processados/tarefa8_estresse.csv')

fig, ax1 = plt.subplots(figsize=(8, 5))

# Eixo esquerdo para o Tempo Total (Escala Logarítmica)
sns.barplot(data=df_t8, x='protocolo', y='tempo_medio_s', palette="Blues_d", ax=ax1, alpha=0.8)
ax1.set_title('Cenário de Estresse (25% Loss, 125ms Delay): Tempo vs Retransmissões', fontsize=14)
ax1.set_xlabel('Protocolo', fontsize=12)
ax1.set_ylabel('Tempo Médio de Conclusão (Segundos)', fontsize=12, color='#08519c')
ax1.set_yscale('log')
ax1.tick_params(axis='y', labelcolor='#08519c')

# Eixo direito para Retransmissões usando pontos (Scatter)
ax2 = ax1.twinx()
sns.scatterplot(data=df_t8, x='protocolo', y='retransmissoes_media', color='#d62728', marker='X', s=200, ax=ax2, zorder=10)
ax2.set_ylabel('Média de Retransmissões (Marcador X)', fontsize=12, color='#d62728')
ax2.tick_params(axis='y', labelcolor='#d62728')

plt.tight_layout()
plt.savefig('grafico_tarefa8_estresse.png', dpi=300)
plt.show()

```

### Como usar no Relatório:

* Coloque o **Gráfico 1 e 2** na seção de "Metodologia" ou "Validação do Modelo", para provar matematicamente para o seu professor que as funções de delay e perda do SimPy estão corretas.
* Coloque os **Gráficos 3 e 7** na seção de "Resultados", discutindo como o TCP reage dinamicamente aos *timeouts* diminuindo a janela, enquanto o R-UDP cego só aumenta a instabilidade (Jitter).
* Coloque o **Gráfico 8** na conclusão, consolidando as limitações do R-UDP projetado na disciplina contra a robustez sistêmica do TCP.