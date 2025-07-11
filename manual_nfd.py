#!/usr/bin/env python3
"""
手动启动 NFD 并创建基于 web.conf 的拓扑
"""

from mininet.log import setLogLevel, info
from minindn.minindn import Minindn
from minindn.util import MiniNDNCLI
from minindn.apps.app_manager import AppManager
from minindn.apps.nfd import Nfd
from minindn.apps.nlsr import Nlsr
from minindn.apps.application import Application
from time import sleep
import os

def main():
    setLogLevel('info')
    
    # 清理之前的实例
    Minindn.cleanUp()
    Minindn.verifyDependencies()

    print("### 手动启动 NFD 和拓扑 ###")
    
    # 创建 Mini-NDN 实例，指定拓扑文件和 NFD 配置
    ndn = Minindn(
        topoFile="web.conf",  # 使用你的拓扑文件
        nfdConfigFile="custom-nfd.conf"  # 使用你的 NFD 配置
    )

    print("### 启动拓扑 ###")
    ndn.start()
    sleep(5)

    print("### 启动 NFD ###")
    # 为每个主机启动 NFD
    for host in ndn.net.hosts:
        print(f"启动 NFD 在 {host.name}")
        # 使用自定义配置启动 NFD
        nfd_cmd = f"nfd --config {os.path.abspath('custom-nfd.conf')}"
        host.cmd(f"{nfd_cmd} > /tmp/{host.name}-nfd.log 2>&1 &")
    
    sleep(10)

    print("### 手动配置路由 ###")
    # 手动添加路由（基于 web.conf 的拓扑）
    consumer = ndn.net.get('consumer')
    producer = ndn.net.get('producer')
    
    # 在消费者上添加到生产者的路由
    consumer.cmd("nfdc route add /producer udp4://10.0.0.2:6363")
    
    # 在生产者上添加到消费者的路由（如果需要）
    # producer.cmd("nfdc route add /consumer udp4://10.0.0.1:6363")

    print("### 启动应用程序 ###")
    
    # 启动生产者应用
    print("启动生产者...")
    producer_cmd = "/home/a_coin_fan/code/ndn-dev/producer/bin/ndnput --prefix producer --datasetId 1 --config /home/a_coin_fan/code/ndn-dev/producer/config.ini"
    producer.cmd(f"{producer_cmd} > /tmp/producer-app.log 2>&1 &")
    sleep(5)

    # 启动消费者应用
    print("启动消费者...")
    consumer_cmd = "/home/a_coin_fan/code/ndn-dev/consumer/bin/ndnget /producer/1/medium_test.txt -v --no-version-discovery"
    consumer.cmd(f"{consumer_cmd} > /tmp/consumer-app.log 2>&1")
    
    print("### 检查状态 ###")
    print("生产者 NFD 状态:")
    producer.cmd("nfd-status")
    
    print("消费者 NFD 状态:")
    consumer.cmd("nfd-status")

    print("### 进入 CLI ###")
    MiniNDNCLI(ndn.net)

if __name__ == '__main__':
    main()
