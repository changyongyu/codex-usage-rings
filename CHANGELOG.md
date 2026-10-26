# Changelog

## 2026-10-26 — Switchable desktop styles

- Ship Mondrian and Memphis Polka Dots with matching card and tray style menus.
- Default new installations and legacy settings to Mondrian; preserve the selected style across restarts.
- Replace concentric gauges with two 300-degree open gauges and enlarge the card typography.
- Show exact local reset dates/times and live countdowns for the 5-hour, weekly and monthly allowances.
- Keep theme colors stable; add explicit low-allowance labels below 20% and distinct unavailable-data states.
- Add deterministic previews for both styles and tests for settings migration, menu switching, restart persistence and time boundaries.

## 2026-10-22 — Public fork preparation

- Add a monthly workspace allowance progress bar with decimal-precision balance parsing and reset countdown.
- Update the card appearance, Chinese labels, rounded arcs, and overall text scaling.
- Keep Codex authentication in the installed client's App Server; remove unused direct-auth code.
- Add Windows task installation, removal, a desktop launcher, and supervised restart handling.
- Add synthetic preview generation and locally runnable allowance tests.
- Replace local-machine documentation with portable setup and maintenance instructions.
- Preserve upstream attribution and component-specific licensing notices.

## Earlier local development

The initial desktop card was adapted from the upstream double-ring widget, then extended with App Server usage retrieval and an independent Windows scheduled-task launcher. See THIRD_PARTY_NOTICES.md for sources.
