import assert from "node:assert/strict";
import { test } from "node:test";
import { localeForCountry } from "./country-locale.ts";

test("langue initiale selon le pays", () => {
  assert.equal(localeForCountry("CI"), "fr");
  assert.equal(localeForCountry("fr"), "fr");
  assert.equal(localeForCountry("DE"), "de");
  assert.equal(localeForCountry("AT"), "de");
  assert.equal(localeForCountry("NG"), "en");
  assert.equal(localeForCountry("US"), "en");
});

test("pas d'avis sans pays fiable ou pour un pays plurilingue", () => {
  for (const country of [undefined, null, "", "XX", "CH", "BE", "CA", "FRA"]) {
    assert.equal(localeForCountry(country), undefined);
  }
});
