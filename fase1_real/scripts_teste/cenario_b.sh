#!/bin/bash
# ==========================================================================
# Cenário B: 10% de perda / 50 ms de delay
# Executa transferência em AMBOS os modos: TCP nativo e R-UDP (Go-Back-N)
# ==========================================================================

AUTH="20261008479CarlosHenrique"
SERVER_HOST_TCP="servidor_tcp"
SERVER_HOST_RUDP="servidor_rudp"
SERVER_PORT_TCP=5001
SERVER_PORT_RUDP=5000
TEST_FILE="/app/arquivo_teste.bin"

echo "==========================================="
echo "        INICIANDO CENÁRIO B"
echo "   (10% loss / 50ms delay)"
echo "==========================================="

# 1. Limpar regras antigas do Traffic Control (tc)
echo "[1] Removendo regras de rede antigas..."
tc qdisc del dev eth0 root 2> /dev/null

# 1b. Forçar TCP Reno no kernel (alinhamento com Fase 2 - SimPy)
echo "[1b] Forçando algoritmo de congestionamento TCP Reno..."
sysctl -w net.ipv4.tcp_congestion_control=reno

# 2. Aplicar a nova restrição de rede
echo "[2] Aplicando restrições: 50ms de delay | 10% de loss"
tc qdisc add dev eth0 root netem delay 50ms loss 10%

# 3. Geração de Massa de Dados
if [ ! -f "$TEST_FILE" ]; then
    echo "[3] Gerando arquivo de teste de 10 MB (arquivo_teste.bin)..."
    dd if=/dev/urandom of="$TEST_FILE" bs=1M count=10
else
    echo "[3] Arquivo de teste de 10 MB já existe."
fi

# =============================================
# ETAPA TCP NATIVO
# =============================================
echo ""
echo ">>> ETAPA 1/2: Transferência TCP Nativa <<<"
echo ""

echo "[4a] Iniciando tcpdump para captura TCP..."
tcpdump -i eth0 -w /app/dados_e_logs/pcap/cenarioB_tcp.pcap &
TCPDUMP_PID=$!
sleep 1

echo "[5a] Iniciando cliente TCP..."
python3 cliente.py --host "$SERVER_HOST_TCP" --port "$SERVER_PORT_TCP" --file "$TEST_FILE" --modo TCP --auth "$AUTH"

echo "[6a] Transferência TCP concluída! Desligando tcpdump..."
sleep 1
kill $TCPDUMP_PID 2>/dev/null
wait $TCPDUMP_PID 2>/dev/null

sleep 2

# =============================================
# ETAPA R-UDP (Go-Back-N)
# =============================================
echo ""
echo ">>> ETAPA 2/2: Transferência R-UDP (Go-Back-N) <<<"
echo ""

echo "[4b] Iniciando tcpdump para captura R-UDP..."
tcpdump -i eth0 -w /app/dados_e_logs/pcap/cenarioB_rudp.pcap &
TCPDUMP_PID=$!
sleep 1

echo "[5b] Iniciando cliente R-UDP..."
python3 cliente.py --host "$SERVER_HOST_RUDP" --port "$SERVER_PORT_RUDP" --file "$TEST_FILE" --modo RUDP --auth "$AUTH"

echo "[6b] Transferência R-UDP concluída! Desligando tcpdump..."
sleep 1
kill $TCPDUMP_PID 2>/dev/null
wait $TCPDUMP_PID 2>/dev/null

echo ""
echo "==========================================="
echo "  Cenário B finalizado com sucesso."
echo "  Capturas salvas:"
echo "    - cenarioB_tcp.pcap"
echo "    - cenarioB_rudp.pcap"
echo "==========================================="
