# Measurement image for program-improvement chains.
#
# Network is needed ONCE, here. Containers started from this image are always run with
# `--network none` by genesis/program_improvement.py: they execute third-party library code and
# model-written replacements of single functions, which are untrusted.
#
# Valgrind's Callgrind counts the instructions executed between the two calls of marker.c, so the
# cost of a function is a count, not a duration: it does not depend on what else the host is doing.
#
# Build:  docker build -t genesis-improve:v1 deploy/program-improvement
FROM python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS build
RUN apt-get update && apt-get install -y --no-install-recommends valgrind gcc libc6-dev
COPY marker.c /marker.c
RUN gcc -O1 -shared -fPIC -o /libgenesis_marker.so /marker.c

FROM python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
RUN apt-get update && apt-get install -y --no-install-recommends valgrind && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir pytest==8.3.3
COPY --from=build /libgenesis_marker.so /usr/local/lib/libgenesis_marker.so
