#!/bin/bash
echo "=== Minindn-Simulator ==="

echo "CleanUp Environment"
sudo pkill -f nfd 2>/dev/null
sudo pkill -f ndnclient 2>/dev/null
sudo rm -rf /tmp/ndn/*

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
CLIENT_BIN="${PROJECT_ROOT}/client/bin/ndnclient"
NFDC_FILE="${PROJECT_ROOT}/nfd.ini"
CLIENT_FILE="${PROJECT_ROOT}/exp-clientconfig.ini"

# 检查可执行文件是否存在
if [[ ! -x "$CLIENT_BIN" ]]; then
    echo "Automatically Building..."
    make -C "$PROJECT_ROOT" &> /dev/null || {
        echo "Build failed."
        exit 1
    }
fi

echo
echo "=== Select Topology File ==="
TOPO_DIR="$PROJECT_ROOT/topologies"
TOPO_FILES=("$TOPO_DIR"/*.conf)

declare -A topo_map
for f in "${TOPO_FILES[@]}"; do
    topo_map["$(basename "$f")"]="$f"
done

echo "Select a topology:"
select name in "${!topo_map[@]}"; do
    if [[ -n $name ]]; then
        echo "You selected full path: ${topo_map[$name]}"
        break
    else
        echo "Invalid selection"
    fi
done
SELECTED_TOPO="${topo_map[$name]}"

echo
echo "=== Select File Size ==="
sizes=(50MB 1MB 10MB 100MB 500MB 1GB "Custom")

select size in "${sizes[@]}"; do
    if [[ "$size" == "Custom" ]]; then
        read -p "Enter custom size: " custom_size
        size=$custom_size
        break
    elif [[ -n "$size" ]]; then
        echo "You selected: ${size}"
        break
    else
        echo "Invalid selection."
    fi
done


TEST_FILE="$PROJECT_ROOT/experiments/${size}.txt"
"$PROJECT_ROOT/file_generator.sh" "${size}"

if [[ $? -ne 0 || ! -f "$TEST_FILE" ]]; then
    echo "Error: File generation failed. Cleaning up..."
    rm -f "$TEST_FILE"
    exit 1
fi

echo
read -p "Enter log directory (leave empty to skip): " LOG_DIR

CMD="sudo python3 minindn-simulator.py --topo-file \"$SELECTED_TOPO\" --test-file \"$TEST_FILE\" --nfdc-file \"$NFDC_FILE\" --client-file \"$CLIENT_FILE\""

# 只有用户输入了 log-dir 才添加参数
if [[ -n "$LOG_DIR" ]]; then
    CMD="$CMD --log-dir \"$LOG_DIR\""
fi

echo

echo "=== Running Test ==="
cd "$PROJECT_ROOT" || exit
echo "Running command: $CMD"
eval $CMD
echo
echo "=== End Of Test ==="
