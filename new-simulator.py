from time import sleep
from mininet.log import setLogLevel, info
from mininet.topo import Topo

from minindn.minindn import Minindn
from minindn.util import MiniNDNCLI
from minindn.apps.app_manager import AppManager
from minindn.apps.nfd import Nfd
from minindn.apps.nlsr import Nlsr

def setup_cross_node_routing(ndn):
    """设置跨节点路由"""
    info("=== Setting up cross-node routing ===\n")
    
    hosts = ndn.net.hosts
    host_ips = {host.name: host.IP() for host in hosts}
    
    for i, host in enumerate(hosts):
        # 为每个节点添加到其他节点producer的路由
        for j, other_host in enumerate(hosts):
            if i != j:
                producer_prefix = f"/pro{j}"
                other_ip = host_ips[other_host.name]
                
                # 创建到其他节点的face
                face_create_cmd = f'nfdc face create udp4://{other_ip}:6363'
                result = host.cmd(face_create_cmd)
                info(f'{host.name}: Created face to {other_host.name} ({other_ip}): {result}')
                
                # 添加路由
                route_add_cmd = f'nfdc route add {producer_prefix} udp4://{other_ip}:6363'
                result = host.cmd(route_add_cmd)
                info(f'{host.name}: Added route {producer_prefix} -> {other_host.name}: {result}')
                
                sleep(1)  # 给路由时间生效

if __name__ == '__main__':
    setLogLevel('info')
    
    Minindn.cleanUp()
    Minindn.verifyDependencies()

    topo = Topo()
    client0 = topo.addHost('client0')
    client1 = topo.addHost('client1')
    client2 = topo.addHost('client2')

    topo.addLink(client0, client1)
    topo.addLink(client1, client2)
    topo.addLink(client2, client0)

    ndn = Minindn(topo=topo)
    ndn.start()

    info("Starting NFD on nodes\n")
    nfds = AppManager(ndn, ndn.net.hosts, Nfd, logLevel="INFO")  # 改为INFO减少日志

    # 等待NFD启动
    sleep(30)

    # 创建测试文件
    for client_host in ndn.net.hosts:
        client_host.cmd('mkdir -p /tmp/ndn/')
        client_host.cmd('mkdir -p /home/a_coin_fan/code/ndn-dev/experiments/')
        # 创建测试文件
        test_content = f"Hello from {client_host.name} - this is test content"
        client_host.cmd(f'echo "{test_content}" > /home/a_coin_fan/code/ndn-dev/experiments/small_test.txt')

    # 为每个client启动应用程序
    clients = ndn.net.hosts
    total_clients = len(clients)
    assert(total_clients == 3), "Expected exactly 3 clients"

    info("=== Starting client applications ===\n")
    for i, client_host in enumerate(clients):
        producer_prefix = f"/pro{i}"

        # 启动client应用程序（后台运行）
        client_cmd = (
            f'/home/a_coin_fan/code/ndn-dev/client/bin/ndnclient '
            f'--directory /home/a_coin_fan/code/ndn-dev/experiments '
            f'--filename small_test.txt '
            f'--id {i} '
            f'--nodes 3 '
            f'--config /home/a_coin_fan/code/ndn-dev/exp-clientconfig.ini '
            f'> /tmp/ndn/client{i}.log 2>&1 &'
        )

        info(f'Starting client {i} on {client_host.name}...\n')
        client_host.cmd(client_cmd)
        
        sleep(3)  # 给应用时间启动

    # 设置跨节点路由
    setup_cross_node_routing(ndn)

    # 等待路由生效
    info("Waiting for routing to converge...\n")
    sleep(10)

    # 检查应用程序状态
    info("=== Checking Application Status ===\n")
    for i, client_host in enumerate(clients):
        # 检查进程
        process_check = client_host.cmd('pgrep -f ndnclient | wc -l')
        info(f'Client {i} running processes: {process_check.strip()}\n')
        
        # 检查日志
        log_lines = client_host.cmd(f'wc -l /tmp/ndn/client{i}.log 2>/dev/null || echo "0"')
        info(f'Client {i} log lines: {log_lines.strip()}\n')

    # 检查路由表
    info("=== Checking Routing Tables ===\n")
    for i, client_host in enumerate(clients):
        info(f'--- {client_host.name} FIB ---\n')
        fib_output = client_host.cmd('nfdc fib list | grep -E "(pro|nexthops)"')
        info(f'{fib_output}\n')

    # 手动测试连接
    info("=== Testing Manual Connectivity ===\n")
    test_host = clients[0]
    for j in range(1, total_clients):
        test_prefix = f"/pro{j}"
        info(f'Testing {test_host.name} -> {test_prefix}\n')
        
        # 使用ndnpeek测试
        peek_result = test_host.cmd(f'timeout 5 ndnpeek {test_prefix}/small_test.txt')
        if peek_result.strip():
            info(f'SUCCESS: {peek_result[:50]}...\n')
        else:
            info(f'FAILED: No response\n')
            
            # 调试信息
            debug_cmd = f'nfdc status | grep -A5 -B5 "faceid.*{j}"'
            debug_info = test_host.cmd(debug_cmd)
            info(f'Debug info: {debug_info}\n')

    info("=== Manual Testing Commands ===\n")
    info("1. Check processes: client0 pgrep -f ndnclient\n")
    info("2. Check logs: client0 tail /tmp/ndn/client0.log\n")
    info("3. Check FIB: client0 nfdc fib list\n")
    info("4. Check faces: client0 nfdc face list\n")
    info("5. Test connection: client0 ndnpeek /pro1/small_test.txt\n")
    info("6. Check specific face: client0 nfdc face list | grep udp4\n")

    input("Press enter to continue to CLI...")

    MiniNDNCLI(ndn.net)

    ndn.stop()