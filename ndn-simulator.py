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
        self._face_log_thread = None
        self._face_log_stop = False
    
    def start_nfd(self):
        """启动 NFD，并把 nfd 日志重定向到 /tmp/ndn/<name>-nfd.log"""
        config_file = f"/tmp/{self.name}-nfd.conf"
        self.create_nfd_config(config_file)
        
        # 确保日志目录存在
        os.makedirs('/tmp/ndn', exist_ok=True)
        nfd_log = f'/tmp/ndn/{self.name}-nfd.log'
        # 使用重定向把日志写到文件（在命名空间内运行）
        nfd_cmd = f"nfd --config {config_file} > {nfd_log} 2>&1"
        self.nfd_process = self.popen(nfd_cmd, shell=True)
        print(f"✓ NFD 启动在 {self.name}, log={nfd_log}")
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
        mcast no
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
}}
"""
        
        with open(config_file, 'w') as f:
            f.write(config_content)
    
    def dump_face_route_logs(self, dest_dir='/tmp/ndn'):
        """导出当前 host 的 face/route/fib 列表到文件（覆盖写）"""
        os.makedirs(dest_dir, exist_ok=True)
        env = f"NDN_CLIENT_TRANSPORT=unix:///run/nfd/{self.name}.sock"
        try:
            faces = self.cmd(f"{env} nfdc face list 2>/dev/null || true")
        except Exception:
            faces = ""
        try:
            routes = self.cmd(f"{env} nfdc route list 2>/dev/null || true")
        except Exception:
            routes = ""
        try:
            fib = self.cmd(f"{env} nfdc fib list 2>/dev/null || true")
        except Exception:
            fib = ""
        with open(os.path.join(dest_dir, f"{self.name}-faces.log"), 'w') as f:
            f.write(faces)
        with open(os.path.join(dest_dir, f"{self.name}-routes.log"), 'w') as f:
            f.write(routes)
        with open(os.path.join(dest_dir, f"{self.name}-fib.log"), 'w') as f:
            f.write(fib)
        # 同时保存最近的 nfd 日志尾部，便于排查
        nfd_log = f"/tmp/ndn/{self.name}-nfd.log"
        try:
            tail = self.cmd(f"tail -n 200 {nfd_log} 2>/dev/null || true")
        except Exception:
            tail = ""
        with open(os.path.join(dest_dir, f"{self.name}-nfd-tail.log"), 'w') as f:
            f.write(tail)
        
    def start_face_log_monitor(self, interval=5.0, dest_dir='/tmp/ndn'):
        """后台线程定期导出 face/route/fib 日志（可在 setup 后启动）"""
        if self._face_log_thread and self._face_log_thread.is_alive():
            return
        self._face_log_stop = False
        def _loop():
            while not self._face_log_stop:
                try:
                    self.dump_face_route_logs(dest_dir)
                except Exception:
                    pass
                time.sleep(interval)
        t = threading.Thread(target=_loop, daemon=True)
        self._face_log_thread = t
        t.start()

    def stop_face_log_monitor(self):
        self._face_log_stop = True
        if self._face_log_thread:
            self._face_log_thread.join(timeout=1.0)
            self._face_log_thread = None

    def add_route(self, prefix, nexthop):
        """添加路由（保持不变，但会在外部调用 dump）"""
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
        cmd = f"{CLIENT_BIN} -c {config_file} -f {transfer_file} -i {id} -n {nodes_count} -d {directory} 2>&1 | tee /tmp/ndn/{id}.log"
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

def create_network_config(nodes = 10, bw = 100, delay = '0ms', loss = 0, max_queue_size = 10000, file_name = "testfile_6442450.txt"):
    """创建网络配置"""
    config = {
        'nodes': {},
        'links': {},
        'applications': {},
        'routes': {},
    }

    # 自动生成 nodes 部分（保留但不用于接口分配）
    for i in range(nodes):
        config['nodes'][f'pro{i}'] = {'ip': f'10.{i}.{i}.0/30', 'type': 'producer'}
        for j in range(nodes):
            if i != j:
                config['nodes'][f'con{i}to{j}'] = {'ip': f'10.{i}.{j}.0/30', 'type': 'consumer'}

    # 自动生成 links 部分，按每条点对点链路分配 /30 子网
    for i in range(nodes):
        for j in range(nodes):
            if i == j:
                continue
            consumer_name = f'con{i}to{j}'
            producer_name = f'pro{j}'
            link_name = f'{consumer_name}-{producer_name}'
            # 为每条点对点链路生成独立 /30 子网：consumer .1, producer .2
            ip1 = f'10.{i}.{j}.1/30'
            ip2 = f'10.{i}.{j}.2/30'
            config['links'][link_name] = {
                'nodes': (consumer_name, producer_name),
                'bw': bw,
                'delay': delay,
                'loss': loss,
                'max_queue_size': max_queue_size,
                'use_htb': True,
                'jitter': None,
                'ip1': ip1,
                'ip2': ip2,
            }

    # applications
    for i in range(nodes):
        config['applications'][f'pro{i}'] = {
            'config_file': os.path.join(PROJECT_ROOT, 'exp-clientconfig.ini'),
            'transfer_file': file_name,
            'id': i,
            'nodes_count': nodes,
            'directory': os.path.join(PROJECT_ROOT, 'experiments')
        }

    # routes 指向 producer 的实际 /ip（不带掩码）
    for i in range(nodes):
        for j in range(nodes):
            if i == j:
                continue
            consumer_name = f'con{i}to{j}'
            producer_name = f'pro{j}'
            producer_ip = config['links'][f'{consumer_name}-{producer_name}']['ip2'].split('/')[0]
            config['routes'][consumer_name] = [
                (f'/pro{j}', f'udp4://{producer_ip}:6363')
            ]

    return config

def create_topology_from_config(config):
    """根据配置创建拓扑（仅创建 link 并记录接口名，不在此配置 IP）"""
    net = Mininet(host=NDNHost, link=TCLink)
    hosts = {}

    # 添加节点（不在这里设置接口 IP）
    for name, node_config in config['nodes'].items():
        host = net.addHost(name)
        hosts[name] = host
        print(f"✓ 创建节点: {name}")

    # 创建链路并记录接口名（不要在这里写 IP）
    for link_name, link_config in config['links'].items():
        node1_name, node2_name = link_config['nodes']
        node1 = hosts[node1_name]
        node2 = hosts[node2_name]

        link_params = {
            'cls': TCLink,
            'bw': link_config['bw'],
            'delay': link_config['delay'],
            'loss': link_config['loss'],
            'max_queue_size': link_config['max_queue_size'],
            'use_htb': link_config.get('use_htb', True)
        }
        if 'jitter' in link_config and link_config['jitter']:
            link_params['jitter'] = link_config['jitter']

        link = net.addLink(node1, node2, **link_params)

        # 保存接口名，实际 IP 在 net.start() 后配置
        try:
            link_config['intf1'] = link.intf1.name
            link_config['intf2'] = link.intf2.name
        except Exception:
            link_config['intf1'] = None
            link_config['intf2'] = None

        print(f"✓ 创建链路: {link_name} ({node1_name}<->{node2_name})")

    return net, hosts

def setup_log_path(config):
    start_time_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    first_app = next(iter(config['applications'].values()))
    file_name = first_app['transfer_file']
    log_dir = os.path.join("logs", f"{start_time_str}_{file_name}")
    return log_dir

def setup_ndn_environment(net, hosts, config):
    """设置 NDN 环境：启动网络 -> 配置接口 IP -> 启动 NFD -> 创建 route -> 启动应用"""
    
    print("### 启动网络 ###")
    net.start()

    # 在网络启动后配置每条链路的 /30 地址（flush 并写入）
    print("### 配置链路接口地址（/30） ###")
    for link_name, link_config in config['links'].items():
        node1_name, node2_name = link_config['nodes']
        node1 = hosts[node1_name]
        node2 = hosts[node2_name]
        intf1 = link_config.get('intf1')
        intf2 = link_config.get('intf2')
        ip1 = link_config.get('ip1')
        ip2 = link_config.get('ip2')
        if not intf1 or not intf2:
            continue
        try:
            # 清除并设置地址
            node1.cmd(f"ip addr flush dev {intf1}")
            node2.cmd(f"ip addr flush dev {intf2}")
            if ip1:
                node1.cmd(f"ip addr add {ip1} dev {intf1}")
            if ip2:
                node2.cmd(f"ip addr add {ip2} dev {intf2}")
            node1.cmd(f"ip link set {intf1} up")
            node2.cmd(f"ip link set {intf2} up")
            # 轻微等待并验证 ARP/ping 可达（非阻塞）
            # 可选：在这里加入更严格的 ping 检查/重试
        except Exception:
            pass

    # 小等待让内核完成 ARP
    sleep(0.5)

    print("### 启动 NFD ###")
    for host in hosts.values():
        host.start_nfd()
        sleep(1)

    print("### 配置路由 ###")
    for node_name, routes in config['routes'].items():
        node = hosts[node_name]
        for prefix, nexthop in routes:
            print(f"add route for {prefix} and {nexthop} on {node_name}")
            node.add_route(prefix, nexthop)
    sleep(3)

    print("### 启动应用程序 ###")
    threads = []
    ok_dir = "/tmp/ndn"
    os.makedirs(ok_dir, exist_ok=True)
    ok_file = [os.path.join(ok_dir, f"pro{app_config['id']}.ok") for node_name, app_config in config['applications'].items() if node_name in hosts]

    print(ok_file)

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

    time.sleep(5)
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
            nodes=3,                           # 节点数量
            bw=100,                             # 带宽 (Mbps)   
            delay='0ms',                        # 延迟
            loss=0,                             # 丢包率 (%)
            max_queue_size=10000,            # 最大队列大小 (字节)
            file_name="testfile_6442450.txt",   # 请求的文件名
        )
        
        # 读取网络拓扑
        print("### 读取网络拓扑 ###")
        net, hosts = create_topology_from_config(config)

        # 创建logs目录
        log_dir = setup_log_path(config)

        # 设置 NDN 环境
        net = setup_ndn_environment(net, hosts, config)

        print("testing")
        input("Press Enter to stop")

        CLI(net)  # 启动 CLI 以便手动操作网络

        # 移动日志文件
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