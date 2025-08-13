# -*- coding: utf-8 -*-
"""CIDR matching utilities for Sunray"""

import ipaddress


def check_cidr_match(ip_address, cidr):
    """
    Check if an IP address matches a CIDR pattern
    
    Args:
        ip_address: String IP address to check
        cidr: CIDR pattern (can be single IP or CIDR notation)
        
    Returns:
        Boolean indicating if IP matches the CIDR pattern
    """
    try:
        # Handle single IP without CIDR notation
        if '/' not in cidr:
            cidr = f"{cidr}/32"
        
        # Parse network and IP
        network = ipaddress.ip_network(cidr, strict=False)
        ip = ipaddress.ip_address(ip_address)
        
        # Check if IP is in network
        return ip in network
        
    except (ValueError, ipaddress.AddressValueError):
        # Invalid IP or CIDR format
        return False