import os
import csv
import socket
import argparse
try:
    import dpkt
except ImportError:
    print("Biblioteca 'dpkt' não encontrada. Instale usando: pip install dpkt")
    exit(1)

# Valor real do cabeçalho X-Custom-Auth para detecção nos pacotes
AUTH_VALUE = "20261008479CarlosHenrique"

def flags_tcp_para_texto(flags):
    """Converte bitmask de flags TCP para string legível (ex: SYN,ACK)."""
    nomes = []
    if flags & dpkt.tcp.TH_SYN:
        nomes.append("SYN")
    if flags & dpkt.tcp.TH_FIN:
        nomes.append("FIN")
    if flags & dpkt.tcp.TH_RST:
        nomes.append("RST")
    if flags & dpkt.tcp.TH_PUSH:
        nomes.append("PSH")
    if flags & dpkt.tcp.TH_ACK:
        nomes.append("ACK")
    if flags & dpkt.tcp.TH_URG:
        nomes.append("URG")
    return ",".join(nomes) if nomes else ""

def extrair_pcap_para_csv(pcap_file, csv_file):
    print(f"Lendo arquivo: {pcap_file} ...")
    
    with open(pcap_file, 'rb') as f_in, open(csv_file, 'w', newline='', encoding='utf-8') as f_out:
        try:
            pcap = dpkt.pcap.Reader(f_in)
        except ValueError:
            print(f"Formato não suportado nativamente pelo dpkt (pode ser pcapng). Tente capturar sem a flag pcapng no tcpdump.")
            return

        writer = csv.writer(f_out)
        writer.writerow([
            'timestamp',
            'protocolo',           # TCP, UDP, ICMP, Outro
            'ip_origem',
            'porta_origem',
            'ip_destino',
            'porta_destino',
            'tamanho_pacote',       # Tamanho total do frame (bytes)
            'tamanho_payload',      # Tamanho apenas do payload de transporte (bytes)
            'ip_ttl',               # Time to Live do pacote IP
            'flags_tcp',            # Flags TCP legíveis (SYN,ACK,FIN...) - vazio se UDP
            'numero_sequencia_tcp', # Sequence Number TCP (raw) - vazio se UDP
            'numero_ack_tcp',       # Acknowledgment Number TCP (raw) - vazio se UDP
            'tamanho_janela_tcp',   # Window Size TCP - vazio se UDP
            'auth_header_presente'  # Se o payload contém o X-Custom-Auth
        ])
        
        count = 0
        for timestamp, buf in pcap:
            count += 1
            try:
                # O tcpdump em eth0 no docker normalmente usa Ethernet
                eth = dpkt.ethernet.Ethernet(buf)
                
                # Se não for pacote IP, ignoramos
                if not isinstance(eth.data, dpkt.ip.IP):
                    continue
                
                ip = eth.data
                ip_src = socket.inet_ntoa(ip.src)
                ip_dst = socket.inet_ntoa(ip.dst)
                ip_ttl = ip.ttl
                
                tamanho = len(buf)
                porta_src = ""
                porta_dst = ""
                payload = b""
                protocolo = "Outro"
                flags_tcp = ""
                seq_tcp = ""
                ack_tcp = ""
                win_tcp = ""
                tamanho_payload = 0
                
                if isinstance(ip.data, dpkt.tcp.TCP):
                    protocolo = "TCP"
                    tcp = ip.data
                    porta_src = tcp.sport
                    porta_dst = tcp.dport
                    payload = tcp.data
                    tamanho_payload = len(tcp.data)
                    flags_tcp = flags_tcp_para_texto(tcp.flags)
                    seq_tcp = tcp.seq
                    ack_tcp = tcp.ack
                    win_tcp = tcp.win
                elif isinstance(ip.data, dpkt.udp.UDP):
                    protocolo = "UDP"
                    udp = ip.data
                    porta_src = udp.sport
                    porta_dst = udp.dport
                    payload = udp.data
                    tamanho_payload = len(udp.data)
                elif isinstance(ip.data, dpkt.icmp.ICMP):
                    protocolo = "ICMP"
                
                # Verifica se o header X-Custom-Auth está no payload
                auth_presente = "Nao"
                if AUTH_VALUE.encode('utf-8') in payload:
                    auth_presente = "Sim"
                    
                writer.writerow([
                    timestamp,
                    protocolo,
                    ip_src,
                    porta_src,
                    ip_dst,
                    porta_dst,
                    tamanho,
                    tamanho_payload,
                    ip_ttl,
                    flags_tcp,
                    seq_tcp,
                    ack_tcp,
                    win_tcp,
                    auth_presente
                ])
            except Exception as e:
                # Ignora pacotes malformados
                pass
                
        print(f"Sucesso! {count} pacotes processados e salvos em {csv_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extrai pacotes de .pcap para .csv usando dpkt")
    parser.add_argument("--pcap_dir", default="../dados_e_logs/pcap", help="Diretório contendo os arquivos .pcap")
    parser.add_argument("--out_dir", default="../dados_e_logs/processados", help="Diretório de saída para os arquivos .csv")
    args = parser.parse_args()
    
    # Resolve caminhos relativos de onde o script está sendo chamado
    base_path = os.getcwd()
    pcap_dir = os.path.abspath(os.path.join(base_path, args.pcap_dir))
    out_dir = os.path.abspath(os.path.join(base_path, args.out_dir))
    
    # Se estiver rodando da raiz, ajusta o default automaticamente
    if os.path.exists(os.path.join(base_path, "dados_e_logs/pcap")):
        pcap_dir = os.path.join(base_path, "dados_e_logs/pcap")
        out_dir = os.path.join(base_path, "dados_e_logs/processados")
    
    if not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
        
    encontrou_pcap = False
    if os.path.exists(pcap_dir):
        for filename in os.listdir(pcap_dir):
            if filename.endswith('.pcap'):
                encontrou_pcap = True
                pcap_path = os.path.join(pcap_dir, filename)
                csv_path = os.path.join(out_dir, filename.replace('.pcap', '.csv'))
                extrair_pcap_para_csv(pcap_path, csv_path)
    
    if not encontrou_pcap:
        print(f"Nenhum arquivo .pcap encontrado em: {pcap_dir}")
