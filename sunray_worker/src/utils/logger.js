/**
 * Simple logger utility with environment-based log levels
 */

export class Logger {
  constructor(env) {
    // Set log level from environment or default to 'error'
    // Levels: debug, info, warn, error, none
    this.level = (env.LOG_LEVEL || 'error').toLowerCase();
    this.levels = {
      debug: 0,
      info: 1,
      warn: 2,
      error: 3,
      none: 99
    };
    this.currentLevel = this.levels[this.level] || this.levels.error;
  }

  debug(...args) {
    if (this.currentLevel <= this.levels.debug) {
      console.log('[DEBUG]', ...args);
    }
  }

  info(...args) {
    if (this.currentLevel <= this.levels.info) {
      console.log('[INFO]', ...args);
    }
  }

  warn(...args) {
    if (this.currentLevel <= this.levels.warn) {
      console.warn('[WARN]', ...args);
    }
  }

  error(...args) {
    if (this.currentLevel <= this.levels.error) {
      console.error('[ERROR]', ...args);
    }
  }
}

// Create logger instance
export function createLogger(env) {
  return new Logger(env);
}