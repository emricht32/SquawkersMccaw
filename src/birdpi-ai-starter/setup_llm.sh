#!/usr/bin/env bash
set -euo pipefail
# Build llama.cpp for Raspberry Pi 5 and fetch the GGUF once.
sudo apt-get update
sudo apt-get install -y git cmake build-essential libcurl4-openssl-dev ca-certificates
if [ ! -d llama.cpp/.git ]; then
  git clone --depth 1 https://github.com/ggml-org/llama.cpp.git llama.cpp
fi
cmake -S llama.cpp -B llama.cpp/build -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=ON
cmake --build llama.cpp/build -j 4 --target llama-server
cat <<'NOTE'
Done. Start llama.cpp in another terminal:
  ./llama.cpp/build/bin/llama-server -hf Qwen/Qwen3-0.6B-GGUF:Q4_K_M --host 127.0.0.1 --port 8082 -c 2048 -t 4
The first launch downloads the model (~500 MB) and requires internet.
If your llama.cpp version cannot resolve :Q4_K_M, inspect the Qwen GGUF model repository and specify a local .gguf file with -m instead.
NOTE
