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
import datetime
import shutil
import threading

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CLIENT_BIN = os.path.join(PROJECT_ROOT, "client/bin/ndnclient")

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
        # sleep(2)  # 等待 NFD 启动
        
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
        print(f"  命令: {cmd}")
        print(f"  结果: {result}")
        return result
    
    def get_nfd_status(self):
        """获取 NFD 状态"""
        env = f"NDN_CLIENT_TRANSPORT=unix:///run/nfd/{self.name}.sock"
        cmd = f"{env} nfd-status"
        return self.cmd(cmd)

    def start_producer(self, config_file, transfer_file, id, nodes_count, directory):
        """启动生产者应用"""
        cmd = f"{CLIENT_BIN} -c {config_file} -f {transfer_file} -i {id} -n {nodes_count} -d {directory}"
        proc = self.popen(cmd, shell=True)
        self.app_processes.append(proc)
        print(f"✓ 生产者应用启动在 {self.name}: {id}")
        print(f"  命令: {cmd}")
        return proc
    
    def cleanup(self):
        """清理进程"""
        if self.nfd_process:
            self.nfd_process.terminate()
        for proc in self.app_processes:
            proc.terminate()

def create_network_config(nodes = 10, bw = 100, delay = '0ms', loss = 0, max_queue_size = 10000000, file_name = "testfile_6442450.txt"):
    """创建网络配置"""
    config = {
        'nodes': {},
        'links': {},
        'applications': {},
        'routes': {},
    }

    # 自动生成 nodes 部分
    for i in range(nodes):
        # 生成 producer
        config['nodes'][f'pro{i}'] = {'ip': f'10.{i}.{i}.0', 'type': 'producer'}
        # 生成 consumer（每个 client 对其他 client 的请求）
        for j in range(nodes):
            if i != j:
                config['nodes'][f'con{i}to{j}'] = {'ip': f'10.{i}.{j}.0', 'type': 'consumer'}

    # 自动生成 links 部分
    for i in range(nodes):
        for j in range(nodes):
            if i != j:
                consumer_name = f'con{i}to{j}'
                producer_name = f'pro{j}'
                link_name = f'{consumer_name}-{producer_name}'
                config['links'][link_name] = {
                    'nodes': (consumer_name, producer_name),
                    'bw': bw,
                    'delay': delay,
                    'loss': loss,
                    'max_queue_size': max_queue_size,
                    'use_htb': True,
                    'jitter': None
                }

    # 自动生成 applications 部分
    for i in range(nodes):
        config['applications'][f'pro{i}'] = {
            'config_file': os.path.join(PROJECT_ROOT, 'exp-clientconfig.ini'),
            'transfer_file': file_name,
            'id': i,
            'nodes_count': nodes,
            'directory': os.path.join(PROJECT_ROOT, 'experiments')
        }

    # 自动生成 routes 部分
    for i in range(nodes):
        for j in range(nodes):
            if i != j:
                consumer_name = f'con{i}to{j}'
                producer_name = f'pro{j}'
                config['routes'][consumer_name] = [
                    (f'/pro{j}', f'udp4://10.{j}.{j}.0:6363')
                ]

    return config

def create_topology_from_config(config):
    """根据配置创建拓扑"""
    
    # 创建网络
    net = Mininet(host=NDNHost, link=TCLink)
    hosts = {}
    
    # 添加节点
    for name, node_config in config['nodes'].items():
        host = net.addHost(name, ip=node_config['ip'])
        hosts[name] = host
        print(f"✓ 创建节点: {name} ({node_config['ip']})")
    
    # 创建链路
    for link_name, link_config in config['links'].items():
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

def setup_log_path(config):
    start_time_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    first_app = next(iter(config['applications'].values()))
    file_name = first_app['transfer_file']
    log_dir = os.path.join("logs", f"{start_time_str}_{file_name}")
    return log_dir

def setup_ndn_environment(net, hosts, config):
    """设置 NDN 环境"""
    
    print("### 启动网络 ###")
    net.start()
    
    print("### 启动 NFD ###")
    for host in hosts.values():
        host.start_nfd()
    sleep(10)

    print("### 配置路由 ###")
    for node_name, routes in config['routes'].items():
        node = hosts[node_name]
        for prefix, nexthop in routes:
            node.add_route(prefix, nexthop)
    sleep(10)

    print("### 启动应用程序 ###")
    threads = []
    ok_dir = "/tmp/ndn"
    os.makedirs(ok_dir, exist_ok=True)
    ok_file = [os.path.join(ok_dir, f"pro{app_config['id']}.ok") for node_name, app_config in config['applications'].items() if node_name in hosts]

    for node_name, app_config in config['applications'].items():
        if node_name in hosts:
            node = hosts[node_name]
            thread = threading.Thread(
                target=node.start_producer,
                kwargs={
                    'config_file': app_config['config_file'],
                    'transfer_file': app_config['transfer_file'],
                    'id': app_config['id'],
                    'nodes_count': app_config['nodes_count'],
                    'directory': app_config['directory']
                }
            )
            threads.append(thread)
            thread.start()

    import time
    while True:
        if all(os.path.exists(ok) for ok in ok_file):
            break
        time.sleep(1)

    with open(os.path.join(ok_dir, "all.ok"), 'w') as f:
        f.write("all producers started\n")
    return net


def log_movement(log_dir):
    import glob

    log_files = glob.glob('/tmp/ndn/*.log')
    for log_file in log_files:
        fname = os.path.basename(log_file)
        target_path = os.path.join(log_dir, fname)
        shutil.move(log_file, target_path)

def main():  
    setLogLevel('info')
    
    try:
        # 创建网络拓扑
        print("### 创建网络配置 ###")
        config = create_network_config(
            nodes=2,                           # 节点数量
            bw=100,                             # 带宽 (Mbps)   
            delay='0ms',                        # 延迟
            loss=0,                             # 丢包率 (%)
            max_queue_size=10000000,            # 最大队列大小 (字节)
            file_name="small_test.txt",   # 请求的文件名
        )
        
        # 读取网络拓扑
        print("### 读取网络拓扑 ###")
        net, hosts = create_topology_from_config(config)

        # 创建logs目录
        log_dir = setup_log_path(config)

        # 设置 NDN 环境
        net = setup_ndn_environment(net, hosts, config)
    
        CLI(net)

        # 移动日志文件
        log_movement(log_dir)
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