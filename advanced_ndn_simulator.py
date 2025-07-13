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

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PRODUCER_BIN = os.path.join(PROJECT_ROOT, "producer/bin/ndnput")
CONSUMER_BIN = os.path.join(PROJECT_ROOT, "consumer/bin/ndnget")

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
    
    def start_producer(self, prefix, config_file, directory, log_dir):
        """启动生产者应用"""
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "producer-app.log")
        env = f"NDN_CLIENT_TRANSPORT=unix:///run/nfd/{self.name}.sock"
        cmd = f"{env} {PRODUCER_BIN} --prefix {prefix} --config {config_file} -d {directory} > {log_path} 2>&1"
        proc = self.popen(cmd, shell=True)
        self.app_processes.append(proc)
        print(f"✓ 生产者应用启动在 {self.name}: {prefix}")
        return proc
    
    def start_consumer(self, config_file, interest_name, log_dir):
        """启动消费者应用"""
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "consumer-app.log")
        env = f"NDN_CLIENT_TRANSPORT=unix:///run/nfd/{self.name}.sock"
        cmd = f"{env} {CONSUMER_BIN} --prefix {interest_name} --config {config_file} > {log_path} 2>&1"
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

def setup_ndn_environment(net, hosts, config, log_dir):
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
                config_file=app_config['config_file'],
                directory=app_config['directory'],
                log_dir=log_dir
            )
    
    return net

def run_tests(hosts, config, log_dir):
    """运行测试"""
    
    print("### 运行测试 ###")
    
    total_bw = 0.0
    total_delay = 0.0
    total_time = 0.0
    total_bytes = 0
    test_count = 0
    
    for test in config.tests:
        print(f"\n--- 测试: {test['name']} ---")
        print(f"描述: {test['description']}")
        # 统一生成日志目录
        consumer = hosts[test['consumer']]
        print(f"消费者 {test['consumer']} 请求: {test['interest']}")
        import time
        start_time = time.time()
        result = consumer.start_consumer(test['config'], test['interest'], log_dir)
        end_time = time.time()
        transfer_time = end_time - start_time
        
        # 获取链路参数
        bw = None
        delay = None
        # 查找链路（假设 interest 里有 prefix，且 prefix 与 links 相关）
        for link_name, link_config in config.links.items():
            if test['consumer'] in link_config['nodes']:
                bw = link_config['bw']
                delay = link_config['delay']
                break
        
        # 分析结果并提取传输信息
        bytes_transferred = 0
        segments_received = 0
        max_segment_number = 0
        
        if "ERROR" in result:
            print(f"❌ 测试失败:")
            print(result)
        else:
            print(f"✓ 测试成功")
        
        # 调试输出：显示完整的consumer输出
        print(f"  --- Consumer 完整输出 (调试用) ---")
        for i, line in enumerate(result.split('\n')):
            if line.strip():
                print(f"  [{i}] {line}")
        print(f"  --- 输出结束 ---")
            
        # 提取传输统计信息
        for line in result.split('\n'):
            if any(keyword in line for keyword in ['Published', 'Received', 'segments', 'bytes']):
                print(f"  {line}")
            
            # 提取segment号码 - 从 "Received segment #206" 格式中提取
            if 'received segment #' in line.lower():
                import re
                segment_match = re.search(r'segment\s*#(\d+)', line, re.IGNORECASE)
                if segment_match:
                    segment_num = int(segment_match.group(1))
                    max_segment_number = max(max_segment_number, segment_num)
            
            # 提取字节数 - 改进的正则表达式
            if 'bytes' in line.lower():
                import re
                # 匹配各种格式：123 bytes, 123bytes, Received 123 bytes, etc.
                bytes_patterns = [
                    r'(\d+)\s*bytes',
                    r'bytes:\s*(\d+)',
                    r'received\s+(\d+)',
                    r'transferred\s+(\d+)',
                    r'size\s*:\s*(\d+)'
                ]
                for pattern in bytes_patterns:
                    bytes_match = re.search(pattern, line, re.IGNORECASE)
                    if bytes_match:
                        bytes_transferred = int(bytes_match.group(1))
                        break
            
            # 提取段数 - 改进的正则表达式
            if 'segment' in line.lower() and 'received segment #' not in line.lower():
                import re
                # 匹配各种格式：123 segments, segments: 123, Received 123 segments, etc.
                segment_patterns = [
                    r'(\d+)\s*segments?',
                    r'segments?\s*:\s*(\d+)',
                    r'received\s+(\d+)\s+segments?',
                    r'total\s+segments?\s*:\s*(\d+)',
                    r'segments?\s+received\s*:\s*(\d+)'
                ]
                for pattern in segment_patterns:
                    segments_match = re.search(pattern, line, re.IGNORECASE)
                    if segments_match:
                        segments_received = int(segments_match.group(1))
                        break
        
        # 如果找到了segment号码，计算总段数（segment从0开始，所以+1）
        if max_segment_number > 0:
            calculated_segments = max_segment_number + 1
            print(f"  最大段号: #{max_segment_number}")
            print(f"  计算的段数: {calculated_segments} (基于最大段号+1)")
            segments_received = max(segments_received, calculated_segments)
        
        print(f"  链路带宽: {bw} Mbps")
        print(f"  链路延迟: {delay}")
        print(f"  传输时间: {transfer_time:.2f} 秒")
        
        if segments_received > 0:
            print(f"  接收段数: {segments_received}")
            
            # 从NDN consumer输出中提取段大小（通常是8192字节）
            segment_size = 8192  # NDN默认段大小
            
            # 尝试从输出中解析实际段大小
            for line in result.split('\n'):
                if 'segment size' in line.lower() or 'payload size' in line.lower():
                    import re
                    size_match = re.search(r'(\d+)', line)
                    if size_match:
                        segment_size = int(size_match.group(1))
                        break
            
            # 计算基于段的数据量
            calculated_bytes = segments_received * segment_size
            print(f"  段大小: {segment_size} 字节")
            print(f"  计算数据量: {calculated_bytes} 字节 ({segments_received} × {segment_size})")
            
            if transfer_time > 0:
                segment_based_bw = calculated_bytes * 8 / transfer_time / 1e6
                print(f"  基于段的传输带宽: {segment_based_bw:.2f} Mbps")
                
                # 计算带宽利用率
                if bw and bw > 0:
                    utilization = (segment_based_bw / bw) * 100
                    print(f"  带宽利用率: {utilization:.1f}%")
        
        if bytes_transferred > 0 and transfer_time > 0:
            reported_bw = bytes_transferred * 8 / transfer_time / 1e6
            print(f"  报告的传输带宽: {reported_bw:.2f} Mbps")
            print(f"  报告的数据量: {bytes_transferred} 字节")
            
        total_bw += bw if bw else 0
        total_delay += float(delay.replace('ms','')) if delay else 0
        total_time += transfer_time
        
        # 优先使用基于段的数据量，否则使用报告的字节数
        if segments_received > 0:
            segment_size = 8192  # 默认NDN段大小
            calculated_bytes = segments_received * segment_size
            total_bytes += calculated_bytes
        else:
            total_bytes += bytes_transferred
            
        test_count += 1
        sleep(2)  # 测试间隔
        
    if test_count > 0:
        print("\n=== 测试统计 ===")
        print(f'time: {transfer_time:.2f}')
        print(f"总传输数据量: {total_bytes} 字节")
        if total_bytes > 0 and total_time > 0:
            print(f"总体平均传输速率: {total_bytes * 8 / total_time / 1e6:.2f} Mbps")

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

        # 创建logs目录
        start_time_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = os.path.basename(str(config.tests[0]['interest']))
        log_dir = os.path.join("logs", f"{start_time_str}_{file_name}")
        
        # 设置 NDN 环境
        net = setup_ndn_environment(net, hosts, config, log_dir)
        
        # 等待系统稳定
        sleep(5)
        
        # 运行测试
        run_tests(hosts, config, log_dir)
        
        # 显示状态
        show_network_status(hosts)
    
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

        # 移动日志文件到指定目录
        for fname in ['cwnd.log', 'rtt.log']:
            if os.path.exists(fname):
                target_path = os.path.join(log_dir, fname)
                shutil.move(fname, target_path)

if __name__ == '__main__':
    main()
