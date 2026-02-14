#!/bin/bash

# CSB Helper Swift Build Script

set -e

echo "🚀 Building CSB Helper Swift Edition..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Swift is installed
if ! command -v swift &> /dev/null; then
    print_error "Swift is not installed. Please install Swift or Xcode."
    exit 1
fi

print_status "Swift version: $(swift --version)"

# Build CLI application
print_status "Building CLI application..."
cd CSBHelperSwift

if swift build -c release; then
    print_success "CLI application built successfully!"
    CLI_PATH="$(pwd)/.build/release/CSBHelperCLI"
    print_status "CLI executable: $CLI_PATH"
else
    print_error "Failed to build CLI application"
    exit 1
fi

# Test CLI application
print_status "Testing CLI application..."
if $CLI_PATH --help > /dev/null 2>&1; then
    print_success "CLI application is working!"
else
    print_warning "CLI application may have issues"
fi

cd ..

# Build macOS GUI application (if running on macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    print_status "Building macOS GUI application..."
    cd CSBHelperApp
    
    if swift build -c release; then
        print_success "macOS GUI application built successfully!"
        GUI_PATH="$(pwd)/.build/release/CSBHelperApp"
        print_status "GUI executable: $GUI_PATH"
    else
        print_warning "Failed to build macOS GUI application (this is optional)"
    fi
    
    cd ..
else
    print_warning "Skipping macOS GUI build (not running on macOS)"
fi

# Run tests
print_status "Running tests..."
cd CSBHelperSwift

if swift test; then
    print_success "All tests passed!"
else
    print_warning "Some tests failed"
fi

cd ..

print_success "Build completed!"
echo
echo "📋 Usage:"
echo "  CLI: $CLI_PATH list --type courses"
echo "  CLI: $CLI_PATH search 'Google Cloud'"
echo "  CLI: $CLI_PATH --help"

if [[ "$OSTYPE" == "darwin"* ]] && [[ -f "CSBHelperApp/.build/release/CSBHelperApp" ]]; then
    echo "  GUI: CSBHelperApp/.build/release/CSBHelperApp"
fi

echo
echo "📁 Make sure your JSON data is in the 'data' folder:"
echo "  data/courses/*.json"
echo "  data/paths/*.json" 
echo "  data/labs/*.json"
