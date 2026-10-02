/**
 * event_bus.js
 * Central Pub/Sub Event Bus and Logger for Stack n Stock Admin Portal
 */

class EventBus {
    constructor() {
        this.listeners = {};
        this.eventLog = [];
    }

    /**
     * Subscribe to an event
     * @param {string} eventName 
     * @param {function} callback 
     */
    on(eventName, callback) {
        if (!this.listeners[eventName]) {
            this.listeners[eventName] = [];
        }
        this.listeners[eventName].push(callback);
    }

    /**
     * Publish an event
     * @param {string} eventName 
     * @param {object} payload 
     */
    emit(eventName, payload = {}) {
        const timestamp = new Date();
        const eventRecord = {
            id: crypto.randomUUID(),
            timestamp: timestamp.toISOString(),
            event: eventName,
            payload: payload
        };
        
        // Log the event (Requirement #19)
        this.eventLog.push(eventRecord);
        console.log(`[EventBus] ${eventName}`, payload);

        // Notify listeners
        if (this.listeners[eventName]) {
            this.listeners[eventName].forEach(callback => {
                try {
                    callback(payload);
                } catch (error) {
                    console.error(`[EventBus] Error in listener for ${eventName}:`, error);
                }
            });
        }
        eventRecord.payload = JSON.parse(JSON.stringify(payload));
        (this.listeners['*'] || []).forEach(callback => callback(eventName, eventRecord.payload));
    }

    /**
     * Get the full event log
     * @returns {Array} Array of event objects
     */
    getEventLog() {
        return this.eventLog;
    }
}

// Global instance
const studyEventBus = new EventBus();
