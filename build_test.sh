#!/bin/bash

# Build test script for NDN Consumer and Producer
# Author: GitHub Copilot

echo "============================================"
echo "NDN Consumer and Producer Build Test"
echo "============================================"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "Checking prerequisites..."

if ! command_exists g++; then
    echo "❌ g++ not found. Please install g++ compiler."
    exit 1
fi

if ! command_exists make; then
    echo "❌ make not found. Please install make."
    exit 1
fi

echo "✅ Build tools found"

# Check for required libraries (basic check)
echo "Checking library dependencies..."

# Test compile with ndn-cxx
echo '#include <ndn-cxx/face.hpp>
int main() { return 0; }' > /tmp/test_ndn.cpp

if g++ -std=c++17 /tmp/test_ndn.cpp -lndn-cxx -o /tmp/test_ndn 2>/dev/null; then
    echo "✅ ndn-cxx library found"
    rm -f /tmp/test_ndn /tmp/test_ndn.cpp
else
    echo "❌ ndn-cxx library not found. Please install ndn-cxx development package."
    rm -f /tmp/test_ndn.cpp
    exit 1
fi

# Test compile with boost
echo '#include <boost/program_options.hpp>
int main() { return 0; }' > /tmp/test_boost.cpp

if g++ -std=c++17 /tmp/test_boost.cpp -lboost_program_options -o /tmp/test_boost 2>/dev/null; then
    echo "✅ Boost libraries found"
    rm -f /tmp/test_boost /tmp/test_boost.cpp
else
    echo "❌ Boost libraries not found. Please install boost development package."
    rm -f /tmp/test_boost.cpp
    exit 1
fi

echo ""
echo "Starting build process..."
echo ""

# Build consumer
echo "Building consumer..."
cd consumer
if make clean && make; then
    echo "✅ Consumer built successfully"
    if [ -f "bin/ndnget" ]; then
        echo "✅ Consumer executable created: bin/ndnget"
    else
        echo "❌ Consumer executable not found"
        exit 1
    fi
else
    echo "❌ Consumer build failed"
    exit 1
fi

cd ..

# Build producer
echo ""
echo "Building producer..."
cd producer
if make clean && make; then
    echo "✅ Producer built successfully"
    if [ -f "bin/ndnput" ]; then
        echo "✅ Producer executable created: bin/ndnput"
    else
        echo "❌ Producer executable not found"
        exit 1
    fi
else
    echo "❌ Producer build failed"
    exit 1
fi

cd ..

echo ""
echo "============================================"
echo "✅ Build test completed successfully!"
echo "============================================"
echo ""
echo "Binaries created:"
echo "  Consumer: consumer/bin/ndnget"
echo "  Producer: producer/bin/ndnput"
echo ""
echo "To test the binaries:"
echo "  ./consumer/bin/ndnget --help"
echo "  ./producer/bin/ndnput --help"
echo ""
echo "To install system-wide:"
echo "  make install"
