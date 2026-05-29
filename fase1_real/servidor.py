import socket
import time
import argparse
import os
import logging
from rudp_protocol import RUDPSocket

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Servidor:
    """
    Camada de Aplicação (Servidor). Prepara o socket local para escutar
    transferências tanto TCP padrão quanto no nosso protocolo R-UDP.
    """
    def __init__(self, host, port, auth_data):
        self.host = host
        self.port = port
        self.auth_data = auth_data

    def iniciar(self, modo):
        if modo == "TCP":
            self._escutar_tcp()
        else:
            self._escutar_rudp()

    def _escutar_tcp(self):
        """
        Escuta TCP em loop contínuo, aceitando múltiplas conexões sequenciais.
        Isso permite rodar cenários A, B e C sem reiniciar o container.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CONGESTION, b'reno')
        except Exception as e:
            logging.warning(f"Não foi possível forçar TCP Reno via socket: {e}")
        sock.bind((self.host, self.port))
        sock.listen(1)
        
        sessao = 0
        logging.info(f"Servidor TCP escutando em {self.host}:{self.port} (modo loop)...")
        
        while True:
            conn, addr = sock.accept()
            sessao += 1
            logging.info(f"[Sessão TCP #{sessao}] Conexão recebida de {addr}")
            
            start_time = time.time()
            bytes_received = 0
            
            filename = f"arquivo_recebido_tcp_{sessao}.bin"
            with open(filename, 'wb') as f:
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    f.write(data)
                    bytes_received += len(data)
                    
            conn.close()
            end_time = time.time()
            
            self.registrar_metricas(start_time, end_time, bytes_received, f"TCP (Sessão #{sessao})")
            logging.info(f"[Sessão TCP #{sessao}] Aguardando próxima conexão...")

    def _escutar_rudp(self):
        """
        Escuta R-UDP em loop contínuo, aceitando múltiplas transferências.
        Usa um único socket UDP com SO_REUSEADDR e reseta apenas o estado
        do Go-Back-N entre sessões para evitar erro de porta ocupada.
        """
        sessao = 0
        logging.info(f"Servidor R-UDP escutando em {self.host}:{self.port} (modo loop)...")
        
        # Cria o socket UDP uma única vez
        base_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        base_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        base_sock.bind((self.host, self.port))
        
        while True:
            sessao += 1
            
            # Cria um RUDPSocket injetando o socket já existente
            rudp_sock = RUDPSocket(auth_data=self.auth_data)
            rudp_sock.sock = base_sock  # Reutiliza o socket base
            rudp_sock.expected_seq_num = 0  # Reseta estado Go-Back-N
            
            logging.info(f"[Sessão R-UDP #{sessao}] Aguardando transferência...")
            
            start_time = time.time()
            filename = f"arquivo_recebido_rudp_{sessao}.bin"
            
            # A rotina recv_file só destrava quando um sinalizador FIN for processado
            rudp_sock.recv_file(filename)
            end_time = time.time()
            
            # Como o receptor grava direto no disco, pegamos o tamanho do arquivo
            bytes_received = os.path.getsize(filename) if os.path.exists(filename) else 0
            self.registrar_metricas(start_time, end_time, bytes_received, f"R-UDP (Sessão #{sessao})")

    def registrar_metricas(self, start, end, total_bytes, modo):
        """Exibe os resultados da recepção, como o tempo real decorrido no servidor."""
        duration = end - start
        if duration <= 0:
            duration = 0.001
            
        throughput = (total_bytes * 8 / 1024 / 1024) / duration 
        
        logging.info("=========================================")
        logging.info(f"MÉTRICAS DO SERVIDOR: MODO {modo}")
        logging.info("=========================================")
        logging.info(f"Tempo Total Recv:    {duration:.4f} s")
        logging.info(f"Vazão (Throughput):  {throughput:.4f} Mbps")
        logging.info(f"Total de Bytes:      {total_bytes}")
        logging.info("=========================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor de Transferência de Arquivos")
    parser.add_argument("--host", default="0.0.0.0", help="Endereço IP de escuta")
    parser.add_argument("--port", type=int, default=5000, help="Porta de escuta")
    parser.add_argument("--modo", choices=["TCP", "RUDP"], default="TCP", help="Modo de transporte")
    parser.add_argument("--auth", default="20261008479CarlosHenrique", help="Cabeçalho X-Custom-Auth Esperado")
    
    args = parser.parse_args()

    servidor = Servidor(args.host, args.port, args.auth)
    
    try:
        servidor.iniciar(args.modo)
    except KeyboardInterrupt:
        logging.info("Servidor encerrado pelo usuário.")
