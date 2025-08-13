/**
 * URL pattern matching utilities
 */

/**
 * Check if URL matches public pattern
 */
export function checkPublicURL(pathname, pattern) {
  try {
    // Convert pattern to regex if it's not already
    const regex = patternToRegex(pattern);
    return regex.test(pathname);
  } catch (error) {
    console.error('Public URL check error:', error);
    return false;
  }
}

/**
 * Check if URL matches token authentication pattern
 */
export function checkTokenURL(pathname, pattern) {
  try {
    // Convert pattern to regex if it's not already
    const regex = patternToRegex(pattern);
    return regex.test(pathname);
  } catch (error) {
    console.error('Token URL check error:', error);
    return false;
  }
}

/**
 * Convert a pattern string to a RegExp
 * Supports:
 * - Regular expressions (starting with ^)
 * - Glob patterns (* and **)
 * - Exact matches
 */
function patternToRegex(pattern) {
  // If it looks like a regex (starts with ^), compile it
  if (pattern.startsWith('^')) {
    return new RegExp(pattern);
  }
  
  // If it contains wildcards, convert to regex
  if (pattern.includes('*')) {
    // Escape special regex characters except *
    let regexStr = pattern
      .replace(/[.+?^${}()|[\]\\]/g, '\\$&')
      .replace(/\*\*/g, '.*')  // ** matches any path depth
      .replace(/\*/g, '[^/]*'); // * matches within path segment
    
    // Make it match the full path
    regexStr = '^' + regexStr + '$';
    return new RegExp(regexStr);
  }
  
  // Exact match
  return new RegExp('^' + escapeRegex(pattern) + '$');
}

/**
 * Escape regex special characters
 */
function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Validate a pattern
 */
export function isValidPattern(pattern) {
  try {
    patternToRegex(pattern);
    return true;
  } catch {
    return false;
  }
}