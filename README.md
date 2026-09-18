# Water Guard

A Home Assistant integration that protects the house from water damage. It
watches leak sensors, shuts off the water when one fires, and keeps it off until
someone restores it. Norwegian Bokmål: *Vannvakt*.

**Status:** not yet released. This repository is being set up.

## Planned scope

- Leak sensors (`binary_sensor`, moisture) and one or more water shut-off
  valves (`valve`, or `switch` for relay-driven valves).
- A leak closes every valve and **latches**: the water stays off until it is
  explicitly restored, and only once no sensor reports a leak.
- Each valve counts as closed or open only when it reports that state.
  Failures are published, not assumed away.
- A restore action, and status entities for dashboards and automations.
- Settings under **Settings → Devices & services → Water Guard → Configure**,
  in English and Norwegian Bokmål.

## Working with House State

[House State](https://github.com/mvheimburg/house-state) turns the water off
for vacation and on for guests. It has no leak protection of its own.

Water Guard will provide its own "main water" valve entity, which refuses to
open while a leak is latched. Select that valve in House State under
**Configure → Water**, instead of the real valve. House State then reports the
refusal as a failed valve, and the water stays off. Neither integration needs
to know about the other.

## Dashboard card

[Water Guard card](https://github.com/mvheimburg/lovelace-water-guard) shows
whether the water is on, flags a detected leak, and offers «Gjenopprett vann»
(Restore water).

## License

MIT
