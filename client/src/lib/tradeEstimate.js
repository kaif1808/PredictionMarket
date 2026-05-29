/**
 * @typedef {"yes" | "no"} TradeDirection
 */

/**
 * Return the UI quote for the selected direction from the current YES probability.
 *
 * @param {number} rawYesPrice
 * @param {TradeDirection} direction
 * @returns {number}
 */
export function selectedQuotePrice(rawYesPrice, direction) {
  const boundedYesPrice = Math.min(1, Math.max(0, rawYesPrice));
  return direction === "yes" ? boundedYesPrice : 1 - boundedYesPrice;
}

/**
 * Deterministic estimate used by the trade panel preview.
 *
 * @param {number} rawYesPrice
 * @param {TradeDirection} direction
 * @param {number} quantity
 * @returns {number}
 */
export function estimateTradeAmount(rawYesPrice, direction, quantity) {
  return selectedQuotePrice(rawYesPrice, direction) * quantity;
}
