# Makefile for NDN Producer
# Author: GitHub Copilot

# Compiler settings
CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -O2 -g
LDFLAGS = 
LIBS = -lndn-cxx -lboost_program_options -lboost_system -lboost_thread -lpthread -lfmt

# Directories
SRCDIR = .
OBJDIR = obj
BINDIR = bin

# Target executable
TARGET = ndnput
BINPATH = $(BINDIR)/$(TARGET)

# Source files
SOURCES = $(wildcard $(SRCDIR)/*.cpp)
OBJECTS = $(SOURCES:$(SRCDIR)/%.cpp=$(OBJDIR)/%.o)

# Header files for dependency tracking
HEADERS = $(wildcard $(SRCDIR)/*.hpp)

# Default target
all: $(BINPATH)

# Create directories if they don't exist
$(OBJDIR):
	mkdir -p $(OBJDIR)

$(BINDIR):
	mkdir -p $(BINDIR)

# Build the executable
$(BINPATH): $(OBJECTS) | $(BINDIR)
	$(CXX) $(OBJECTS) -o $@ $(LDFLAGS) $(LIBS)
	@echo "Built $(TARGET) successfully"

# Compile source files to object files
$(OBJDIR)/%.o: $(SRCDIR)/%.cpp $(HEADERS) | $(OBJDIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Clean build files
clean:
	rm -rf $(OBJDIR) $(BINDIR)
	@echo "Cleaned build files"

# Install (copy to /usr/local/bin)
install: $(BINPATH)
	sudo cp $(BINPATH) /usr/local/bin/
	@echo "Installed $(TARGET) to /usr/local/bin/"

# Uninstall
uninstall:
	sudo rm -f /usr/local/bin/$(TARGET)
	@echo "Uninstalled $(TARGET)"

# Debug build
debug: CXXFLAGS += -DDEBUG -g3
debug: $(BINPATH)

# Release build
release: CXXFLAGS += -O3 -DNDEBUG
release: clean $(BINPATH)

# Show help
help:
	@echo "Available targets:"
	@echo "  all        - Build $(TARGET) (default)"
	@echo "  clean      - Remove build files"
	@echo "  install    - Install $(TARGET) to /usr/local/bin"
	@echo "  uninstall  - Remove $(TARGET) from /usr/local/bin"
	@echo "  debug      - Build with debug flags"
	@echo "  release    - Build optimized release version"
	@echo "  help       - Show this help message"

# Phony targets
.PHONY: all clean install uninstall debug release help

# Dependency tracking
-include $(OBJECTS:.o=.d)

# Generate dependency files
$(OBJDIR)/%.d: $(SRCDIR)/%.cpp | $(OBJDIR)
	@$(CXX) $(CXXFLAGS) -MM -MT $(@:.d=.o) $< > $@
