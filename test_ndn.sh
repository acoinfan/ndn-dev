#!/bin/bash

# 快速测试脚本

echo "=== NDN 网络模拟器测试 ==="

echo "0, cleaning old logs..."
sudo rm /tmp/consumer-app.log
sudo rm /tmp/producer-app.log
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

echo "选择运行模式:"
echo "  1. 简单模式 (pure_manual.py)"
echo "  2. 高级模式 (advanced_ndn_simulator.py)"
echo "  3. 自定义配置模式"

read -p "请选择 [1-3]: " choice

case $choice in
    1)
        echo "运行简单模式..."
        sudo python3 pure_manual.py
        ;;
    2)
        echo "运行高级模式..."
        sudo python3 advanced_ndn_simulator.py
        ;;
    3)
        echo "运行自定义配置模式..."
        echo "可用配置文件:"
        ls -la *.py | grep config
        read -p "请输入配置文件名: " config_file
        sudo python3 advanced_ndn_simulator.py $config_file
        ;;
    *)
        echo "默认运行简单模式..."
        sudo python3 pure_manual.py
        ;;
esac

echo "=== 测试完成 ==="
echo "using cat /tmp/consumer-app.log to view consumer logs"
echo "using cat /tmp/producer-app.log to view producer logs"

