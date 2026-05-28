import test from "node:test";
import assert from "node:assert/strict";
import { interpolateDisplayPrice } from "./priceLerp.js";

test("interpolateDisplayPrice is monotonic and bounded when moving up", () => {
  const fromPrice = 0.25;
  const toPrice = 0.9;
  const startTimeMs = 1_000;
  const durationMs = 400;
  const samples = [0, 50, 100, 200, 300, 400, 600].map((dt) =>
    interpolateDisplayPrice({ fromPrice, toPrice, startTimeMs, durationMs, nowMs: startTimeMs + dt })
  );

  for (let i = 0; i < samples.length; i += 1) {
    assert.ok(samples[i] >= 0 && samples[i] <= 1);
    if (i > 0) assert.ok(samples[i] >= samples[i - 1]);
  }
  assert.ok(Math.abs(samples[0] - fromPrice) < 1e-12);
  assert.ok(Math.abs(samples[samples.length - 1] - toPrice) < 1e-12);
});

test("interpolateDisplayPrice is monotonic and bounded when moving down", () => {
  const fromPrice = 0.8;
  const toPrice = 0.2;
  const startTimeMs = 10_000;
  const durationMs = 400;
  const samples = [0, 50, 100, 200, 300, 400, 800].map((dt) =>
    interpolateDisplayPrice({ fromPrice, toPrice, startTimeMs, durationMs, nowMs: startTimeMs + dt })
  );

  for (let i = 0; i < samples.length; i += 1) {
    assert.ok(samples[i] >= 0 && samples[i] <= 1);
    if (i > 0) assert.ok(samples[i] <= samples[i - 1]);
  }
  assert.ok(Math.abs(samples[0] - fromPrice) < 1e-12);
  assert.ok(Math.abs(samples[samples.length - 1] - toPrice) < 1e-12);
});
