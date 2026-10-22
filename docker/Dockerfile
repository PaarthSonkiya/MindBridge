# MindBridge for RB3 Gen 2 (linux/arm64). Build once online, then run fully offline.
#
#   docker buildx build --platform linux/arm64 -f docker/Dockerfile -t mindbridge:0.3 .
#   docker save mindbridge:0.3 | gzip > mindbridge-0.3-arm64.tar.gz      # ship this to judges
#
# Run on the device with Wi-Fi/Ethernet switched off (models mounted read-only; NPU and sound passed through).
# --network host only exposes the UI on 127.0.0.1; MindBridge itself blocks every non-loopback connection.
#   docker load < mindbridge-0.3-arm64.tar.gz
#   docker run --rm -it --network host \
#     --device /dev/fastrpc-cdsp --device /dev/snd -v /usr/lib/dsp:/usr/lib/dsp:ro \
#     -v "$(ls /usr/lib/aarch64-linux-gnu/libcdsprpc.so* | head -1)":/usr/lib/aarch64-linux-gnu/libcdsprpc.so:ro \
#     -v $PWD/models:/app/models:ro -v $PWD/data:/app/data mindbridge:0.3
# libcdsprpc.so (FastRPC client, from the host's Qualcomm packages) is what lets QNN reach the Hexagon DSP;
# without it the container still works, with speech recognition on the CPU.
# then open http://127.0.0.1:8765 on the device's browser.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv libportaudio2 libsndfile1 alsa-utils ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt
ENV PATH=/opt/venv/bin:$PATH

COPY mindbridge ./mindbridge
COPY config ./config
COPY bench ./bench
COPY scripts ./scripts
RUN mkdir -p models data

ENV MINDBRIDGE_STRICT_OFFLINE=true
EXPOSE 8765
HEALTHCHECK CMD curl -sf http://127.0.0.1:8765/api/status || exit 1
CMD ["bash", "scripts/run.sh", "--headless"]
