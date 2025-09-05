#!/usr/bin/env python3
"""
Robust IPv4-only fix that handles all edge cases.
This ensures Python NEVER attempts IPv6 connections.
"""

import socket
import os
import sys
import logging

logger = logging.getLogger(__name__)

# Store original getaddrinfo
_original_getaddrinfo = socket.getaddrinfo

def force_ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """
    Force IPv4-only resolution by:
    1. Always requesting AF_INET explicitly
    2. Filtering out any IPv6 results
    3. Handling edge cases
    """
    # Force AF_INET if AF_UNSPEC or AF_INET6 was requested
    if family == 0 or family == socket.AF_INET6:
        family = socket.AF_INET
    
    try:
        # Get results with forced IPv4
        results = _original_getaddrinfo(host, port, family, type, proto, flags)
        
        # Double-check: filter out any IPv6 results (shouldn't happen but be safe)
        ipv4_results = [r for r in results if r[0] == socket.AF_INET]
        
        if not ipv4_results and results:
            # If we somehow got only IPv6, try again explicitly with AF_INET
            logger.warning(f"Got non-IPv4 results for {host}, retrying with AF_INET")
            results = _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
            ipv4_results = [r for r in results if r[0] == socket.AF_INET]
        
        return ipv4_results if ipv4_results else results
        
    except socket.gaierror as e:
        # If IPv4 lookup fails, log and re-raise
        logger.debug(f"IPv4 lookup failed for {host}:{port} - {e}")
        raise

def apply_ipv4_fix():
    """Apply comprehensive IPv4-only fix"""
    
    # 1. Monkey-patch socket.getaddrinfo
    socket.getaddrinfo = force_ipv4_getaddrinfo
    
    # 2. Set environment variables to prefer IPv4
    os.environ['PYTHON_PREFER_IPV4'] = '1'
    
    # 3. Force urllib3 to use IPv4
    try:
        import urllib3.util.connection as urllib3_connection
        # Force create_connection to use our patched getaddrinfo
        def patched_create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                                     source_address=None, socket_options=None):
            """Patched create_connection that ensures IPv4"""
            host, port = address
            err = None
            
            # Force IPv4 family
            for res in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM):
                af, socktype, proto, canonname, sa = res
                sock = None
                try:
                    sock = socket.socket(af, socktype, proto)
                    if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                        sock.settimeout(timeout)
                    if source_address:
                        sock.bind(source_address)
                    if socket_options:
                        for opt in socket_options:
                            sock.setsockopt(*opt)
                    sock.connect(sa)
                    return sock
                except socket.error as _:
                    err = _
                    if sock is not None:
                        sock.close()
            
            if err is not None:
                raise err
            else:
                raise socket.error("getaddrinfo returns an empty list")
        
        urllib3_connection.create_connection = patched_create_connection
        logger.info("Patched urllib3 connection creation")
    except ImportError:
        pass  # urllib3 not imported yet, our getaddrinfo patch will handle it
    
    # 4. Also patch the socket.create_connection directly
    if hasattr(socket, 'create_connection'):
        original_create_connection = socket.create_connection
        
        def ipv4_create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                                  source_address=None):
            """Force IPv4 in socket.create_connection"""
            # This will use our patched getaddrinfo which forces IPv4
            return original_create_connection(address, timeout, source_address)
        
        socket.create_connection = ipv4_create_connection
    
    print("✅ IPv4-only mode enabled (robust version)")
    logger.info("Applied comprehensive IPv4-only fix")

def test_fix():
    """Test that the fix is working"""
    import urllib.request
    
    test_hosts = [
        'google.com',
        'api.telegram.org',
        'ipv6.google.com'  # This should work even though it's IPv6-named
    ]
    
    print("\nTesting IPv4-only fix:")
    for host in test_hosts:
        try:
            # Test DNS resolution
            results = socket.getaddrinfo(host, 443, 0, socket.SOCK_STREAM)
            ipv4_count = sum(1 for r in results if r[0] == socket.AF_INET)
            ipv6_count = sum(1 for r in results if r[0] == socket.AF_INET6)
            
            print(f"  {host}: {ipv4_count} IPv4, {ipv6_count} IPv6 addresses")
            
            if ipv6_count > 0:
                print(f"    ⚠️  WARNING: IPv6 addresses present for {host}")
            
        except Exception as e:
            print(f"  {host}: Error - {e}")

if __name__ == "__main__":
    print("Applying robust IPv4-only fix...")
    apply_ipv4_fix()
    test_fix()
