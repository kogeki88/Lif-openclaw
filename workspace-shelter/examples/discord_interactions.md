# Example Discord Interactions

## Create + Load Persona
User:
`!persona create Makima canon --source Chainsaw Man`

Shelter:
`Persona "Makima" created and loaded.`

## Natural Language Switch
User:
`Shelter, portray Makima.`

Shelter:
`Persona switched to "Makima".`

## In-Character Reply with Persona Memory
User:
`What do you want from me?`

Shelter:
`You already know. Precision, not excuses. Start with one clean decision.`

## Persona Info
User:
`!persona info Makima`

Shelter:
```json
{
  "name": "Makima",
  "slug": "makima",
  "source": "Chainsaw Man",
  "persona_type": "canon",
  "summary": "High-control strategist with calm dominance and precise verbal pressure."
}
```

## Persona Memory Reset
User:
`!persona reset Makima`

Shelter:
`Memory reset for "Makima".`

## Persona Off (Back to Base Identity)
User:
`!persona off`

Shelter:
`Persona layer off. Shelter base identity restored.`

## Persona Index Listing
User:
`!persona list`

Shelter:
`- Makima [canon] (source: Chainsaw Man, last_used: 2026-04-10T03:22:00.000000+00:00)`

