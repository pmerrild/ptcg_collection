# Migration Plan: Pokemon TCG API

## Background

The project previously used the [`pokemontcgsdk`](https://github.com/PokemonTCG/pokemon-tcg-sdk-python)
Python SDK to ingest card and set data from `api.pokemontcg.io`. This API is no longer reliably
supported, so the data ingestion pipeline has been migrated to call the
[poke.church REST API](https://poke.church/developer/docs/getting-started/authentication) directly
using Python's `requests` library.

Alternative APIs that were evaluated:

| API | Docs | Notes |
|-----|------|-------|
| **poke.church** ✅ | https://poke.church/developer/docs/getting-started/authentication | Actively maintained, requires Bearer token auth |
| **scrydex.com** | https://scrydex.com/docs | Alternative option if poke.church becomes unavailable |

---

## What has already been done

- [x] Removed `pokemontcgsdk` dependency from `requirements-dev.txt`
- [x] Added `requests` to `requirements-dev.txt`
- [x] Rewrote `src/01 bronze_all_cards_API.ipynb`:
  - Sets ingestion cell now calls `https://api.poke.church/v1/sets` with pagination
  - Cards ingestion cell now calls `https://api.poke.church/v1/cards` with pagination
  - Both cells use the existing Databricks secret `POKEMON_API_KEY` (same secret scope `my_scope`)
- [x] Marked `src/archive/testing.py` as deprecated

---

## What still needs to be done

### 1. Obtain a poke.church API key

- Register at https://poke.church and create an API key.
- Store the key in Databricks Secrets under the existing scope:
  ```bash
  databricks secrets put-secret my_scope POKEMON_API_KEY
  ```
  (Replace the old `pokemontcgsdk` key with the new poke.church Bearer token.)

### 2. Verify the poke.church API response schema

The `fetch_all_pages` helper in the updated notebook assumes the API returns:
```json
{
  "data": [...],
  "totalCount": 12345
}
```
Confirm this against the live API response and adjust `fetch_all_pages` and the Spark schemas
in `src/01 bronze_all_cards_API.ipynb` if the field names differ.

Key fields to verify for **sets**:
- `id`, `name`, `series`, `printedTotal`, `total`, `ptcgoCode`, `releaseDate`, `updatedAt`, `images.symbol`, `images.logo`

Key fields to verify for **cards**:
- `id`, `name`, `supertype`, `subtypes`, `hp`, `types`, `set.id`, `set.ptcgoCode`,
  `number`, `artist`, `rarity`, `images.small`, `images.large`, `tcgplayer.prices.*`

### 3. Run a test ingestion

After updating the secret, run `src/01 bronze_all_cards_API.ipynb` on the dev Databricks workspace:
```bash
databricks bundle run --target dev
```
Verify:
- `workspace.pokemon_tcg_collection.tcg_all_sets` is populated correctly.
- `workspace.pokemon_tcg_collection.tcg_all_cards` is populated correctly.
- Row counts are comparable to the previous API (~15,000+ cards).

### 4. Re-validate the silver layer

Run `src/02 silver_own_collection.ipynb` to confirm the JOIN between your personal
collection and the freshly ingested card/set data still produces correct results.
Pay special attention to the `ptcgoCode` → `set.id` mapping logic and the set-code
override `CASE` statements in the SQL cells of `src/01 bronze_all_cards_API.ipynb`.

### 5. Update the Databricks Job

Confirm that the daily job (`resources/ptcg_collection.job.yml`) triggers the
correct notebooks and that the wheel dependency in `resources/ptcg_collection.job.yml`
still references the right dist artifact after rebuilding:
```bash
pip install build
python -m build
databricks bundle deploy --target prod
```

### 6. (Optional) Evaluate scrydex.com as a fallback

If poke.church proves unreliable, the same `fetch_all_pages` approach can be
redirected to scrydex.com by:
1. Changing `BASE_URL` to the scrydex endpoint.
2. Updating the `Authorization` header format per their docs (https://scrydex.com/docs).
3. Adjusting the response schema mappings if field names differ.

### 7. Clean up archived code

Once the new pipeline has been running in production for a full release cycle,
consider deleting `src/archive/testing.py` as it references the obsolete SDK.

---

## Architecture overview (post-migration)

```
Databricks Job (Daily Trigger)
  └─ Bronze Notebook: src/01 bronze_all_cards_API.ipynb
       ├─ Cell 1: GET https://api.poke.church/v1/sets  → tcg_all_sets  (Delta)
       └─ Cell 2: GET https://api.poke.church/v1/cards → tcg_all_cards (Delta)

  └─ Silver Notebook: src/02 silver_own_collection.ipynb
       └─ Joins tcg_all_cards / tcg_all_sets with personal collection CSV
          → silver_tcg_collection (Delta)
```
