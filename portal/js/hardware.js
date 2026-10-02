/**
 * hardware.js - Stack n Stock Pick Study
 * Simulates and manages hardware integration logic.
 */

class HardwareManager {
    constructor() {
        this.states = {
            controller: 'Disconnected', // Connected, Disconnected
            irSensor: 'Ready',          // Ready, Triggered, Fault
            ptl: 'Connected'            // Connected, Fault
        };

        this.studyState = 'IDLE';

        this.debounceTimeMs = 400; // Cooldown for IR sensor
        this.lastTriggerTime = 0;

        // PTL tracking
        this.activePTLSlot = null;
        this.ptlOnTimestamp = null;

        this._initEventListeners();
    }

    _getEventBus() {
        if (typeof studyEventBus !== 'undefined') {
            return studyEventBus;
        }
        return null;
    }

    _initEventListeners() {
        const bus = this._getEventBus();
        if (bus) {
            bus.on('SYSTEM_STATE_CHANGED', (data) => {
                if (typeof data === 'string') {
                    this.studyState = data;
                } else if (data && typeof data === 'object') {
                    this.studyState = data.newState || data.state || 'IDLE';
                }
            });
        }
    }

    // API to set state directly (fallback)
    setStudyState(state) {
        this.studyState = state;
    }

    // 1. Connection states
    setControllerState(state) {
        this.states.controller = state;
        this._notifyHardwareStateChange();
    }

    setIRSensorState(state) {
        this.states.irSensor = state;
        this._notifyHardwareStateChange();
    }

    setPTLState(state) {
        this.states.ptl = state;
        this._notifyHardwareStateChange();
    }

    _notifyHardwareStateChange() {
        const bus = this._getEventBus();
        if (bus) {
            bus.emit('HARDWARE_STATE_CHANGED', this.states);
        }
    }

    // 4. DIY Pick-to-Light (PTL) API
    turnOnPTL(slotNumber) {
        if (this.states.ptl === 'Fault') {
            console.warn("Hardware: Cannot turn on PTL. PTL is in Fault state.");
            return;
        }

        // Turn off all others implicitly by tracking active slot
        this.activePTLSlot = slotNumber;
        this.ptlOnTimestamp = performance.now(); // T0

        const bus = this._getEventBus();
        if (bus) {
            bus.emit('PTL_TURNED_ON', { slot: slotNumber, timestamp: this.ptlOnTimestamp });
        }
        console.log(`Hardware: PTL turned ON for slot ${slotNumber}`);
    }

    turnOffAllPTL() {
        this.activePTLSlot = null;
        this.ptlOnTimestamp = null;
        
        const bus = this._getEventBus();
        if (bus) {
            bus.emit('PTL_TURNED_OFF_ALL', { timestamp: performance.now() });
        }
    }

    // 2. IR Sensor trigger logic
    triggerIRSensor() {
        const now = performance.now();

        if (this.states.irSensor === 'Fault') {
            console.warn("Hardware: IR Sensor trigger ignored. Sensor is in Fault state.");
            return;
        }

        if (this.studyState !== 'PICKING') {
            console.warn(`Hardware: IR Sensor trigger ignored. Study state is ${this.studyState}, not PICKING.`);
            return;
        }

        // Debounce / Cooldown check
        if (now - this.lastTriggerTime < this.debounceTimeMs) {
            console.log("Hardware: IR Sensor trigger ignored due to debounce cooldown.");
            return;
        }

        this.lastTriggerTime = now;
        this.setIRSensorState('Triggered');

        const bus = this._getEventBus();
        if (bus) {
            bus.emit('IR_TRIGGER', { timestamp: now });
        }
        
        this._processConfirmation('IR', now);

        // Reset IR state to Ready after a short delay
        setTimeout(() => {
            if (this.states.irSensor !== 'Fault') {
                this.setIRSensorState('Ready');
            }
        }, this.debounceTimeMs);
    }

    // 3. Manual Backup confirmation
    manualConfirm() {
        if (this.studyState !== 'PICKING') {
            console.warn(`Hardware: Manual confirm ignored. Study state is ${this.studyState}, not PICKING.`);
            return;
        }

        const now = performance.now();

        const bus = this._getEventBus();
        if (bus) {
            bus.emit('MANUAL_CONFIRM', { timestamp: now });
        }

        this._processConfirmation('Manual', now);
    }

    // 5. Calculate Pick Cycle Time & emit PICK_COMPLETE
    _processConfirmation(source, timestampT1) {
        if (window.studyPersistence && !window.studyPersistence.canOperate()) return;
        if (this.activePTLSlot !== null && this.ptlOnTimestamp !== null) {
            const cycleTimeMs = timestampT1 - this.ptlOnTimestamp;
            const completedSlot = this.activePTLSlot;
            
            // Emit PICK_COMPLETE
            const bus = this._getEventBus();
            if (bus) {
                bus.emit('PICK_COMPLETE', {
                    id: crypto.randomUUID(), valid: true, accuracy: 'not assessed',
                    slot: completedSlot,
                    source: source,
                    cycleTimeMs: cycleTimeMs,
                    timestamp: timestampT1
                });
            }

            console.log(`Hardware: Pick completed at slot ${completedSlot} via ${source}. Cycle time: ${cycleTimeMs.toFixed(2)}ms`);
            
            // Turn off PTL after successful pick
            this.turnOffAllPTL();
        } else {
            console.warn(`Hardware: ${source} confirmation received, but no PTL was active.`);
        }
    }
}

// Make globally available
const manager = new HardwareManager();
window.hardwareManager = manager;
window.hardware = manager;
