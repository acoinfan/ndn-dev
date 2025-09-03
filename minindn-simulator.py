from mininet.log import setLogLevel, info
from mininet.topo import Topo
from minindn.minindn import Minindn
from minindn.util import MiniNDNCLI
from minindn.apps.app_manager import AppManager
from minindn.apps.nfd import Nfd
from minindn.helpers.ndn_routing_helper import NdnRoutingHelper
from minindn.helpers.nfdc import Nfdc
from time import sleep
from mininet.node import OVSController
import os
import time

def main():
    setLogLevel('info')
    
    Minindn.cleanUp()
    Minindn.verifyDependencies()

    # 这里可以传入topo(使用minindn示例文件格式即可)
    # topo = Topo()
    # client0 = topo.addHost('client0')
    # client1 = topo.addHost('client1')
    # client2 = topo.addHost('client2')
    # topo.addLink(client0, client1, bw=100, max_queue_size=10000, delay='0ms')
    # topo.addLink(client1, client2, bw=100, max_queue_size=10000, delay='0ms')
    # topo.addLink(client2, client0, bw=100, max_queue_size=10000, delay='0ms')

    ndn = Minindn()
    ndn.start()
    
    info('Starting NFD on nodes\n')
    nfds = AppManager(ndn, ndn.net.hosts, Nfd)
    
    sleep(2)
    
    info("Setting up static routes\n")
    info('Adding static routes to NFD\n')
    grh = NdnRoutingHelper(ndn.net, Nfdc.PROTOCOL_UDP)
    # For all host, pass ndn.net.hosts or a list, [ndn.net['a'], ..] or [ndn.net.hosts[0],.]
    
    host_names = [host.name for host in ndn.net.hosts if host.name.startswith('client')]
    total_host = len(host_names)
    ok_file = [f"/tmp/ndn/pro{idx}.ok" for idx in range(total_host)]
    
    for idx in range(total_host):
        grh.addOrigin([ndn.net[f'client{idx}']], [f"/pro{idx}"])
    
    grh.calculateRoutes()
    sleep(2)

    info('Route addition to NFD completed succesfully\n')

    info(ndn.net["client0"].cmd("nfdc face list"))
    info(ndn.net["client0"].cmd("nfdc fib list"))
    info(ndn.net["client0"].cmd("nfdc strategy show /client0"))


    ok_file = []
    CLIENT_BIN = '/home/a_coin_fan/code/ndn-dev/client/bin/ndnclient'
    if os.path.isfile(CLIENT_BIN):
        for idx, hostname in enumerate(host_names):
            host = ndn.net[hostname]
            log = f'/tmp/ndn/{hostname}.log'
            # 保留参数位置，用户自行填充
            cmd = (
                f'NDN_CLIENT_TRANSPORT="unix:///run/nfd/{hostname}.sock" {CLIENT_BIN} --config /home/a_coin_fan/code/ndn-dev/exp-clientconfig.ini '
                f'--directory /home/a_coin_fan/code/ndn-dev/experiments '
                f'--filename testfile_6442450.txt '
                f'--id {idx} '
                f'--nodes {total_host} > /tmp/ndn/client{idx}.log 2>&1 &'
            )
            info(f'start client on {hostname}: {cmd}\n')
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
    MiniNDNCLI(ndn.net)
    
    
main()
