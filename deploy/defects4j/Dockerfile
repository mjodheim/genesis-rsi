# Defects4J validator image for Genesis.
#
# Network is needed ONCE, here, to fetch the benchmark. Containers started from this image are
# always run with `--network none` by genesis/defects4j_sandbox.py: a candidate patch is compiled
# and executed against the project test suite, so it is untrusted code and must not reach the
# host, the network or anything but its own checkout.
#
# Build:  docker build -t genesis-defects4j:8c16da8 deploy/defects4j
FROM ubuntu:22.04

ARG DEFECTS4J_REVISION=8c16da8230843cdc918eaf4ddb449637f02b83c6

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64 \
    TZ=America/Los_Angeles \
    LC_ALL=C.UTF-8

RUN apt-get update -y \
 && apt-get install -y --no-install-recommends \
        openjdk-11-jdk-headless git subversion perl cpanminus make gcc libc6-dev \
        libdbi-perl curl unzip ca-certificates tzdata patch \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
 && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/rjust/defects4j.git /defects4j \
 && git -C /defects4j checkout --detach "$DEFECTS4J_REVISION" \
 && test "$(git -C /defects4j rev-parse HEAD)" = "$DEFECTS4J_REVISION"

WORKDIR /defects4j
RUN cpanm --notest --installdeps . && rm -rf /root/.cpanm
RUN ./init.sh

# The sandbox runs as an arbitrary unprivileged uid with a read-only root filesystem: the
# benchmark must be readable by anyone, and git must accept repositories it does not own.
RUN git config --system --add safe.directory '*' \
 && git config --system user.name "defects4j" \
 && git config --system user.email "defects4j@localhost" \
 && chmod -R a+rX /defects4j \
 && echo "$DEFECTS4J_REVISION" > /defects4j/REVISION

ENV PATH="/defects4j/framework/bin:${PATH}"
WORKDIR /work
