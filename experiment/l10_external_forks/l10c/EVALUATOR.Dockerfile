FROM rust@sha256:1f0dbad1df66647807e6952d1db85d0b2bda7606cb2139d82517e4f009967376
WORKDIR /seed
COPY Cargo.toml Cargo.lock ./
COPY src/main.rs src/main.rs
RUN cargo fetch --locked
WORKDIR /workspace
