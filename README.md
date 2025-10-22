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
├── README.md              # This file
├── Makefile              # Main build file
├── nfd.conf              # NFD configuration
├── test_transmission.sh  # Automated test script
├── experiments/          # Test data directory
│   └── 1/
│       └── test.txt     # Sample test file
├── consumer/             # Consumer application
│   ├── Makefile
│   ├── *.cpp, *.hpp     # Source files
│   └── bin/
│       └── ndnget       # Consumer executable
└── producer/             # Producer application
    ├── Makefile
    ├── config.ini       # Producer configuration
    ├── *.cpp, *.hpp     # Source files
    └── bin/
        └── ndnput       # Producer executable
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
