/**
 * Concurrency utilities for implementing Global FIFO Queue
 * This module provides a semaphore for concurrency control and a global queue
 * for processing messages in FIFO order regardless of conversation.
 */

/**
 * A FIFO semaphore with abort signal support for controlling concurrency
 */
export class Semaphore {
  private permits: number;
  private queue: Array<(release: () => void) => void> = [];
  
  constructor(private readonly max: number) {
    if (!Number.isFinite(max) || max <= 0) {
      throw new Error("Semaphore max must be a positive finite number");
    }
    this.permits = max;
  }

  /**
   * Acquire a permit; returns a release function
   * @param signal Optional AbortSignal to cancel waiting
   * @returns Promise that resolves to a release function
   */
  async acquire(signal?: AbortSignal): Promise<() => void> {
    // Fast path: permit immediately available
    if (this.permits > 0) {
      this.permits--;
      let released = false;
      return Promise.resolve(() => {
        if (!released) {
          released = true;
          this.release();
        }
      });
    }

    // Slow path: must wait for a permit
    return new Promise<() => void>((resolve, reject) => {
      const grant = (release: () => void) => resolve(release);
      this.queue.push(grant);
      
      // Handle abort signal if provided
      if (signal) {
        const onAbort = () => {
          // Remove from queue if still pending
          const idx = this.queue.indexOf(grant);
          if (idx >= 0) {
            this.queue.splice(idx, 1);
          }
          reject(new DOMException("Aborted", "AbortError"));
        };
        
        if (signal.aborted) {
          return onAbort();
        }
        signal.addEventListener("abort", onAbort, { once: true });
      }
    });
  }

  /**
   * Release a permit back to the pool
   */
  private release() {
    const next = this.queue.shift();
    if (next) {
      // Handoff to next waiter without changing permit count
      let released = false;
      next(() => {
        if (!released) {
          released = true;
          this.release();
        }
      });
    } else {
      // No waiters, return permit to pool
      this.permits++;
    }
  }

  /**
   * Get the number of available permits
   */
  get available(): number {
    return this.permits;
  }

  /**
   * Get the number of tasks waiting for permits
   */
  get waiting(): number {
    return this.queue.length;
  }
  
  /**
   * Get the maximum number of permits
   */
  get maxPermits(): number {
    return this.max;
  }
}

/**
 * Task type for the global queue
 */
export type Task = () => Promise<void>;

/**
 * Global FIFO queue with worker pool for processing tasks
 * Implements Option 4: processes tasks in strict FIFO order
 */
export class GlobalQueue {
  private q: Task[] = [];
  private running = new Set<Promise<void>>();
  private draining = false;
  private stopped = false;
  private metrics = {
    totalEnqueued: 0,
    totalProcessed: 0,
    totalErrors: 0,
    totalDropped: 0,
    currentQueueLength: 0,
    currentRunning: 0,
  };
  
  constructor(
    private readonly sem: Semaphore,
    private readonly maxQueueSize: number = 2000  // Default max queue size
  ) {}

  /**
   * Enqueue a task for processing
   * @param task The async task to execute
   */
  enqueue(task: Task): void {
    if (this.stopped) {
      console.warn("⚠️ GlobalQueue: Attempted to enqueue task after queue was stopped");
      return;
    }
    
    // Check queue size limit
    if (this.q.length >= this.maxQueueSize) {
      console.error(`❌ GlobalQueue: Queue full (${this.q.length}/${this.maxQueueSize}), dropping task to prevent memory overflow`);
      this.metrics.totalDropped++;
      return;
    }
    
    this.q.push(task);
    this.metrics.totalEnqueued++;
    this.metrics.currentQueueLength = this.q.length;
    
    console.log(`📥 GlobalQueue: Task enqueued (queue length: ${this.q.length}, running: ${this.running.size}/${this.sem.maxPermits})`);
    
    // Try to process tasks if not already draining
    this.drain();
  }

  /**
   * Process tasks from the queue
   */
  private async drain(): Promise<void> {
    if (this.draining || this.stopped) return;
    
    this.draining = true;
    
    try {
      while (this.q.length > 0 && this.sem.available > 0 && !this.stopped) {
        const nextTask = this.q.shift()!;
        this.metrics.currentQueueLength = this.q.length;
        
        const release = await this.sem.acquire();
        
        // Create a wrapper to properly track the promise
        const runTask = async () => {
          const startTime = Date.now();
          try {
            console.log(`🔧 GlobalQueue: Starting task (queue: ${this.q.length}, running: ${this.running.size}/${this.sem.maxPermits})`);
            await nextTask();
            this.metrics.totalProcessed++;
            const duration = Date.now() - startTime;
            console.log(`✅ GlobalQueue: Task completed in ${duration}ms`);
          } catch (error) {
            this.metrics.totalErrors++;
            console.error("❌ GlobalQueue: Task error:", error);
          } finally {
            release();
            // The promise will be removed from running set in the p.finally() block below
            
            // Try to process more tasks
            if (!this.stopped) {
              // Use setImmediate to avoid stack overflow on recursive calls
              setImmediate(() => this.drain());
            }
          }
        };
        
        // Create and track the task promise
        const p = runTask();
        this.running.add(p);
        this.metrics.currentRunning = this.running.size;
        
        // Clean up after completion
        p.finally(() => {
          this.running.delete(p);
          this.metrics.currentRunning = this.running.size;
        });
      }
    } finally {
      this.draining = false;
    }
    
    // Log queue state
    if (this.q.length > 0) {
      console.log(`⏸️ GlobalQueue: Waiting for permits (queue: ${this.q.length}, running: ${this.running.size}/${this.sem.maxPermits})`);
    }
  }

  /**
   * Wait for all running tasks to complete
   * @param timeoutMs Maximum time to wait in milliseconds
   */
  async awaitIdle(timeoutMs = 15000): Promise<void> {
    console.log(`⏳ GlobalQueue: Waiting for ${this.running.size} running tasks to complete...`);
    
    if (this.running.size === 0) {
      console.log("✅ GlobalQueue: No running tasks");
      return;
    }
    
    const all = Promise.allSettled(Array.from(this.running));
    
    await Promise.race([
      all,
      new Promise<void>((resolve) => setTimeout(() => {
        console.warn(`⚠️ GlobalQueue: Timeout after ${timeoutMs}ms, ${this.running.size} tasks still running`);
        resolve();
      }, timeoutMs))
    ]);
    
    console.log(`✅ GlobalQueue: Idle (${this.metrics.totalProcessed} processed, ${this.metrics.totalErrors} errors)`);
  }

  /**
   * Stop the queue from processing new tasks
   */
  stop(): void {
    this.stopped = true;
    console.log("🛑 GlobalQueue: Stopped");
  }

  /**
   * Get queue metrics
   */
  getMetrics() {
    return {
      ...this.metrics,
      currentQueueLength: this.q.length,
      currentRunning: this.running.size,
      availablePermits: this.sem.available,
      maxPermits: this.sem.maxPermits,
    };
  }
  
  /**
   * Log current queue status
   */
  logStatus(): void {
    const metrics = this.getMetrics();
    console.log("📊 GlobalQueue Status:");
    console.log(`  - Queue length: ${metrics.currentQueueLength}/${this.maxQueueSize}`);
    console.log(`  - Running tasks: ${metrics.currentRunning}/${metrics.maxPermits}`);
    console.log(`  - Available permits: ${metrics.availablePermits}`);
    console.log(`  - Total enqueued: ${metrics.totalEnqueued}`);
    console.log(`  - Total processed: ${metrics.totalProcessed}`);
    console.log(`  - Total errors: ${metrics.totalErrors}`);
    console.log(`  - Total dropped: ${metrics.totalDropped || 0}`);
  }
}

/**
 * Create a global queue with the specified concurrency
 * @param maxConcurrency Maximum number of concurrent tasks
 */
export function createGlobalQueue(maxConcurrency: number, maxQueueSize: number = 2000): GlobalQueue {
  const semaphore = new Semaphore(maxConcurrency);
  return new GlobalQueue(semaphore, maxQueueSize);
}
