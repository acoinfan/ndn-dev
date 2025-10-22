#!/bin/bash
echo "=== Minindn-Simulator ==="

echo "CleanUp Environment"

sudo pkill -f nfd
sudo pkill -f ndnclient

sudo rm -rf /tmp/ndn/*

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
CLIENT_BIN="${PROJECT_ROOT}/client/bin/ndnclient"/


if ! command -v $CLIENT_BIN &> /dev/null; then
    echo "Automatically Building" 
    make &> /dev/null
fi

echo "=== Running Test ==="
cd "$PROJECT_ROOT"

sudo python3 minindn-simulator.py topologies/web.conf

echo "=== End Of Test ==="


