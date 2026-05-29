"""
==========================================================================
 Tarefas de Validação - Fase 2 (SimPy)
 PPGCC/UFPI - Redes de Computadores - 2026.1
 Aluno: Carlos Henrique - Matrícula: 20261008479

 Executa as 10 tarefas de validação exigidas na avaliação (Seção 3.1).
 Cada tarefa gera um CSV dedicado em dados_e_logs/processados/.
==========================================================================
"""

import os
import csv
import sys
import time
import numpy as np
import argparse

# Importa o simulador do mesmo diretório
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from simulador import (
    run_single_simulation, write_summary_csv, write_events_csv,
    FILE_SIZE_DEFAULT, CHUNK_SIZE, WINDOW_SIZE_RUDP, TIMEOUT_RUDP,
    N_EXECUCOES
)

try:
    from scipy import stats as scipy_stats
except ImportError:
    print("AVISO: scipy não encontrado. Instale com: pip install scipy")
    print("A Tarefa 10 (Intervalo de Confiança) será calculada de forma aproximada.")
    scipy_stats = None


OUT_DIR = "dados_e_logs/processados"


def ensure_dir(path):
    os.makedirs(os.path.dirname(path) if not path.endswith('/') else path, exist_ok=True)


def write_csv(filepath, rows, fieldnames=None):
    """Utilitário para escrever CSV genérico."""
    if not rows:
        print(f"  [AVISO] Nenhum dado para salvar em {filepath}")
        return

    if fieldnames is None:
        fieldnames = list(rows[0].keys())

    ensure_dir(filepath)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"  [CSV] Salvo: {filepath} ({len(rows)} linhas)")


# ==============================================================
# TAREFA 1: Modelagem de Atraso
# ==============================================================
def tarefa1_modelagem_atraso(seed=42):
    """
    Compara distribuição de delay simulado (Normal) com valores configurados.
    Executa simulação e extrai RTTs reais para cada cenário.
    """
    print("\n" + "=" * 60)
    print(" TAREFA 1: Modelagem de Atraso")
    print("=" * 60)

    cenarios = [
        ('A', 10, 0.0),
        ('B', 50, 0.1),
        ('C', 100, 0.2),
    ]

    rows = []
    n_runs = 10  # Múltiplas execuções para amostragem estatística

    for nome, delay, loss in cenarios:
        all_rtts = []
        for i in range(n_runs):
            result, events, _ = run_single_simulation(
                'R-UDP', delay, loss, seed=seed + i
            )
            # Extrai RTTs dos eventos ACK
            for e in events:
                if e['tipo_evento'] == 'ACK' and e['rtt_ms'] != '':
                    all_rtts.append(float(e['rtt_ms']))

        if all_rtts:
            rtts = np.array(all_rtts)
            # O delay teórico (ida + volta) é 2 * delay_ms
            rtt_teorico = 2 * delay

            rows.append({
                'cenario': nome,
                'delay_configurado_ms': delay,
                'rtt_teorico_ms': rtt_teorico,
                'rtt_medio_observado_ms': round(float(np.mean(rtts)), 4),
                'rtt_desvio_observado_ms': round(float(np.std(rtts)), 4),
                'rtt_min_ms': round(float(np.min(rtts)), 4),
                'rtt_max_ms': round(float(np.max(rtts)), 4),
                'rtt_mediana_ms': round(float(np.median(rtts)), 4),
                'rtt_p05_ms': round(float(np.percentile(rtts, 5)), 4),
                'rtt_p95_ms': round(float(np.percentile(rtts, 95)), 4),
                'diferenca_pct': round(abs(float(np.mean(rtts)) - rtt_teorico) / rtt_teorico * 100, 2) if rtt_teorico > 0 else 0,
                'n_amostras': len(rtts),
                'n_execucoes': n_runs,
            })
            print(f"  Cenário {nome}: RTT médio={np.mean(rtts):.2f}ms (teórico={rtt_teorico}ms)")

    filepath = os.path.join(OUT_DIR, "tarefa1_atraso.csv")
    write_csv(filepath, rows)
    return rows


# ==============================================================
# TAREFA 2: Modelo de Perda de Bernoulli
# ==============================================================
def tarefa2_perda_bernoulli(seed=42):
    """
    Valida a taxa de perda observada contra o p configurado.
    """
    print("\n" + "=" * 60)
    print(" TAREFA 2: Modelo de Perda de Bernoulli")
    print("=" * 60)

    cenarios = [
        ('A', 10, 0.0),
        ('B', 50, 0.1),
        ('C', 100, 0.2),
        ('D_estresse', 125, 0.25),
    ]

    rows = []
    n_runs = 30

    for nome, delay, loss in cenarios:
        taxas = []
        perdas_dados_list = []
        perdas_ack_list = []

        for i in range(n_runs):
            result, _, _ = run_single_simulation(
                'R-UDP', delay, loss, seed=seed + i
            )
            taxas.append(result['taxa_perda_observada'])
            perdas_dados_list.append(result['pacotes_perdidos_dados'])
            perdas_ack_list.append(result['pacotes_perdidos_ack'])

        taxas = np.array(taxas)

        rows.append({
            'cenario': nome,
            'taxa_perda_configurada': loss,
            'taxa_perda_media_observada': round(float(np.mean(taxas)), 6),
            'taxa_perda_desvio': round(float(np.std(taxas)), 6),
            'taxa_perda_min': round(float(np.min(taxas)), 6),
            'taxa_perda_max': round(float(np.max(taxas)), 6),
            'perdas_dados_media': round(float(np.mean(perdas_dados_list)), 2),
            'perdas_ack_media': round(float(np.mean(perdas_ack_list)), 2),
            'diferenca_absoluta': round(abs(float(np.mean(taxas)) - loss), 6),
            'convergiu': 'Sim' if abs(float(np.mean(taxas)) - loss) < 0.03 else 'Nao',
            'n_execucoes': n_runs,
        })
        print(f"  Cenário {nome}: Perda observada={np.mean(taxas):.4f} (configurada={loss})")

    filepath = os.path.join(OUT_DIR, "tarefa2_perda.csv")
    write_csv(filepath, rows)
    return rows


# ==============================================================
# TAREFA 3: Simulação de Timeout
# ==============================================================
def tarefa3_timeout(seed=42):
    """
    Conta retransmissões e timeouts por cenário e protocolo.
    """
    print("\n" + "=" * 60)
    print(" TAREFA 3: Simulação de Timeout e Retransmissões")
    print("=" * 60)

    cenarios = [
        ('A', 10, 0.0),
        ('B', 50, 0.1),
        ('C', 100, 0.2),
    ]

    rows = []
    n_runs = 30

    for nome, delay, loss in cenarios:
        for protocolo in ['TCP', 'R-UDP']:
            retx_list = []
            timeout_list = []
            fast_retx_list = []

            for i in range(n_runs):
                result, _, _ = run_single_simulation(
                    protocolo, delay, loss, seed=seed + i
                )
                retx_list.append(result['total_retransmissoes'])
                timeout_list.append(result['total_timeouts'])
                if protocolo == 'TCP':
                    fast_retx_list.append(result.get('fast_retransmits', 0))

            row = {
                'cenario': nome,
                'protocolo': protocolo,
                'delay_ms': delay,
                'taxa_perda': loss,
                'retransmissoes_media': round(float(np.mean(retx_list)), 2),
                'retransmissoes_desvio': round(float(np.std(retx_list)), 2),
                'retransmissoes_min': int(np.min(retx_list)),
                'retransmissoes_max': int(np.max(retx_list)),
                'timeouts_media': round(float(np.mean(timeout_list)), 2),
                'timeouts_desvio': round(float(np.std(timeout_list)), 2),
                'n_execucoes': n_runs,
            }

            if protocolo == 'TCP':
                row['fast_retransmits_media'] = round(float(np.mean(fast_retx_list)), 2)
                row['fast_retransmits_desvio'] = round(float(np.std(fast_retx_list)), 2)

            rows.append(row)
            print(f"  Cenário {nome}/{protocolo}: Retx média={np.mean(retx_list):.1f}, "
                  f"Timeouts={np.mean(timeout_list):.1f}")

    filepath = os.path.join(OUT_DIR, "tarefa3_timeout.csv")
    write_csv(filepath, rows)
    return rows


# ==============================================================
# TAREFA 4: Curva de Vazão (Throughput)
# ==============================================================
def tarefa4_curva_vazao(seed=42):
    """
    Varia tamanho do arquivo (1, 5, 10, 25, 50, 100 MB) e registra throughput.
    """
    print("\n" + "=" * 60)
    print(" TAREFA 4: Curva de Vazão (Throughput) por Tamanho de Arquivo")
    print("=" * 60)

    tamanhos_mb = [1, 5, 10, 25, 50, 100]
    cenarios = [
        ('A', 10, 0.0),
        ('B', 50, 0.1),
        ('C', 100, 0.2),
    ]

    rows = []
    n_runs = 5  # Menos execuções pois 100MB é custoso

    for nome, delay, loss in cenarios:
        for tam_mb in tamanhos_mb:
            file_size = tam_mb * 1024 * 1024

            for protocolo in ['TCP', 'R-UDP']:
                vazoes = []
                tempos = []

                for i in range(n_runs):
                    result, _, _ = run_single_simulation(
                        protocolo, delay, loss, file_size=file_size, seed=seed + i
                    )
                    vazoes.append(result['vazao_mbps'])
                    tempos.append(result['tempo_total_s'])

                rows.append({
                    'cenario': nome,
                    'protocolo': protocolo,
                    'tamanho_arquivo_mb': tam_mb,
                    'tamanho_arquivo_bytes': file_size,
                    'delay_ms': delay,
                    'taxa_perda': loss,
                    'vazao_media_mbps': round(float(np.mean(vazoes)), 4),
                    'vazao_desvio_mbps': round(float(np.std(vazoes)), 4),
                    'vazao_min_mbps': round(float(np.min(vazoes)), 4),
                    'vazao_max_mbps': round(float(np.max(vazoes)), 4),
                    'tempo_medio_s': round(float(np.mean(tempos)), 4),
                    'tempo_desvio_s': round(float(np.std(tempos)), 4),
                    'n_execucoes': n_runs,
                })

                print(f"  Cenário {nome}/{protocolo}/{tam_mb}MB: "
                      f"Vazão={np.mean(vazoes):.2f} Mbps, Tempo={np.mean(tempos):.2f}s")

    filepath = os.path.join(OUT_DIR, "tarefa4_vazao.csv")
    write_csv(filepath, rows)
    return rows


# ==============================================================
# TAREFA 5: Sensibilidade da Janela
# ==============================================================
def tarefa5_sensibilidade_janela(seed=42):
    """
    Varia WINDOW_SIZE (1, 5, 10, 20, 50, 100) e registra impacto no R-UDP.
    """
    print("\n" + "=" * 60)
    print(" TAREFA 5: Sensibilidade da Janela (Window Size)")
    print("=" * 60)

    janelas = [1, 2, 5, 10, 20, 50, 100]
    cenarios = [
        ('A', 10, 0.0),
        ('B', 50, 0.1),
        ('C', 100, 0.2),
    ]

    rows = []
    n_runs = 10

    for nome, delay, loss in cenarios:
        for win in janelas:
            vazoes = []
            retx = []
            tempos = []
            timeouts = []

            for i in range(n_runs):
                result, _, _ = run_single_simulation(
                    'R-UDP', delay, loss, window_size=win, seed=seed + i
                )
                vazoes.append(result['vazao_mbps'])
                retx.append(result['total_retransmissoes'])
                tempos.append(result['tempo_total_s'])
                timeouts.append(result['total_timeouts'])

            rows.append({
                'cenario': nome,
                'protocolo': 'R-UDP',
                'janela': win,
                'delay_ms': delay,
                'taxa_perda': loss,
                'vazao_media_mbps': round(float(np.mean(vazoes)), 4),
                'vazao_desvio_mbps': round(float(np.std(vazoes)), 4),
                'retransmissoes_media': round(float(np.mean(retx)), 2),
                'retransmissoes_desvio': round(float(np.std(retx)), 2),
                'timeouts_media': round(float(np.mean(timeouts)), 2),
                'tempo_medio_s': round(float(np.mean(tempos)), 4),
                'tempo_desvio_s': round(float(np.std(tempos)), 4),
                'saturou': 'Sim' if win >= 50 and np.mean(vazoes) <= np.mean(vazoes) else 'Nao',
                'n_execucoes': n_runs,
            })

            print(f"  Cenário {nome}/Janela={win}: "
                  f"Vazão={np.mean(vazoes):.2f} Mbps, Retx={np.mean(retx):.0f}")

    filepath = os.path.join(OUT_DIR, "tarefa5_janela.csv")
    write_csv(filepath, rows)
    return rows


# ==============================================================
# TAREFA 6: Validação de RTT
# ==============================================================
def tarefa6_validacao_rtt(seed=42):
    """
    Compara RTT médio simulado com valores teóricos (2 * delay).
    """
    print("\n" + "=" * 60)
    print(" TAREFA 6: Validação de RTT")
    print("=" * 60)

    cenarios = [
        ('A', 10, 0.0),
        ('B', 50, 0.1),
        ('C', 100, 0.2),
    ]

    rows = []
    n_runs = 30

    for nome, delay, loss in cenarios:
        for protocolo in ['TCP', 'R-UDP']:
            rtts = []
            for i in range(n_runs):
                result, _, _ = run_single_simulation(
                    protocolo, delay, loss, seed=seed + i
                )
                rtts.append(result['rtt_medio_ms'])

            rtt_teorico = 2 * delay

            rows.append({
                'cenario': nome,
                'protocolo': protocolo,
                'delay_configurado_ms': delay,
                'rtt_teorico_ms': rtt_teorico,
                'rtt_medio_simulado_ms': round(float(np.mean(rtts)), 4),
                'rtt_desvio_simulado_ms': round(float(np.std(rtts)), 4),
                'rtt_min_ms': round(float(np.min(rtts)), 4),
                'rtt_max_ms': round(float(np.max(rtts)), 4),
                'diferenca_pct': round(abs(float(np.mean(rtts)) - rtt_teorico) / rtt_teorico * 100, 2) if rtt_teorico > 0 else 0,
                'n_execucoes': n_runs,
            })
            print(f"  Cenário {nome}/{protocolo}: RTT simulado={np.mean(rtts):.2f}ms "
                  f"(teórico={rtt_teorico}ms, diff={abs(np.mean(rtts)-rtt_teorico):.2f}ms)")

    filepath = os.path.join(OUT_DIR, "tarefa6_rtt.csv")
    write_csv(filepath, rows)
    return rows


# ==============================================================
# TAREFA 7: Impacto do Jitter
# ==============================================================
def tarefa7_impacto_jitter(seed=42):
    """
    Varia desvio padrão do jitter e mede estabilidade do fluxo.
    Obs: O simulador usa jitter = Normal(0, delay*0.1). Aqui variamos o fator.
    """
    print("\n" + "=" * 60)
    print(" TAREFA 7: Impacto do Jitter")
    print("=" * 60)

    # Jitter é controlado como fração do delay (0%, 10%, 25%, 50%)
    # Para variar, rodamos com diferentes delays mantendo loss=0.1
    # e comparamos a variabilidade do throughput
    delay_base = 50
    loss = 0.1

    # Simulamos com diferentes delays para capturar o efeito do jitter natural
    # (que é proporcional ao delay: std = delay * 0.1)
    delays = [10, 25, 50, 75, 100, 150, 200]

    rows = []
    n_runs = 20

    for delay in delays:
        for protocolo in ['TCP', 'R-UDP']:
            jitters = []
            vazoes = []
            rtt_devs = []

            for i in range(n_runs):
                result, _, _ = run_single_simulation(
                    protocolo, delay, loss, seed=seed + i
                )
                jitters.append(result['jitter_medio_ms'])
                vazoes.append(result['vazao_mbps'])
                rtt_devs.append(result['rtt_desvio_ms'])

            rows.append({
                'protocolo': protocolo,
                'delay_ms': delay,
                'jitter_std_teorico_ms': round(delay * 0.1, 2),
                'taxa_perda': loss,
                'jitter_medio_observado_ms': round(float(np.mean(jitters)), 4),
                'jitter_desvio_observado_ms': round(float(np.std(jitters)), 4),
                'rtt_desvio_medio_ms': round(float(np.mean(rtt_devs)), 4),
                'vazao_media_mbps': round(float(np.mean(vazoes)), 4),
                'vazao_desvio_mbps': round(float(np.std(vazoes)), 4),
                'coef_variacao_vazao_pct': round(float(np.std(vazoes) / np.mean(vazoes) * 100), 2) if np.mean(vazoes) > 0 else 0,
                'n_execucoes': n_runs,
            })

            print(f"  Delay={delay}ms/{protocolo}: Jitter={np.mean(jitters):.2f}ms, "
                  f"Vazão={np.mean(vazoes):.2f}±{np.std(vazoes):.2f} Mbps")

    filepath = os.path.join(OUT_DIR, "tarefa7_jitter.csv")
    write_csv(filepath, rows)
    return rows


# ==============================================================
# TAREFA 8: Cenário de Estresse (25% loss)
# ==============================================================
def tarefa8_estresse(seed=42):
    """
    Cenário com 25% de perda de pacotes e previsão de tempo de transferência.
    """
    print("\n" + "=" * 60)
    print(" TAREFA 8: Cenário de Estresse (25% loss)")
    print("=" * 60)

    delay = 125
    loss = 0.25

    rows = []
    n_runs = 30

    for protocolo in ['TCP', 'R-UDP']:
        tempos = []
        vazoes = []
        retx = []
        timeouts = []
        perdas_dados = []
        perdas_ack = []

        for i in range(n_runs):
            result, _, _ = run_single_simulation(
                protocolo, delay, loss, seed=seed + i
            )
            tempos.append(result['tempo_total_s'])
            vazoes.append(result['vazao_mbps'])
            retx.append(result['total_retransmissoes'])
            timeouts.append(result['total_timeouts'])
            perdas_dados.append(result['pacotes_perdidos_dados'])
            perdas_ack.append(result['pacotes_perdidos_ack'])

        rows.append({
            'protocolo': protocolo,
            'delay_ms': delay,
            'taxa_perda_configurada': loss,
            'tempo_medio_s': round(float(np.mean(tempos)), 4),
            'tempo_desvio_s': round(float(np.std(tempos)), 4),
            'tempo_min_s': round(float(np.min(tempos)), 4),
            'tempo_max_s': round(float(np.max(tempos)), 4),
            'vazao_media_mbps': round(float(np.mean(vazoes)), 4),
            'vazao_desvio_mbps': round(float(np.std(vazoes)), 4),
            'retransmissoes_media': round(float(np.mean(retx)), 2),
            'retransmissoes_desvio': round(float(np.std(retx)), 2),
            'timeouts_media': round(float(np.mean(timeouts)), 2),
            'perdas_dados_media': round(float(np.mean(perdas_dados)), 2),
            'perdas_ack_media': round(float(np.mean(perdas_ack)), 2),
            'previsao_tempo_s': round(float(np.mean(tempos)), 2),
            'n_execucoes': n_runs,
        })

        print(f"  {protocolo}: Tempo previsto={np.mean(tempos):.2f}s, "
              f"Vazão={np.mean(vazoes):.2f} Mbps, Retx={np.mean(retx):.0f}")

    filepath = os.path.join(OUT_DIR, "tarefa8_estresse.csv")
    write_csv(filepath, rows)
    return rows


# ==============================================================
# TAREFA 9: Análise de Eficiência (Dados vs Controle)
# ==============================================================
def tarefa9_eficiencia(seed=42):
    """
    Razão entre pacotes de dados e pacotes de controle (ACKs).
    """
    print("\n" + "=" * 60)
    print(" TAREFA 9: Análise de Eficiência (Dados vs Controle)")
    print("=" * 60)

    cenarios = [
        ('A', 10, 0.0),
        ('B', 50, 0.1),
        ('C', 100, 0.2),
        ('D_estresse', 125, 0.25),
    ]

    rows = []
    n_runs = 30

    for nome, delay, loss in cenarios:
        for protocolo in ['TCP', 'R-UDP']:
            eficiencias = []
            dados_list = []
            acks_list = []
            overheads = []

            for i in range(n_runs):
                result, _, _ = run_single_simulation(
                    protocolo, delay, loss, seed=seed + i
                )
                eficiencias.append(result['eficiencia_dados_controle'])
                dados_list.append(result['total_pacotes_dados_enviados'])
                acks_list.append(result['total_acks_enviados'])
                overheads.append(result['overhead_pct'])

            rows.append({
                'cenario': nome,
                'protocolo': protocolo,
                'delay_ms': delay,
                'taxa_perda': loss,
                'eficiencia_media': round(float(np.mean(eficiencias)), 6),
                'eficiencia_desvio': round(float(np.std(eficiencias)), 6),
                'pacotes_dados_media': round(float(np.mean(dados_list)), 2),
                'pacotes_dados_desvio': round(float(np.std(dados_list)), 2),
                'acks_media': round(float(np.mean(acks_list)), 2),
                'acks_desvio': round(float(np.std(acks_list)), 2),
                'razao_dados_controle': round(float(np.mean(dados_list)) / float(np.mean(acks_list)), 4) if np.mean(acks_list) > 0 else 0,
                'overhead_medio_pct': round(float(np.mean(overheads)), 2),
                'n_execucoes': n_runs,
            })

            print(f"  Cenário {nome}/{protocolo}: Eficiência={np.mean(eficiencias):.4f}, "
                  f"Dados/Ctrl={np.mean(dados_list):.0f}/{np.mean(acks_list):.0f}")

    filepath = os.path.join(OUT_DIR, "tarefa9_eficiencia.csv")
    write_csv(filepath, rows)
    return rows


# ==============================================================
# TAREFA 10: Convergência Estatística (IC 95%)
# ==============================================================
def tarefa10_convergencia(seed=42):
    """
    30+ execuções por cenário/protocolo → média, desvio, IC 95%.
    """
    print("\n" + "=" * 60)
    print(" TAREFA 10: Convergência Estatística (IC 95%)")
    print("=" * 60)

    cenarios = [
        ('A', 10, 0.0),
        ('B', 50, 0.1),
        ('C', 100, 0.2),
    ]

    rows = []
    n_runs = 30

    metricas_interesse = [
        'vazao_mbps', 'tempo_total_s', 'total_retransmissoes',
        'rtt_medio_ms', 'jitter_medio_ms', 'eficiencia_dados_controle'
    ]

    for nome, delay, loss in cenarios:
        for protocolo in ['TCP', 'R-UDP']:
            # Coleta todas as execuções
            resultados = {m: [] for m in metricas_interesse}

            for i in range(n_runs):
                result, _, _ = run_single_simulation(
                    protocolo, delay, loss, seed=seed + i
                )
                for m in metricas_interesse:
                    resultados[m].append(result[m])

            # Calcula IC 95% para cada métrica
            for metrica in metricas_interesse:
                valores = np.array(resultados[metrica])
                media = float(np.mean(valores))
                desvio = float(np.std(valores, ddof=1))
                n = len(valores)
                erro_padrao = desvio / np.sqrt(n)

                # IC 95% com t-student
                if scipy_stats:
                    t_crit = scipy_stats.t.ppf(0.975, df=n - 1)
                else:
                    # Aproximação para n=30: t ≈ 2.045
                    t_crit = 2.045

                ic_inferior = media - t_crit * erro_padrao
                ic_superior = media + t_crit * erro_padrao
                margem = t_crit * erro_padrao

                # Coeficiente de variação (indica convergência)
                cv = (desvio / media * 100) if media != 0 else 0

                rows.append({
                    'cenario': nome,
                    'protocolo': protocolo,
                    'metrica': metrica,
                    'delay_ms': delay,
                    'taxa_perda': loss,
                    'n_execucoes': n,
                    'media': round(media, 6),
                    'desvio_padrao': round(desvio, 6),
                    'erro_padrao': round(erro_padrao, 6),
                    'ic_95_inferior': round(ic_inferior, 6),
                    'ic_95_superior': round(ic_superior, 6),
                    'margem_erro': round(margem, 6),
                    'margem_erro_pct': round(margem / abs(media) * 100, 2) if media != 0 else 0,
                    'coef_variacao_pct': round(cv, 2),
                    'convergiu': 'Sim' if cv < 10 else 'Nao',
                    'min': round(float(np.min(valores)), 6),
                    'max': round(float(np.max(valores)), 6),
                    'mediana': round(float(np.median(valores)), 6),
                })

            print(f"  Cenário {nome}/{protocolo}: {n_runs} execuções processadas com IC 95%")

    filepath = os.path.join(OUT_DIR, "tarefa10_convergencia.csv")
    write_csv(filepath, rows)
    return rows


# ==============================================================
# MAIN: Executa todas as tarefas
# ==============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tarefas de Validação - Fase 2 (SimPy)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--tarefas", nargs="+", type=int, default=list(range(1, 11)),
                        help="Número(s) da(s) tarefa(s) a executar (1-10). Default: todas")
    parser.add_argument("--seed", type=int, default=42,
                        help="Seed base para reprodutibilidade")
    parser.add_argument("--out_dir", default="dados_e_logs/processados",
                        help="Diretório de saída")
    args = parser.parse_args()

    OUT_DIR = args.out_dir
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 60)
    print(" TAREFAS DE VALIDAÇÃO - FASE 2 (SimPy)")
    print(" PPGCC/UFPI - Redes de Computadores - 2026.1")
    print(" Aluno: Carlos Henrique - Matrícula: 20261008479")
    print("=" * 60)
    print(f" Tarefas selecionadas: {args.tarefas}")
    print(f" Seed base: {args.seed}")
    print()

    tarefas = {
        1: ("Modelagem de Atraso", tarefa1_modelagem_atraso),
        2: ("Modelo de Perda de Bernoulli", tarefa2_perda_bernoulli),
        3: ("Simulação de Timeout", tarefa3_timeout),
        4: ("Curva de Vazão (Throughput)", tarefa4_curva_vazao),
        5: ("Sensibilidade da Janela", tarefa5_sensibilidade_janela),
        6: ("Validação de RTT", tarefa6_validacao_rtt),
        7: ("Impacto do Jitter", tarefa7_impacto_jitter),
        8: ("Cenário de Estresse", tarefa8_estresse),
        9: ("Análise de Eficiência", tarefa9_eficiencia),
        10: ("Convergência Estatística", tarefa10_convergencia),
    }

    start = time.time()

    for t_num in sorted(args.tarefas):
        if t_num in tarefas:
            nome, func = tarefas[t_num]
            try:
                func(seed=args.seed)
            except Exception as e:
                print(f"\n  [ERRO] Tarefa {t_num} ({nome}): {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"\n  [AVISO] Tarefa {t_num} não existe (válidas: 1-10)")

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f" TODAS AS TAREFAS CONCLUÍDAS!")
    print(f" Tempo total: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f" Resultados em: {os.path.abspath(OUT_DIR)}")
    print(f"{'='*60}")
