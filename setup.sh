#!/bin/bash

# Crawl4AI MCP Server Setup Script

echo "===== Crawl4AI MCP Server Setup ====="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed. Please install Python 3 and try again."
    exit 1
fi

# Get Python version
python_version=$(python3 --version | cut -d ' ' -f 2)
echo "✅ Found Python $python_version"

# Create virtual environment
echo "🔧 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Make server executable
echo "🔧 Making server executable..."
chmod +x crawl4ai_mcp.py

# Get absolute path to the server script
SCRIPT_PATH=$(pwd)/crawl4ai_mcp.py
echo "📄 Server script path: $SCRIPT_PATH"

# Determine OS and config file location
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CONFIG_DIR="$HOME/Library/Application Support/Claude"
    CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    CONFIG_DIR="$HOME/.config/Claude"
    CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
elif [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "cygwin"* || "$OSTYPE" == "win32" ]]; then
    # Windows
    CONFIG_DIR="$APPDATA/Claude"
    CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
else
    echo "❌ Unsupported operating system."
    exit 1
fi

# Ensure the directory exists
mkdir -p "$CONFIG_DIR"

# Create or update the configuration file
echo "🔧 Updating Claude Desktop configuration..."
if [ -f "$CONFIG_FILE" ]; then
    # Config file exists, check if it has mcpServers
    if grep -q "mcpServers" "$CONFIG_FILE"; then
        echo "📝 Updating existing mcpServers configuration..."
        # Make a backup of the original config
        cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"
        # Check if our server is already configured
        if grep -q "crawl4ai" "$CONFIG_FILE"; then
            echo "✅ crawl4ai server is already configured"
        else
            # Add our server to the existing mcpServers
            tmp_file=$(mktemp)
            # This uses sed to add our server after the opening bracket of mcpServers
            sed 's/"mcpServers": {/"mcpServers": {\n    "crawl4ai": {\n      "command": "python3",\n      "args": [\n        "'"$SCRIPT_PATH"'"\n      ]\n    },/g' "$CONFIG_FILE" > "$tmp_file"
            mv "$tmp_file" "$CONFIG_FILE"
            echo "✅ Added crawl4ai server to configuration"
        fi
    else
        # No mcpServers, add it
        echo "📝 Adding mcpServers to configuration..."
        # Make a backup of the original config
        cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"
        tmp_file=$(mktemp)
        # This adds the mcpServers section to the config
        sed 's/{/{\n  "mcpServers": {\n    "crawl4ai": {\n      "command": "python3",\n      "args": [\n        "'"$SCRIPT_PATH"'"\n      ]\n    }\n  },/g' "$CONFIG_FILE" > "$tmp_file"
        mv "$tmp_file" "$CONFIG_FILE"
        echo "✅ Added mcpServers configuration"
    fi
else
    # No config file, create it from scratch
    echo "📝 Creating new configuration file..."
    echo '{
  "mcpServers": {
    "crawl4ai": {
      "command": "python3",
      "args": [
        "'"$SCRIPT_PATH"'"
      ]
    }
  }
}' > "$CONFIG_FILE"
    echo "✅ Created new configuration file"
fi

echo "🚀 Setup complete!"
echo "Please restart Claude Desktop to use the Crawl4AI MCP server."
echo ""
echo "To activate the virtual environment manually:"
echo "source venv/bin/activate"
