from mininet.log import setLogLevel, info
from mininet.topo import Topo
from minindn.minindn import Minindn
from minindn.util import MiniNDNCLI
from minindn.apps.app_manager import AppManager
from minindn.apps.nfd import Nfd
from minindn.helpers.ndn_routing_helper import NdnRoutingHelper
from minindn.helpers.nfdc import Nfdc
from time import sleep
import os
import time
import shutil
import argparse, sys, signal

def main():
    TEMP_DIR = os.path.join("/tmp", "ndn")
    WORK_DIR = os.getcwd()
    LOG_DIR = os.path.join(WORK_DIR, "logs")
    FILE_DIR = os.path.join(WORK_DIR, "experiments")
    
    CLIENT_BIN = os.path.join(WORK_DIR, "client", "bin", "ndnclient")
    CONFIG_FILE = os.path.join(WORK_DIR, "exp-clientconfig.ini")
    setLogLevel('info')
    
    
    parser = argparse.ArgumentParser(description="Parser for Minindn-Simulator")
    parser.add_argument("--test-file", required=True, type=str, help="the file to transfer")
    parser.add_argument("--topo-file", required=True, type=str, help="the topology file")
    args = parser.parse_args()

    TEST_FILE = os.path.basename(args.test_file)
    sys.argv = [sys.argv[0], args.topo_file]

    info("Setup Environment\n")
    if os.path.exists(TEMP_DIR):
        files = os.listdir(TEMP_DIR)
        for file in files:
            os.remove(os.path.join(TEMP_DIR, file))
    else:
        os.makedirs(TEMP_DIR)
        
    custom_home = os.path.join("/tmp", "nfd")
    if os.path.exists(custom_home):
        shutil.rmtree(custom_home)
    os.makedirs(custom_home)
        
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
    # # default: nfds = AppManager(ndn, ndn.net.hosts, Nfd, csSize=65536, csPolicy='lru', csUnsolicitedPolicy='drop-all')
    for host in ndn.net.hosts:
        host.params['params']['homeDir'] = os.path.join(custom_home, host.name)
    sleep(2)
        
    nfds = AppManager(ndn, ndn.net.hosts, Nfd, csSize=65536, logLevel='TRACE') 
    sleep(2)
    for host in ndn.net.hosts:
    #     # ndn.net[host.name].cmd(        
    #     # 'nfdc log set cs TRACE || '
    #     # 'nfdc log set nfd.Cs TRACE || '
    #     # 'nfdc log set nfd.ContentStore TRACE')
        ndn.net[host.name].cmd('nfdc strategy set / /localhost/nfd/strategy/asf \
            retx-suppression-initial~4000ms \
            retx-suppression-max~16000ms \
            retx-suppression-multiplier~2')
        # ndn.net[host.name].cmd('nfdc strategy set / /localhost/nfd/strategy/asf')
        
    info("Setting up static routes\n")
    info('Adding static routes to NFD\n')
    grh = NdnRoutingHelper(ndn.net, Nfdc.PROTOCOL_UDP) # support PROTOCOL_TCP, PROTOCOL_UDP, PROTOCOL_ETHER
    # For all host, pass ndn.net.hosts or a list, [ndn.net['a'], ..] or [ndn.net.hosts[0],.]
    
    
    host_names = [host.name for host in ndn.net.hosts if host.name.startswith('client')]
    total_host = len(host_names)
    ok_file = [os.path.join(TEMP_DIR, f"pro{idx}.ok") for idx in range(total_host)]
    finish_file = [os.path.join(TEMP_DIR, f"{idx}.finish") for idx in range(total_host)]
    
    for idx in range(total_host):
        grh.addOrigin([ndn.net[f'client{idx}']], [f"/pro{idx}"])
    
    grh.calculateRoutes()
    sleep(2)

    info('Route addition to NFD completed succesfully\n')
    
    pid_list = []
    if os.path.isfile(CLIENT_BIN):
        for idx, hostname in enumerate(host_names):
            host = ndn.net[hostname]
            log = os.path.join(TEMP_DIR, f'{hostname}.log')
            # 保留参数位置，用户自行填充
            cmd = (
                f'{CLIENT_BIN} --config {CONFIG_FILE} '
                f'--directory {FILE_DIR} '
                f'--filename {TEST_FILE} '
                f'--id {idx} '
                f'--nodes {total_host} &'
            )
            info(f'start client on {hostname}: {cmd}\n')
            proc = host.popen(cmd)
            pid_list.append(proc.pid)
    else:
        info('WARN: client binary not found, skipping starting clients\n')

    while True:
        if all(os.path.exists(ok) for ok in ok_file):
            break
        time.sleep(0.5)

    time.sleep(5)
    with open(os.path.join(TEMP_DIR, "all.ok"), 'w') as f:
        f.write("all producers started\n")
    
    info(f"pidList: {pid_list}\n")
    while True:
        if all(os.path.exists(finish) for finish in finish_file):
            break
        time.sleep(0.5)
    info("All clients finished\n")
    sleep(2)
    try:
        cs_log = os.path.join(TEMP_DIR, "cs.log")
        hits = 0
        info("Collecting CS data\n")
        for host in ndn.net.hosts:
            ndn.net[host.name].cmd(f'{{ echo "{host.name}:"; nfdc status report; }} >> {cs_log} 2>&1')
    except:
        info(f"Failed to collect CS info\n")
        
        
    for pid in pid_list:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception as e:
            info(f"Failed to kill {pid}: {e}\n")
    info('setup complete — drop to Mininet CLI. Stop the network when done.\n')
    MiniNDNCLI(ndn.net)
    
    # save logs
    files = os.listdir('/tmp/ndn/')
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    LOG_DIR = os.path.join(LOG_DIR, timestamp)
    os.makedirs(LOG_DIR)
    
    for file_name in files:
        if file_name.endswith(".log"):
            src_file = os.path.join("/tmp/ndn", file_name)
            dst_file = os.path.join(LOG_DIR, file_name)
            if os.path.getsize(src_file) != 0:
                shutil.move(src_file, dst_file)

    src_topo = os.path.join(WORK_DIR, args.topo_file)
    dst_topo = os.path.join(LOG_DIR, "topo.conf")
    src_conf = os.path.join(WORK_DIR, "exp-clientconfig.ini")
    dst_conf = os.path.join(LOG_DIR, "client.ini")

    shutil.copy(src_topo, dst_topo)
    shutil.copy(src_conf, dst_conf)
    extract_and_append_segmentation_data(LOG_DIR)
    
    ndn.stop()
    # calculate output
    
def extract_and_append_segmentation_data(log_dir):
    """提取分段数据并追加到相关日志"""
    from pathlib import Path
    import re
    
    log_path = Path(log_dir)
    
    # 提取所有 pro*.log 的 Segmenting took 数据
    segment_data = {}
    for pro_log in log_path.glob("pro*.log"):
        producer_id = re.search(r'pro(\d+)', pro_log.name).group(1)
        lines = []
        
        try:
            with pro_log.open('r') as f:
                for line in f:
                    if "Segmenting took" in line:
                        lines.append(line.strip())
            
            if lines:
                segment_data[producer_id] = lines
                info(f"Extracted {len(lines)} segmentation lines from pro{producer_id}.log\n")
        except Exception as e:
            info(f"Failed to read {pro_log}: {e}\n")
    
    # 追加到对应的 consumer 日志
    for producer_id, lines in segment_data.items():
        # 找到所有 con*to{producer_id}.log 文件
        pattern = f"con*to{producer_id}.log"
        target_files = list(log_path.glob(pattern))
        
        for target_file in target_files:
            try:
                with target_file.open('a') as f:
                    f.write(f"\n=== Segmentation data from pro{producer_id}.log ===\n")
                    for line in lines:
                        f.write(line + "\n")
                info(f"Appended segmentation data to {target_file.name}\n")
            except Exception as e:
                info(f"Failed to append to {target_file}: {e}\n")      
    
    

main()
