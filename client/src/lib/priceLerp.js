/**
 * @typedef {Object} PriceLerpInput
 * @property {number} fromPrice
 * @property {number} toPrice
 * @property {number} startTimeMs
 * @property {number} durationMs
 * @property {number} nowMs
 */

/**
 * @param {number} value
 * @param {number} min
 * @param {number} max
 * @returns {number}
 */
function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

/**
 * @param {number} t
 * @returns {number}
 */
function easeOutCubic(t) {
  return 1 - (1 - t) ** 3;
}

/**
 * Deterministic, bounded price interpolation for display-only smoothing.
 *
 * @param {PriceLerpInput} input
 * @returns {number}
 */
export function interpolateDisplayPrice(input) {
  const { fromPrice, toPrice, startTimeMs, durationMs, nowMs } = input;
  const safeDuration = Math.max(1, durationMs);
  const progress = clamp((nowMs - startTimeMs) / safeDuration, 0, 1);
  const eased = easeOutCubic(progress);
  const next = fromPrice + (toPrice - fromPrice) * eased;
  return clamp(next, 0, 1);
}
