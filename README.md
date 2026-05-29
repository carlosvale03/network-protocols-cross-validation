# Projeto de Redes de Computadores: Validação Cruzada (PPGCC/UFPI)

Este repositório contém o código-fonte, scripts de automação, dados coletados e gráficos do trabalho prático da disciplina de **Redes de Computadores (2026.1)** do Programa de Pós-Graduação em Ciência da Computação (PPGCC) da Universidade Federal do Piauí (UFPI).

**Aluno:** Carlos Henrique  
**Matrícula:** 20261008479  
**Tema:** Análise comparativa entre sistemas de transferência de arquivos reais (Sockets/Docker/`tc`) e modelagem de simulação de eventos discretos (SimPy).

---

## 📂 Estrutura do Repositório

O projeto está organizado da seguinte forma:

```text
trabalho01-redes/
├── README.md                          # Este manual de instruções e documentação
├── docker-compose.yml                 # Orquestração do ambiente Docker (Cliente e Servidores)
│
├── fase1_real/                        # Fase 1: Implementação Real com Sockets
│   ├── cliente.py                     # Aplicação cliente (transfere via TCP ou R-UDP)
│   ├── servidor.py                    # Aplicação servidor (escuta conexões TCP e R-UDP em loop)
│   ├── rudp_protocol.py               # Lógica de transporte R-UDP (Go-Back-N, Checksum, ACKs)
│   ├── extrator_pcap.py               # Script para converter arquivos .pcap brutos em CSV
│   ├── Dockerfile                     # Imagem Ubuntu para os contêineres com iproute2 e tcpdump
│   └── scripts_teste/                 # Automação de injeção de falhas (tc) e coletas
│       ├── cenario_a.sh               # Cenário A: 0% de perda / 10 ms delay
│       ├── cenario_b.sh               # Cenário B: 10% de perda / 50 ms delay
│       └── cenario_c.sh               # Cenário C: 20% de perda / 100 ms delay
│
├── fase2_simulacao/                   # Fase 2: Simulação Estocástica de Eventos Discretos
│   ├── simulador.py                   # Motor de simulação SimPy para TCP Reno e R-UDP GBN
│   ├── tarefas_validacao.py           # Script para rodar as 10 tarefas estocásticas de validação
│   └── requirements.txt               # Dependências do simulador (simpy, numpy, scipy)
│
├── dados_e_logs/                      # Armazenamento de todas as métricas coletadas
│   ├── pcap/                          # Capturas originais em formato binário (.pcap)
│   └── processados/                   # Logs de eventos e medições convertidos para CSV
│
├── analise_estatistica/               # Análise de Dados e Geração de Gráficos
│   └── analise_colab.ipynb            # Notebook Jupyter/Google Colab para processamento visual
│
└── relatorio_sbc/                     # Relatório no formato de Artigo Científico (SBC)
    ├── relatorio_trabalho01_redes_mestrado_carlos_ofc.pdf  # Artigo final em PDF (Validação Cruzada)
    └── figuras/                       # Figuras e gráficos de redes exportados para o artigo

```

---

## 🛠️ Requisitos e Preparação do Ambiente

### Requisitos do Sistema
* **Sistema Operacional:** Windows 11 com WSL2 ativado (ou Linux nativo).
* **Terminal:** PowerShell (recomendado no Windows) ou Bash.
* **Ferramentas:**
  * Docker Desktop instalado e rodando.
  * Python 3.10+ instalado localmente (para a Fase 2 e processamento).

### Instalação de Dependências Locais (Python)
Para executar a simulação e o extrator PCAP no ambiente local, instale as dependências executando o comando a seguir no PowerShell:
```powershell
pip install -r fase2_simulacao/requirements.txt dpkt pandas matplotlib seaborn scipy
```

---

## 🚀 Fase 1: Executando os Cenários Reais (Docker + Sockets)

A Fase 1 roda de forma isolada dentro de contêineres Docker, permitindo a injeção artificial de latência e perda de pacotes através do utilitário `tc netem` do Linux.

### 1. Iniciar o Ambiente Docker
Na raiz do repositório, levante a rede de contêineres:
```powershell
docker-compose up --build -d
```
*Isso criará 3 contêineres:*
* `servidor_redes` (escutando R-UDP na porta 5000)
* `servidor_tcp_redes` (escutando TCP na porta 5001)
* `cliente_redes` (mantido em background esperando a execução dos testes)

### 2. Executar os Cenários de Rede
Os cenários automatizam a geração de um arquivo de 10 MB, limpam as regras antigas, aplicam a degradação de link no cliente via `tc`, disparam o `tcpdump` em background e realizam a transferência em ambos os modos (TCP e R-UDP).

Execute cada cenário de forma sequencial no seu terminal:

* **Cenário A (0% perda / 10ms delay):**
  ```powershell
  docker exec -it cliente_redes bash /app/scripts_teste/cenario_a.sh
  ```
* **Cenário B (10% perda / 50ms delay):**
  ```powershell
  docker exec -it cliente_redes bash /app/scripts_teste/cenario_b.sh
  ```
* **Cenário C (20% perda / 100ms delay):**
  ```powershell
  docker exec -it cliente_redes bash /app/scripts_teste/cenario_c.sh
  ```

Os arquivos binários brutos capturados (`.pcap`) serão salvos automaticamente na pasta mapeada local `./dados_e_logs/pcap/`.

### 3. Extrair Pacotes e Gerar Logs CSV
Para converter as capturas `.pcap` em tabelas estruturadas de logs em CSV (usadas para análise no notebook), execute o extrator dentro do container cliente:
```powershell
docker exec -it cliente_redes python3 extrator_pcap.py
```
Isso lê a pasta `./dados_e_logs/pcap/` e gera arquivos processados na pasta `./dados_e_logs/processados/`.

---

## 📊 Fase 2: Executando a Simulação Estocástica (SimPy)

A Fase 2 consiste em simular estatisticamente o comportamento dos protocolos sob a distribuição de perda de Bernoulli e atraso de distribuição Normal (incluindo Jitter).

O simulador e a validação rodam diretamente no Python local (ou no Colab).

### Executar a Bateria Completa de 10 Tarefas de Validação
Para rodar todas as tarefas teóricas solicitadas e exportar as planilhas estatísticas processadas para a pasta `dados_e_logs/processados/`, execute o script PowerShell:
```powershell
python fase2_simulacao/tarefas_validacao.py
```

### O que são as 10 Tarefas de Validação Executadas?
1. **Modelagem de Atraso:** Validação estatística do RTT simulado contra os valores teóricos ($2 \times \text{delay}$).
2. **Modelo de Perda de Bernoulli:** Verificação se a taxa de perdas dos eventos aleatórios converge com o parâmetro de rede configurado.
3. **Simulação de Timeout:** Contagem comparativa de ocorrência de timeouts entre TCP Reno e R-UDP (Go-Back-N).
4. **Curva de Vazão:** Análise do escalonamento de desempenho variando o tamanho do arquivo de 1 MB a 100 MB.
5. **Sensibilidade da Janela:** Análise de sensibilidade variando o tamanho da janela $N$ de 1 a 100 no R-UDP, identificando pontos de congestionamento.
6. **Validação de RTT:** Comparativo do RTT simulado de ambos os protocolos em 30 rodadas.
7. **Impacto do Jitter:** Medição do impacto da variância da latência na estabilidade do fluxo de vazão.
8. **Cenário de Estresse:** Simulação extrema operando com 25% de perdas e 125ms de delay de canal.
9. **Análise de Eficiência:** Cálculo da fração de esforço (pacotes de dados úteis transmitidos vs. pacotes de controle ACKs).
10. **Convergência Estatística:** Geração de Intervalo de Confiança de 95% usando a distribuição *T-Student* sobre 30 execuções independentes do modelo.

---

## 📈 Processando os Gráficos no Jupyter/Google Colab

A pasta `analise_estatistica/` contém o notebook [analise_colab.ipynb](file:///c:/Users/Carlos Vale/Documents/02 mestrado - ciencias da computação/redes de computadores/trabalhos/trabalho01-redes/analise_estatistica/analise_colab.ipynb).

Para rodar localmente:
1. Abra seu ambiente Jupyter ou VS Code.
2. Carregue o notebook e execute todas as células (`Run All`).
3. O notebook processará as planilhas da pasta `dados_e_logs/processados/` e salvará os gráficos no formato `.pdf` diretamente dentro da pasta de figuras do artigo LaTeX `relatorio_sbc/figuras/`.

---

*Trabalho desenvolvido para fins avaliativos da disciplina de Redes de Computadores (PPGCC/UFPI - 2026).*
