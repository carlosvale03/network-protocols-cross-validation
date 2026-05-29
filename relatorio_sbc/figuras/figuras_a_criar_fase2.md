Excelente! A Fase 1 tratou do "mundo real" (Docker, Sockets, tc), onde você capturou pacotes um a um. Já a Fase 2 é uma **simulação estocástica**. A grande diferença aqui é que você tem **30 execuções para cada cenário**, o que significa que o foco dos seus gráficos agora deve ser **estatística, consistência e o comportamento macro dos protocolos sob estresse**.

Como você já tem o arquivo mágico `simulacao_resumo.csv` (que tem a consolidação das 240 execuções) e os históricos detalhados (`cwnd` e `eventos`), aqui estão os gráficos ideais para a Fase 2 e o porquê de cada um ser essencial para o seu relatório:

---

### 1. Desempenho e Variância: Tempo Total (Boxplot)

Como a simulação tem aleatoriedade (estocástica), a média importa, mas a variância (o quanto o tempo varia entre as 30 execuções) importa ainda mais.

* **Arquivo a usar:** `simulacao_resumo.csv`
* **Como fazer:** Eixo X = Cenários (A, B, C, D). Eixo Y = Tempo Total (s). Crie duas "caixas" lado a lado (hue = Protocolo) para cada cenário usando a biblioteca `seaborn`.
* **O que ele mostra:** O Boxplot mostrará a mediana e a dispersão. Você verá que no Cenário A, a variância é quase zero. Nos cenários de alta perda, o TCP terá "bigodes" (whiskers) longos (mostrando que dependendo de *quais* pacotes são perdidos, o TCP pode demorar muito mais para recuperar), enquanto o R-UDP, com sua janela estática, terá uma dispersão diferente.

### 2. A "Teimosia" vs. A "Educação": Média de Retransmissões (Gráfico de Barras Agrupadas)

Lembra da nossa conclusão brilhante sobre o TCP fazer 4.600 retransmissões e o R-UDP explodir para mais de 35.000? Isso precisa virar um gráfico de impacto.

* **Arquivo a usar:** `simulacao_resumo.csv`
* **Como fazer:** Agrupe por Cenário e Protocolo, calcule a **Média** da coluna `Retx` (Retransmissões). Eixo X = Cenários, Eixo Y = Média de Retransmissões.
* **O que ele mostra:** Vai gerar um contraste absurdo no Cenário C e D. A barra do R-UDP vai lá no teto, provando visualmente o problema de não ter um algoritmo de controle de congestionamento.

### 3. O Colapso da Janela de Congestionamento TCP (Gráfico de Linha Comparativo)

Você tem os arquivos de histórico da janela (cwnd) para os cenários. Vamos usá-los para provar que a teoria do TCP está funcionando na sua simulação.

* **Arquivos a usar:** `simulacao_cwnd_A_TCP.csv` e `simulacao_cwnd_D_estresse_TCP.csv`. *(Filtre apenas para a "Execução 1" de cada arquivo para o gráfico não ficar uma bagunça de 30 linhas sobrepostas).*
* **Como fazer:** Faça um gráfico de linhas (subplot duplo, um em cima do outro, ou sobrepostos se a escala permitir). Eixo X = Tempo da simulação, Eixo Y = Tamanho da Janela (cwnd).
* **O que ele mostra:**
* No **Cenário A**: Uma linha que cresce maravilhosamente (Slow Start) e se mantém alta.
* No **Cenário D**: Um eletrocardiograma caótico (dentes de serra minúsculos), mostrando o TCP sofrendo perdas repetidas, colapsando a janela para 1 MSS e recuando (Exponential Backoff).



### 4. Anatomia do Caos: Fatiamento de Eventos (Gráfico de Barras Empilhadas a 100%)

O simulador registrou milhares de eventos. O que aconteceu com esses pacotes?

* **Arquivos a usar:** `simulacao_eventos_D_estresse_RUDP.csv` vs `simulacao_eventos_D_estresse_TCP.csv` (Foque apenas na Execução 1 ou faça a média).
* **Como fazer:** Conte a frequência de cada tipo de evento na coluna (ex: `SEND`, `ACK`, `TIMEOUT`, `DROP`). Converta isso em porcentagem (totalizando 100% para a barra do TCP e 100% para a do R-UDP). Eixo X = Protocolo, Eixo Y = % de Eventos, Cores = Tipo de Evento.
* **O que ele mostra:** O R-UDP terá uma fatia vermelha de `TIMEOUTS` e `RETRANSMISSIONS` gigantesca engolindo a fatia de `SEND` (sucesso), enquanto o TCP terá uma proporção diferente, ilustrando a eficiência do transporte de dados vs. sobrecarga de erros.

---

### 💻 Código Base (Python/Seaborn) para rodar no seu Colab/Jupyter

Aqui está um "esqueleto" para você copiar, colar e adaptar no seu Colab para ler esse `simulacao_resumo.csv` e gerar os dois primeiros gráficos espetaculares:

```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 1. Carregar os dados (Ajuste o caminho se estiver no Colab)
df_resumo = pd.read_csv("dados_e_logs/processados/simulacao_resumo.csv")

# Configurar o estilo visual (Deixa o gráfico com cara de artigo científico)
sns.set_theme(style="whitegrid")

# =========================================================
# GRÁFICO 1: Boxplot de Tempo de Simulação
# =========================================================
plt.figure(figsize=(10, 6))
sns.boxplot(
    data=df_resumo, 
    x="Cenario", y="Tempo_s", hue="Protocolo", 
    palette={"TCP": "#1f77b4", "R-UDP": "#d62728"}
)
# Como o cenário D tem tempos gigantes, uma escala logarítmica ajuda a ver tudo
plt.yscale("log") 
plt.title("Variância do Tempo de Transferência por Cenário (Escala Log)", fontsize=14, pad=15)
plt.ylabel("Tempo Total (Segundos - Log)", fontsize=12)
plt.xlabel("Cenário de Rede", fontsize=12)
plt.legend(title="Protocolo")
plt.tight_layout()
plt.savefig("boxplot_tempo_fase2.png", dpi=300)
plt.show()

# =========================================================
# GRÁFICO 2: Explosão de Retransmissões
# =========================================================
plt.figure(figsize=(10, 6))
# O barplot do seaborn já calcula a média por padrão se houver múltiplos valores (as 30 runs)
sns.barplot(
    data=df_resumo, 
    x="Cenario", y="Retransmissoes", hue="Protocolo",
    palette={"TCP": "#1f77b4", "R-UDP": "#d62728"},
    errorbar=None # Desliga a barrinha de erro pra ficar mais limpo
)
plt.title("Impacto da Ausência de Controle de Congestionamento (Média de Retransmissões)", fontsize=14, pad=15)
plt.ylabel("Quantidade Média de Retransmissões", fontsize=12)
plt.xlabel("Cenário de Rede", fontsize=12)
plt.tight_layout()
plt.savefig("barplot_retransmissoes_fase2.png", dpi=300)
plt.show()

```

Com esses gráficos em mãos, a sua defesa de trabalho vai se basear puramente em dados irrefutáveis. Você pode demonstrar a Fase 1 (gráficos que você já pensou) e terminar a apresentação com o impacto em massa da Fase 2.