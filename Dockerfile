FROM ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac

# Host build tools are recorded in each build report. Runtime ABI inputs and
# LLVM-MinGW are independently pinned in sources.json.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential bison flex pkg-config cmake ninja-build python3 ca-certificates \
    git patch file binutils rpm2cpio cpio xz-utils

WORKDIR /src
