import socket
import time
import argparse
import os
import logging
from rudp_protocol import RUDPSocket

# Configuração simples de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Cliente:
    """
    Camada de Aplicação (Cliente). Abstrai a lógica de se comunicar com TCP padrão
    ou usando a nossa implementação R-UDP (Go-Back-N).
    """
    def __init__(self, host, port, auth_data):
        self.host = host
        self.port = port
        self.auth_data = auth_data

    def transferir_tcp(self, file_path):
        """Transfere o arquivo usando o protocolo TCP convencional do S.O."""
        logging.info(f"Iniciando transferência TCP para {self.host}:{self.port}...")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CONGESTION, b'reno')
        except Exception as e:
            logging.warning(f"Não foi possível forçar TCP Reno via socket: {e}")
        sock.connect((self.host, self.port))
        
        start_time = time.time()
        bytes_sent = 0
        
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                sock.sendall(chunk)
                bytes_sent += len(chunk)
                
        sock.close()
        end_time = time.time()
        
        self.registrar_metricas(start_time, end_time, bytes_sent, "TCP")

    def transferir_rudp(self, file_path):
        """Transfere o arquivo usando a nossa implementação de transporte R-UDP."""
        logging.info(f"Iniciando transferência R-UDP para {self.host}:{self.port}...")
        
        rudp_sock = RUDPSocket(auth_data=self.auth_data, timeout=0.5, window_size=10)
        rudp_sock.connect((self.host, self.port))
        
        start_time = time.time()
        # Chama a função não bloqueante baseada em Janela Deslizante
        rudp_sock.send_file(file_path, chunk_size=1024)
        end_time = time.time()
        
        bytes_sent = os.path.getsize(file_path)
        self.registrar_metricas(start_time, end_time, bytes_sent, "R-UDP")

    def registrar_metricas(self, start, end, total_bytes, modo):
        """Calcula e exibe/registra o tempo da transferência e a Vazão (Throughput)."""
        duration = end - start
        if duration <= 0:
            duration = 0.001
            
        # Vazão = (Bytes * 8 bits) / (1024 * 1024) / Tempo (em Segundos) = Mbps
        throughput = (total_bytes * 8 / 1024 / 1024) / duration 
        
        logging.info("=========================================")
        logging.info(f"MÉTRICAS DO CLIENTE: MODO {modo}")
        logging.info("=========================================")
        logging.info(f"Tempo Total:         {duration:.4f} s")
        logging.info(f"Vazão (Throughput):  {throughput:.4f} Mbps")
        logging.info(f"Total de Bytes:      {total_bytes}")
        logging.info("=========================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente de Transferência de Arquivos")
    parser.add_argument("--host", default="127.0.0.1", help="Endereço IP do servidor")
    parser.add_argument("--port", type=int, default=5000, help="Porta de destino")
    parser.add_argument("--file", required=True, help="Caminho do arquivo a ser enviado")
    parser.add_argument("--modo", choices=["TCP", "RUDP"], default="TCP", help="Modo de transporte")
    parser.add_argument("--auth", default="20261008479CarlosHenrique", help="Cabeçalho X-Custom-Auth")
    
    args = parser.parse_args()

    if not os.path.exists(args.file):
        logging.error(f"Arquivo não encontrado: {args.file}")
        exit(1)

    cliente = Cliente(args.host, args.port, args.auth)
    
    if args.modo == "TCP":
        cliente.transferir_tcp(args.file)
    else:
        cliente.transferir_rudp(args.file)
