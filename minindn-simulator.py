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
import argparse, sys, signal, configparser
from dataclasses import dataclass
from pathlib import Path

@dataclass
class NfdConfig:
    strategy: str
    protocol: str
    logLevel: str
    csSize: int
    csPolicy: str
    csUnsolicitedPolicy: str
    supInitial: str
    supMax: str
    supMultiplier: str
    
setLogLevel('info')
args = parse_args()
TEMP_DIR: str = os.path.join("/tmp", "ndn")
WORK_DIR: str = os.getcwd()
LOG_DIR: str = os.path.join(WORK_DIR, "logs")
FILE_DIR: str = os.path.join(WORK_DIR, "experiments")
TRACE_DIR: str = os.path.join("/tmp", "minindn")
SOCKET_DIR: str = os.path.join("/var", "run", "nfd")

CLIENT_BIN: str = os.path.join(WORK_DIR, "client", "bin", "ndnclient")
CLIENT_CONFIG_FILE: str = os.path.join(WORK_DIR, "exp-clientconfig.ini")
TEST_FILE: str = os.path.basename(args.test_file)
TOPO_FILE: str = os.path.abspath(args.topo_file)

@dataclass
class Paths:
    TEMP = Path("/tmp/ndn")
    WORK = Path.cwd()
    LOG = WORK / "logs"
    FILE = WORK / "experiments"
    TRACE = Path("/tmp/minindn")
    SOCKET = Path("/var/run/nfd")

    CLIENT_BIN = WORK / "client" / "bin" / "ndnclient" 
    CLIENT_CONFIG_FILE = WORK / "exp-clientconfig.ini"
    TEST_FILE: Path | None = None
    TOPO_FILE: Path | None = None
    NFDC_CONFIG_FILE: Path | None = None
        
def parse_args():
    parser = argparse.ArgumentParser(description="Parser for Minindn-Simulator")
    parser.add_argument("--test-file", required=True, type=str, help="the file to transfer")
    parser.add_argument("--topo-file", required=True, type=str, help="the topology file")
    parser.add_argument("--nfdc-file", required=True, type=str, help="nfdc config file")
    args = parser.parse_args()
    paths = Paths()
    

def load_Nfdconfig(path: str) -> NfdConfig:
    config = configparser.ConfigParser()
    try:
        config.read(path)
    except(FileNotFoundError):
        raise RuntimeError(f"{path}: file not found\n")
    
    try:
        strategy : str = f'/localhost/nfd/strategy/{config.get("general", "strategy", fallback=None) or "best-route"}'
        protocol : str  = config.get("general", "protocol", fallback=None) or "tcp"
        logLevel : str = config.get("general", "logLevel", fallback=None) or "trace"
        logLevel = logLevel.upper()
        
        csSize : int = config.getint("cache", "csSize", fallback=65536) or 65536
        csPolicy : str = config.get("cache", "csPolicy", fallback=None) or "lru"
        csUnsolicitedPolicy : str = config.get("cache", "csUnsolicitedPolicy", fallback=None) or "drop-all"
        
        supInitial : str = f'retx-suppression-initial~{config.getint("suppression", "retx-suppression-initial", fallback=10) or 10}ms'
        supMax : str = f'retx-suppression-max~{config.getint("suppression", "retx-suppression-max", fallback=250) or 250}ms'
        supMultiplier : str = f'retx-suppression-multiplier~{config.getint("suppression", "retx-suppression-multiplier", fallback=2) or 2}'
    except Exception as e:
        raise RuntimeError(f"Error reading config file {path}: {e}") from e
    
    return NfdConfig(
        strategy=strategy,
        protocol=protocol,
        logLevel=logLevel,
        csSize=csSize,
        csPolicy=csPolicy,
        csUnsolicitedPolicy=csUnsolicitedPolicy,
        supInitial=supInitial,
        supMax=supMax,
        supMultiplier=supMultiplier
    )

def setup_env(TEMP_DIR: str, TRACE_DIR: str):
    info("Setting up Environment...\n")
    
    # Cleanup /tmp/ndn
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)

    # Create /tmp/ndn/trace
    if not os.path.exists(TRACE_DIR):
        os.makedirs(TRACE_DIR)
        
    Minindn.cleanUp()
    Minindn.verifyDependencies()
    info("Done\n")
    
def setup_Minindn(TOPO_FILE: str, TRACE_DIR: str, nfdConfig: NfdConfig):
    # Setup nfd & sockets
    info('Starting NFD on nodes...\n')
    ndn = Minindn(topoFile=TOPO_FILE)
    ndn.start()    
    
    # Register TRACE file directory: /tmp/ndn/trace/<host_name>/log
    info(getattr(Minindn, "workDir", "/tmp/minindn"))
    nfds = AppManager(ndn, ndn.net.hosts, Nfd, csSize=nfdConfig.csSize, 
                      csPolicy=nfdConfig.csPolicy, csUnsolicitedPolicy=nfdConfig.csUnsolicitedPolicy, logLevel=nfdConfig.logLevel) 

    info("Done\n")
    return ndn, nfds
    
def wait_for_sockets(nodes: list[str], SOCKET_DIR: str):
    info("Waiting for Socket files...\n")
    while True:
        if all(os.path.exists(socket) for socket in [f'{SOCKET_DIR}/{node}.sock' for node in nodes]):
            break
        time.sleep(0.5)
    info("Done\n")

def setup_routing(ndn, clients: list[str], nfdConfig: NfdConfig):
    grh = NdnRoutingHelper(ndn.net, nfdConfig.protocol)
    for client in clients:
        client_id = client.split("client")[-1]
        grh.addOrigin([ndn.net[client]], [f"/pro{client_id}"])
    grh.calculateRoutes()
    
        
def setup_strategy(ndn, nfdConfig: NfdConfig):
    info("Setting up strategy...\n")
    for host in ndn.net.hosts:
        ndn.net[host.name].cmd(f'nfdc strategy set \
            {nfdConfig.strategy} {nfdConfig.supInitial} \
            {nfdConfig.supMax} {nfdConfig.supMultiplier}')    
    sleep(1)
    info("Done\n")

def simulate(n):
    if os.path.isfile(CLIENT_BIN):
        for client in clients:
            log = os.path.join(TEMP_DIR, f'{client}.log')
            # 保留参数位置，用户自行填充
            cmd = (
                f'{CLIENT_BIN} --config {CLIENT_CONFIG_FILE} '
                f'--directory {FILE_DIR} '
                f'--filename {TEST_FILE} '
                f'--id {client.split("client")[-1]} '
                f'--nodes {len(clients)} &'
            )
            info(f'start client on {client}: {cmd}\n')
            proc = ndn.net[client].popen(cmd)
            pid_list.append(proc.pid)
    else:
        info('WARN: client binary not found, skipping starting clients\n')

    while True:
        if all(os.path.exists(ok) for ok in [f'{TEMP_DIR}/pro{client.split("client")[-1]}.ok' for client in clients]):
            break
        time.sleep(0.5)

    time.sleep(5)
    with open(os.path.join(TEMP_DIR, "all.ok"), 'w') as f:
        f.write("all producers started\n")
    
    info(f"pidList: {pid_list}\n")
    while True:
        if all(os.path.exists(finish) for finish in [f'{TEMP_DIR}/{client.split("client")[-1]}.finish' for client in clients]):
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
                
def main():
    setLogLevel('info')
    args = parse_args()
    TEMP_DIR: str = os.path.join("/tmp", "ndn")
    WORK_DIR: str = os.getcwd()
    LOG_DIR: str = os.path.join(WORK_DIR, "logs")
    FILE_DIR: str = os.path.join(WORK_DIR, "experiments")
    TRACE_DIR: str = os.path.join("/tmp", "minindn")
    SOCKET_DIR: str = os.path.join("/var", "run", "nfd")
    
    CLIENT_BIN: str = os.path.join(WORK_DIR, "client", "bin", "ndnclient")
    CLIENT_CONFIG_FILE: str = os.path.join(WORK_DIR, "exp-clientconfig.ini")
    TEST_FILE: str = os.path.basename(args.test_file)
    TOPO_FILE: str = os.path.abspath(args.topo_file)
    
    # Cleanup sys.argv
    sys.argv = [sys.argv[0]]
    nfdConfig: NfdConfig = load_Nfdconfig(args.nfdc_file)

    setup_env(TEMP_DIR=TEMP_DIR, TRACE_DIR=TRACE_DIR)

    ndn, nfds = setup_Minindn(TOPO_FILE, TRACE_DIR, nfdConfig)

    nodes: list[str] = [host.name for host in ndn.net.hosts]
    clients: list[str] = [node for node in nodes if node.startswith('client')]
    switches: list[str] = [node for node in nodes if node.startswith('s')]
    
    wait_for_sockets(nodes, SOCKET_DIR)
    
    setup_routing(ndn, clients, nfdConfig)
    
    setup_strategy(ndn, nfdConfig)

    info("Preparation Done\n")
    
    sleep(1)
    pid_list = simulate(ndn)
    pid_list = []
    if os.path.isfile(CLIENT_BIN):
        for client in clients:
            log = os.path.join(TEMP_DIR, f'{client}.log')
            # 保留参数位置，用户自行填充
            cmd = (
                f'{CLIENT_BIN} --config {CLIENT_CONFIG_FILE} '
                f'--directory {FILE_DIR} '
                f'--filename {TEST_FILE} '
                f'--id {client.split("client")[-1]} '
                f'--nodes {len(clients)} &'
            )
            info(f'start client on {client}: {cmd}\n')
            proc = ndn.net[client].popen(cmd)
            pid_list.append(proc.pid)
    else:
        info('WARN: client binary not found, skipping starting clients\n')

    while True:
        if all(os.path.exists(ok) for ok in [f'{TEMP_DIR}/pro{client.split("client")[-1]}.ok' for client in clients]):
            break
        time.sleep(0.5)

    time.sleep(5)
    with open(os.path.join(TEMP_DIR, "all.ok"), 'w') as f:
        f.write("all producers started\n")
    
    info(f"pidList: {pid_list}\n")
    while True:
        if all(os.path.exists(finish) for finish in [f'{TEMP_DIR}/{client.split("client")[-1]}.finish' for client in clients]):
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

