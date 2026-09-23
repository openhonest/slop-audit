import { expect, test } from "vitest";
import { band } from "./band.js";

test("a positive number is positive", () => {
  expect(band(3)).toBe("pos");
});
