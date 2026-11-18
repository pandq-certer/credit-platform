FROM debian:bookworm-slim AS ffmpeg

ARG FFMPEG_VERSION=7.1.5
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
      build-essential nasm yasm pkg-config xz-utils ca-certificates \
      libmp3lame-dev libvorbis-dev libopus-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY vendor/FFmpeg-n${FFMPEG_VERSION}.tar.gz /src/
RUN tar xzf FFmpeg-n${FFMPEG_VERSION}.tar.gz
WORKDIR /src/FFmpeg-n${FFMPEG_VERSION}
# 修正稿原命令含 --enable-lgpl，但 FFmpeg 7.1.5 无此选项（仅支持 --enable-gpl）；
# 使用等价的 LGPL 构建参数：禁 GPL、禁 nonfree。
RUN ./configure --disable-gpl --disable-nonfree \
      --enable-shared --disable-static \
      --enable-libmp3lame --enable-libvorbis --enable-libopus \
      --prefix=/opt/credit/sys-01/ffmpeg \
    && make -j"$(nproc)" \
    && make install


FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/credit/sys-01/ffmpeg/bin:$PATH \
    LD_LIBRARY_PATH=/opt/credit/sys-01/ffmpeg/lib

RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 libgomp1 curl libmp3lame0 libvorbis0a libvorbisenc2 \
      libvorbisfile3 libopus0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ffmpeg /opt/credit/sys-01/ffmpeg /opt/credit/sys-01/ffmpeg

WORKDIR /app
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
COPY requirements.txt .
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -e . \
    && useradd -m -u 10002 app \
    && mkdir -p /data/tmp && chown -R app /data/tmp /app

USER app
EXPOSE 8102
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8102", "--workers", "1"]
