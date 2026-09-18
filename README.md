# Water Guard

A Home Assistant integration that raises a leak alert, gets it to the right
people's phones, and gives the household one clear action afterwards:
**Override: open water**. Norwegian Bokmål: *Vannvakt*.

It is built for houses where something else already shuts off the water — for
example a KNX leak block wired to the leak sensors. Water Guard can also shut
the water off itself, as an option.

## Install

Requires Home Assistant **2026.2 or later**. Add
`https://github.com/mvheimburg/water-guard` as a HACS custom repository with
category **Integration**, install, and restart Home Assistant. Then add **Water
Guard** under **Settings → Devices & services**. One entry guards one water
supply; a cabin can have its own.

## Settings

Under **Settings → Devices & services → Water Guard → Configure**:

| Setting | Purpose |
|---|---|
| Leak sensors | Moisture `binary_sensor`s. Any of them turning on raises the alert. Required. |
| People to alert | `person`s. Each gets a push on every phone that runs the Home Assistant app and tracks them. |
| Water valves | `valve`s, or `switch`es that drive a valve (on means water flows). Override opens them. Optional. |
| Shut off the water on a leak | Off by default. Turn on only when nothing else shuts the water. |

Changes are saved when you submit, and saving never opens or closes a valve.

## What happens on a leak

1. A leak sensor turns on — or is already on when Home Assistant starts.
2. The **Leak** binary sensor turns on and **stays on**: a sensor drying out
   does not clear it. A `leak` event is fired.
3. With *Shut off the water on a leak*, every valve is closed and must report
   closed.
4. A Home Assistant notification appears, and each person gets a high-priority
   push (time-sensitive on iOS). The text says whether the water was shut off,
   or which valve failed to close. It follows Home Assistant's language:
   Norwegian Bokmål or English.
5. Another sensor reporting later updates the alert and replaces the push on the
   phone; the same sensor again does not alert twice.

The Leak sensor's attributes show `since`, the `sensors` that fired, who was
`notified` (`sent`, `failed`, or `no_app` for a person without the app),
`wet_sensors` right now, `unavailable_sensors`, and the `last_result` of moving
the valves. The alert survives restarts.

## Override

**Override: open water** (the button, or the `water_guard.override` action on
the Leak sensor) forces the water back on:

- It opens every configured valve and waits for each to report open. A valve
  that does not open is reported, and the alert stays.
- Otherwise it clears the alert, removes the notification, and clears the push
  from everyone's phones.
- It works while a sensor still reports a leak — that is what an override is
  for — and returns `still_wet` so a card can say so.

If a KNX leak block also latches, override opens the valve through Home
Assistant; whether the KNX logic lets it stay open is up to that logic.

## Events

`water_guard_event` with `entry_id` and `type`: `leak` (since, sensors),
`valves` (target, reason, status, valves, updated), and `override` (sensors,
still_wet).

## With House State

[House State](https://github.com/mvheimburg/house-state) turns the water off for
vacation and on for guests. It has no leak handling of its own. Point House
State's **Configure → Water** at the same valve Water Guard uses. Water Guard
does not stop House State from opening it, so a KNX leak block that keeps the
valve closed remains the thing that holds the water off.

## Dashboard card

[Water Guard card](https://github.com/mvheimburg/lovelace-water-guard) shows
the alert and offers the override.

## Development and release

Python 3.13, `pip install -r requirements_test.txt`, then:

```sh
python -m pytest -q
ruff check custom_components tests
```

Tests run against real Home Assistant 2026.2.3. CI runs tests, Ruff, version
parity, hassfest and HACS validation. The version is kept in `pyproject.toml`
and the manifest; pushing a new version to `main` tags `v<version>` and
publishes a `water_guard.zip` release.

## License

MIT
