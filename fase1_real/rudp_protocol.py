import socket
import struct
import threading
import zlib
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constantes de Flags (usadas em operações bit-a-bit)
FLAG_SYN  = 0x01
FLAG_FIN  = 0x02
FLAG_ACK  = 0x04
FLAG_DATA = 0x08

class RUDPHeader:
    """
    Classe para representar e serializar o cabeçalho R-UDP customizado.
    Formato do Struct (Total = 64 bytes):
    - auth_len: 1 byte (!B) - tamanho do X-Custom-Auth real
    - auth_data: 50 bytes (50s) - X-Custom-Auth (Matrícula + Nome)
    - seq_num: 4 bytes (I) - Número de Sequência
    - ack_num: 4 bytes (I) - Número de Confirmação
    - flags: 1 byte (B) - Flags de controle
    - checksum: 4 bytes (I) - Checksum CRC32 do pacote
    """
    FORMAT = "!B 50s I I B I"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, auth_data, seq_num, ack_num, flags, checksum=0):
        # Trunca para no máximo 50 caracteres e codifica
        self.auth_data_bytes = str(auth_data)[:50].encode('utf-8')
        self.auth_len = len(self.auth_data_bytes)
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.flags = flags
        self.checksum = checksum

    def pack(self):
        """Serializa o cabeçalho em bytes."""
        return struct.pack(
            self.FORMAT,
            self.auth_len,
            self.auth_data_bytes.ljust(50, b'\0'),
            self.seq_num,
            self.ack_num,
            self.flags,
            self.checksum
        )

    @classmethod
    def unpack(cls, data):
        """Deserializa os bytes recebidos para um objeto RUDPHeader."""
        if len(data) < cls.SIZE:
            return None
        
        header_data = data[:cls.SIZE]
        auth_len, auth_bytes, seq_num, ack_num, flags, checksum = struct.unpack(cls.FORMAT, header_data)
        
        # Recupera apenas o tamanho útil da string
        auth_str = auth_bytes[:auth_len].decode('utf-8')
        return cls(auth_str, seq_num, ack_num, flags, checksum)

def calculate_packet_checksum(data_bytes):
    """
    Calcula o CRC32 do pacote inteiro, zerando temporariamente
    os 4 bytes do checksum no cabeçalho (posição 60 a 64).
    Isso unifica a validação e evita erros de repacking (struct).
    """
    if len(data_bytes) < RUDPHeader.SIZE:
        return 0
    temp = bytearray(data_bytes)
    # O campo checksum fica nos últimos 4 bytes do cabeçalho de 64 bytes
    temp[60:64] = b'\x00\x00\x00\x00'
    return zlib.crc32(temp) & 0xffffffff

class RUDPSocket:
    """
    Implementação de Transporte Seguro R-UDP sobre UDP padrão.
    Utiliza protocolo de Janela Deslizante Go-Back-N.
    """
    def __init__(self, auth_data="20261008479CarlosHenrique", timeout=0.5, window_size=10):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.auth_data = auth_data
        self.timeout = timeout
        self.window_size = window_size
        self.target_address = None
        self.srtt = None
        self.rttvar = None
        self.send_times = {}
        
        # Estado do Remetente (Go-Back-N)
        self.base = 0
        self.next_seq_num = 0
        
        # Estruturas para concorrência
        self.lock = threading.Lock()
        self.window_cond = threading.Condition(self.lock)
        
        # Timer global do remetente
        self.timer = None
        
        # Buffer de pacotes enviados e não confirmados: seq_num -> bytes_do_pacote_inteiro
        self.unacked_packets = {}  
        self.is_running = True
        
        # Estado do Receptor (Go-Back-N exige recebimento em ordem estrita)
        self.expected_seq_num = 0

    def bind(self, address):
        self.sock.bind(address)

    def connect(self, address):
        self.target_address = address

    def _start_timer(self):
        """Inicia (ou reinicia) o temporizador. Se ele expirar, chamará _handle_timeout."""
        if self.timer is not None:
            self.timer.cancel()
        self.timer = threading.Timer(self.timeout, self._handle_timeout)
        self.timer.daemon = True
        self.timer.start()

    def _stop_timer(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

    def _handle_timeout(self):
        """
        Rotina acionada caso o temporizador expire.
        Pela lógica Go-Back-N, retransmitimos *todos* os pacotes não confirmados
        presentes na janela atual [base, next_seq_num - 1].
        """
        try:
            with self.lock:
                if not self.unacked_packets or self.base >= self.next_seq_num:
                    return
                logging.warning(f"[TIMEOUT] Retransmitindo janela a partir de seq={self.base} até {self.next_seq_num - 1}. Buffer: {len(self.unacked_packets)} pacotes")
                self.send_times.clear()
                
                # Retransmite todos a partir do base até o que já foi enviado
                for seq in range(self.base, self.next_seq_num):
                    if seq in self.unacked_packets:
                        self.sock.sendto(self.unacked_packets[seq], self.target_address)
                
                # Reinicia o timer após a retransmissão
                self._start_timer()
        except Exception as e:
            logging.error(f"Erro crítico no handle_timeout: {e}")

    def _ack_listener(self):
        """
        Thread separada que escuta ACKs continuamente e de forma não-bloqueante para a thread principal.
        Se um ACK chegar, libera espaço na janela de envio (Go-Back-N).
        """
        # Setamos um pequeno timeout de escuta de socket para poder verificar is_running ciclicamente
        self.sock.settimeout(0.5)
        
        while self.is_running:
            try:
                data, _ = self.sock.recvfrom(2048)
                header = RUDPHeader.unpack(data)
                
                if not header:
                    continue
                
                # 1. Validar a integridade (Checksum) do pacote ACK
                calc_checksum = calculate_packet_checksum(data)
                if calc_checksum != header.checksum:
                    logging.warning(f"Corrupção detectada no receptor de ACKs! Calc={calc_checksum} != Recv={header.checksum}. Descartando.")
                    continue
                
                # Trata apenas se for um pacote do tipo ACK
                if header.flags & FLAG_ACK:
                    ack_num = header.ack_num
                    
                    with self.window_cond:
                        # Em Go-Back-N, um ACK N confirma *cumulativamente* todos os pacotes até N
                        if ack_num >= self.base:
                            logging.info(f"ACK Recebido: {ack_num}, Base Atual: {self.base}, Next: {self.next_seq_num}")

                            if ack_num in self.send_times:
                                rtt_sample = time.time() - self.send_times[ack_num]
                                if self.srtt is None:
                                    self.srtt = rtt_sample
                                    self.rttvar = rtt_sample / 2
                                else:
                                    self.rttvar = 0.75 * self.rttvar + 0.25 * abs(self.srtt - rtt_sample)
                                    self.srtt = 0.875 * self.srtt + 0.125 * rtt_sample

                                self.timeout = max(0.05, self.srtt + 4 * self.rttvar)
                                logging.debug(
                                    f"RTO atualizado: RTT={rtt_sample:.4f}s, "
                                    f"SRTT={self.srtt:.4f}s, RTTVAR={self.rttvar:.4f}s, "
                                    f"Timeout={self.timeout:.4f}s"
                                )
                            
                            # Remove do buffer tudo que foi confirmado (de base até ack_num)
                            for seq in range(self.base, ack_num + 1):
                                if seq in self.unacked_packets:
                                    del self.unacked_packets[seq]
                                self.send_times.pop(seq, None)
                            
                            # Atualiza a base
                            self.base = ack_num + 1
                            
                            # Gerencia o temporizador
                            if self.base == self.next_seq_num:
                                # Todos foram confirmados
                                logging.info("Janela Finalizada com Sucesso (Base == Next).")
                                self.unacked_packets.clear()
                                self._stop_timer()
                            else:
                                # Ainda tem pacote em voo, reinicia o timer da base
                                self._start_timer()
                            
                            # Acorda a Thread principal que possivelmente estava travada esperando espaço na janela
                            self.window_cond.notify_all()
                        else:
                            if ack_num == self.next_seq_num - 1 and self.base == self.next_seq_num:
                                logging.debug(f"ACK Final do pacote {ack_num} redundante recebido. Ignorando silenciosamente.")
                            else:
                                logging.info(f"ACK Duplicado/Ignorado: {ack_num} (Base Atual: {self.base}, Next: {self.next_seq_num})")
                            
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    logging.error(f"Erro na thread de escuta de ACK: {e}")

    def send_file(self, file_path, chunk_size=1024):
        """Método principal do cliente para envio de um arquivo inteiro via Go-Back-N."""
        self.is_running = True
        
        # Inicia a thread que recebe os ACKs paralelamente
        ack_thread = threading.Thread(target=self._ack_listener)
        ack_thread.daemon = True
        ack_thread.start()

        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                with self.window_cond:
                    # Lógica Go-Back-N: a Thread bloqueia se a janela estiver cheia
                    while self.next_seq_num >= self.base + self.window_size:
                        logging.debug(f"Janela cheia (Base: {self.base}, Nxt: {self.next_seq_num}). Aguardando ACKs...")
                        self.window_cond.wait()
                    
                    # Cria o cabeçalho base para os dados
                    seq_num = self.next_seq_num
                    header = RUDPHeader(self.auth_data, seq_num, 0, FLAG_DATA, 0)
                    
                    # Cria o pacote base com checksum zerado para poder calcular
                    packet_sem_checksum = header.pack() + chunk
                    
                    # Calcula e aplica o checksum no pacote bruto
                    checksum = calculate_packet_checksum(packet_sem_checksum)
                    header.checksum = checksum
                    
                    # Monta o pacote final e envia
                    packet_final = header.pack() + chunk
                    self.send_times[seq_num] = time.time()
                    self.sock.sendto(packet_final, self.target_address)
                    
                    # Guarda no buffer de retransmissão
                    self.unacked_packets[seq_num] = packet_final
                    
                    # Se foi o primeiro pacote do voo, liga o timer
                    if self.base == self.next_seq_num:
                        self._start_timer()
                    
                    self.next_seq_num += 1

        # Encerramento: Aguarda até todos os ACKs chegarem
        with self.window_cond:
            while self.base < self.next_seq_num:
                logging.info(f"Teardown: Aguardando esvaziamento da janela (Base: {self.base}, Next: {self.next_seq_num})...")
                self.window_cond.wait()
            
            # Quando todos os pacotes confirmarem, envia a flag FIN
            # Para simplificar, mandamos sem garantia estrita aqui, 
            # mas podemos mandar algumas vezes se necessário.
            logging.info("Enviando pacote FIN para encerrar a conexão de forma segura...")
            header_fin = RUDPHeader(self.auth_data, self.next_seq_num, 0, FLAG_FIN, 0)
            for _ in range(3):
                self.sock.sendto(header_fin.pack(), self.target_address)
                time.sleep(0.1)
            
        self.is_running = False
        self._stop_timer()

    def _send_ack(self, ack_num, addr):
        """Cria e envia um pacote ACK com checksum válido."""
        ack_header = RUDPHeader(self.auth_data, 0, ack_num, FLAG_ACK, 0)
        packet_sem_checksum = ack_header.pack()
        ack_header.checksum = calculate_packet_checksum(packet_sem_checksum)
        self.sock.sendto(ack_header.pack(), addr)

    def recv_file(self, save_path):
        """Método principal do servidor para receber dados via Go-Back-N."""
        self.sock.settimeout(1.0)
        self.expected_seq_num = 0
        
        with open(save_path, 'wb') as f:
            while True:
                try:
                    data, addr = self.sock.recvfrom(2048)
                    header = RUDPHeader.unpack(data)
                    
                    if not header:
                        continue
                        
                    payload = data[RUDPHeader.SIZE:]
                    
                    # 1. Validar a integridade (Checksum)
                    calc_checksum = calculate_packet_checksum(data)
                    
                    if calc_checksum != header.checksum:
                        logging.warning(f"Corrupção detectada no payload! Calc={calc_checksum} != Recv={header.checksum} (Seq={header.seq_num}). Descartando pacote.")
                        continue # Descarta pacote silenciosamente (o remetente dará timeout)
                    
                    # 2. Tratar Conexão FIN
                    if header.flags & FLAG_FIN:
                        logging.info("FIN recebido. Transferência finalizada com sucesso.")
                        # Retorna um ACK de FIN
                        self._send_ack(header.seq_num, addr)
                        break
                        
                    # 3. Tratar recebimento de Dados (Go-Back-N)
                    if header.flags & FLAG_DATA:
                        # GBN: Só processamos se for exatamente o pacote esperado em sequência
                        if header.seq_num == self.expected_seq_num:
                            f.write(payload)
                            
                            # Envia ACK confirmando este pacote
                            self._send_ack(self.expected_seq_num, addr)
                            
                            self.expected_seq_num += 1
                        else:
                            # Se não for o pacote esperado (perda anterior detectada ou duplicado)
                            # Nós enviamos o ACK da maior sequência *cumulativa* recebida até agora.
                            # Como a base começa em 0, se for > 0, devolve o expected-1.
                            logging.debug(f"Pacote {header.seq_num} fora de ordem. Esperado era {self.expected_seq_num}.")
                            if self.expected_seq_num > 0:
                                self._send_ack(self.expected_seq_num - 1, addr)

                except socket.timeout:
                    # Timeout do loop de recv_file, volta para o while
                    continue
                except Exception as e:
                    logging.error(f"Erro na recepção R-UDP: {e}")
