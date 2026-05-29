#!/bin/bash
# ==========================================================================
# Cenário A: 0% de perda / 10 ms de delay
# Executa transferência em AMBOS os modos: TCP nativo e R-UDP (Go-Back-N)
# ==========================================================================

AUTH="20261008479CarlosHenrique"
SERVER_HOST_TCP="servidor_tcp"
SERVER_HOST_RUDP="servidor_rudp"
SERVER_PORT_TCP=5001
SERVER_PORT_RUDP=5000
TEST_FILE="/app/arquivo_teste.bin"

echo "==========================================="
echo "        INICIANDO CENÁRIO A"
echo "   (0% loss / 10ms delay)"
echo "==========================================="

# 1. Limpar regras antigas do Traffic Control (tc)
echo "[1] Removendo regras de rede antigas..."
tc qdisc del dev eth0 root 2> /dev/null

# 1b. Forçar TCP Reno no kernel (alinhamento com Fase 2 - SimPy)
echo "[1b] Forçando algoritmo de congestionamento TCP Reno..."
sysctl -w net.ipv4.tcp_congestion_control=reno

# 2. Aplicar a nova restrição de rede no container Cliente
echo "[2] Aplicando restrições: 10ms de delay | 0% de loss"
tc qdisc add dev eth0 root netem delay 10ms

# 3. Geração de Massa de Dados (Dummy file de 10 MB)
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

# 4a. Iniciar a Captura de Pacotes para TCP
echo "[4a] Iniciando tcpdump para captura TCP..."
tcpdump -i eth0 -w /app/dados_e_logs/pcap/cenarioA_tcp.pcap &
TCPDUMP_PID=$!
sleep 1

# 5a. Executar a Transferência TCP
echo "[5a] Iniciando cliente TCP..."
python3 cliente.py --host "$SERVER_HOST_TCP" --port "$SERVER_PORT_TCP" --file "$TEST_FILE" --modo TCP --auth "$AUTH"

# 6a. Finaliza o tcpdump
echo "[6a] Transferência TCP concluída! Desligando tcpdump..."
sleep 1
kill $TCPDUMP_PID 2>/dev/null
wait $TCPDUMP_PID 2>/dev/null

# Pequena pausa entre testes para garantir cleanup
sleep 2

# =============================================
# ETAPA R-UDP (Go-Back-N)
# =============================================
echo ""
echo ">>> ETAPA 2/2: Transferência R-UDP (Go-Back-N) <<<"
echo ""

# 4b. Iniciar a Captura de Pacotes para R-UDP
echo "[4b] Iniciando tcpdump para captura R-UDP..."
tcpdump -i eth0 -w /app/dados_e_logs/pcap/cenarioA_rudp.pcap &
TCPDUMP_PID=$!
sleep 1

# 5b. Executar a Transferência R-UDP
echo "[5b] Iniciando cliente R-UDP..."
python3 cliente.py --host "$SERVER_HOST_RUDP" --port "$SERVER_PORT_RUDP" --file "$TEST_FILE" --modo RUDP --auth "$AUTH"

# 6b. Finaliza o tcpdump
echo "[6b] Transferência R-UDP concluída! Desligando tcpdump..."
sleep 1
kill $TCPDUMP_PID 2>/dev/null
wait $TCPDUMP_PID 2>/dev/null

echo ""
echo "==========================================="
echo "  Cenário A finalizado com sucesso."
echo "  Capturas salvas:"
echo "    - cenarioA_tcp.pcap"
echo "    - cenarioA_rudp.pcap"
echo "==========================================="
