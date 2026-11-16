# Night mode split: definition in LightConfig, evaluation as a pure function, response in LightController

Night mode responsibility is divided across three places rather than bundled in one:

1. **Definition** (`LightConfig`) — the configured window (`start`, `end`) and action (`pause` or `dim`) are stored as settings, set once on settings save.
2. **Evaluation** — a pure function `is_night_mode_active(now, start, end) -> bool` answers whether the window is currently active. Called per-event, not at settings-save time, because the clock advances independently of settings.
3. **Response** (`LightController`) — the controller calls the evaluator on each event and applies the configured action: suppress the event (pause) or cap brightness (dim).

This mirrors the cooldown timer pattern: a coordinator watches conditions and calls the controller when they are met. Night mode's "pause" behaviour is the same pattern. Night mode's "dim" behaviour is domain logic and therefore stays in the controller rather than being applied by an external coordinator.
