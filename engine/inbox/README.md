# Inbox contract

Teammate bots cannot be called from cron. If they still produce picks, drop a JSON file here
(or in a subfolder except `smagpf/`). The engine merges files on each `collect` run, applies
house rules, and strips bot/tipster names.

```json
{
  "date": "2026-11-06",
  "picks": [
    {
      "date": "2026-11-06",
      "ko": "19:45",
      "league": "Wales - FAW Championship",
      "match": "Penrhyncoch v Caersws",
      "market": "Both teams to score",
      "selection": "Yes",
      "odds": 1.47,
      "eventId": "sr:match:12345678",
      "marketId": "29",
      "specifier": "",
      "outcomeId": "74",
      "table": "8 v 12/16",
      "x12": "1.90/3.40/4.00",
      "case": "table 8 v 12/16; 1X2 1.90/3.40/4.00; home 80% of 10; away 80% of 10; H2H 75% of 4"
    }
  ]
}
```

Required fields: `match`, `selection`, `eventId`, `marketId`, `outcomeId`.
Include `table` and `x12` (or the same text inside `case`) so matchup rules can classify the game.
Double-chance legs are always dropped.
