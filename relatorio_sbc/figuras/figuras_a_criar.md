### 1. Vazão (Throughput) ao Longo do Tempo (Gráfico de Linha)

Esse é o gráfico mais importante para mostrar a eficiência bruta da transferência. Ele vai responder: *"Quem conseguiu transferir os dados mais rápido e de forma mais estável?"*

* **Como fazer:** Agrupe os pacotes em intervalos de tempo (ex: a cada 0.1 segundo ou 1 segundo) usando a coluna `timestamp`. Some a coluna `tamanho_payload` de todos os pacotes naquele intervalo e converta para Kilobits ou Megabits por segundo (Kbps / Mbps).
* **Visualização ideal:** Coloque as duas linhas (TCP e R-UDP) no mesmo gráfico para comparar diretamente. O eixo X será o Tempo (em segundos) e o eixo Y será a Vazão (Mbps).

### 2. Gráfico de Tempo-Sequência (Gráfico de Stevens)

Esse gráfico é clássico em análise de redes e mostra exatamente como os dados fluem, permitindo ver visualmente onde ocorrem perdas, retransmissões e atrasos.

* **Para o TCP:** Plote um gráfico de dispersão (Scatter plot). Eixo X = `timestamp` (subtraindo o timestamp do primeiro pacote para começar em 0) e Eixo Y = `numero_sequencia_tcp`.
* **O que ele mostra:** Uma linha reta e inclinada significa uma transferência perfeita. Degraus ou pontos "voltando" no eixo Y indicam retransmissões.
* **Para o R-UDP:** Como os dados da rede marcam isso como UDP, a ferramenta de captura não lê nativamente o número de sequência do seu R-UDP. Se o seu R-UDP colocou o número de sequência no payload e não aparece no CSV, não tem problema focar esse gráfico apenas no TCP ou plotar os pacotes R-UDP apenas pela ordem de chegada.

### 3. Dinâmica da Janela de Recepção TCP (Gráfico de Linha)

Como seu trabalho fala sobre janelas deslizantes (Go-Back-N ou Selective Repeat), é muito interessante mostrar como o TCP lida com o controle de fluxo na prática.

* **Como fazer:** Use apenas o arquivo `cenarioA_tcp.csv`. Coloque no eixo X o `timestamp` e no eixo Y o `tamanho_janela_tcp`.
* **O que ele mostra:** Ele evidenciará o comportamento do mecanismo de Controle de Fluxo/Congestionamento do TCP se adaptando à rede.

### 4. Distribuição do Tamanho dos Pacotes / Overhead (Gráfico de Barras ou Histograma)

A ideia aqui é comparar o quanto de "esforço" de rede foi gasto com dados úteis x controle.

* **Como fazer:** Para cada protocolo, some o total da coluna `tamanho_pacote` (que inclui cabeçalhos IP, TCP/UDP e MAC) e compare com a soma total da coluna `tamanho_payload`.
* **O que ele mostra:** O TCP geralmente tem um overhead maior devido ao handshake de três vias (pacotes com `flags_tcp` apenas como SYN ou ACK e payload = 0) e cabeçalhos maiores (20+ bytes contra 8 bytes do UDP). Isso é um ótimo ponto de discussão para o seu relatório sobre por que o UDP puro é mais leve.

### 5. Pacotes de Dados vs. Pacotes de Controle (Gráfico de Pizza ou Barras Empilhadas)

* **Como fazer:** No arquivo TCP, conte quantos pacotes têm `tamanho_payload` maior que zero (Dados) versus quantos pacotes têm `tamanho_payload` igual a zero (Acks puros, SYNs, FINs).
* **O que ele mostra:** Reforça a análise do impacto do mecanismo de confirmação na rede.

---

**Dica de Ouro para o Relatório:**
Ao gerar esses gráficos (especialmente o de Vazão), **crie uma seção comparando os cenários** quando você rodar as condições com perda de pacotes e jitter (atraso variável) injetados pelo `tc`. A mágica do relatório será mostrar o TCP sofrendo (reduzindo a janela drasticamente por achar que é congestionamento) e explicar como a *sua* implementação do R-UDP se comportou frente às mesmas perdas.

Como você vai fazer isso no Python (Jupyter/Colab)? Você prefere que eu te mostre um esboço de código em `pandas` e `matplotlib` para já gerar o primeiro gráfico (Vazão vs Tempo)?