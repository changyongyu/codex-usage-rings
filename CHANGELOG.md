# Changelog

## 2026-10-27 — Horizontal liquid allowance cards

- Replace the dual rings with a full-cell liquid hero, a soft weekly progress strip and a large monthly balance.
- Ship matching Mondrian and Memphis Polka Dots palettes without offset shadows; keep saved style and position settings.
- Use a 464 × 284 default card at 1.00 scale, retaining exact reset dates, countdowns and unavailable/low-allowance states.
- Animate only brief changes and drag releases; respect Windows reduced-motion preferences and stop timers on hide, errors and exit.
- Cache static drawing layers and reuse the canvas image to keep animation bounded and idle rendering quiet.

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
