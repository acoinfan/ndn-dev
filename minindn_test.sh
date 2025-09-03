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
echo "2. 清理之前的进程及文件..."
sudo pkill -f nfd
sudo pkill -f ndnclient

sudo rm -rf /tmp/ndn/*
sudo rm -rf /tmp/*-nfd.conf

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
CLIENT_BIN="${PROJECT_ROOT}/client/bin/ndnclient"/


# 重新编译应用（如果需要）
echo "3. 检查应用程序..."
if [ ! -f "$CLIENT_BIN" ]; then
    echo "编译客户端应用..."
    cd "${PROJECT_ROOT}/client" && make -j$(nproc)
fi


# 运行测试
echo "4. 运行网络模拟..."
cd "$PROJECT_ROOT"

sudo python3 minindn-simulator.py web.conf

echo "=== 测试完成 ==="


