#!/bin/bash

# Example script to run the HashiCorp Vault Airbyte connector

echo "HashiCorp Vault Airbyte Connector Example"
echo "=========================================="

# Check if config exists
if [ ! -f "secrets/config.json" ]; then
    echo "Error: secrets/config.json not found!"
    echo "Please create it from the example:"
    echo "  cp secrets/config.json.example secrets/config.json"
    echo "  # Then edit with your Vault credentials"
    exit 1
fi

# Install dependencies if needed
if ! python -c "import airbyte_cdk" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# 1. Check connection
echo -e "\n1. Checking connection to Vault..."
python main.py check --config secrets/config.json

# 2. Discover available streams
echo -e "\n2. Discovering available streams..."
python main.py discover --config secrets/config.json > catalog.json
echo "Available streams:"
python -c "import json; print('\n'.join([f'  - {s[\"name\"]}' for s in json.load(open('catalog.json'))['catalog']['streams']]))"

# 3. Create a configured catalog for all streams
echo -e "\n3. Creating configured catalog..."
python -c "
import json
catalog = json.load(open('catalog.json'))
configured = {
    'streams': [
        {
            'stream': stream,
            'sync_mode': 'full_refresh',
            'destination_sync_mode': 'overwrite'
        }
        for stream in catalog['catalog']['streams']
    ]
}
json.dump(configured, open('configured_catalog.json', 'w'), indent=2)
"

echo "Configured catalog created with all streams"

# 4. Read sample data
echo -e "\n4. Reading data (first 5 records per stream)..."
python main.py read --config secrets/config.json --catalog configured_catalog.json | head -n 50

echo -e "\nExample complete! To read all data, run:"
echo "  python main.py read --config secrets/config.json --catalog configured_catalog.json"