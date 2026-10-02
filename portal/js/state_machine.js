/**
 * Timing & State Machine Specialist
 * Implements portal/js/state_machine.js
 */

class StudyStateMachine {
    constructor() {
        // Study States
        this.STATES = {
            SETUP: 'SETUP',
            READY: 'READY',
            PICKING: 'PICKING',
            BREAK: 'BREAK',
            COMPLETED: 'COMPLETED',
            PAUSED: 'PAUSED',
            TOTE_CHANGE: 'TOTE_CHANGE',
            HARDWARE_FAULT: 'HARDWARE_FAULT'
        };

        // Duration Modes
        this.MODES = {
            MODE_A: 'MODE_A', // Wall-Clock
            MODE_B: 'MODE_B'  // Active Picking
        };

        // Initial State
        this.currentState = this.STATES.SETUP;
        this.previousState = this.STATES.SETUP;
        this.lastActiveState = this.STATES.PICKING;
        this.mode = this.MODES.MODE_A;

        // Constants
        this.BLOCK_DURATION_MS = 10 * 60 * 1000; // 10 minutes (600,000 ms)
        this.BREAK_DURATION_MS = 102 * 1000;     // 1 min 42 seconds (102,000 ms)
        this.TARGET_TOTAL_TIME_MS = 60 * 60 * 1000; // 60 minutes (3,600,000 ms)

        // Timers and metrics
        this.totalElapsedMs = 0;
        this.activePickingMs = 0;
        this.breakMs = 0;
        this.interruptionMs = 0;
        this.startedAt = null;
        this.blockNumber = 1;
        this.completion = 'either';
        
        this.currentBlockPickingMs = 0;
        this.currentBreakMs = 0;
        
        this.tickInterval = null;
        this.lastTickTime = 0;

        this.init();
    }

    init() {
        // Assume studyEventBus is globally available from event_bus.js
        this.registerEventListeners();
    }

    getEventBus() {
        if (typeof studyEventBus !== 'undefined') {
            return studyEventBus;
        }
        if (typeof window !== 'undefined' && window.studyEventBus) {
            return window.studyEventBus;
        }
        console.warn('studyEventBus is not available globally. Events will not be dispatched.');
        return { on: () => {}, emit: () => {} };
    }

    registerEventListeners() {
        const bus = this.getEventBus();
        
        bus.on('STUDY_SETUP_COMPLETE', (data) => {
            const p = data?.protocol;
            if (p) {
                this.BLOCK_DURATION_MS = p.workSec * 1000;
                this.BREAK_DURATION_MS = p.breakSec * 1000;
                this.TARGET_TOTAL_TIME_MS = p.durationSec * 1000;
                this.completion = p.completion;
            }
            this.transitionTo(this.STATES.READY);
        });
        
        bus.on('STUDY_START', (data) => {
            if (data && data.mode && this.MODES[data.mode]) {
                this.mode = data.mode;
            }
            this.startStudy();
        });
        
        bus.on('STUDY_PAUSE', () => this.pauseStudy());
        bus.on('STUDY_RESUME', () => this.resumeStudy());
        
        bus.on('TOTE_CHANGE_START', () => this.transitionTo(this.STATES.TOTE_CHANGE));
        bus.on('TOTE_READY', () => this.resumeFromInterruption());
        
        bus.on('HARDWARE_FAULT_START', () => this.transitionTo(this.STATES.HARDWARE_FAULT));
        bus.on('HARDWARE_FAULT_RESOLVED', () => this.resumeFromInterruption());
    }

    transitionTo(newState) {
        if (this.currentState === newState || this.currentState === this.STATES.COMPLETED) {
            return;
        }

        this.previousState = this.currentState;
        
        // Track the last active operational state (PICKING or BREAK) to return to after interruptions
        if (this.previousState === this.STATES.PICKING || this.previousState === this.STATES.BREAK) {
            this.lastActiveState = this.previousState;
        }

        this.currentState = newState;

        this.getEventBus().emit('SYSTEM_STATE_CHANGED', {
            oldState: this.previousState,
            newState: this.currentState,
            timestamp: Date.now(),
            metrics: this.getMetrics()
        });

        this.handleStateEntry(newState);
    }

    setState(newState) {
        this.transitionTo(newState);
    }

    handleStateEntry(state) {
        switch (state) {
            case this.STATES.BREAK:
                if (this.previousState === this.STATES.PICKING) {
                    this.currentBreakMs = 0;
                    this.getEventBus().emit('BREAK_START', this.getMetrics());
                }
                break;
            case this.STATES.PICKING:
                if (this.previousState === this.STATES.BREAK) {
                    this.currentBlockPickingMs = 0; // Reset block picking time after a break
                    this.blockNumber++;
                    this.getEventBus().emit('BREAK_END', this.getMetrics());
                }
                break;
            case this.STATES.COMPLETED:
                this.stopTick();
                this.getEventBus().emit('STUDY_END', this.getMetrics());
                break;
        }
    }

    startStudy() {
        if (this.currentState === this.STATES.SETUP || this.currentState === this.STATES.READY) {
            this.totalElapsedMs = 0;
            this.activePickingMs = 0;
            this.breakMs = 0;
            this.currentBlockPickingMs = 0;
            this.currentBreakMs = 0;
            this.startedAt = Date.now();
            this.interruptionMs = 0;
            this.blockNumber = 1;
            
            this.transitionTo(this.STATES.PICKING);
            this.startTick();
        }
    }

    pauseStudy() {
        if (this.currentState !== this.STATES.COMPLETED && this.currentState !== this.STATES.PAUSED) {
            this.transitionTo(this.STATES.PAUSED);
        }
    }

    resumeStudy() {
        if (this.currentState === this.STATES.PAUSED) {
            this.resumeFromInterruption();
        }
    }

    resumeFromInterruption() {
        if (this.currentState === this.STATES.COMPLETED) return;
        
        // Return to the last known active state (PICKING or BREAK)
        const nextState = this.resumeState || this.lastActiveState || this.STATES.PICKING;
        this.resumeState = null;
        this.transitionTo(nextState);
        this.startTick();
    }

    startTick() {
        if (this.tickInterval) return;
        
        this.lastTickTime = Date.now();
        this.tickInterval = setInterval(() => this.tick(), 100); // 10Hz update
    }

    stopTick() {
        if (this.tickInterval) {
            clearInterval(this.tickInterval);
            this.tickInterval = null;
        }
    }

    tick() {
        if (this.currentState === this.STATES.COMPLETED) {
            this.stopTick();
            return;
        }

        const now = Date.now();
        const delta = now - this.lastTickTime;
        this.lastTickTime = now;

        // Accumulate total elapsed time unless the study is fully stopped/paused
        if (this.startedAt && this.currentState !== this.STATES.READY) {
            this.totalElapsedMs = now - this.startedAt;
            if (['PAUSED','HARDWARE_FAULT','TOTE_CHANGE'].includes(this.currentState)) this.interruptionMs += delta;
        }

        // Mode A completion check
        if (this.completion !== 'cycles' && this.mode === this.MODES.MODE_A && this.totalElapsedMs >= this.TARGET_TOTAL_TIME_MS) {
            this.transitionTo(this.STATES.COMPLETED);
            return;
        }

        // Mode B completion check
        if (this.completion !== 'cycles' && this.mode === this.MODES.MODE_B && this.activePickingMs >= this.TARGET_TOTAL_TIME_MS) {
            this.transitionTo(this.STATES.COMPLETED);
            return;
        }

        // State-specific accumulators
        switch (this.currentState) {
            case this.STATES.PICKING:
                this.activePickingMs += delta;
                this.currentBlockPickingMs += delta;

                if (this.completion !== 'cycles' && this.mode === this.MODES.MODE_B && this.activePickingMs >= this.TARGET_TOTAL_TIME_MS) {
                    this.activePickingMs = this.TARGET_TOTAL_TIME_MS;
                    this.transitionTo(this.STATES.COMPLETED);
                    break;
                }

                // Check for block end
                if (this.currentBlockPickingMs >= this.BLOCK_DURATION_MS) {
                    this.transitionTo(this.STATES.BREAK);
                }
                break;

            case this.STATES.BREAK:
                this.breakMs += delta;
                this.currentBreakMs += delta;

                // Check for break end
                if (this.currentBreakMs >= this.BREAK_DURATION_MS) {
                    this.transitionTo(this.STATES.PICKING);
                }
                break;
        }
    }

    getMetrics() {
        return {
            mode: this.mode,
            currentState: this.currentState,
            totalElapsedMs: this.totalElapsedMs,
            activePickingMs: this.activePickingMs,
            breakMs: this.breakMs,
            currentBlockPickingMs: this.currentBlockPickingMs,
            currentBreakMs: this.currentBreakMs
        };
    }
}

// Ensure it's available globally in the browser environment
if (typeof window !== 'undefined') {
    window.StudyStateMachine = StudyStateMachine;
    // Instantiate it immediately so it sets up listeners
    window.studyStateMachineInstance = new StudyStateMachine();
}

// For CommonJS / Node environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StudyStateMachine;
}
