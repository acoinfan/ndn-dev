# NDN Consumer and Producer

This project contains NDN (Named Data Networking) consumer and producer applications for data transmission testing and experimentation.

## 🚀 Quick Start

### 1. Setup Environment
```bash
# Clone the repository
git clone <repository-url>
cd ndn-dev

# Install dependencies
cd install
./install.sh --use-existing --no-wifi

# Build binary files
make
```

### 2. Automatic Test
```bash
# TO DO
```

## 🔧 Client Configuration
Read `exp-clientconfig.ini` for more details:

## 📁 Project Structure

```
ndn-dev/
├── README.md                  # This file
├── Makefile                   # Main build file
├── debug.md                   # Debug notes
├── exp-clientconfig.ini       # Client experiment configuration
├── minindn-simulator.py       # Mini-NDN simulation helper
├── minindn_test.sh            # Mini-NDN test script
├── client/                    # NDN client (consumer/producer) sources
│   ├── main.cpp               # Entry point
│   ├── *.cpp, *.hpp           # Source files
│   ├── bin/
│   │   └── ndnclient          # Built client executable
│   └── obj/                   # Build artifacts
│       └── core/
├── core/                      # Core shared headers/sources
│   ├── common.hpp
│   ├── version.hpp
│   └── version.cpp.in / version.cpp
├── experiments/               # Experiment assets and data
├── install/                   # Install scripts and utilities
│   ├── install.sh
│   └── util/
│       ├── testbed_topo_generator.py
│       ├── patches/
│       │   └── ndn-cxx-dummy-keychain.patch
│       └── pkgdep/            # OS-specific dependency installers
│           ├── debian.sh
│           ├── ubuntu.sh
│           ├── fedora.sh
│           └── common.sh
├── logs/                      # Runtime logs
└── topologies/                # Network topology configs
    ├── old.conf
    └── web.conf
```

## 📊 Performance Metrics

The consumer provides detailed performance statistics:
- **Transfer Time**: Total transmission time
- **Throughput**: Data transfer rate (Mbit/s)
- **RTT**: Round-trip time statistics
- **Segments**: Number of data segments
- **Retransmissions**: Failed transmission count

Example output:
```
All segments have been received.
Time elapsed: 0.00117695 seconds
Segments received: 1
Transferred size: 0.449 kB
Goodput: 3.051959 Mbit/s
Congestion marks: 0 (caused 0 window decreases)
Timeouts: 0 (caused 0 window decreases)
Retransmitted segments: 0 (0%), skipped: 0
RTT min/avg/max = 1.078/1.078/1.078 ms
```


## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 References

- [NDN-CXX Documentation](https://named-data.net/doc/ndn-cxx/)
- [NFD Documentation](https://named-data.net/doc/NFD/)
- [Named Data Networking](https://named-data.net/)
- [NDN Testbed](https://named-data.net/ndn-testbed/)

## Interest Name Format
```
/test/[filename]
Example: /test/data/1/test.txt
```

---

*For detailed implementation information, see the source code in `consumer/` and `producer/` directories.*
