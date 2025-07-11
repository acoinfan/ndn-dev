#!/usr/bin/env python3

from mininet.log import setLogLevel, info
from minindn.minindn import Minindn
from minindn.util import MiniNDNCLI
from minindn.apps.app_manager import AppManager
from minindn.apps.nfd import Nfd
from minindn.apps.nlsr import Nlsr
from minindn.apps.application import Application
from time import sleep
import os
import shutil

def setup_custom_nfd_configs(ndn):
    """为每个节点设置自定义的 NFD 配置"""
    
    # 读取我们的自定义配置模板
    template_path = "custom-nfd.conf"
    
    for host in ndn.net.hosts:
        # Mini-NDN 为每个节点创建的工作目录
        node_dir = f"/tmp/minindn/{host.name}"
        nfd_conf_path = f"{node_dir}/nfd.conf"
        
        # 确保目录存在
        os.makedirs(node_dir, exist_ok=True)
        
        # 读取并修改配置
        with open(template_path, "r") as f:
            config_content = f.read()
        
        # 修改 socket 路径以匹配 Mini-NDN 的约定
        config_content = config_content.replace(
            "path /run/nfd/nfd.sock",
            f"path /run/nfd/{host.name}.sock"
        )
        
        # 写入节点特定的配置
        with open(nfd_conf_path, "w") as f:
            f.write(config_content)
        
        print(f"✓ 创建自定义 NFD 配置: {host.name} -> {nfd_conf_path}")

def configure_environment(ndn):
    """配置每个节点的环境变量和路由"""
    for host in ndn.net.hosts:
        # 设置 NDN 客户端使用正确的 socket
        host.cmd(f"export NDN_CLIENT_TRANSPORT=unix:///run/nfd/{host.name}.sock")
        print(f"✓ 配置环境变量: {host.name}")
    
    # 添加路由配置
    print("### 添加路由配置 ###")
    consumer = ndn.net.get('consumer')
    producer = ndn.net.get('producer')
    
    # 消费者到生产者的路由
    consumer.cmd("NDN_CLIENT_TRANSPORT=unix:///run/nfd/consumer.sock nfdc route add /producer udp4://10.0.0.2:6363")
    print("✓ 添加路由: consumer -> producer")
    
    # 生产者到消费者的路由（可选）
    producer.cmd("NDN_CLIENT_TRANSPORT=unix:///run/nfd/producer.sock nfdc route add /producer udp4://10.0.0.1:6363")
    print("✓ 添加路由: producer -> consumer")

def main():
    setLogLevel('info')
    Minindn.cleanUp()
    Minindn.verifyDependencies()

    print("### 启动 Mini-NDN 拓扑 ###")
    
    # 使用 web.conf 拓扑
    ndn = Minindn(topoFile="web.conf")
    ndn.start()
    sleep(3)

    print("### 设置自定义 NFD 配置 ###")
    setup_custom_nfd_configs(ndn)

    print("### 启动 NFD ###")
    # 启动 NFD（会使用我们刚才创建的配置文件）
    nfds = AppManager(ndn, ndn.net.hosts, Nfd)
    sleep(8)

    print("### 配置环境 ###")
    configure_environment(ndn)

    print("### 启动 NLSR ###")
    nlsrs = AppManager(ndn, ndn.net.hosts, Nlsr)
    sleep(8)

    # 获取节点
    consumers = [host for host in ndn.net.hosts if host.name.startswith("con")]
    producers = [host for host in ndn.net.hosts if host.name.startswith("pro")]

    print("### 启动生产者应用 ###")
    for producer in producers:
        # 设置环境变量并启动应用
        cmd = f"/home/a_coin_fan/code/ndn-dev/producer/bin/ndnput --prefix producer --datasetId 1 --config /home/a_coin_fan/code/ndn-dev/producer/config.ini"
        Application(producer).start(cmd, "producer.log")
        print(f"✓ 启动生产者: {producer.name}")
        sleep(5)
    
    print("### 启动消费者应用 ###")
    for consumer in consumers:
        # 设置环境变量并启动应用
        cmd = f"/home/a_coin_fan/code/ndn-dev/consumer/bin/ndnget /producer/1/medium_test.txt -v --no-version-discovery"
        Application(consumer).start(cmd, "consumer.log")
        print(f"✓ 启动消费者: {consumer.name}")
        sleep(3)

    print("### 检查状态 ###")
    for host in ndn.net.hosts:
        print(f"\n--- {host.name} NFD 状态 ---")
        result = host.cmd(f"NDN_CLIENT_TRANSPORT=unix:///run/nfd/{host.name}.sock nfd-status | head -20")
        print(result)
        
        print(f"\n--- {host.name} 路由表 ---")
        result = host.cmd(f"NDN_CLIENT_TRANSPORT=unix:///run/nfd/{host.name}.sock nfd-status | grep -A 10 'FIB:'")
        print(result)


if __name__ == '__main__':
    main()
