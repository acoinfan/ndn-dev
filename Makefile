# Main Makefile for NDN Consumer and Producer
# Author: GitHub Copilot

.PHONY: all clean consumer producer install

# Default target
all: consumer producer

# Build consumer
consumer:
	$(MAKE) -C consumer

# Build producer  
producer:
	$(MAKE) -C producer

# Clean all
clean:
	$(MAKE) -C consumer clean
	$(MAKE) -C producer clean

# Install (optional)
install: all
	$(MAKE) -C consumer install
	$(MAKE) -C producer install

# Help
help:
	@echo "Available targets:"
	@echo "  all        - Build both consumer and producer"
	@echo "  consumer   - Build consumer only"
	@echo "  producer   - Build producer only"
	@echo "  clean      - Clean all build files"
	@echo "  install    - Install binaries (optional)"
	@echo "  help       - Show this help message"
