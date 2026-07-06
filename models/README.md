# Models

Large binary model artifacts (walking policies, LLM weights, detectors) are **not
committed** to this repository (see `.gitignore`). They are distributed out of band
and installed to `/var/lib/droidos/models` on a target.

## Walking policies (spec §25)

Training happens on a separate simulation/training computer; the installed image
performs **inference** using the exported policy. A portable format such as ONNX is
preferred. A motion package accompanies each policy with:

- model file + checksum
- observation definition and action definition
- normalization data
- expected control rate
- supported body revision
- safety envelope
- version information

The brain **rejects** a gait policy if it is for a different body, its checksum is
invalid, its observation layout is incompatible, its required sensors are
unavailable, or it has not been approved for physical operation. See the
`gait_policy:` block in `bodies/ig-mk1/manifest.yaml` and the validation in
`droidos.body.loader`.

## LLM models (spec §15)

The default provider is the deterministic offline parser (no model needed). A local
`llama.cpp` provider can serve a GGUF model over its OpenAI-compatible endpoint; a
remote compatible HTTP provider is also supported. The model provider is
configuration, not core architecture, and secrets are never stored in body
manifests or exposed to the LLM context.
