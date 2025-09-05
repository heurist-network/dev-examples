#!/usr/bin/env python3
"""
Fix for IPv6 connectivity issues on systems with IPv6 enabled but no connectivity.
Forces Python to use IPv4 for all connections.
"""

import socket

# Store the original getaddrinfo function
original_getaddrinfo = socket.getaddrinfo

def force_ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """
    Wrapper for socket.getaddrinfo that forces IPv4 (AF_INET) connections.
    This prevents connection failures on systems with IPv6 DNS but no IPv6 connectivity.
    """
    # If family is not specified (0) or is IPv6 (AF_INET6), force it to IPv4
    if family == 0 or family == socket.AF_INET6:
        family = socket.AF_INET
    
    return original_getaddrinfo(host, port, family, type, proto, flags)

def apply_ipv4_fix():
    """Apply the IPv4-only fix by monkeypatching socket.getaddrinfo"""
    socket.getaddrinfo = force_ipv4_getaddrinfo
    print("✓ IPv4-only mode enabled - this will prevent IPv6 connection failures")

def remove_ipv4_fix():
    """Remove the IPv4-only fix and restore original behavior"""
    socket.getaddrinfo = original_getaddrinfo
    print("✓ IPv4-only mode disabled - restored original behavior")

if __name__ == "__main__":
    # Test the fix
    import requests
    
    print("Testing without fix...")
    try:
        response = requests.get("https://api.telegram.org", timeout=5)
        print(f"✓ Connection successful: {response.status_code}")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
    
    print("\nApplying IPv4-only fix...")
    apply_ipv4_fix()
    
    print("Testing with fix...")
    try:
        response = requests.get("https://api.telegram.org", timeout=5)
        print(f"✓ Connection successful: {response.status_code}")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
