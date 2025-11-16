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
import shutil, csv, re
import argparse, sys, signal, configparser
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple, Optional

@dataclass
class NfdConfig:
    strategy: str
    protocol: str
    logLevel: str
    csSize: int
    csPolicy: str
    csUnsolicitedPolicy: str
    supInitial: str | None
    supMax: str | None
    supMultiplier: str | None
    cli: bool
    
class Paths:
    TEMP = Path("/tmp/ndn")
    WORK = Path.cwd()
    LOG_BASE = WORK / "logs"
    FILE = WORK / "experiments"
    TRACE = Path("/tmp/minindn")
    SOCKET = Path("/var/run/nfd")

    LOG = None
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
    parser.add_argument("--log-dir", type=str, help="log dir", default=None)
    args = parser.parse_args()
    
    log_dir: str = args.log_dir if args.log_dir else time.strftime("%Y%m%d-%H%M%S")
    
    Paths.TEST_FILE = Path(Path(args.test_file).name)
    Paths.TOPO_FILE = Path(args.topo_file).resolve()
    Paths.NFDC_CONFIG_FILE = Path(args.nfdc_file).resolve()
    Paths.CLIENT_CONFIG_FILE = Path(args.client_file).resolve()
    Paths.LOG = Paths.LOG_BASE / log_dir 
    

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
        cli : bool = config.getboolean("general", "cli", fallback=False) or False
        logLevel = logLevel.upper()
        
        csSize : int = config.getint("cache", "csSize", fallback=65536) or 65536
        csPolicy : str = config.get("cache", "csPolicy", fallback=None) or "lru"
        csUnsolicitedPolicy : str = config.get("cache", "csUnsolicitedPolicy", fallback=None) or "drop-all"
        
        val = config.get("suppression", "retx-suppression-initial", fallback="")
        supInitial : str | None = f'retx-suppression-initial~{val}' if val else None  
        
        val = config.get("suppression", "retx-suppression-max", fallback="")
        supMax : str | None = f'retx-suppression-max~{val}' if val else None
        
        val = config.get("suppression", "retx-suppression-multiplier", fallback="")
        supMultiplier : str | None = f'retx-suppression-multiplier~{val}' if val else None
        
    except Exception as e:
        raise RuntimeError(f"Error reading config file {Paths.NFDC_CONFIG_FILE}: {e}") from e
    
    return NfdConfig(
        strategy=strategy,
        protocol=protocol,
        logLevel=logLevel,
        cli=cli,
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
    
    # Cleanup /var/run/nfd
    if Paths.SOCKET.exists():
        shutil.rmtree(Paths.SOCKET)
    Paths.SOCKET.mkdir(parents=True, exist_ok=True)    
    
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
    params = [nfdConfig.strategy, 'v=5', nfdConfig.supInitial, nfdConfig.supMax, nfdConfig.supMultiplier]
    params = [str(p) for p in params if p is not None and str(p).strip() != '']
    cmd = "/".join(params)
    
    for host in ndn.net.hosts:
        ndn.net[host.name].cmd(cmd)    
    sleep(1)
    info("Done\n")

def simulate(ndn, clients: list[str], nfdConfig: NfdConfig):
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
                f'--nodes {len(clients)}'
           
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
    
    if nfdConfig.cli:
        info("Using Ctrl+D or exit to drop CLI\n")
        MiniNDNCLI(ndn.net)    


def collecting_logs(clients, switches, nfdConfig: NfdConfig):
    # buiding directories
    
    Paths.LOG.mkdir(parents=True, exist_ok=True)

    # copying topo.conf, client.ini, nfd.ini
    src_topo = Paths.TOPO_FILE
    dst_topo = Paths.LOG / "topo.conf"

    src_conf = Paths.CLIENT_CONFIG_FILE
    dst_conf = Paths.LOG / "client.ini"

    src_nfdc = Paths.NFDC_CONFIG_FILE
    dst_nfdc = Paths.LOG / "nfd.ini"
    
    shutil.copy(str(src_topo), str(dst_topo))
    shutil.copy(str(src_conf), str(dst_conf))
    shutil.copy(str(src_nfdc), str(dst_nfdc))
    
    # Analysing Data
    statistics: Dict = collecting_transfer_times(clients)
    if nfdConfig.logLevel == "TRACE" or nfdConfig.logLevel == "DEBUG":
        collecting_cache_stats(clients + switches)
    producer_io_statistics: Dict = collecting_producer_io()
    
    collecting_summary(statistics, producer_io_statistics)
    saving_original_logs()


def collecting_transfer_times(clients: List[int]):
    num_clients = len(clients)
    transfer_matrix: List[List[Optional[float]]] = [["" for _ in range(num_clients)] for _ in range(num_clients)]
    io_times: List[Optional[float]] = [None] * num_clients

    max_time: float = -1
    min_time: float = 1e18
    max_link: Optional[Tuple[int, int]] = None
    min_link: Optional[Tuple[int, int]] = None

    file_size_kb: Optional[int] = None
    seg_counts: Optional[int] = None
    
    # Compiling Regex Expression
    re_fname        = re.compile(r"con(\d+)to(\d+)\.log$")
    re_time_elapsed = re.compile(r"Time elapsed:\s*([0-9.]+)\s*seconds")
    re_file_size = re.compile(r"Transferred size:\s*([0-9.eE+-]+)\s*kB")
    re_io_time      = re.compile(r"I/O Time:\s*([0-9.]+)\s*μs")
    re_seg_counts   = re.compile(r'Segments received:\s*([0-9]+)\s*')
    
    # iterating through /tmp/ndn
    for path in Paths.TEMP.iterdir():
        if not path.is_file():
            continue

        m = re_fname.match(path.name)
        if not m:
            continue
        
        # Extract "Consumer" and "Producer"
        consumer = int(m.group(1))
        producer = int(m.group(2))

        # Read the content
        content = path.read_text(encoding="utf8")

        # Extract and recording time elapsed
        m_time = re_time_elapsed.search(content)
        if not m_time:
            continue
        elapsed = float(m_time.group(1))
        transfer_matrix[consumer][producer] = elapsed
        
        # Extract IO time (Belongs to consumer)
        m_io = re_io_time.search(content)
        if m_io:
            io_times[consumer] = float(m_io.group(1))

        # Recording file size and numbers of segments
        if file_size_kb is None:
            m_size = re_file_size.search(content)
            if m_size:
                file_size_kb = int(float(m_size.group(1)))
        if seg_counts is None:
            m_counts = re_seg_counts.search(content)
            if m_counts:
                seg_counts = int(m_counts.group(1))
        

        # Updating Max/Min transfer time
        if elapsed > max_time:
            max_time = elapsed
            max_link = (consumer, producer)

        if elapsed < min_time:
            min_time = elapsed
            min_link = (consumer, producer)

    # Writing transfer_times.csv
    transfer_times_csv = Paths.LOG / "transfer_times.csv"
    with transfer_times_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["consumer/producer(seconds)"] + [f'pro{i}' for i in range(0, num_clients)])
        for i, row in enumerate(transfer_matrix):
            writer.writerow([f'con{i}'] + row)

    # Writing consumer_io.csv
    consumer_io_csv = Paths.LOG / "consumer_io.csv"
    with consumer_io_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["client", "io_time(μs)"])
        for cid, io in enumerate(io_times):
            writer.writerow([cid, io if io is not None else ""])

    valid_ios = [x for x in io_times if x is not None]
    
    return {
        "max_time": max_time,
        "max_link": max_link,
        "min_time": min_time,
        "min_link": min_link,
        "file_size": file_size_kb,
        "seg_counts": seg_counts,
        "max_consumer_io": max(valid_ios) if valid_ios else None,
        "avg_consumer_io": sum(valid_ios) / len(valid_ios) if valid_ios else None,
        "num_clients": num_clients
    }

def collecting_cache_stats(hosts):
    # Compiling Regex Expression
    re_interest = re.compile(r"interest=/pro\d+/.*")
    re_forwarder = re.compile(r"DEBUG: \[nfd\.Forwarder\]")
    re_strategy = re.compile(r"DEBUG: \[nfd\..+Strategy\]")

    log_file = Paths.LOG / "cache_stats.csv"
    
    with log_file.open("w", newline="") as log:
        writer = csv.writer(log)
        writer.writerow(["host", "hit", "cold_miss", "suppress_miss", "retry_miss"])
        for host in hosts:
            counts:dict = {'hit': 0 ,'cold_miss': 0, 'suppress_miss': 0, 'retry_miss': 0}
            
            trace_file = Paths.TRACE / host / "log" / "nfd.log"
            with trace_file.open("r", encoding="utf8") as f:
                for line in f:
                    # If Invalid interest, skip
                    if not re_interest.search(line):
                        continue

                    # hit
                    if re_forwarder.search(line) and "onContentStoreHit" in line:
                        counts['hit'] += 1
                        continue

                    # miss
                    if re_strategy.search(line):
                        # cold miss
                        if ("new forward-to=" in line) or ("new to=" in line):
                            counts['cold_miss'] += 1
                        # suppress miss
                        if "suppressed" in line:
                            counts['suppress_miss'] += 1
                            # skip retx (asf strategy Trace Log: retx retry=xxx suppress)
                            continue
                        # retry miss 
                        if "retx retry-to" in line:
                            counts['retry_miss'] += 1
            writer.writerow([host, counts["hit"], counts["cold_miss"], counts["suppress_miss"], counts["retry_miss"]])

def collecting_producer_io():
    # Compiling Regex Expression
    re_fname         = re.compile(r"pro(\d+)\.log$")
    re_segment_time  = re.compile(r"Segmenting took\s*([0-9.]+)\s*μs")
    
    max_segment_time, sum_segmemt_time, counts = 0, 0, 0
    log_file = Paths.LOG / "producer_io.csv"
    
    with log_file.open("w", newline="") as log:
        writer = csv.writer(log)
        writer.writerow(["proucer", "seg_time"])
        
        # iterating through /tmp/ndn
        for path in Paths.TEMP.iterdir():
            if not path.is_file():
                continue

            m = re_fname.match(path.name)
            if not m:
                continue
            
            # Extract "Producer"
            producer = int(m.group(1))
            
            # Read the content
            content = path.read_text(encoding="utf8")

            # Extract and recording segment_time
            m_time = re_segment_time.search(content)
            if not m_time:
                continue
            segment_time = int(m_time.group(1))    
            writer.writerow([producer, segment_time])
            
            # Collecting statistics
            if segment_time > max_segment_time:
                max_segment_time = segment_time
            sum_segmemt_time += segment_time
            counts += 1
    
    return {
        "max_producer_io": max_segment_time,
        "avg_producer_io": sum_segmemt_time / counts if counts != 0 else 0
    }

def collecting_summary(statistics: dict, producer_io_statistics: dict):
    log_file = Paths.LOG / "summary.csv"
    with log_file.open("w", newline="") as log:
        writer = csv.writer(log)
        writer.writerow(["key", "value1", "value2"])
        writer.writerow(["file_size(kB/seg_counts)", statistics["file_size"], statistics["seg_counts"]])
        writer.writerow(["max_transfer_time(s)", statistics["max_time"], statistics["max_link"]])
        writer.writerow(["min_transfer_time(s)", statistics["min_time"], statistics["min_link"]])
        writer.writerow(["consumer_io(max[μs]/avg[μs])", statistics["max_consumer_io"], statistics["avg_consumer_io"]])
        writer.writerow(["producer_io(max[μs]/avg[μs])", producer_io_statistics["max_producer_io"], producer_io_statistics["avg_producer_io"]])

        # bw = 100 Mbps
        bandwidth: float = 100
        # throughput Mbps
        max_throughput: float = statistics["file_size"] * 8 / 1000 / statistics["min_time"]
        min_throughput: float = statistics["file_size"] * 8 / 1000 / statistics["max_time"]
        
        # Using bits to calculate
        total_file_bits: int = statistics["file_size"] * 1000 * 8 * (statistics["num_clients"] - 1)
        
        # Mbps in throughput
        throughput_mbps: float = total_file_bits / statistics["max_time"] / 1e6 
        
        utilization: float = throughput_mbps / bandwidth
        
        # io percentage[in worse case] (μs -> s)
        consumer_io_percentage = statistics["max_consumer_io"] / 1e6 / statistics["max_time"]
        producer_io_percentage = producer_io_statistics["max_producer_io"] / 1e6 / statistics["max_time"]
        
        writer.writerow(["max/min throughput for single link(Mbps)", max_throughput, min_throughput])
        writer.writerow(["throughput(Mbps)", throughput_mbps, f"based on bw={bandwidth}Mbps"])
        writer.writerow(["ultilization", utilization, f"{utilization * 100}%"])
        writer.writerow(["consumer io percentage", consumer_io_percentage, f"{consumer_io_percentage*100}%"])
        writer.writerow(["producer io percentage", producer_io_percentage, f"{producer_io_percentage*100}%"])

def saving_original_logs():
    log_path = Paths.TEMP
    re_pro_fname = re.compile(r"pro\d+\.log$")
    re_con_fname = re.compile(r"con\d+to\d+\.log$")
    re_con_rtt_fname = re.compile(r"con\d+to\d+-rtt\.log$")
    re_con_cwnd_fname = re.compile(r"con\d+to\d+-cwnd\.log$")
    
    details = Paths.LOG / "details"
    rtt = Paths.LOG / "rtt"
    cwnd = Paths.LOG / "cwnd"
    
    details.mkdir(parents=True, exist_ok=True)
    rtt.mkdir(parents=True, exist_ok=True)
    cwnd.mkdir(parents=True, exist_ok=True)
    
    for path in Paths.TEMP.iterdir():
        if not path.is_file():
            continue 
        
        filename = path.name
        
        if re_pro_fname.match(filename) or re_con_fname.match(filename):
            shutil.move(path, details / filename)
        elif re_con_rtt_fname.match(filename):
            shutil.move(path, rtt / filename)
        elif re_con_cwnd_fname.match(filename):
            shutil.move(path, cwnd / filename)


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
    
    sleep(10)
    
    simulate(ndn, clients, nfdConfig)
    
    # collecting logs
    collecting_logs(clients, switches, nfdConfig)

    # stop ndn
    ndn.stop()
    

    
    

main()

