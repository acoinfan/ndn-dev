#!/usr/bin/env python3
"""
高级 NDN 网络模拟器 - 使用配置文件定义网络
"""

from mininet.net import Mininet
from mininet.node import Host
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from time import sleep
import os
import importlib.util
import sys

class NDNHost(Host):
    """扩展的 Host 类，支持 NDN 功能"""
    
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.nfd_process = None
        self.app_processes = []
    
    def start_nfd(self):
        """启动 NFD"""
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
    
    auto_prefix_propagate {{
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
        proc = self.popen(cmd, shell=True)
        self.app_processes.append(proc)
        print(f"✓ 生产者应用启动在 {self.name}: {prefix}")
        return proc
    
    def start_consumer(self, interest_name):
        """启动消费者应用"""
        env = f"NDN_CLIENT_TRANSPORT=unix:///run/nfd/{self.name}.sock"
        cmd = f"{env} /home/a_coin_fan/code/ndn-dev/consumer/bin/ndnget {interest_name} -v --no-version-discovery"
        return self.cmd(cmd)
    
    def cleanup(self):
        """清理进程"""
        if self.nfd_process:
            self.nfd_process.terminate()
        for proc in self.app_processes:
            proc.terminate()

def load_config(config_file='network_config.py'):
    """加载网络配置"""
    spec = importlib.util.spec_from_file_location("network_config", config_file)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config

def create_topology_from_config(config):
    """根据配置创建拓扑"""
    
    # 创建网络
    net = Mininet(host=NDNHost, link=TCLink)
    hosts = {}
    
    # 添加节点
    for name, node_config in config.nodes.items():
        host = net.addHost(name, ip=node_config['ip'])
        hosts[name] = host
        print(f"✓ 创建节点: {name} ({node_config['ip']})")
    
    # 创建链路
    for link_name, link_config in config.links.items():
        node1_name, node2_name = link_config['nodes']
        node1 = hosts[node1_name]
        node2 = hosts[node2_name]
        
        # 创建链路参数
        link_params = {
            'cls': TCLink,
            'bw': link_config['bw'],
            'delay': link_config['delay'],
            'loss': link_config['loss'],
            'max_queue_size': link_config['max_queue_size'],
            'use_htb': link_config.get('use_htb', True)
        }
        
        # 添加可选参数
        if 'jitter' in link_config and link_config['jitter']:
            link_params['jitter'] = link_config['jitter']
        
        link = net.addLink(node1, node2, **link_params)
        
        print(f"✓ 创建链路: {link_name}")
        print(f"  - 带宽: {link_config['bw']} Mbps")
        print(f"  - 延迟: {link_config['delay']}")
        print(f"  - 丢包率: {link_config['loss']}%")
        print(f"  - 队列大小: {link_config['max_queue_size']}")
    
    return net, hosts

def setup_ndn_environment(net, hosts, config):
    """设置 NDN 环境"""
    
    print("### 启动网络 ###")
    net.start()
    
    print("### 启动 NFD ###")
    for host in hosts.values():
        host.start_nfd()
    
    print("### 配置路由 ###")
    for node_name, routes in config.routes.items():
        node = hosts[node_name]
        for prefix, nexthop in routes:
            node.add_route(prefix, nexthop)
    
    print("### 启动应用程序 ###")
    for node_name, app_config in config.applications.items():
        if node_name in hosts:
            node = hosts[node_name]
            node.start_producer(
                prefix=app_config['prefix'],
                dataset_id=app_config['dataset_id'],
                config_file=app_config['config_file']
            )
    
    return net

def run_tests(hosts, config):
    """运行测试"""
    
    print("### 运行测试 ###")
    
    for test in config.tests:
        print(f"\n--- 测试: {test['name']} ---")
        print(f"描述: {test['description']}")
        
        consumer = hosts[test['consumer']]
        
        print(f"消费者 {test['consumer']} 请求: {test['interest']}")
        result = consumer.start_consumer(test['interest'])
        
        # 分析结果
        if "ERROR" in result:
            print(f"❌ 测试失败:")
            print(result)
        else:
            print(f"✓ 测试成功")
            # 只显示关键信息
            for line in result.split('\n'):
                if any(keyword in line for keyword in ['Published', 'Received', 'segments', 'bytes']):
                    print(f"  {line}")
        
        sleep(2)  # 测试间隔

def show_network_status(hosts):
    """显示网络状态"""
    
    print("\n### 网络状态 ###")
    
    for name, host in hosts.items():
        print(f"\n--- {name} ---")
        status = host.get_nfd_status()
        
        # 显示关键统计信息
        print("统计信息:")
        for line in status.split('\n'):
            if any(keyword in line.lower() for keyword in ['interests', 'data', 'nacks', 'uptime']):
                print(f"  {line.strip()}")
        
        # 显示路由表
        print("路由表:")
        fib_lines = status.split('\n')
        in_fib = False
        for line in fib_lines:
            if 'FIB:' in line:
                in_fib = True
            elif in_fib and line.startswith('  /'):
                print(f"  {line.strip()}")
            elif in_fib and not line.startswith('  '):
                break

def main():
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    else:
        config_file = 'network_config.py'
    
    setLogLevel('info')
    
    try:
        # 加载配置
        print(f"### 加载配置文件: {config_file} ###")
        config = load_config(config_file)
        
        # 创建拓扑
        print("### 创建网络拓扑 ###")
        net, hosts = create_topology_from_config(config)
        
        # 设置 NDN 环境
        net = setup_ndn_environment(net, hosts, config)
        
        # 等待系统稳定
        sleep(5)
        
        # 运行测试
        run_tests(hosts, config)
        
        # 显示状态
        show_network_status(hosts)
        
        print("\n### 进入 CLI ###")
        print("可用命令:")
        print("  <node> <command>    - 在指定节点执行命令")
        print("  pingall             - 测试所有节点连通性")
        print("  exit                - 退出")
        
        # 进入 CLI
        CLI(net)
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("### 清理资源 ###")
        try:
            for host in hosts.values():
                host.cleanup()
            net.stop()
        except:
            pass

if __name__ == '__main__':
    main()
