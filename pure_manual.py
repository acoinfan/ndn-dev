#!/usr/bin/env python3
"""
纯 Mininet 实现的 NDN 网络，完全控制链路属性
"""

from mininet.net import Mininet
from mininet.node import Host
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from time import sleep
import os
import subprocess
import signal

class NDNHost(Host):
    """扩展的 Host 类，支持 NDN 功能"""
    
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.nfd_process = None
        self.nlsr_process = None
    
    def start_nfd(self, config_file=None):
        """启动 NFD"""
        if config_file is None:
            config_file = f"/tmp/{self.name}-nfd.conf"
            self.create_nfd_config(config_file)
        
        # 启动 NFD
        nfd_cmd = f"nfd --config {config_file}"
        self.nfd_process = self.popen(nfd_cmd, shell=True)
        sleep(2)  # 等待 NFD 启动
        
        print(f"✓ NFD 启动在 {self.name}")
        return self.nfd_process
    
    def create_nfd_config(self, config_file):
        """为节点创建 NFD 配置文件"""
        config_content = f"""
general {{
}}

log {{
    default_level INFO
}}

tables {{
    cs_max_packets 65536
    cs_policy lru
    cs_unsolicited_policy drop-all
    
    strategy_choice {{
        / /localhost/nfd/strategy/best-route
        /localhost /localhost/nfd/strategy/multicast
        /localhost/nfd /localhost/nfd/strategy/best-route
        /ndn/broadcast /localhost/nfd/strategy/multicast
    }}
    
    network_region {{
    }}
}}

face_system {{
    general {{
        enable_congestion_marking yes
    }}
    
    unix {{
        path /run/nfd/{self.name}.sock
    }}
    
    tcp {{
        listen yes
        port 6363
        enable_v4 yes
        enable_v6 yes
    }}
    
    udp {{
        listen yes
        port 6363
        enable_v4 yes
        enable_v6 yes
        idle_timeout 600
        keep_alive_interval 25
        mcast yes
        mcast_group 224.0.23.170
        mcast_port 56363
        mcast_group_v6 ff02::1234
        mcast_port_v6 56363
    }}
    
    ether {{
        listen yes
        idle_timeout 600
        mcast yes
        mcast_group 01:00:5E:00:17:AA
        whitelist {{
            *
        }}
    }}
}}

authorizations {{
    authorize {{
        certfile any
        privileges {{
            faces
            fib
            cs
            strategy-choice
        }}
    }}
}}

rib {{
    localhost_security {{
        trust-anchor {{
            type any
        }}
    }}
    
    prefix_announcement_validation {{
        trust-anchor {{
            type any
        }}
    }}
    
    auto_prefix_propagate {{
        cost 15
        timeout 10000
        refresh_interval 300
        base_advertise_interval 15000
        max_advertise_interval 600000
    }}
    
    readvertise_nlsr {{
        cost 15
        timeout 10000
        refresh_interval 300
    }}
}}
"""
        
        with open(config_file, 'w') as f:
            f.write(config_content)
    
    def add_route(self, prefix, nexthop):
        """添加路由"""
        env = f"NDN_CLIENT_TRANSPORT=unix:///run/nfd/{self.name}.sock"
        cmd = f"{env} nfdc route add {prefix} {nexthop}"
        result = self.cmd(cmd)
        print(f"✓ {self.name}: 添加路由 {prefix} -> {nexthop}")
        return result
    
    def get_nfd_status(self):
        """获取 NFD 状态"""
        env = f"NDN_CLIENT_TRANSPORT=unix:///run/nfd/{self.name}.sock"
        cmd = f"{env} nfd-status"
        return self.cmd(cmd)
    
    def start_producer(self, prefix, dataset_id, config_file):
        """启动生产者应用"""
        env = f"NDN_CLIENT_TRANSPORT=unix:///run/nfd/{self.name}.sock"
        cmd = f"{env} /home/a_coin_fan/code/ndn-dev/producer/bin/ndnput --prefix {prefix} --datasetId {dataset_id} --config {config_file}"
        return self.popen(cmd, shell=True)
    
    def start_consumer(self, interest_name):
        """启动消费者应用"""
        env = f"NDN_CLIENT_TRANSPORT=unix:///run/nfd/{self.name}.sock"
        cmd = f"{env} /home/a_coin_fan/code/ndn-dev/consumer/bin/ndnget {interest_name} -v --no-version-discovery"
        return self.cmd(cmd)
    
    def cleanup(self):
        """清理进程"""
        if self.nfd_process:
            self.nfd_process.terminate()

def create_custom_topology():
    """创建自定义拓扑"""
    
    # 创建网络
    net = Mininet(host=NDNHost, link=TCLink)
    
    # 添加节点
    consumer = net.addHost('consumer', ip='10.0.0.1/24')
    producer = net.addHost('producer', ip='10.0.0.2/24')
    
    # 添加链路 - 你可以在这里完全控制链路属性
    links = {
        # 链路配置：(node1, node2, 属性)
        'consumer-producer': {
            'nodes': (consumer, producer),
            'bw': 30,        # 带宽 30 Mbps
            'delay': '10ms', # 延迟 10ms
            'loss': 1,       # 丢包率 1%
            'max_queue_size': 1000,
            'use_htb': True  # 使用 HTB 队列
        }
    }
    
    # 创建链路
    for link_name, config in links.items():
        node1, node2 = config['nodes']
        link = net.addLink(
            node1, node2,
            cls=TCLink,
            bw=config['bw'],
            delay=config['delay'],
            loss=config['loss'],
            max_queue_size=config['max_queue_size'],
            use_htb=config.get('use_htb', True)
        )
        print(f"✓ 创建链路: {link_name} (bw={config['bw']}Mbps, delay={config['delay']}, loss={config['loss']}%)")
    
    return net, consumer, producer

def setup_ndn_environment(net, consumer, producer):
    """设置 NDN 环境"""
    
    print("### 启动网络 ###")
    net.start()
    
    print("### 启动 NFD ###")
    consumer.start_nfd()
    producer.start_nfd()
    
    print("### 配置路由 ###")
    # 消费者到生产者的路由
    consumer.add_route('/producer', f'udp4://{producer.IP()}:6363')
    
    # 生产者到消费者的路由（可选）
    producer.add_route('/consumer', f'udp4://{consumer.IP()}:6363')
    
    return net

def test_applications(consumer, producer):
    """测试应用程序"""
    
    print("### 启动生产者应用 ###")
    producer_proc = producer.start_producer(
        prefix='producer',
        dataset_id=1,
        config_file='/home/a_coin_fan/code/ndn-dev/producer/config.ini'
    )
    
    sleep(3)  # 等待生产者启动
    
    print("### 测试消费者应用 ###")
    result = consumer.start_consumer('/producer/1/medium_test.txt')
    print(f"消费者结果:\n{result}")
    
    return producer_proc

def show_network_status(consumer, producer):
    """显示网络状态"""
    
    print("\n### 网络状态 ###")
    
    for host in [consumer, producer]:
        print(f"\n--- {host.name} NFD 状态 ---")
        status = host.get_nfd_status()
        # 只显示关键信息
        for line in status.split('\n'):
            if any(keyword in line for keyword in ['version', 'uptime', 'nInInterests', 'nInData', 'nOutInterests', 'nOutData']):
                print(line)
        
        print(f"\n--- {host.name} 路由表 ---")
        fib_lines = status.split('\n')
        in_fib = False
        for line in fib_lines:
            if 'FIB:' in line:
                in_fib = True
                print(line)
            elif in_fib and line.startswith('  /'):
                print(line)
            elif in_fib and not line.startswith('  '):
                break

def main():
    setLogLevel('info')
    
    print("### 创建自定义 NDN 拓扑 ###")
    net, consumer, producer = create_custom_topology()
    
    try:
        # 设置 NDN 环境
        net = setup_ndn_environment(net, consumer, producer)
        
        # 测试应用
        producer_proc = test_applications(consumer, producer)
        
        # 显示状态
        show_network_status(consumer, producer)
        
        print("\n### 进入 CLI（输入 'exit' 退出）###")
        print("可用命令：")
        print("  consumer <command>  - 在消费者节点执行命令")
        print("  producer <command>  - 在生产者节点执行命令")
        print("  status              - 显示网络状态")
        print("  test                - 重新测试应用")
        
        # 进入 CLI
        CLI(net)
        
    except KeyboardInterrupt:
        print("\n### 用户中断 ###")
    finally:
        print("### 清理资源 ###")
        consumer.cleanup()
        producer.cleanup()
        net.stop()

if __name__ == '__main__':
    main()
