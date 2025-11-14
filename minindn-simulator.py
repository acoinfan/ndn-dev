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
    
class Paths:
    TEMP = Path("/tmp/ndn")
    WORK = Path.cwd()
    LOG = WORK / "logs"
    FILE = WORK / "experiments"
    TRACE = Path("/tmp/minindn")
    SOCKET = Path("/var/run/nfd")

    CLIENT_BIN = WORK / "client" / "bin" / "ndnclient"
    CLIENT_CONFIG_FILE = None
    TEST_FILE = None
    TOPO_FILE = None
    NFDC_CONFIG_FILE = None
        
def parse_args():
    parser = argparse.ArgumentParser(description="Parser for Minindn-Simulator")
    parser.add_argument("--test-file", required=True, type=str, help="the file to transfer")
    parser.add_argument("--topo-file", required=True, type=str, help="the topology file")
    parser.add_argument("--nfdc-file", required=True, type=str, help="nfdc config file")
    parser.add_argument("--client-file", required=True, type=str, help="client config file")
    args = parser.parse_args()
    
    Paths.TEST_FILE = Path(Path(args.test_file).name)
    Paths.TOPO_FILE = Path(args.topo_file).resolve()
    Paths.NFDC_CONFIG_FILE = Path(args.nfdc_file).resolve()
    Paths.CLIENT_CONFIG_FILE = Path(args.client_file).resolve()
                  
    

def load_Nfdconfig() -> NfdConfig:
    config = configparser.ConfigParser()
    try:
        config.read(Paths.NFDC_CONFIG_FILE)
    except(FileNotFoundError):
        raise RuntimeError(f"{Paths.NFDC_CONFIG_FILE}: file not found\n")
    
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
        raise RuntimeError(f"Error reading config file {Paths.NFDC_CONFIG_FILE}: {e}") from e
    
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

def setup_env():
    info("Setting up Environment...\n")
    
    # Cleanup /tmp/ndn
    if Paths.TEMP.exists():
        shutil.rmtree(Paths.TEMP)
    Paths.TEMP.mkdir(parents=True, exist_ok=True)
    
    # Cleanup /tmp/minindn/trace
    if Paths.TRACE.exists():
        shutil.rmtree(Paths.TRACE)
    Paths.TRACE.mkdir(parents=True, exist_ok=True)
        
    Minindn.cleanUp()
    Minindn.verifyDependencies()
    info("Done\n")
    
def setup_Minindn(nfdConfig: NfdConfig):
    # Setup nfd & sockets
    info('Starting NFD on nodes...\n')
    ndn = Minindn(topoFile=Paths.TOPO_FILE)
    ndn.start()    
    
    # Register TRACE file directory: /tmp/minindn/<host_name>/log
    nfds = AppManager(ndn, ndn.net.hosts, Nfd, csSize=nfdConfig.csSize, 
                      csPolicy=nfdConfig.csPolicy, csUnsolicitedPolicy=nfdConfig.csUnsolicitedPolicy, logLevel=nfdConfig.logLevel) 

    info("Done\n")
    return ndn, nfds
    
def wait_for_sockets(nodes: list[str]):
    info("Waiting for Socket files...\n")
    while True:
        if all(os.path.exists(socket) for socket in [f'{Paths.SOCKET}/{node}.sock' for node in nodes]):
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

def simulate(ndn, clients: list[str]):
    pid_list: list[int] = []
    if Paths.CLIENT_BIN.exists():
        for client in clients:
            log = Paths.TEMP / f'{client}.log'
            # 保留参数位置，用户自行填充
            cmd = (
                f'{Paths.CLIENT_BIN} --config {Paths.CLIENT_CONFIG_FILE} '
                f'--directory {Paths.FILE} '
                f'--filename {Paths.TEST_FILE} '
                f'--id {client.split("client")[-1]} '
                f'--nodes {len(clients)} &'
            )
            info(f'start client on {client}: {cmd}\n')
            proc = ndn.net[client].popen(cmd)
            pid_list.append(proc.pid)
    else:
        info('WARN: client binary not found, skipping starting clients\n')

    # detect for producer
    while True:
        ok_files = [Paths.TEMP / f"pro{client.split('client')[-1]}.ok" for client in clients]
        if all(ok.exists() for ok in ok_files):
            break
        time.sleep(0.5)

    # send out signal
    time.sleep(1)
    (Paths.TEMP / "all.ok").write_text("all producers started\n")
    
    info(f"pidList: {pid_list}\n")
    
    # detect for finish
    while True:
        finish_files = [Paths.TEMP / f"{client.split('client')[-1]}.finish" for client in clients]
        if all(finish.exists() for finish in finish_files):
            break
        sleep(0.5)
        
    info("All clients finished\n")
    
    time.sleep(2)
    try:
        cs_log = Paths.TEMP / "cs.log"
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
    parse_args()
    
    # Cleanup sys.argv
    sys.argv = [sys.argv[0]]
    nfdConfig: NfdConfig = load_Nfdconfig()

    setup_env()

    ndn, nfds = setup_Minindn(nfdConfig)

    nodes: list[str] = [host.name for host in ndn.net.hosts]
    clients: list[str] = [node for node in nodes if node.startswith('client')]
    switches: list[str] = [node for node in nodes if node.startswith('s')]
    
    wait_for_sockets(nodes)
    
    setup_routing(ndn, clients, nfdConfig)
    
    setup_strategy(ndn, nfdConfig)

    info("Preparation Done\n")
    
    sleep(1)
    
    simulate(ndn, clients)
    
    # collecting logs
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_dir = Paths.LOG / timestamp
    log_dir.mkdir(parents=True, exist_ok=True)

    # 移动 .log 文件
    for file_path in Paths.TEMP.glob("*.log"):
        if file_path.stat().st_size != 0:
            shutil.move(str(file_path), str(log_dir / file_path.name))

    # 拷贝拓扑文件和客户端配置
    src_topo = Paths.TOPO_FILE
    dst_topo = log_dir / "topo.conf"

    src_conf = Paths.CLIENT_CONFIG_FILE
    dst_conf = log_dir / "client.ini"

    shutil.copy(str(src_topo), str(dst_topo))
    shutil.copy(str(src_conf), str(dst_conf))

    # 提取并追加分段数据
    extract_and_append_segmentation_data(log_dir)

    # 停止网络
    ndn.stop()
    
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

