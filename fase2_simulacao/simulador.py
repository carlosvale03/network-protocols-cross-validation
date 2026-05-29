"""
==========================================================================
 Simulador de Eventos Discretos - Fase 2 (SimPy)
 PPGCC/UFPI - Redes de Computadores - 2026.1
 Aluno: Carlos Henrique - Matrícula: 20261008479

 Modela TCP nativo e R-UDP (Go-Back-N) para validação cruzada com a Fase 1.
 Executa N_EXECUCOES por cenário/protocolo e gera CSVs de resumo + eventos.
==========================================================================
"""

import os
import csv
import sys
import time
import simpy
import random
import argparse
import numpy as np
from collections import defaultdict

# ==============================================================
# CONSTANTES ALINHADAS COM A FASE 1 (rudp_protocol.py / cliente.py)
# ==============================================================
FILE_SIZE_DEFAULT = 10 * 1024 * 1024   # 10 MB (mesmo da Fase 1)
CHUNK_SIZE = 1024                       # 1024 bytes por pacote (mesmo da Fase 1)
WINDOW_SIZE_RUDP = 10                   # Janela Go-Back-N (mesmo da Fase 1)
TIMEOUT_RUDP = 0.5                      # 500 ms (mesmo da Fase 1)

# TCP - Parâmetros alinhados com defaults do Linux
TCP_INITIAL_CWND = 10                   # cwnd inicial (Linux default desde 2010)
TCP_INITIAL_SSTHRESH = 65535            # ssthresh inicial alto
TCP_MIN_RTO = 0.2                       # RTO mínimo (200ms)
TCP_MAX_RTO = 60.0                      # RTO máximo (60s)
TCP_ALPHA = 0.125                       # Fator EWMA para SRTT (RFC 6298)
TCP_BETA = 0.25                         # Fator EWMA para RTTVAR (RFC 6298)
TCP_DUP_ACK_THRESHOLD = 3              # Fast Retransmit após 3 ACKs duplicados

# Simulação
N_EXECUCOES = 30                        # Para convergência estatística (Tarefa 10)
HEADER_RUDP_SIZE = 64                   # Tamanho do cabeçalho R-UDP (struct de 64 bytes)
HEADER_TCP_SIZE = 20                    # Cabeçalho TCP padrão (20 bytes sem opções)
HEADER_UDP_SIZE = 8                     # Cabeçalho UDP padrão
HEADER_IP_SIZE = 20                     # Cabeçalho IP padrão
HEADER_ETH_SIZE = 14                    # Cabeçalho Ethernet
ACK_SIZE = HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_TCP_SIZE  # ACK TCP puro
BANDWIDTH_BYTES_PER_SEC = 12_500_000    # 100 Mbps = 12.5 MB/s


# ==============================================================
# CLASSE: Coletor de Eventos (registra tudo que acontece)
# ==============================================================
class EventCollector:
    """
    Registra cada evento individual da simulação com timestamp preciso.
    Armazena dados equivalentes ao CSV da Fase 1 (extrator_pcap.py).
    """
    def __init__(self):
        self.events = []
        self.rtt_samples = []         # RTT por pacote confirmado
        self.send_timestamps = {}     # seq_num -> timestamp de envio (para RTT)

    def log_event(self, timestamp, protocolo, tipo_evento, seq_num, ack_num,
                  tamanho_payload, tamanho_pacote, rtt_ms=None, perdido=False,
                  cwnd=None, ssthresh=None, janela=None, flags="",
                  retransmissao=False, timeout_disparado=False):
        """Registra um evento atômico da simulação."""
        self.events.append({
            'timestamp': round(timestamp, 6),
            'protocolo': protocolo,
            'tipo_evento': tipo_evento,           # DATA, ACK, RETX, TIMEOUT, LOSS, FIN, DUPACK
            'seq_num': seq_num,
            'ack_num': ack_num,
            'tamanho_payload': tamanho_payload,
            'tamanho_pacote': tamanho_pacote,      # payload + headers (equivalente ao frame Ethernet)
            'rtt_ms': round(rtt_ms, 4) if rtt_ms is not None else '',
            'perdido': 'Sim' if perdido else 'Nao',
            'retransmissao': 'Sim' if retransmissao else 'Nao',
            'timeout_disparado': 'Sim' if timeout_disparado else 'Nao',
            'cwnd': cwnd if cwnd is not None else '',
            'ssthresh': ssthresh if ssthresh is not None else '',
            'janela': janela if janela is not None else '',
            'flags': flags,
        })

    def record_send(self, seq_num, timestamp):
        """Registra o momento do envio para cálculo de RTT."""
        self.send_timestamps[seq_num] = timestamp

    def record_ack(self, seq_num, timestamp):
        """Calcula e registra o RTT quando o ACK chega."""
        if seq_num in self.send_timestamps:
            rtt = (timestamp - self.send_timestamps[seq_num]) * 1000  # em ms
            self.rtt_samples.append(rtt)
            del self.send_timestamps[seq_num]
            return rtt
        return None

    def get_stats(self):
        """Calcula estatísticas agregadas sobre RTT e jitter."""
        if not self.rtt_samples:
            return {
                'rtt_medio_ms': 0, 'rtt_desvio_ms': 0, 'rtt_min_ms': 0,
                'rtt_max_ms': 0, 'rtt_mediana_ms': 0, 'rtt_p95_ms': 0,
                'rtt_p99_ms': 0, 'jitter_medio_ms': 0, 'jitter_desvio_ms': 0,
                'jitter_max_ms': 0
            }

        rtts = np.array(self.rtt_samples)

        # Jitter = variação absoluta entre RTTs consecutivos (RFC 3550)
        if len(rtts) > 1:
            jitters = np.abs(np.diff(rtts))
        else:
            jitters = np.array([0.0])

        return {
            'rtt_medio_ms': round(float(np.mean(rtts)), 4),
            'rtt_desvio_ms': round(float(np.std(rtts)), 4),
            'rtt_min_ms': round(float(np.min(rtts)), 4),
            'rtt_max_ms': round(float(np.max(rtts)), 4),
            'rtt_mediana_ms': round(float(np.median(rtts)), 4),
            'rtt_p95_ms': round(float(np.percentile(rtts, 95)), 4),
            'rtt_p99_ms': round(float(np.percentile(rtts, 99)), 4),
            'jitter_medio_ms': round(float(np.mean(jitters)), 4),
            'jitter_desvio_ms': round(float(np.std(jitters)), 4),
            'jitter_max_ms': round(float(np.max(jitters)), 4),
        }


# ==============================================================
# CLASSE: Simulador R-UDP (Go-Back-N) — Espelha rudp_protocol.py
# ==============================================================
class RUDPSimulator:
    """
    Simulador Go-Back-N alinhado com a implementação real da Fase 1.
    Cada pacote tem: Header (64 bytes) + Payload (CHUNK_SIZE bytes).
    """
    def __init__(self, env, delay_ms, loss_prob, file_size=FILE_SIZE_DEFAULT,
                 window_size=WINDOW_SIZE_RUDP, timeout=TIMEOUT_RUDP):
        self.env = env
        self.delay = delay_ms / 1000.0
        self.loss_prob = loss_prob
        self.file_size = file_size
        self.total_packets = file_size // CHUNK_SIZE
        self.window_size = window_size
        self.timeout = timeout
        self.srtt = None
        self.rttvar = None
        self.send_times = {}

        # Estado Go-Back-N (espelha rudp_protocol.py)
        self.base = 0
        self.next_seq_num = 0
        self.expected_seq_num = 0

        # Canais SimPy
        self.channel_to_recv = simpy.Store(env)
        self.channel_to_send = simpy.Store(env)
        self.link_resource = simpy.Resource(env, capacity=1)

        # Métricas
        self.total_data_pkts_sent = 0   # Pacotes de dados enviados (incluindo retransmissões)
        self.total_acks_sent = 0         # Pacotes ACK enviados pelo receptor
        self.total_acks_received = 0     # ACKs recebidos pelo remetente
        self.retransmissions = 0         # Retransmissões por timeout
        self.packets_lost_data = 0       # Pacotes de dados perdidos na rede
        self.packets_lost_ack = 0        # ACKs perdidos na rede
        self.timeouts_disparados = 0     # Quantas vezes o timeout expirou
        self.dup_acks_received = 0       # ACKs duplicados recebidos

        self.unacked = set()
        self.timer_process = None
        self.sender_wakeup = env.event()

        # Controle FIFO do canal: garante que pacotes não cheguem fora de ordem
        # (jitter pode variar o delay mas não inverte a sequência)
        self.last_arrival_data = 0.0
        self.last_arrival_ack = 0.0

        # Coletor de eventos
        self.collector = EventCollector()

    def sender(self):
        while self.base < self.total_packets:
            while (self.next_seq_num < self.base + self.window_size and
                   self.next_seq_num < self.total_packets):
                seq = self.next_seq_num
                self.unacked.add(seq)

                if self.base == self.next_seq_num:
                    self.timer_process = self.env.process(self.timeout_timer())

                tamanho_payload = CHUNK_SIZE
                tamanho_pacote = HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_UDP_SIZE + HEADER_RUDP_SIZE + tamanho_payload

                self.collector.record_send(seq, self.env.now)
                self.send_times[seq] = self.env.now
                self.collector.log_event(
                    timestamp=self.env.now, protocolo='R-UDP', tipo_evento='DATA',
                    seq_num=seq, ack_num=0, tamanho_payload=tamanho_payload,
                    tamanho_pacote=tamanho_pacote, janela=self.window_size,
                    flags='DATA'
                )

                self.env.process(self.network_delay(seq, 'data'))
                self.total_data_pkts_sent += 1
                self.next_seq_num += 1

                yield self.env.timeout(0.0001)

            if self.base < self.total_packets:
                self.sender_wakeup = self.env.event()
                yield self.sender_wakeup

    def timeout_timer(self):
        try:
            yield self.env.timeout(self.timeout)
            if not self.unacked or self.base >= self.total_packets:
                return

            # Timeout expirou: Go-Back-N retransmite toda a janela pendente,
            # preservando base/next_seq_num/unacked. A janela so avanca com ACK.
            janela_pendente = sorted(self.unacked)
            n_retx = len(janela_pendente)
            self.retransmissions += n_retx
            self.timeouts_disparados += 1
            self.send_times.clear()

            self.collector.log_event(
                timestamp=self.env.now, protocolo='R-UDP', tipo_evento='TIMEOUT',
                seq_num=self.base, ack_num=0, tamanho_payload=0,
                tamanho_pacote=0, janela=self.window_size,
                timeout_disparado=True, flags='TIMEOUT'
            )

            # Retransmite de fato cada pacote ainda nao confirmado.
            for seq in janela_pendente:
                tamanho_payload = CHUNK_SIZE
                tamanho_pacote = HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_UDP_SIZE + HEADER_RUDP_SIZE + tamanho_payload
                self.collector.record_send(seq, self.env.now)
                self.collector.log_event(
                    timestamp=self.env.now, protocolo='R-UDP', tipo_evento='RETX',
                    seq_num=seq, ack_num=0, tamanho_payload=tamanho_payload,
                    tamanho_pacote=tamanho_pacote, janela=self.window_size,
                    retransmissao=True, flags='DATA'
                )
                self.env.process(self.network_delay(seq, 'data'))
                self.total_data_pkts_sent += 1

            if self.unacked and self.base < self.next_seq_num:
                self.timer_process = self.env.process(self.timeout_timer())
        except simpy.Interrupt:
            pass

    def ack_listener(self):
        last_ack = -1
        while self.base < self.total_packets:
            ack_num = yield self.channel_to_send.get()
            self.total_acks_received += 1

            rtt = self.collector.record_ack(ack_num, self.env.now)

            if ack_num >= self.base:
                if ack_num in self.send_times:
                    rtt_sample = self.env.now - self.send_times[ack_num]
                    if self.srtt is None:
                        self.srtt = rtt_sample
                        self.rttvar = rtt_sample / 2
                    else:
                        self.rttvar = 0.75 * self.rttvar + 0.25 * abs(self.srtt - rtt_sample)
                        self.srtt = 0.875 * self.srtt + 0.125 * rtt_sample

                    self.timeout = max(0.05, self.srtt + 4 * self.rttvar)

                tamanho_pacote_ack = HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_UDP_SIZE + HEADER_RUDP_SIZE
                self.collector.log_event(
                    timestamp=self.env.now, protocolo='R-UDP', tipo_evento='ACK',
                    seq_num=0, ack_num=ack_num, tamanho_payload=0,
                    tamanho_pacote=tamanho_pacote_ack, rtt_ms=rtt,
                    janela=self.window_size, flags='ACK'
                )

                for s in list(self.unacked):
                    if s <= ack_num:
                        self.unacked.remove(s)
                        self.send_times.pop(s, None)

                self.base = ack_num + 1

                if self.timer_process and self.timer_process.is_alive:
                    self.timer_process.interrupt()

                if self.base < self.next_seq_num:
                    self.timer_process = self.env.process(self.timeout_timer())

                if not self.sender_wakeup.triggered:
                    self.sender_wakeup.succeed()
            else:
                self.dup_acks_received += 1
                self.collector.log_event(
                    timestamp=self.env.now, protocolo='R-UDP', tipo_evento='DUPACK',
                    seq_num=0, ack_num=ack_num, tamanho_payload=0,
                    tamanho_pacote=HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_UDP_SIZE + HEADER_RUDP_SIZE,
                    janela=self.window_size, flags='ACK'
                )

            last_ack = ack_num

    def receiver(self):
        while True:
            seq_num = yield self.channel_to_recv.get()

            if seq_num == self.expected_seq_num:
                self.expected_seq_num += 1
                self.env.process(self.network_delay(self.expected_seq_num - 1, 'ack'))
                self.total_acks_sent += 1
            else:
                if self.expected_seq_num > 0:
                    self.env.process(self.network_delay(self.expected_seq_num - 1, 'ack'))
                    self.total_acks_sent += 1

    def network_delay(self, num, pkt_type):
        """Canal com fila física, transmissão serial, propagação e perda."""
        if pkt_type == 'data':
            frame_size = HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_UDP_SIZE + HEADER_RUDP_SIZE + CHUNK_SIZE
        else:
            frame_size = HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_UDP_SIZE + HEADER_RUDP_SIZE

        transmission_delay = frame_size / BANDWIDTH_BYTES_PER_SEC
        request = self.link_resource.request()
        yield request
        yield self.env.timeout(transmission_delay)
        self.link_resource.release(request)

        jitter = np.random.normal(0, self.delay * 0.1) if self.delay > 0 else 0
        desired_delay = max(0.001, self.delay + jitter)
        desired_arrival = self.env.now + desired_delay

        if pkt_type == 'data':
            actual_arrival = max(desired_arrival, self.last_arrival_data + 0.00001)
            self.last_arrival_data = actual_arrival
        else:
            actual_arrival = max(desired_arrival, self.last_arrival_ack + 0.00001)
            self.last_arrival_ack = actual_arrival

        yield self.env.timeout(actual_arrival - self.env.now)

        if random.random() >= self.loss_prob:
            if pkt_type == 'data':
                self.channel_to_recv.put(num)
            else:
                self.channel_to_send.put(num)
        else:
            # Pacote perdido
            if pkt_type == 'data':
                self.packets_lost_data += 1
                self.collector.log_event(
                    timestamp=self.env.now, protocolo='R-UDP', tipo_evento='LOSS',
                    seq_num=num, ack_num=0, tamanho_payload=CHUNK_SIZE,
                    tamanho_pacote=HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_UDP_SIZE + HEADER_RUDP_SIZE + CHUNK_SIZE,
                    perdido=True, janela=self.window_size, flags='DATA'
                )
            else:
                self.packets_lost_ack += 1
                self.collector.log_event(
                    timestamp=self.env.now, protocolo='R-UDP', tipo_evento='LOSS',
                    seq_num=0, ack_num=num, tamanho_payload=0,
                    tamanho_pacote=HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_UDP_SIZE + HEADER_RUDP_SIZE,
                    perdido=True, janela=self.window_size, flags='ACK'
                )


# ==============================================================
# CLASSE: Simulador TCP (Slow Start + Congestion Avoidance + Fast Retransmit)
# ==============================================================
class TCPSimulator:
    """
    Modelo simplificado de TCP (Reno) para comparação com R-UDP.
    Modela: Slow Start, Congestion Avoidance (AIMD), Fast Retransmit,
    RTO dinâmico (RFC 6298).
    """
    def __init__(self, env, delay_ms, loss_prob, file_size=FILE_SIZE_DEFAULT):
        self.env = env
        self.delay = delay_ms / 1000.0
        self.loss_prob = loss_prob
        self.file_size = file_size
        self.total_packets = file_size // CHUNK_SIZE

        # Estado TCP
        self.cwnd = TCP_INITIAL_CWND
        self.ssthresh = TCP_INITIAL_SSTHRESH
        self.next_seq_num = 0
        self.base = 0                   # Oldest unacked

        # RTO dinâmico (RFC 6298)
        self.srtt = None
        self.rttvar = None
        self.rto = 1.0                  # RTO inicial 1s (RFC 6298)

        # Canais
        self.channel_to_recv = simpy.Store(env)
        self.channel_to_send = simpy.Store(env)
        self.link_resource = simpy.Resource(env, capacity=1)

        # Métricas
        self.total_data_pkts_sent = 0
        self.total_acks_sent = 0
        self.total_acks_received = 0
        self.retransmissions = 0
        self.fast_retransmits = 0
        self.timeout_retransmits = 0
        self.timeouts_disparados = 0
        self.packets_lost_data = 0
        self.packets_lost_ack = 0
        self.dup_acks_received = 0
        self.slow_start_exits = 0       # Quantas vezes saiu de slow start

        # Fast retransmit tracking
        self.dup_ack_count = defaultdict(int)
        self.last_ack_num = -1

        self.unacked = set()
        self.retransmitted_packets = set()
        self.bytes_acked = 0
        self.timer_process = None

        # Controle FIFO do canal
        self.last_arrival_data = 0.0
        self.last_arrival_ack = 0.0
        self.sender_wakeup = env.event()

        # Histórico de cwnd para gráficos
        self.cwnd_history = []          # (timestamp, cwnd, ssthresh, fase)

        # Coletor de eventos
        self.collector = EventCollector()

    def _record_cwnd(self, fase):
        """Registra estado da janela de congestionamento."""
        self.cwnd_history.append({
            'timestamp': round(self.env.now, 6),
            'cwnd': round(self.cwnd, 2),
            'ssthresh': round(self.ssthresh, 2),
            'fase': fase  # 'SLOW_START', 'CONG_AVOID', 'FAST_RETX', 'TIMEOUT'
        })

    def _update_rto(self, rtt_sample):
        """Atualiza RTO usando algoritmo de Jacobson/Karels (RFC 6298)."""
        rtt_s = rtt_sample / 1000.0  # converter de ms para s

        if self.srtt is None:
            # Primeira medição
            self.srtt = rtt_s
            self.rttvar = rtt_s / 2.0
        else:
            self.rttvar = (1 - TCP_BETA) * self.rttvar + TCP_BETA * abs(self.srtt - rtt_s)
            self.srtt = (1 - TCP_ALPHA) * self.srtt + TCP_ALPHA * rtt_s

        self.rto = max(TCP_MIN_RTO, min(TCP_MAX_RTO, self.srtt + 4 * self.rttvar))

    def sender(self):
        self._record_cwnd('SLOW_START')
        while self.base < self.total_packets:
            effective_window = int(self.cwnd)
            while (self.next_seq_num < self.base + effective_window and
                   self.next_seq_num < self.total_packets):
                seq = self.next_seq_num
                self.unacked.add(seq)

                if self.base == self.next_seq_num:
                    self.timer_process = self.env.process(self.timeout_timer())

                tamanho_payload = CHUNK_SIZE
                tamanho_pacote = HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_TCP_SIZE + tamanho_payload

                self.collector.record_send(seq, self.env.now)
                self.collector.log_event(
                    timestamp=self.env.now, protocolo='TCP', tipo_evento='DATA',
                    seq_num=seq, ack_num=0, tamanho_payload=tamanho_payload,
                    tamanho_pacote=tamanho_pacote, cwnd=round(self.cwnd, 2),
                    ssthresh=round(self.ssthresh, 2), flags='PSH,ACK'
                )

                self.env.process(self.network_delay(seq, 'data'))
                self.total_data_pkts_sent += 1
                self.next_seq_num += 1

                yield self.env.timeout(0.0001)

            if self.base < self.total_packets:
                self.sender_wakeup = self.env.event()
                yield self.sender_wakeup

    def timeout_timer(self):
        try:
            yield self.env.timeout(self.rto)
            if self.base >= self.total_packets:
                return

            self.timeouts_disparados += 1

            self.collector.log_event(
                timestamp=self.env.now, protocolo='TCP', tipo_evento='TIMEOUT',
                seq_num=self.base, ack_num=0, tamanho_payload=0,
                tamanho_pacote=0, cwnd=round(self.cwnd, 2),
                ssthresh=round(self.ssthresh, 2),
                timeout_disparado=True, flags='TIMEOUT'
            )

            # TCP Reno: ssthresh = cwnd/2, cwnd = 1
            self.ssthresh = max(2, self.cwnd / 2)
            self.cwnd = 1
            self.rto = min(TCP_MAX_RTO, self.rto * 2)
            self._record_cwnd('TIMEOUT')

            # Retransmite o segmento mais antigo ainda nao confirmado.
            # Nao descartamos pacotes em voo nem recuamos next_seq_num: a
            # janela so anda quando ACKs cumulativos confirmam bytes reais.
            self.unacked = {s for s in self.unacked if s >= self.base}
            self.unacked.add(self.base)

            tamanho_payload = CHUNK_SIZE
            tamanho_pacote = HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_TCP_SIZE + tamanho_payload
            self.collector.record_send(self.base, self.env.now)
            self.collector.log_event(
                timestamp=self.env.now, protocolo='TCP', tipo_evento='RETX',
                seq_num=self.base, ack_num=0, tamanho_payload=tamanho_payload,
                tamanho_pacote=tamanho_pacote, cwnd=round(self.cwnd, 2),
                ssthresh=round(self.ssthresh, 2),
                retransmissao=True, flags='PSH,ACK'
            )
            self.env.process(self.network_delay(self.base, 'data'))
            self.retransmitted_packets.add(self.base)
            self.retransmissions += 1
            self.timeout_retransmits += 1
            self.total_data_pkts_sent += 1

            self.dup_ack_count.clear()
            self.timer_process = self.env.process(self.timeout_timer())

            if not self.sender_wakeup.triggered:
                self.sender_wakeup.succeed()
        except simpy.Interrupt:
            pass

    def ack_listener(self):
        while self.base < self.total_packets:
            ack_num = yield self.channel_to_send.get()
            self.total_acks_received += 1

            # Karn/Partridge: ACK cumulativo que cobre segmento retransmitido
            # nao gera amostra confiavel de RTT/RTO.
            ack_covers_retx = any(s <= ack_num for s in self.retransmitted_packets)
            if ack_num >= self.base and not ack_covers_retx:
                rtt = self.collector.record_ack(ack_num, self.env.now)
            else:
                rtt = None

            if rtt is not None:
                self._update_rto(rtt)

            if ack_num >= self.base:
                # Novo ACK cumulativo
                self.collector.log_event(
                    timestamp=self.env.now, protocolo='TCP', tipo_evento='ACK',
                    seq_num=0, ack_num=ack_num, tamanho_payload=0,
                    tamanho_pacote=ACK_SIZE, rtt_ms=rtt,
                    cwnd=round(self.cwnd, 2), ssthresh=round(self.ssthresh, 2),
                    flags='ACK'
                )

                pkts_acked = ack_num - self.base + 1

                for s in list(self.unacked):
                    if s <= ack_num:
                        self.unacked.remove(s)

                self.base = ack_num + 1
                self.bytes_acked = min(self.base * CHUNK_SIZE, self.file_size)
                self.retransmitted_packets = {
                    s for s in self.retransmitted_packets if s > ack_num
                }
                self.dup_ack_count.clear()

                # Atualizar cwnd
                if self.cwnd < self.ssthresh:
                    # Slow Start: cwnd += pkts_acked (crescimento exponencial)
                    self.cwnd += pkts_acked
                    self._record_cwnd('SLOW_START')
                else:
                    # Congestion Avoidance: cwnd += pkts_acked / cwnd (linear)
                    self.cwnd += pkts_acked / self.cwnd
                    self._record_cwnd('CONG_AVOID')

                if self.timer_process and self.timer_process.is_alive:
                    self.timer_process.interrupt()

                if self.base < self.next_seq_num:
                    self.timer_process = self.env.process(self.timeout_timer())

                if not self.sender_wakeup.triggered:
                    self.sender_wakeup.succeed()
            else:
                # ACK duplicado
                self.dup_acks_received += 1
                self.dup_ack_count[ack_num] += 1

                self.collector.log_event(
                    timestamp=self.env.now, protocolo='TCP', tipo_evento='DUPACK',
                    seq_num=0, ack_num=ack_num, tamanho_payload=0,
                    tamanho_pacote=ACK_SIZE,
                    cwnd=round(self.cwnd, 2), ssthresh=round(self.ssthresh, 2),
                    flags='ACK'
                )

                # Fast Retransmit: 3 ACKs duplicados
                if self.dup_ack_count[ack_num] == TCP_DUP_ACK_THRESHOLD:
                    self.fast_retransmits += 1
                    self.retransmissions += 1

                    # ssthresh = cwnd/2, cwnd = ssthresh + 3 (Fast Recovery entry)
                    self.ssthresh = max(2, self.cwnd / 2)
                    self.cwnd = self.ssthresh + TCP_DUP_ACK_THRESHOLD
                    self._record_cwnd('FAST_RETX')

                    retx_seq = ack_num + 1
                    if retx_seq < self.total_packets:
                        tamanho_payload = CHUNK_SIZE
                        tamanho_pacote = HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_TCP_SIZE + tamanho_payload
                        self.collector.record_send(retx_seq, self.env.now)
                        self.collector.log_event(
                            timestamp=self.env.now, protocolo='TCP', tipo_evento='FAST_RETX',
                            seq_num=retx_seq, ack_num=0,
                            tamanho_payload=tamanho_payload,
                            tamanho_pacote=tamanho_pacote,
                            cwnd=round(self.cwnd, 2), ssthresh=round(self.ssthresh, 2),
                            retransmissao=True, flags='PSH,ACK'
                        )
                        self.env.process(self.network_delay(retx_seq, 'data'))
                        self.retransmitted_packets.add(retx_seq)
                        self.total_data_pkts_sent += 1

                    if self.timer_process and self.timer_process.is_alive:
                        self.timer_process.interrupt()
                    self.timer_process = self.env.process(self.timeout_timer())

                    if not self.sender_wakeup.triggered:
                        self.sender_wakeup.succeed()

    def receiver(self):
        """Receptor TCP simplificado com ACKs cumulativos e buffer de reordenação."""
        expected = 0
        recv_buffer = set()

        while True:
            seq_num = yield self.channel_to_recv.get()

            if seq_num == expected:
                expected += 1
                # Verifica buffer para pacotes que já chegaram fora de ordem
                while expected in recv_buffer:
                    recv_buffer.remove(expected)
                    expected += 1
                self.env.process(self.network_delay(expected - 1, 'ack'))
                self.total_acks_sent += 1
            elif seq_num > expected:
                # Fora de ordem — armazena (TCP faz SACK, simplificamos)
                recv_buffer.add(seq_num)
                # Reenvia ACK do último em ordem (gera dup ACK)
                ack_val = expected - 1
                self.env.process(self.network_delay(ack_val, 'ack'))
                self.total_acks_sent += 1
            else:
                # Pacote já recebido (duplicado), reenvia ACK
                ack_val = expected - 1
                self.env.process(self.network_delay(ack_val, 'ack'))
                self.total_acks_sent += 1

    def network_delay(self, num, pkt_type):
        """Canal com fila física, transmissão serial, propagação e perda."""
        if pkt_type == 'data':
            frame_size = HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_TCP_SIZE + CHUNK_SIZE
        else:
            frame_size = ACK_SIZE

        transmission_delay = frame_size / BANDWIDTH_BYTES_PER_SEC
        request = self.link_resource.request()
        yield request
        yield self.env.timeout(transmission_delay)
        self.link_resource.release(request)

        jitter = np.random.normal(0, self.delay * 0.1) if self.delay > 0 else 0
        desired_delay = max(0.001, self.delay + jitter)
        desired_arrival = self.env.now + desired_delay

        if pkt_type == 'data':
            actual_arrival = max(desired_arrival, self.last_arrival_data + 0.00001)
            self.last_arrival_data = actual_arrival
        else:
            actual_arrival = max(desired_arrival, self.last_arrival_ack + 0.00001)
            self.last_arrival_ack = actual_arrival

        yield self.env.timeout(actual_arrival - self.env.now)

        if random.random() >= self.loss_prob:
            if pkt_type == 'data':
                self.channel_to_recv.put(num)
            else:
                self.channel_to_send.put(num)
        else:
            if pkt_type == 'data':
                self.packets_lost_data += 1
                self.collector.log_event(
                    timestamp=self.env.now, protocolo='TCP', tipo_evento='LOSS',
                    seq_num=num, ack_num=0, tamanho_payload=CHUNK_SIZE,
                    tamanho_pacote=HEADER_ETH_SIZE + HEADER_IP_SIZE + HEADER_TCP_SIZE + CHUNK_SIZE,
                    perdido=True, cwnd=round(self.cwnd, 2),
                    ssthresh=round(self.ssthresh, 2), flags='DATA'
                )
            else:
                self.packets_lost_ack += 1
                self.collector.log_event(
                    timestamp=self.env.now, protocolo='TCP', tipo_evento='LOSS',
                    seq_num=0, ack_num=num, tamanho_payload=0,
                    tamanho_pacote=ACK_SIZE, perdido=True,
                    cwnd=round(self.cwnd, 2), ssthresh=round(self.ssthresh, 2),
                    flags='ACK'
                )


# ==============================================================
# FUNÇÕES AUXILIARES: Execução e Escrita de Resultados
# ==============================================================

def run_single_simulation(protocolo, delay_ms, loss_prob, file_size=FILE_SIZE_DEFAULT,
                          window_size=WINDOW_SIZE_RUDP, seed=None):
    """
    Executa uma única simulação e retorna métricas + eventos.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    env = simpy.Environment()

    if protocolo == 'R-UDP':
        sim = RUDPSimulator(env, delay_ms, loss_prob, file_size, window_size)
    else:
        sim = TCPSimulator(env, delay_ms, loss_prob, file_size)

    env.process(sim.sender())
    env.process(sim.ack_listener())
    env.process(sim.receiver())

    env.run()

    if getattr(sim, 'bytes_acked', file_size) < file_size:
        raise RuntimeError(
            f"{protocolo} encerrou antes de confirmar o arquivo completo: "
            f"{getattr(sim, 'bytes_acked', 0)} de {file_size} bytes ACKed"
        )

    tempo_total = env.now
    vazao_mbps = (file_size * 8 / 1024 / 1024) / tempo_total if tempo_total > 0 else 0
    total_packets = file_size // CHUNK_SIZE

    # Dados úteis transmitidos vs total de bytes na rede
    bytes_dados_uteis = total_packets * CHUNK_SIZE
    bytes_total_enviados = sim.total_data_pkts_sent * (CHUNK_SIZE + (HEADER_RUDP_SIZE if protocolo == 'R-UDP' else HEADER_TCP_SIZE) + HEADER_IP_SIZE + HEADER_ETH_SIZE)

    stats = sim.collector.get_stats()

    # Eficiência: pacotes dados / (pacotes dados + pacotes controle)
    total_controle = sim.total_acks_sent + sim.total_acks_received
    total_dados = sim.total_data_pkts_sent
    if total_dados + total_controle > 0:
        eficiencia = total_dados / (total_dados + total_controle)
    else:
        eficiencia = 0

    # Taxa de perda observada corrigida (sem dupla contagem)
    total_tentativas = sim.total_data_pkts_sent + sim.total_acks_sent
    perdas_totais = sim.packets_lost_data + sim.packets_lost_ack
    taxa_perda_observada = perdas_totais / total_tentativas if total_tentativas > 0 else 0

    result = {
        'protocolo': protocolo,
        'tempo_total_s': round(tempo_total, 6),
        'vazao_mbps': round(vazao_mbps, 4),
        'total_pacotes_dados_enviados': sim.total_data_pkts_sent,
        'total_pacotes_uteis': total_packets,
        'total_retransmissoes': sim.retransmissions,
        'total_acks_enviados': sim.total_acks_sent,
        'total_acks_recebidos': sim.total_acks_received,
        'total_dup_acks': sim.dup_acks_received,
        'total_timeouts': sim.timeouts_disparados,
        'pacotes_perdidos_dados': sim.packets_lost_data,
        'pacotes_perdidos_ack': sim.packets_lost_ack,
        'taxa_perda_observada': round(taxa_perda_observada, 6),
        'eficiencia_dados_controle': round(eficiencia, 6),
        'bytes_dados_uteis': bytes_dados_uteis,
        'bytes_confirmados_ack': getattr(sim, 'bytes_acked', file_size),
        'bytes_total_na_rede': bytes_total_enviados,
        'overhead_pct': round((bytes_total_enviados - bytes_dados_uteis) / bytes_dados_uteis * 100, 2) if bytes_dados_uteis > 0 else 0,
        'rtt_medio_ms': stats['rtt_medio_ms'],
        'rtt_desvio_ms': stats['rtt_desvio_ms'],
        'rtt_min_ms': stats['rtt_min_ms'],
        'rtt_max_ms': stats['rtt_max_ms'],
        'rtt_mediana_ms': stats['rtt_mediana_ms'],
        'rtt_p95_ms': stats['rtt_p95_ms'],
        'rtt_p99_ms': stats['rtt_p99_ms'],
        'jitter_medio_ms': stats['jitter_medio_ms'],
        'jitter_desvio_ms': stats['jitter_desvio_ms'],
        'jitter_max_ms': stats['jitter_max_ms'],
    }

    # Métricas extras TCP
    if protocolo == 'TCP':
        result['fast_retransmits'] = sim.fast_retransmits
        result['timeout_retransmits'] = sim.timeout_retransmits
        result['slow_start_exits'] = sim.slow_start_exits
        result['rto_final_s'] = round(sim.rto, 6)
        result['cwnd_final'] = round(sim.cwnd, 2)
        result['ssthresh_final'] = round(sim.ssthresh, 2)

    # Métricas extras R-UDP
    if protocolo == 'R-UDP':
        result['janela_fixa'] = window_size

    return result, sim.collector.events, getattr(sim, 'cwnd_history', [])


def write_summary_csv(results, filepath):
    """Escreve CSV de resumo (uma linha por execução)."""
    if not results:
        return

    # Coletar todas as chaves únicas (TCP e R-UDP podem ter colunas diferentes)
    all_keys = []
    for r in results:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction='ignore')
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"  [CSV] Resumo salvo: {filepath} ({len(results)} linhas)")


def write_events_csv(events, filepath):
    """Escreve CSV de eventos detalhados (um por pacote)."""
    if not events:
        return

    fieldnames = [
        'timestamp', 'protocolo', 'tipo_evento', 'seq_num', 'ack_num',
        'tamanho_payload', 'tamanho_pacote', 'rtt_ms', 'perdido',
        'retransmissao', 'timeout_disparado', 'cwnd', 'ssthresh',
        'janela', 'flags'
    ]

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for e in events:
            writer.writerow(e)

    print(f"  [CSV] Eventos salvos: {filepath} ({len(events)} eventos)")


def write_cwnd_csv(cwnd_history, filepath):
    """Escreve histórico de cwnd para gráficos de congestionamento TCP."""
    if not cwnd_history:
        return

    fieldnames = ['timestamp', 'cwnd', 'ssthresh', 'fase']

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in cwnd_history:
            writer.writerow(row)

    print(f"  [CSV] Histórico cwnd salvo: {filepath} ({len(cwnd_history)} pontos)")


# ==============================================================
# MAIN: Orquestrador de Execução
# ==============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Simulador SimPy - TCP e R-UDP (Fase 2 - PPGCC/UFPI)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--execucoes", type=int, default=N_EXECUCOES,
                        help=f"Número de execuções por cenário (default: {N_EXECUCOES})")
    parser.add_argument("--out_dir", default="dados_e_logs/processados",
                        help="Diretório de saída dos CSVs")
    parser.add_argument("--eventos", action="store_true", default=True,
                        help="Salvar CSV de eventos detalhados (default: True)")
    parser.add_argument("--no-eventos", dest="eventos", action="store_false",
                        help="Não salvar CSV de eventos (mais rápido)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Seed base para reprodutibilidade (default: 42)")
    args = parser.parse_args()

    print("=" * 60)
    print(" SIMULADOR DE EVENTOS DISCRETOS - FASE 2 (SimPy)")
    print(" PPGCC/UFPI - Redes de Computadores - 2026.1")
    print(" Aluno: Carlos Henrique - Matrícula: 20261008479")
    print("=" * 60)
    print(f"\n Configuração:")
    print(f"   Arquivo simulado: {FILE_SIZE_DEFAULT / (1024*1024):.0f} MB")
    print(f"   Chunk: {CHUNK_SIZE} bytes")
    print(f"   Janela R-UDP: {WINDOW_SIZE_RUDP}")
    print(f"   Timeout R-UDP: {TIMEOUT_RUDP}s")
    print(f"   Execuções por cenário: {args.execucoes}")
    print(f"   Seed base: {args.seed}")
    print()

    # Cenários alinhados com a Fase 1 + cenário de estresse (Tarefa 8)
    cenarios = [
        ('A', 10, 0.0,  '0% loss / 10ms delay'),
        ('B', 50, 0.1,  '10% loss / 50ms delay'),
        ('C', 100, 0.2, '20% loss / 100ms delay'),
        ('D_estresse', 125, 0.25, '25% loss / 125ms delay (Tarefa 8 - Estresse)'),
    ]

    protocolos = ['TCP', 'R-UDP']

    all_results = []
    start_global = time.time()

    for cenario_nome, delay, loss, descricao in cenarios:
        print(f"\n{'='*60}")
        print(f" CENÁRIO {cenario_nome}: {descricao}")
        print(f"{'='*60}")

        for protocolo in protocolos:
            print(f"\n  >>> Protocolo: {protocolo} ({args.execucoes} execuções)")

            cenario_events = []       # Acumula eventos de todas as execuções
            cenario_cwnd = []         # Acumula cwnd (TCP)

            for i in range(args.execucoes):
                seed = args.seed + i + hash(cenario_nome) % 10000

                result, events, cwnd_hist = run_single_simulation(
                    protocolo=protocolo,
                    delay_ms=delay,
                    loss_prob=loss,
                    seed=seed
                )

                # Adiciona metadados da execução
                result['cenario'] = cenario_nome
                result['delay_ms'] = delay
                result['taxa_perda_config'] = loss
                result['execucao_id'] = i + 1
                result['seed'] = seed

                all_results.append(result)

                # Coleta eventos apenas da primeira execução (para não gerar arquivo gigante)
                if i == 0:
                    cenario_events = events
                    cenario_cwnd = cwnd_hist

                # Progresso
                if (i + 1) % 10 == 0 or i == 0 or i == args.execucoes - 1:
                    print(f"    Execução {i+1}/{args.execucoes}: "
                          f"Tempo={result['tempo_total_s']:.2f}s | "
                          f"Vazão={result['vazao_mbps']:.2f} Mbps | "
                          f"Retx={result['total_retransmissoes']} | "
                          f"RTT={result['rtt_medio_ms']:.2f}ms")

            # Salvar eventos detalhados da primeira execução
            if args.eventos and cenario_events:
                events_path = os.path.join(
                    args.out_dir,
                    f"simulacao_eventos_{cenario_nome}_{protocolo.replace('-', '')}.csv"
                )
                write_events_csv(cenario_events, events_path)

            # Salvar cwnd (apenas TCP)
            if protocolo == 'TCP' and cenario_cwnd:
                cwnd_path = os.path.join(
                    args.out_dir,
                    f"simulacao_cwnd_{cenario_nome}_TCP.csv"
                )
                write_cwnd_csv(cenario_cwnd, cwnd_path)

    # Salvar CSV de resumo consolidado
    summary_path = os.path.join(args.out_dir, "simulacao_resumo.csv")
    write_summary_csv(all_results, summary_path)

    elapsed = time.time() - start_global
    total_simulations = len(all_results)

    print(f"\n{'='*60}")
    print(f" SIMULAÇÃO CONCLUÍDA!")
    print(f"{'='*60}")
    print(f"  Total de simulações: {total_simulations}")
    print(f"  Tempo total: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"  Resultados em: {os.path.abspath(args.out_dir)}")
    print(f"{'='*60}")
