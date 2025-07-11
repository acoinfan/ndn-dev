from mininet.log import setLogLevel, info
from minindn.minindn import Minindn
from minindn.util import MiniNDNCLI
from minindn.apps.app_manager import AppManager
from minindn.apps.nfd import Nfd
from minindn.apps.nlsr import Nlsr
from minindn.apps.application import Application
from time import sleep
import os

def create_custom_nfd_configs(ndn):
    """为每个节点创建自定义的 NFD 配置文件"""
    
    # 读取配置模板
    with open("nfd-template.conf", "r") as f:
        template_config = f.read()
    
    for host in ndn.net.hosts:
        # 替换节点名称占位符
        custom_config = template_config.replace("{{NODE_NAME}}", host.name)
        
        # 确保目录存在
        config_dir = f"/tmp/minindn/{host.name}"
        os.makedirs(config_dir, exist_ok=True)
        
        # 写入节点特定的配置文件
        config_path = f"{config_dir}/nfd.conf"
        with open(config_path, "w") as f:
            f.write(custom_config)
        
        print(f"Created custom NFD config for {host.name}: {config_path}")
        
        # 设置环境变量以便 NFD 使用正确的 socket 路径
        host.cmd(f"export NDN_CLIENT_TRANSPORT=unix:///run/nfd/{host.name}.sock")

def main():
    setLogLevel('debug')
    Minindn.cleanUp()
    Minindn.verifyDependencies()

    print("### starting Minindn ###")
    
    ndn = Minindn(topoFile="web.conf")
    ndn.start()
    sleep(5)

    print("### creating custom NFD configs ###")
    create_custom_nfd_configs(ndn)

    print("### starting NFD ###")
    nfds = AppManager(ndn, ndn.net.hosts, Nfd)
    sleep(10)

    nlsrs = AppManager(ndn, ndn.net.hosts, Nlsr)
    sleep(10)


    consumers = [host for host in ndn.net.hosts if host.name.startswith("con")]
    producers = [host for host in ndn.net.hosts if host.name.startswith("pro")]

    print("### starting Producer ###")
    for producer in producers:
        Application(producer).start("/home/a_coin_fan/code/ndn-dev/producer/bin/ndnput --prefix producer --datasetId 1 --config /home/a_coin_fan/code/ndn-dev/producer/config.ini", "producer.log")
        sleep(10)
    
    print("### starting Consumer ###")
    for consumer in consumers:
        Application(consumer).start("/home/a_coin_fan/code/ndn-dev/consumer/bin/ndnget /producer/1/medium_test.txt -v --no-version-discovery", "consumer.log")
        sleep(5)
        print("### finish sending ##")
    MiniNDNCLI(ndn.net)


main()