# NDN Consumer and Producer

This project contains NDN (Named Data Networking) consumer and producer applications for data transmission testing and experimentation.

## 🚀 Quick Start

### 1. Setup Environment
```bash
# Clone the repository
git clone <repository-url>
cd ndn-dev

# Make test script executable
chmod +x test_transmission.sh

# Run automated test
./test_transmission.sh
```

### 2. Manual Test
```bash
# Start NFD in background
sudo /usr/local/bin/nfd --config nfd.conf &

# Start producer
cd producer
./bin/ndnput --prefix /test/data --datasetId 1 &

# Request data with consumer
cd ../consumer
./bin/ndnget /test/data/1/test.txt --no-version-discovery > received_file.txt
```

## 📋 Prerequisites

Before building, make sure you have the following dependencies installed:

### Required Libraries
- `ndn-cxx` - NDN C++ library
- `boost` - Boost C++ libraries (program_options, system, thread)
- `spdlog` - Fast C++ logging library (for producer)
- `fmt` - Formatting library (for producer)
- `pthread` - POSIX threads
- `nfd` - NDN Forwarding Daemon

### Ubuntu/Debian Installation
```bash
# Install NDN-CXX and NFD
sudo apt-get update
sudo apt-get install libndn-cxx-dev nfd

# Install Boost libraries
sudo apt-get install libboost-all-dev

# Install spdlog and fmt
sudo apt-get install libspdlog-dev libfmt-dev

# Install build tools
sudo apt-get install build-essential g++ make
```

### CentOS/RHEL Installation
```bash
# Install NDN-CXX and NFD (may need to build from source)
# Install Boost libraries
sudo yum install boost-devel

# Install spdlog and fmt
sudo yum install spdlog-devel fmt-devel

# Install build tools
sudo yum groupinstall "Development Tools"
```

## 🔨 Building

### Build Everything
```bash
make all
```

### Build Consumer Only
```bash
make consumer
```

### Build Producer Only
```bash
make producer
```

### Clean Build Files
```bash
make clean
```

## 🔧 Configuration

### NFD Configuration
The project includes a custom NFD configuration file (`nfd.conf`) with the following settings:
- **Socket Path**: `/run/nfd/nfd.sock`
- **TCP Port**: 6363
- **UDP Port**: 6363
- **Multicast**: Enabled
- **Content Store**: 65536 packets

### Producer Configuration
Producer configuration is stored in `producer/config.ini`:
```ini
[General]
freshness = 10000          # Data packet freshness (ms)
size = 8192               # Maximum chunk size (bytes)
naming-convention = typed  # Name component encoding
quiet = false             # Suppress non-error output
verbose = false           # Verbose Interest logging

[Logging]
log-file = producer.log   # Log file path
log-level = info          # Logging level
```

## 🚀 Usage

### 1. Start NFD (NDN Forwarding Daemon)
```bash
# Create socket directory
sudo mkdir -p /run/nfd

# Start NFD with custom config
sudo /usr/local/bin/nfd --config nfd.conf &
```

### 2. Start Producer
```bash
cd producer
./bin/ndnput --prefix /test/data --datasetId 1 &
```

The producer will:
- Register the prefix `/test/data` with NFD
- Wait for Interest packets
- Serve files from `experiments/1/` directory

### 3. Request Data with Consumer
```bash
cd consumer
./bin/ndnget /test/data/1/test.txt --no-version-discovery
```

### 4. Save Received Data to File
```bash
cd consumer
./bin/ndnget /test/data/1/test.txt --no-version-discovery > received_file.txt
```

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

## 🧪 Testing

### Automated Testing
Run the complete test suite:
```bash
./test_transmission.sh
```

This script will:
1. Start NFD daemon
2. Launch producer
3. Create test data
4. Request data with consumer
5. Verify data integrity
6. Clean up processes

### Manual Testing
```bash
# Terminal 1: Start NFD
sudo /usr/local/bin/nfd --config nfd.conf

# Terminal 2: Start Producer
cd producer
./bin/ndnput --prefix /test/data --datasetId 1

# Terminal 3: Request Data
cd consumer
./bin/ndnget /test/data/1/test.txt --no-version-discovery
```

## 🔍 Troubleshooting

### Common Issues

1. **Build Errors**
   - Ensure all dependencies are installed
   - Check compiler version (requires C++17)
   - Verify library paths

2. **NFD Connection Issues**
   - Check if NFD is running: `ps aux | grep nfd`
   - Verify socket path: `ls -la /run/nfd/nfd.sock`
   - Check NFD configuration

3. **Producer Registration Issues**
   - Ensure NFD is running before starting producer
   - Check producer logs for errors
   - Verify prefix registration

4. **Consumer Timeout**
   - Ensure producer is running and has registered prefix
   - Check Interest name format
   - Verify file exists in experiments directory

### Debug Mode
Enable verbose logging:
```bash
# Producer verbose mode
cd producer
# Edit config.ini: set verbose = true
./bin/ndnput --prefix /test/data --datasetId 1

# Consumer verbose mode
cd consumer
./bin/ndnget /test/data/1/test.txt --verbose
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

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 References

- [NDN-CXX Documentation](https://named-data.net/doc/ndn-cxx/)
- [NFD Documentation](https://named-data.net/doc/NFD/)
- [Named Data Networking](https://named-data.net/)
- [NDN Testbed](https://named-data.net/ndn-testbed/)

## Individual Component Building

### Consumer
```bash
cd consumer
make              # Build consumer
make debug        # Build with debug flags
make release      # Build optimized release
make clean        # Clean build files
make install      # Install to /usr/local/bin
make uninstall    # Remove from /usr/local/bin
```

### Producer
```bash
cd producer
make              # Build producer
make debug        # Build with debug flags
make release      # Build optimized release
make clean        # Clean build files
make install      # Install to /usr/local/bin
make uninstall    # Remove from /usr/local/bin
```

## Usage

### Consumer (ndnget)
```bash
# Basic usage
./consumer/bin/ndnget ndn:/example/data

# With pipeline options
./consumer/bin/ndnget -p fixed -s 10 ndn:/example/data
./consumer/bin/ndnget -p aimd --init-cwnd 2 ndn:/example/data
./consumer/bin/ndnget -p cubic --cubic-beta 0.7 ndn:/example/data

# With verbose output
./consumer/bin/ndnget -v ndn:/example/data

# Show help
./consumer/bin/ndnget --help
```

### Producer (ndnput)
```bash
# Basic usage (reads from config.ini)
./producer/bin/ndnput -p ndn:/example/data

# Show help
./producer/bin/ndnput --help
```

## Configuration

### Producer Configuration (config.ini)
Create a `config.ini` file in the producer directory:

```ini
[General]
freshness = 10000
size = 8192
naming-convention = typed
signing-info = 
print-data-version = true
quiet = false
verbose = false

[Logging]
log-file = producer.log
log-level = info
```

## Troubleshooting

### Common Issues

1. **Missing NDN-CXX**: Install ndn-cxx development package
2. **Missing Boost**: Install boost development package
3. **Missing spdlog**: Install spdlog development package
4. **Permission denied during install**: Use `sudo make install`

### Debug Build
For debugging, use:
```bash
make debug
gdb ./consumer/bin/ndnget
gdb ./producer/bin/ndnput
```

### Verbose Output
Enable verbose output to see detailed information:
```bash
./consumer/bin/ndnget -v ndn:/example/data
./producer/bin/ndnput -v -p ndn:/example/data
```

## Project Structure

```
.
├── Makefile                 # Main Makefile
├── consumer/
│   ├── Makefile            # Consumer Makefile
│   ├── *.cpp *.hpp         # Consumer source files
│   ├── core/               # Core utilities
│   ├── obj/                # Object files (created during build)
│   └── bin/                # Binary output (created during build)
├── producer/
│   ├── Makefile            # Producer Makefile
│   ├── *.cpp *.hpp         # Producer source files
│   ├── obj/                # Object files (created during build)
│   └── bin/                # Binary output (created during build)
└── README.md               # This file
```

## Help

For more information about available make targets:
```bash
make help                   # Main Makefile help
cd consumer && make help    # Consumer Makefile help
cd producer && make help    # Producer Makefile help
```

---

## 📝 Quick Reference

### Essential Commands
```bash
# Complete setup and test
./test_transmission.sh

# Manual NFD start
sudo /usr/local/bin/nfd --config nfd.conf &

# Producer start
cd producer && ./bin/ndnput --prefix /test/data --datasetId 1 &

# Consumer request
cd consumer && ./bin/ndnget /test/data/1/test.txt --no-version-discovery

# Process cleanup
sudo pkill -f nfd
pkill -f ndnput
```

### File Paths
- **NFD Config**: `nfd.conf`
- **Producer Config**: `producer/config.ini`
- **Test Data**: `experiments/1/test.txt`
- **Producer Binary**: `producer/bin/ndnput`
- **Consumer Binary**: `consumer/bin/ndnget`
- **NFD Socket**: `/run/nfd/nfd.sock`

### Interest Name Format
```
/test/data/[datasetId]/[filename]
Example: /test/data/1/test.txt
```

---

*For detailed implementation information, see the source code in `consumer/` and `producer/` directories.*
