/**
 * data_export.js
 * Handles data aggregation and CSV export for the Pick Study Portal
 */

class DataExportManager {
    constructor() {
        this.pickRecords = [];
        this.toteCycles = [];
        this.studyMetadata = {};
        
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Assume studyEventBus is globally available
        studyEventBus.on('STUDY_START', (data) => {
            this.studyMetadata = data; // Includes mode, operator, etc.
        });

        studyEventBus.on('PICK_COMPLETE', (data) => {
            this.pickRecords.push(data);
        });

        studyEventBus.on('TOTE_DEPLETED', (data) => {
            this.toteCycles.push(data);
        });
    }

    exportPickDataCSV() {
        if (this.pickRecords.length === 0) {
            console.warn("No pick data to export.");
            return;
        }

        const headers = [
            'Study ID', 'Operator', 'Pick Number', 'Pick Block', 
            'Tote A/B', 'Tote Cycle', 'Configuration', 'Slot', 
            'SKU ID', 'SKU Name', 'Requested Quantity', 
            'Quantity Before Pick', 'Quantity After Pick', 
            'Pick Start Timestamp', 'Confirmation Timestamp', 
            'Pick Cycle Time', 'Confirmation Source', 
            'Break Status', 'Error / Delay Code', 'Pick ID', 'Valid', 'Accuracy', 'Protocol'
        ];

        let csvContent = headers.join(',') + '\n';
        
        const records = window.studyAdvanced ? window.studyAdvanced.effectivePicks() : this.pickRecords;
        records.forEach(record => {
            const row = [
                this.studyMetadata.studyId || '',
                this.studyMetadata.operator || '',
                record.pickNumber || '',
                record.pickBlock || '',
                record.toteId || '',
                record.toteCycle || '',
                record.configuration || '',
                record.slot || '',
                record.skuId || '',
                record.skuName || '',
                record.requestedQuantity || 1,
                record.qtyBefore ?? '',
                record.qtyAfter ?? '',
                record.startTs || '',
                record.confirmTs || '',
                record.cycleTime ?? '',
                record.confirmationSource || '',
                record.breakStatus || '',
                record.exception || record.delayCode || '', record.id || '', record.valid !== false,
                record.accuracy || 'not assessed', JSON.stringify(this.studyMetadata.protocol || {})
            ];
            csvContent += row.map(v => this.csvCell(v)).join(',') + '\n';
        });

        this.downloadCSV(csvContent, `pick_study_data_${new Date().getTime()}.csv`);
    }

    exportToteCycleCSV() {
        if (this.toteCycles.length === 0) {
            console.warn("No tote cycle data to export.");
            return;
        }

        const headers = [
            'Cycle Number', 'Tote A/B', 'Activated Time', 
            'Depleted Time', 'Depletion Duration', 
            'Replacement Started', 'Replacement Completed', 
            'Changeover Duration', 'Initial Inventory', 
            'Total Items Picked'
        ];

        let csvContent = headers.join(',') + '\n';

        this.toteCycles.forEach(cycle => {
            const row = [
                cycle.cycleNumber || '',
                cycle.toteId || '',
                cycle.activatedTime || '',
                cycle.depletedTime || '',
                cycle.depletionDuration || '',
                cycle.replacementStarted || '',
                cycle.replacementCompleted || '',
                cycle.changeoverDuration || '',
                cycle.initialInventory || '',
                cycle.totalItemsPicked || ''
            ];
            csvContent += row.map(v => this.csvCell(v)).join(',') + '\n';
        });

        this.downloadCSV(csvContent, `tote_cycle_data_${new Date().getTime()}.csv`);
    }

    exportEventLogCSV() {
        const events = studyEventBus.getEventLog();
        if (events.length === 0) return;

        const headers = ['Timestamp', 'Event', 'Payload'];
        let csvContent = headers.join(',') + '\n';
        
        events.forEach(e => {
            const payloadStr = JSON.stringify(e.payload).replace(/"/g, '""');
            csvContent += `"${e.timestamp}","${e.event}","${payloadStr}"\n`;
        });

        this.downloadCSV(csvContent, `event_log_${new Date().getTime()}.csv`);
    }

    downloadCSV(csvContent, filename) {
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        const url = URL.createObjectURL(blob);
        link.setAttribute("href", url);
        link.setAttribute("download", filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    csvCell(value) {
        const text = String(value ?? '');
        const safe = /^[=+@\-\t\r]/.test(text) ? "'" + text : text;
        return '"' + safe.replace(/"/g, '""') + '"';
    }
}

const studyDataExport = new DataExportManager();
window.studyDataExport = studyDataExport;
