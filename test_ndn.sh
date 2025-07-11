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

# 重新编译应用（如果需要）
echo "3. 检查应用程序..."
if [ ! -f "/home/a_coin_fan/code/ndn-dev/producer/bin/ndnput" ]; then
    echo "编译生产者应用..."
    cd /home/a_coin_fan/code/ndn-dev/producer && make
fi

if [ ! -f "/home/a_coin_fan/code/ndn-dev/consumer/bin/ndnget" ]; then
    echo "编译消费者应用..."
    cd /home/a_coin_fan/code/ndn-dev/consumer && make
fi

# 运行测试
echo "4. 运行网络模拟..."
cd /home/a_coin_fan/code/ndn-dev

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
