FROM ubuntu:22.04

# Install essentials
RUN apt-get update && apt-get install -y \
    python3 python3-pip git curl wget \
    build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

# Install Go
RUN curl -sL https://go.dev/dl/go1.24.2.linux-arm64.tar.gz | tar -C /usr/local -xz
ENV PATH="/usr/local/go/bin:${PATH}"

# Install Rust  
RUN curl -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs

# Install FLUX runtime from GitHub
RUN git clone https://github.com/SuperInstance/flux-runtime.git /opt/flux-runtime

# Install cross-assembler
RUN git clone https://github.com/SuperInstance/flux-cross-assembler.git /opt/flux-cross-assembler

# Set up workspace
RUN mkdir -p /workspace/vessel /workspace/repos
WORKDIR /workspace

# Copy agent bridge
COPY agent_bridge.py /workspace/

# Environment
ENV PYTHONPATH="/opt/flux-runtime/src:${PYTHONPATH}"
ENV FLUX_AGENT=1

# Entry: boot the agent
CMD ["python3", "-c", "from agent_bridge import *; import os; rt=FluxAgentRuntime(os.environ['GITHUB_TOKEN']); rt.boot(open('/workspace/onboarding.md').read() if os.path.exists('/workspace/onboarding.md') else '')"]
