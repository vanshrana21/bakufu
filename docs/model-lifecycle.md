# Model lifecycle: what may serve, and what proves it

A trained artifact is not one file. The bundle, the autoencoder that produced 64
of its 78 features, the raster those features were read from, the preprocessing
constants, the seed and the fold metrics are **one scientific release**. Treating
them as independent files is what lets a result change without its version
changing — most quietly through the encoder, whose latent columns keep the names
`ae_0 … ae_63` while meaning something entirely different.

## The path a model takes

```
POST /train
  → one active job row (partial unique index, not just an endpoint check)
  → outbox row, then Celery delivery on Redis
  → worker claims the job, taking a DB-issued fence strictly greater than every
    fence issued before it
  → training writes into models/registry/staging/<job>-<fence>/
  → acceptance checks
  → publish: staging renamed into models/registry/versions/<version>/ (immutable)
  → maybe activate: models/registry/active.json rewritten atomically
  → /predict/point and /prospectivity/heatmap follow the pointer
```

Training never writes to a path inference reads. The move into the registry is
`os.replace` within one directory, so it is atomic; the pointer is written to a
temp file and renamed, so a reader sees the old file or the new one, never half.

## What may become live

`acceptance_report()` decides, comparing the candidate against **the model
actually serving at promotion time**, not against a number recorded earlier. A
candidate is refused unless all of these hold:

- it records its own training inputs — digests for the training raster **and**
  the encoder, plus preprocessing constants and the seed. `provenance: {}` does
  not count: without the digests, inference has nothing to compare against and
  cannot detect drift.
- it takes the same feature list as the model it would replace.
- mean AUC is **strictly** above 0.5 and mean AUC-PR is **strictly** above the
  base rate. Exactly chance is not good enough — `< 0.5` used to accept a coin
  flip at the boundary.
- mean AUC-PR is not more than 10% below the active model's.

A candidate that fails is **still published** — it is evidence, and the job says
why it was not activated — but the pointer does not move.

Activation is on by default (`TRAINING_ACTIVATE_ON_SUCCESS=true`) and is never
unconditional: it is gated on the checks above. Set it to `false` to require
`python -m scripts.promote_model <version>` for every promotion.

## Encoder identity

The encoder is inside the same trust boundary as the models:

- its SHA-256 is pinned in `SHIPPED_DIGESTS` and verified before every load;
- it is loaded with `weights_only=True`, so a swapped checkpoint cannot execute
  code even if it passed the digest check;
- `GET /` reports `encoder_version` beside `model_version`;
- heatmap cache keys include it, so tiles do not survive an encoder change;
- stored predictions record it, so an audit row identifies both halves of the
  model that produced it.

`_verify_provenance()` refuses to score when the raster or encoder serving a
bundle differs from the one recorded in it. A bundle that records nothing cannot
be checked this way — `provenance_bound: false` in `GET /` says so explicitly,
rather than letting an unverifiable pairing look identical to a verified one.
The shipped `prospectivity_v6` is one of these: it predates provenance binding,
and no truthful provenance can be reconstructed for it after the fact.

## Artifact trust

Nothing is deserialised before it is verified.

- `verify_model_path()` refuses any path outside the registry or the shipped
  models directory, so an environment override cannot point at `/tmp`.
- Shipped artifacts are matched against a digest allowlist; registry artifacts
  against the `sha256` in their own `manifest.json`.
- `load_joblib` and `load_torch_checkpoint` go through that check first. There
  is no code path that loads a pickle or a checkpoint without it.

## Recovery

The database is the ledger; the filesystem is not scanned to work out what
happened.

| Failure point | What happens |
|---|---|
| broker accepts, DB update fails | the outbox row stays pending and is redelivered |
| DB update succeeds, broker rejects | the job stays queued; the dispatcher retries |
| duplicate Celery delivery | the second claim fails (fence + conditional update); no second training run |
| worker crashes before claiming | the lease lapses and the sweeper fails the job, freeing the slot |
| worker crashes after publishing, before recording | the job's published version is found again by `artifact_for_job`, and re-publishing the same version is a no-op |
| worker stalls and loses its lease | `still_owns_job()` fails inside the registry lock, so it cannot publish or activate |
| a late worker finishes after the sweeper gave up | terminal state is **not** overwritten; the outcome is appended to the row as evidence |

At startup, `reconcile()` compares what the database says was published against
what the registry holds and what the pointer names. Disagreements are reported
in `GET /`'s `degraded` rather than repaired silently.

## Honest limits

- **Delivery is at-least-once with deduplication, not exactly-once.** A broker
  that accepts a message and then fails the acknowledgement causes a redelivery.
  The idempotent claim and the fixed task id mean it will not train twice.
- **The registry is single-host.** `active.json` is a local file; two API hosts
  do not share a pointer.
- **There is no retention policy.** Published versions accumulate; nothing prunes
  them.
- **The forecast and shortfall models are shipped artifacts**, versioned by
  filename (`prophet_baseline_v1_0_shipped.pkl`,
  `shortfall_classifier_v1.pkl`) and not managed by this registry. They are
  reported in `data_provenance` as fixed versions, which is what they are.
- **`prospectivity_v6` is not provenance-bound**, as above.

## Evidence

| Claim | Test |
|---|---|
| training's artifact is the one inference loads after activation | `test_artifact_provenance.py::test_an_accepted_candidate_does_become_live`, `test_model_registry.py::test_serving_follows_the_pointer` |
| an encoder change is refused, not scored with | `test_artifact_provenance.py::test_a_changed_encoder_stops_inference_rather_than_scoring_with_it` |
| digest mismatch prevents loading | `test_artifact_trust.py::test_a_swapped_encoder_is_refused` |
| a torch checkpoint cannot execute on load | `test_artifact_trust.py::test_the_encoder_loads_weights_only` |
| rejected metrics cannot activate | `test_artifact_provenance.py::test_a_rejected_candidate_is_kept_as_evidence_but_never_activated` |
| exactly-chance metrics cannot activate | `test_artifact_provenance.py::test_exactly_chance_is_not_good_enough` |
| a stale worker cannot rewrite a terminal job | `test_background_jobs.py::test_a_swept_job_cannot_be_resurrected_by_a_late_worker` |
| a stored prediction can reproduce its own response | `test_prediction_record.py` |
