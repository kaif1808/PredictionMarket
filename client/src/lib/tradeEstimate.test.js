import test from "node:test";
import assert from "node:assert/strict";
import { estimateTradeAmount } from "./tradeEstimate.js";

test("estimateTradeAmount uses YES probability for Buy YES", () => {
  const amount = estimateTradeAmount(0.73, "yes", 2);
  assert.ok(Math.abs(amount - 1.46) < 1e-12);
});

test("estimateTradeAmount uses 1 - YES probability for Buy NO", () => {
  const amount = estimateTradeAmount(0.73, "no", 2);
  assert.ok(Math.abs(amount - 0.54) < 1e-12);
});
