/**
 * inventory.js
 * Logic for Inventory & Tote Management (Stack n Stock)
 */

class InventoryManager {
    constructor() {
        this.config = {
            numSlots: 6,
            initialQty: 10,
            maxCycles: 13
        };

        this.totes = {
            'A': this.createTote('A'),
            'B': this.createTote('B')
        };

        this.activeToteId = null;
        this.cycleCounter = 0;
        
        // For controlled randomization
        this.slotDeck = [];

        this.setupEventListeners();
    }

    createTote(id) {
        return {
            id: id,
            status: 'READY', // READY, ACTIVE, REPLACING
            slots: [], // Array of { id, physicalQty, digitalQty }
            cycleData: null // Holds current cycle metrics
        };
    }

    initialize(config = {}) {
        this.configuredInventory = config.inventory || null;
        this.config.numSlots = config.numSlots || 6;
        this.config.initialQty = config.initialQty || 10;
        this.config.maxCycles = config.maxCycles || 13;
        this.config.completion = config.completion || 'either';
        
        this.cycleCounter = 1;

        this.initTote('A');
        this.initTote('B');

        this.activeToteId = 'A';
        this.totes['A'].status = 'ACTIVE';
        this.startCycle('A');
        
        this.buildDeck();
    }

    initTote(toteId) {
        const tote = this.totes[toteId];
        if (this.configuredInventory && this.configuredInventory[toteId]) {
            tote.slots = this.configuredInventory[toteId].map(slot => ({ ...slot }));
            tote.status = 'READY';
            return;
        }
        tote.slots = [];
        for (let i = 1; i <= this.config.numSlots; i++) {
            tote.slots.push({
                id: i,
                physicalQty: this.config.initialQty,
                digitalQty: this.config.initialQty
            });
        }
        tote.status = 'READY';
    }

    startCycle(toteId) {
        const tote = this.totes[toteId];
        tote.cycleData = {
            cycleNumber: this.cycleCounter,
            toteId: toteId,
            activatedTime: new Date().toISOString(),
            depletedTime: null,
            depletionDuration: null,
            replacementStarted: null,
            replacementCompleted: null,
            changeoverDuration: null,
            initialInventory: tote.slots.reduce((total, slot) => total + slot.digitalQty, 0),
            totalItemsPicked: 0
        };
    }

    setupEventListeners() {
        // studyEventBus is assumed globally available via event_bus.js
        if (typeof studyEventBus === 'undefined') {
            console.warn("[InventoryManager] studyEventBus is not defined globally.");
        }

        studyEventBus.on('STUDY_START', (data) => {
            let numSlots = 6;
            if (data && data.configuration) {
                if (data.configuration.includes('4')) numSlots = 4;
                if (data.configuration.includes('6')) numSlots = 6;
            } else if (data && data.numSlots) {
                numSlots = data.numSlots;
            }
            const initialQty = (data && data.initialQty) ? data.initialQty : 10;
            
            this.initialize({ numSlots, initialQty, inventory: data && data.inventory,
                maxCycles: data?.protocol?.maxCycles, completion: data?.protocol?.completion });
        });

        studyEventBus.on('PICK_COMPLETE', (data) => {
            this.handlePickComplete(data);
        });

        studyEventBus.on('TOTE_READY', (data) => {
            this.handleToteReady(data.toteId);
        });
    }

    handlePickComplete(data) {
        const toteId = data.toteId || this.activeToteId;
        if (!toteId) return;

        const slotId = data.slot;
        const qty = data.requestedQuantity || 1;

        const tote = this.totes[toteId];
        if (!tote) return;

        const slot = tote.slots.find(s => s.id === slotId);
        if (slot) {
            // Enrich the shared record before the export listener receives it.
            Object.assign(data, {
                toteId, toteCycle: this.cycleCounter, configuration: `${this.config.numSlots}-slot`,
                skuId: slot.skuId || '', skuName: slot.skuName || '', requestedQuantity: qty,
                qtyBefore: slot.digitalQty, qtyAfter: Math.max(0, slot.digitalQty - qty),
                pickNumber: window.studyDataExport ? window.studyDataExport.pickRecords.length + 1 : '',
                pickBlock: window.studyStateMachineInstance.blockNumber || 1,
                cycleTime: data.cycleTimeMs / 1000, confirmationSource: data.source,
                startTs: new Date(Date.now() - data.cycleTimeMs).toISOString(),
                confirmTs: new Date().toISOString(), breakStatus: 'PICKING'
            });
            // Decrement digital inventory
            slot.digitalQty = Math.max(0, slot.digitalQty - qty);
            slot.physicalQty = Math.max(0, slot.physicalQty - qty);
            
            if (tote.cycleData) {
                tote.cycleData.totalItemsPicked += qty;
            }

            if (slot.digitalQty === 0) {
                studyEventBus.emit('SLOT_DEPLETED', { toteId, slot: slotId });
            }

            this.checkToteDepletion(toteId);
        }
    }

    checkToteDepletion(toteId) {
        const tote = this.totes[toteId];
        const isDepleted = tote.slots.every(s => s.digitalQty === 0);

        if (isDepleted && tote.status === 'ACTIVE') {
            const now = new Date();
            tote.status = 'REPLACING';
            
            if (tote.cycleData) {
                tote.cycleData.depletedTime = now.toISOString();
                const activated = new Date(tote.cycleData.activatedTime);
                tote.cycleData.depletionDuration = (now - activated) / 1000; // in seconds
                tote.cycleData.replacementStarted = now.toISOString();
            }

            // Emit Tote Cycle data (captured by data_export.js)
            studyEventBus.emit('TOTE_DEPLETED', tote.cycleData);
            if (this.config.completion !== 'time' && this.cycleCounter >= this.config.maxCycles) {
                window.studyStateMachineInstance.setState('COMPLETED');
                return;
            }
            studyEventBus.emit('TOTE_CHANGE_START', { toteId });

            this.switchToNextTote();
        }
    }

    switchToNextTote() {
        const nextToteId = this.activeToteId === 'A' ? 'B' : 'A';
        const nextTote = this.totes[nextToteId];

        if (nextTote.status === 'READY') {
            this.activeToteId = nextToteId;
            nextTote.status = 'ACTIVE';
            this.cycleCounter++;
            this.startCycle(nextToteId);
            
            // Rebuild deck for new tote
            this.buildDeck();
        } else {
            // Wait for user/system to mark tote as ready
            this.activeToteId = null;
        }
    }

    handleToteReady(toteId) {
        const tote = this.totes[toteId];
        if (!tote || tote.status === 'READY') return;

        const now = new Date();
        
        // Calculate changeover time if it was replacing
        if (tote.cycleData && tote.cycleData.replacementStarted && tote.status === 'REPLACING') {
            tote.cycleData.replacementCompleted = now.toISOString();
            const started = new Date(tote.cycleData.replacementStarted);
            tote.cycleData.changeoverDuration = (now - started) / 1000; // in seconds
        }

        this.initTote(toteId); // Sets status back to READY and resets slot inventory

        // If no active tote (e.g. both were depleted and we were waiting), activate this one
        if (this.activeToteId === null) {
            this.activeToteId = toteId;
            tote.status = 'ACTIVE';
            this.cycleCounter++;
            this.startCycle(toteId);
            this.buildDeck();
        }
    }

    buildDeck() {
        this.slotDeck = [];
        for (let i = 1; i <= this.config.numSlots; i++) {
            this.slotDeck.push(i);
        }
        this.shuffleDeck();
    }

    shuffleDeck() {
        for (let i = this.slotDeck.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [this.slotDeck[i], this.slotDeck[j]] = [this.slotDeck[j], this.slotDeck[i]];
        }
    }

    /**
     * API for controlled randomization.
     * Returns the next slot ID that has inventory available.
     * Distributes picks equally by shuffling available slots.
     */
    getNextRandomSlot() {
        if (!this.activeToteId) return null;
        
        const activeTote = this.totes[this.activeToteId];
        
        // Safety check to ensure we have any inventory at all
        const hasInventory = activeTote.slots.some(s => s.digitalQty > 0);
        if (!hasInventory) return null;

        while (true) {
            if (this.slotDeck.length === 0) {
                this.buildDeck();
            }

            const slotId = this.slotDeck.pop();
            const slot = activeTote.slots.find(s => s.id === slotId);
            
            if (slot && slot.digitalQty > 0) {
                return slotId;
            }
        }
    }
    
    // Allows manual physical adjustment if required for discrepancies
    adjustPhysicalQty(toteId, slotId, qty) {
        const tote = this.totes[toteId];
        if (tote) {
            const slot = tote.slots.find(s => s.id === slotId);
            if (slot) {
                slot.physicalQty = Math.max(0, qty);
            }
        }
    }

    setSlot(toteId, slotId, skuId, physicalQty, digitalQty) {
        const tote = this.totes[toteId];
        if (!tote) return;
        
        let slot = tote.slots.find(s => s.id === slotId);
        if (slot) {
            slot.skuId = skuId;
            slot.physicalQty = physicalQty;
            slot.digitalQty = digitalQty;
        } else {
            tote.slots.push({
                id: slotId,
                skuId: skuId,
                physicalQty: physicalQty,
                digitalQty: digitalQty
            });
        }
    }

    getActiveToteId() {
        return this.activeToteId;
    }

    getTote(toteId) {
        return this.totes[toteId];
    }
    
    getCycleCounter() {
        return this.cycleCounter;
    }
    
    getToteInventory(toteId) {
        if (!this.totes[toteId]) return [];
        return this.totes[toteId].slots;
    }
    
    getCycleProgress() {
        return `${this.cycleCounter} / ${this.config.maxCycles}`;
    }
}

// Global instance
const studyInventory = new InventoryManager();
