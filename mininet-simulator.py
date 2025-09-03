from mininet.net import Mininet
from mininet.node import Host
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI
import os
import time
import stat

setLogLevel('info')

# 简单拓扑：client0->h1, client1->h2, client2->h3
net = Mininet(link=TCLink)
h1 = net.addHost('h1')
h2 = net.addHost('h2')
h3 = net.addHost('h3')

net.addLink(h1, h2, bw=100, max_queue_size=10000, delay='0ms')
net.addLink(h1, h3, bw=100, max_queue_size=10000, delay='0ms')
net.addLink(h2, h3, bw=100, max_queue_size=10000, delay='0ms')

net.start()

# IP 配置，点对点 /30
h1.setIP('10.0.1.1/30', intf='h1-eth0')
h2.setIP('10.0.1.2/30', intf='h2-eth0')

h1.setIP('10.0.2.1/30', intf='h1-eth1')
h3.setIP('10.0.2.2/30', intf='h3-eth0')

h2.setIP('10.0.3.1/30', intf='h2-eth1')
h3.setIP('10.0.3.2/30', intf='h3-eth1')

info('IP configured\n')

# 使 h2 <-> h3 可达（通过 h1 路由）
# h1.cmd('sysctl -w net.ipv4.ip_forward=1')
# h2.cmd('ip route add 10.0.2.0/30 via 10.0.1.1')
# h3.cmd('ip route add 10.0.1.0/30 via 10.0.2.1')

# 准备目录
os.makedirs('/tmp/ndn', exist_ok=True)
os.system('sudo mkdir -p /run/nfd || true')
os.system('sudo chmod 755 /run/nfd || true')

def write_nfd_conf(client_name):
    conf_dir = f'/tmp/ndn/{client_name}'
    os.makedirs(conf_dir, exist_ok=True)
    conf_path = f'{conf_dir}/nfd.conf'
    conf = f"""general {{
}}

log {{
  default_level INFO
}}

face_system {{
  unix {{
    path /run/nfd/{client_name}.sock
  }}
  tcp {{
    listen yes
    port 6363
    enable_v4 yes
    enable_v6 no
  }}
  udp {{
    listen yes
    port 6363
    enable_v4 yes
    enable_v6 no
    mcast yes
    mcast_group 224.0.23.170
    mcast_port 56363
  }}
}}

tables {{
  cs_max_packets 65536
  strategy_choice {{
    / /localhost/nfd/strategy/best-route
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
    with open(conf_path, 'w') as f:
        f.write(conf)
    return conf_path

def start_nfd(host, client_name, wait=8):
    conf_path = write_nfd_conf(client_name)
    log_path = f'/tmp/ndn/{client_name}-nfd.log'
    host.cmd(f'nfd --config {conf_path} > {log_path} 2>&1 &')
    sock = f'/run/nfd/{client_name}.sock'
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            st = os.stat(sock)
            if stat.S_ISSOCK(st.st_mode):
                info(f'{client_name} socket ready\n')
                return True
        except FileNotFoundError:
            pass
        time.sleep(0.2)
    info(f'ERROR: socket {sock} not found; tail log:\n')
    info(host.cmd(f'tail -n 80 {log_path}'))
    return False

# 启动每个 host 的 NFD（单个 socket / host）
hosts = [(h1, 'client0', '10.0.1.1'), (h2, 'client1', '10.0.1.2'), (h3, 'client2', '10.0.2.2')]
for host, cname, ip in hosts:
    info(f'start nfd for {cname} on {host.name}\n')
    ok = start_nfd(host, cname)
    if not ok:
        info(f'Failed to start nfd for {cname}\n')

# 等待 NFD 稳定
time.sleep(1.0)

# 自动在每个 NFD 上创建到其它节点的 UDP face，并添加 route 指向对应 /proX
def create_faces_and_routes():
    mapping = {
        'client0': ('10.0.1.1', h1),
        'client1': ('10.0.1.2', h2),
        'client2': ('10.0.2.2', h3),
    }
    # pairwise create faces and routes
    for src_name, (src_ip, src_host) in mapping.items():
        env = f'export NDN_CLIENT_TRANSPORT="unix:///run/nfd/{src_name}.sock"; '
        for dst_name, (dst_ip, dst_host) in mapping.items():
            if src_name == dst_name:
                continue
            # create face to dst IP and add route for /pro<dst_index>
            dst_index = dst_name.replace('client','')
            face_cmd = f'{env} nfdc face create udp4://{dst_ip}:6363'
            addroute_cmd = f'{env} nfdc route add /pro{dst_index} udp4://{dst_ip}:6363'
            info(f'On {src_host.name}: {face_cmd} ; {addroute_cmd}\n')
            src_host.cmd(face_cmd)
            time.sleep(0.1)
            src_host.cmd(addroute_cmd)
            time.sleep(0.1)

def create_faces_and_routes_new():
    mapping = {
        'client0': [('10.0.1.1', h1, '10.0.1.2', h2, 1), ('10.0.2.1', h1, '10.0.2.2', h3, 2)],
        'client1': [('10.0.1.2', h2, '10.0.1.1', h1, 0), ('10.0.3.1', h2, '10.0.3.2', h3, 2)],
        'client2': [('10.0.2.2', h3, '10.0.2.1', h1, 0), ('10.0.3.2', h3, '10.0.3.1', h2, 1)]
    }
    # pairwise create faces and routes
    for src_name, src_list in mapping.items():
        env = f'export NDN_CLIENT_TRANSPORT="unix:///run/nfd/{src_name}.sock"; '
        for (src_ip, src_host, dst_ip, dst_host, dst_index) in src_list:
            # create face to dst IP and add route for /pro<dst_index>
            face_cmd = f'{env} nfdc face create udp4://{dst_ip}:6363'
            addroute_cmd = f'{env} nfdc route add /pro{dst_index} udp4://{dst_ip}:6363'
            info(f'On {src_host.name}: {face_cmd} ; {addroute_cmd}\n')
            src_host.cmd(face_cmd)
            time.sleep(0.2)
            src_host.cmd(addroute_cmd)
            time.sleep(0.2)

create_faces_and_routes_new()

# 验证（简短输出）
for host, cname, ip in hosts:
    info(f'=== {cname} faces/routes ===\n')
    info(host.cmd(f'export NDN_CLIENT_TRANSPORT="unix:///run/nfd/{cname}.sock"; nfdc face list'))
    info(host.cmd(f'export NDN_CLIENT_TRANSPORT="unix:///run/nfd/{cname}.sock"; nfdc route list'))

# 启动客户端程序（参数留空，由你填写）
ok_file = []
CLIENT_BIN = '/home/a_coin_fan/code/ndn-dev/client/bin/ndnclient'
if os.path.isfile(CLIENT_BIN):
    for idx, (host, cname, ip) in enumerate(hosts):
        log = f'/tmp/ndn/{cname}.log'
        ok_file.append(f"/tmp/ndn/pro{idx}.ok")
        # 保留参数位置，用户自行填充
        cmd = (
            f'cd /home/a_coin_fan/code/ndn-dev/client && export NDN_CLIENT_TRANSPORT="unix:///run/nfd/{cname}.sock"; '
            f'{CLIENT_BIN} --config /home/a_coin_fan/code/ndn-dev/exp-clientconfig.ini '
            f'--directory /home/a_coin_fan/code/ndn-dev/experiments '
            f'--filename testfile_64424509.txt '
            f'--id {idx} '
            f'--nodes 3 > /tmp/ndn/client{idx}.log 2>&1 &'
        )
        info(f'start client on {host.name}: {cmd}\n')
        host.cmd(cmd)
else:
    info('WARN: client binary not found, skipping starting clients\n')

while True:
    if all(os.path.exists(ok) for ok in ok_file):
        break
    time.sleep(1)

time.sleep(5)
with open(os.path.join("/tmp/ndn/", "all.ok"), 'w') as f:
    f.write("all producers started\n")

input("Press enter to Continue")
info('setup complete — drop to Mininet CLI. Stop the network when done.\n')
CLI(net)

# 清理
net.stop()