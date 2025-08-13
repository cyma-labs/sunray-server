/**
 * CIDR bypass checking utilities
 */

/**
 * Check if an IP address is within a CIDR range
 */
export function checkCIDRBypass(ip, cidr) {
  try {
    // Handle single IP addresses (no CIDR notation)
    if (!cidr.includes('/')) {
      return ip === cidr;
    }
    
    const [range, bits] = cidr.split('/');
    const mask = parseInt(bits);
    
    // Convert IPs to binary
    const ipBinary = ipToBinary(ip);
    const rangeBinary = ipToBinary(range);
    
    if (!ipBinary || !rangeBinary) {
      return false;
    }
    
    // Compare the first 'mask' bits
    const ipPrefix = ipBinary.substring(0, mask);
    const rangePrefix = rangeBinary.substring(0, mask);
    
    return ipPrefix === rangePrefix;
    
  } catch (error) {
    console.error('CIDR check error:', error);
    return false;
  }
}

/**
 * Convert IP address to binary string
 */
function ipToBinary(ip) {
  // Handle IPv4
  if (ip.includes('.')) {
    const parts = ip.split('.');
    if (parts.length !== 4) return null;
    
    let binary = '';
    for (const part of parts) {
      const num = parseInt(part);
      if (isNaN(num) || num < 0 || num > 255) return null;
      binary += num.toString(2).padStart(8, '0');
    }
    return binary;
  }
  
  // Handle IPv6 (simplified - full implementation would be more complex)
  if (ip.includes(':')) {
    // For MVP, we'll do a simple string comparison for IPv6
    // Full IPv6 CIDR checking would require more complex logic
    return null;
  }
  
  return null;
}

/**
 * Validate CIDR notation
 */
export function isValidCIDR(cidr) {
  try {
    if (!cidr.includes('/')) {
      // Single IP address
      return isValidIP(cidr);
    }
    
    const [ip, bits] = cidr.split('/');
    const mask = parseInt(bits);
    
    if (!isValidIP(ip)) return false;
    
    // Check mask range
    if (ip.includes('.')) {
      // IPv4
      return mask >= 0 && mask <= 32;
    } else if (ip.includes(':')) {
      // IPv6
      return mask >= 0 && mask <= 128;
    }
    
    return false;
  } catch {
    return false;
  }
}

/**
 * Validate IP address
 */
function isValidIP(ip) {
  // IPv4 validation
  if (ip.includes('.')) {
    const parts = ip.split('.');
    if (parts.length !== 4) return false;
    
    for (const part of parts) {
      const num = parseInt(part);
      if (isNaN(num) || num < 0 || num > 255) return false;
    }
    return true;
  }
  
  // Basic IPv6 validation (simplified)
  if (ip.includes(':')) {
    // Very basic check - full validation would be more complex
    return /^[0-9a-fA-F:]+$/.test(ip);
  }
  
  return false;
}