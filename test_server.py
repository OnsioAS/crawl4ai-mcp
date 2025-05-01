#!/usr/bin/env python3
"""
Simple test script to check if the crawl4ai MCP server can be started correctly.
"""

import os
import sys
import subprocess
import time
import signal

def signal_handler(sig, frame):
    print("\n⚠️ Test interrupted by user")
    sys.exit(0)

# Register the signal handler for Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

# Set up colored output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️ {text}{Colors.ENDC}")

# The path to the script we want to test
script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crawl4ai_mcp.py")

print_header("Crawl4AI MCP Server Test")
print_info(f"Testing script: {script_path}")
print("-" * 50)

# Check if the script exists
if not os.path.exists(script_path):
    print_error(f"Script not found at {script_path}")
    sys.exit(1)

# Check if the script is executable
if not os.access(script_path, os.X_OK):
    print_warning(f"Script is not executable. Attempting to fix...")
    try:
        os.chmod(script_path, 0o755)
        print_success("Successfully made the script executable.")
    except Exception as e:
        print_error(f"Error making script executable: {e}")
        sys.exit(1)

# Check if venv exists and activate it
venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv")
if os.path.exists(venv_path):
    print_info("Virtual environment found")
    # We can't directly activate the venv in this script, but we can use the Python from the venv
    python_executable = os.path.join(venv_path, "bin", "python")
    if not os.path.exists(python_executable):
        # Try Windows path
        python_executable = os.path.join(venv_path, "Scripts", "python.exe")
        if not os.path.exists(python_executable):
            print_warning("Virtual environment Python not found, using system Python")
            python_executable = sys.executable
else:
    print_warning("Virtual environment not found, using system Python")
    python_executable = sys.executable

print_info(f"Using Python: {python_executable}")

# Check Python version
try:
    python_version = subprocess.check_output([python_executable, "--version"]).decode().strip()
    print_info(f"Python version: {python_version}")
except Exception as e:
    print_error(f"Error checking Python version: {e}")
    sys.exit(1)

# Check if required packages are installed
print_info("Checking required packages...")
try:
    result = subprocess.run(
        [python_executable, "-c", "import crawl4ai, mcp, pydantic; print('All packages found!')"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print_success("All required packages are installed")
    else:
        print_error(f"Missing required packages: {result.stderr}")
        print_info("Try running: pip install -r requirements.txt")
        sys.exit(1)
except Exception as e:
    print_error(f"Error checking packages: {e}")
    sys.exit(1)

# Try to start the server
print_info("Attempting to start the server...")
try:
    # Start the server in the background
    process = subprocess.Popen(
        [python_executable, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait a bit to see if it starts
    time.sleep(3)
    
    # Check if the process is still running
    if process.poll() is None:
        print_success("Server started and is running")
        print_info("Shutting down test server...")
        process.terminate()
        try:
            process.wait(timeout=5)
            print_success("Server shutdown complete")
        except subprocess.TimeoutExpired:
            print_warning("Server did not terminate gracefully, forcing shutdown...")
            process.kill()
            process.wait()
            print_info("Server forcefully shut down")
    else:
        # Process exited, get the output
        stdout, stderr = process.communicate()
        print_error("Server failed to start")
        if stdout:
            print_info("Server output:")
            print(stdout.decode('utf-8'))
        if stderr:
            print_error("Server error:")
            print(stderr.decode('utf-8'))
        sys.exit(1)
        
except Exception as e:
    print_error(f"Error executing script: {e}")
    sys.exit(1)

print("-" * 50)
print_success("Test completed successfully")
print_info("The crawl4ai MCP server should work with Claude Desktop")
print_info("Please restart the Claude Desktop application if you haven't already")

# Print Claude Desktop configuration path
if sys.platform.startswith('darwin'):
    config_path = os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
elif sys.platform.startswith('linux'):
    config_path = os.path.expanduser("~/.config/Claude/claude_desktop_config.json")
elif sys.platform.startswith('win'):
    config_path = os.path.join(os.environ.get('APPDATA', ''), "Claude", "claude_desktop_config.json")
else:
    config_path = "unknown"

print_info(f"Claude Desktop configuration should be at: {config_path}")
