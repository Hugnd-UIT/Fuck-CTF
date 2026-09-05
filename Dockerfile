FROM kalilinux/kali-rolling

LABEL maintainer="Fuck CTF"

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    kali-linux-headless \
    curl \
    wget \
    netcat-traditional \
    socat \
    sshpass \
    git \
    unzip \
    tar \
    file \
    xxd \
    ca-certificates \

    # Compilers 
    build-essential \
    pkg-config \
    libffi-dev \
    libssl-dev \
    python3-dev \

    # Languages
    python3 \
    python3-pip \
    python3-venv \
    php-cli \
    perl \
    ruby \
    ruby-dev \

    # Web & Network
    nmap \
    rustscan \
    ffuf \
    gobuster \
    dirsearch \
    sqlmap \

    # Pwn & Reverse
    gdb \
    gdbserver \
    strace \
    ltrace \
    binutils \
    patchelf \
    upx-ucl \
    radare2 \
    checksec \

    # Crypto & Math
    python3-pwntools \
    python3-ropgadget \
    python3-pycryptodome \
    python3-sympy \
    python3-gmpy2 \
    python3-z3 \
    python3-requests \

    # Password Cracking & Forensics
    john \
    hashcat \
    binwalk \
    exiftool \
    steghide \
    && rm -rf /var/lib/apt/lists/*

RUN rm -f /usr/lib/python3.*/EXTERNALLY-MANAGED

RUN gem install --no-document one_gadget seccomp-tools
RUN pip3 install --no-cache-dir ropper angr

RUN curl -L https://github.com/carlospolop/PEASS-ng/releases/latest/download/linpeas.sh -o /usr/local/bin/linpeas && \
    chmod +x /usr/local/bin/linpeas

RUN git clone --depth 1 https://github.com/pwndbg/pwndbg /opt/pwndbg && \
    cd /opt/pwndbg && ./setup.sh

RUN mkdir -p /root/.ssh && \
    ssh-keyscan -p 2220 bandit.labs.overthewire.org >> /root/.ssh/known_hosts 2>/dev/null || true && \
    ssh-keyscan -p 2231 krypton.labs.overthewire.org >> /root/.ssh/known_hosts 2>/dev/null || true && \
    ssh-keyscan -p 2223 leviathan.labs.overthewire.org >> /root/.ssh/known_hosts 2>/dev/null || true

WORKDIR /data

CMD ["/bin/bash"]