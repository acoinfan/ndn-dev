#!/bin/bash

# 修复 NDN 路由问题的脚本

echo "=== 修复 NDN 路由问题 ==="

# 1. 检查 Mini-NDN 是否在运行
echo "1. 检查 Mini-NDN 环境..."
if [ ! -S "/run/nfd/consumer.sock" ] || [ ! -S "/run/nfd/producer.sock" ]; then
    echo "错误：Mini-NDN 环境未运行！"
    echo "请先运行以下命令启动 Mini-NDN："
    echo "  python3 custom_autotest.py"
    echo "或者："
    echo "  python3 autotest.py"
    exit 1
fi

# 2. 清理旧的进程
echo "2. 清理旧的应用进程..."
sudo pkill ndnput
sudo pkill ndnget

# 2. 检查 NFD 状态
echo "2. 检查 NFD 状态..."
export NDN_CLIENT_TRANSPORT=unix:///run/nfd/producer.sock
echo "生产者 NFD 状态:"
nfd-status | grep -E "(version|uptime)" | head -2

export NDN_CLIENT_TRANSPORT=unix:///run/nfd/consumer.sock
echo "消费者 NFD 状态:"
nfd-status | grep -E "(version|uptime)" | head -2

# 3. 确保路由存在
echo "3. 添加路由..."
export NDN_CLIENT_TRANSPORT=unix:///run/nfd/consumer.sock
nfdc route add /producer udp4://10.0.0.2:6363

export NDN_CLIENT_TRANSPORT=unix:///run/nfd/producer.sock
nfdc route add /producer udp4://10.0.0.1:6363

# 4. 检查路由表
echo "4. 检查路由表..."
export NDN_CLIENT_TRANSPORT=unix:///run/nfd/consumer.sock
echo "消费者 FIB:"
nfd-status | grep -A 2 "/producer nexthops"

export NDN_CLIENT_TRANSPORT=unix:///run/nfd/producer.sock
echo "生产者 FIB:"
nfd-status | grep -A 2 "/producer nexthops"

# 5. 启动生产者应用
echo "5. 启动生产者应用..."
export NDN_CLIENT_TRANSPORT=unix:///run/nfd/producer.sock
cd /home/a_coin_fan/code/ndn-dev/producer
./bin/ndnput --prefix producer --datasetId 1 --config config.ini > /tmp/producer-debug.log 2>&1 &
PRODUCER_PID=$!
echo "生产者 PID: $PRODUCER_PID"

# 6. 等待并测试
echo "6. 等待生产者启动..."
sleep 5

# 7. 测试消费者
echo "7. 测试消费者..."
export NDN_CLIENT_TRANSPORT=unix:///run/nfd/consumer.sock
cd /home/a_coin_fan/code/ndn-dev/consumer
timeout 30 ./bin/ndnget /producer/1/medium_test.txt -v --no-version-discovery

echo "=== 完成 ==="
echo "生产者日志: /tmp/producer-debug.log"
echo "如果还有问题，请检查日志文件"
