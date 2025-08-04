#!/bin/bash

# 快速测试脚本

echo "=== NDN 网络模拟器测试 ==="

# 检查依赖
echo "1. 检查依赖..."
if ! command -v nfd &> /dev/null; then
    echo "错误: nfd 未安装"
    exit 1
fi

if ! command -v nfdc &> /dev/null; then
    echo "错误: nfdc 未安装"
    exit 1
fi

# 清理之前的进程
echo "2. 清理之前的进程..."
sudo pkill -f nfd
sudo pkill -f ndnput
sudo pkill -f ndnget

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PRODUCER_BIN="${PROJECT_ROOT}/producer/bin/ndnput"
CONSUMER_BIN="${PROJECT_ROOT}/consumer/bin/ndnget"

# 重新编译应用（如果需要）
echo "3. 检查应用程序..."
if [ ! -f "$PRODUCER_BIN" ]; then
    echo "编译生产者应用..."
    cd "${PROJECT_ROOT}/producer" && make
fi

if [ ! -f "$CONSUMER_BIN" ]; then
    echo "编译消费者应用..."
    cd "${PROJECT_ROOT}/consumer" && make
fi

# 运行测试
echo "4. 运行网络模拟..."
cd "$PROJECT_ROOT"

sudo python3 old_simulator.py

echo "=== 测试完成 ==="


