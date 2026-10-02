/**
 * Stack n Stock — Balanced Anti-Pattern Permutation Generator (JavaScript)
 * Client-side mirror of scripts/balanced_randomizer.py.
 */

class BalancedRandomizer {
  static generatePickerPool(slots = ['S1', 'S2', 'S3', 'S4'], repsPerSlot = 10, seed = 42) {
    const skus = [
      { sku: 'SKU-A12', desc: 'Small Box Assembly', qty: 1 },
      { sku: 'SKU-B04', desc: 'Component Pouch', qty: 1 },
      { sku: 'SKU-C88', desc: 'Standard Fastener Pack', qty: 2 },
      { sku: 'SKU-D19', desc: 'Heavy Hardware Unit', qty: 1 },
    ];

    let pool = [];
    slots.forEach((slot, sIdx) => {
      for (let r = 0; r < repsPerSlot; r++) {
        const item = skus[(sIdx + r) % skus.length];
        pool.push({
          trialId: 0,
          slotId: slot,
          slotNum: parseInt(slot.replace('S', ''), 10),
          sku: item.sku,
          desc: item.desc,
          qty: item.qty,
          repIndex: r + 1,
        });
      }
    });

    // Pseudo-random seeded PRNG
    let s = seed;
    const rng = () => {
      s = (s * 9301 + 49297) % 233280;
      return s / 233280;
    };

    // Constrained shuffle
    for (let attempt = 0; attempt < 100; attempt++) {
      let shuffled = [...pool];
      for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(rng() * (i + 1));
        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
      }

      let valid = true;
      for (let i = 1; i < shuffled.length; i++) {
        if (shuffled[i].slotId === shuffled[i - 1].slotId) {
          let swapped = false;
          for (let j = i + 1; j < shuffled.length; j++) {
            if (shuffled[j].slotId !== shuffled[i - 1].slotId) {
              [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
              swapped = true;
              break;
            }
          }
          if (!swapped) {
            valid = false;
            break;
          }
        }
      }

      if (valid) {
        shuffled.forEach((t, idx) => (t.trialId = idx + 1));
        return shuffled;
      }
    }

    // Interleaved fallback
    pool.forEach((t, idx) => (t.trialId = idx + 1));
    return pool;
  }

  static generatePackerPool(slots = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6'], repsPerSlot = 6, seed = 42) {
    const compDefs = [
      { band: 'C1', name: 'Simple', desc: '1-2 items | Polybag mailer', items: 2 },
      { band: 'C2', name: 'Standard', desc: '3-5 items | Standard carton', items: 4 },
      { band: 'C3', name: 'Complex', desc: '6+ items | Fragile dunnage pack', items: 7 },
    ];

    let pool = [];
    slots.forEach((slot, sIdx) => {
      for (let r = 0; r < repsPerSlot; r++) {
        const comp = compDefs[r % compDefs.length];
        pool.push({
          trialId: 0,
          slotId: slot,
          slotNum: parseInt(slot.replace('S', ''), 10),
          complexityBand: comp.band,
          complexityName: comp.name,
          packageType: comp.desc,
          itemsCount: comp.items,
          orderId: `ORD-${1000 + pool.length}`,
        });
      }
    });

    let s = seed;
    const rng = () => {
      s = (s * 9301 + 49297) % 233280;
      return s / 233280;
    };

    for (let attempt = 0; attempt < 100; attempt++) {
      let shuffled = [...pool];
      for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(rng() * (i + 1));
        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
      }

      let valid = true;
      for (let i = 1; i < shuffled.length; i++) {
        if (shuffled[i].slotId === shuffled[i - 1].slotId) {
          let swapped = false;
          for (let j = i + 1; j < shuffled.length; j++) {
            if (shuffled[j].slotId !== shuffled[i - 1].slotId) {
              [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
              swapped = true;
              break;
            }
          }
          if (!swapped) {
            valid = false;
            break;
          }
        }
      }

      if (valid) {
        shuffled.forEach((t, idx) => (t.trialId = idx + 1));
        return shuffled;
      }
    }

    pool.forEach((t, idx) => (t.trialId = idx + 1));
    return pool;
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = BalancedRandomizer;
}
if (typeof window !== 'undefined') {
  window.BalancedRandomizer = BalancedRandomizer;
}

