FROM ubuntu:24.04

# Evita prompts interativos durante a instalação do apt
ENV DEBIAN_FRONTEND=noninteractive

# Instala Python 3, tcpdump, iproute2 (para o comando tc) e iputils (ping)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    tcpdump \
    iproute2 \
    iputils-ping \
    && pip3 install dpkt --break-system-packages \
    && rm -rf /var/lib/apt/lists/*


# Configura o diretório de trabalho padrão do contêiner
WORKDIR /app

# Copia os arquivos locais para dentro do contêiner
COPY . /app/
