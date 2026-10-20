Type: research
Status: resolved

## Question

How do you tell a lab's error prose from a gateway's error prose in infra probes? Which headers/status codes/fields reliably identify the serving stack vs the front layer? Find documented examples.
## Answer

Short version: a lab's error prose is the text inside the upstream error body, not the wrapper. A gateway's prose is the wrapper. Cross-check headers, status, and code shape before trusting any single string.

Context: paparazzi `infra` probe module; see docs/research-model-identification.md §3 and unclecode/modelprint probes.

How to separate them:

- Unwrap the router envelope first. OpenRouter returns `{error:{code, message, metadata:{provider_name, provider_code, error_type, raw}}}`. The upstream body lives in `error.metadata.raw`; `provider_name` names who produced it. If `raw` is absent, the message is router-validated and is not lab DNA. OpenRouter also masks upstream detail on 500s, so 500s carry no lab prose. Source: openrouter.ai/docs/api_reference/errors-and-debugging.
- Use headers as stack fingerprints, not identity claims. Stable families from modelprint's header dna probe: `cf-ray` plus `server: cloudflare` = Cloudflare edge; `x-amzn-requestid`/`x-amz-request-id` = AWS/Bedrock; `x-envoy-upstream-service-time` = Google frontends; `openai-processing-ms` plus `openai-version` = OpenAI; `server: gunicorn`/`uvicorn` = serving tier. Values such as request ids vary per call, so compare presence and format only. CORS can hide all of them, which is itself a result, not a failure. Source: github.com/unclecode/modelprint probes/net-headerdna.js.
- Watch status codes. Lab validation errors usually come back as 400 with a business code (Z.ai 1214 invalid parameter, 1301 content filter). Gateway and front-layer blocks usually come back as 403/404/429/502/503/504 with generic prose. Source: docs.z.ai/api-reference/api-code; AWS API Gateway docs.
- Read the code shape. Z.ai uses a numeric string business code inside `{"error":{"code":"1214","message":...}}`. OpenAI-style stacks use string codes such as `invalid_request_error`. A bare `{"message":"Missing Authentication Token"}` with `x-amzn-errortype: MissingAuthenticationTokenException` is API Gateway speaking, not the model. Source: docs.z.ai/api-reference/api-code; AWS re:Post 403 guide.
- Treat gateway prose as a separate family. Cloudflare's own pages carry 1xxx codes in HTML with `cf-ray` and `server: cloudflare`; AWS API Gateway returns `Missing Authentication Token`; Nginx returns plain 502/504 HTML. None of that is lab prose. Source: developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors; AWS API Gateway gateway response docs.

Documented examples:

- OpenRouter provider error: `{error:{code:429, message:"Rate limit exceeded", metadata:{error_type:"rate_limit_exceeded", provider_code:"rate_limited", raw:...}}}`. Upstream text is in `raw`; `error_type` is the stable field. Source: openrouter.ai/docs/api_reference/errors-and-debugging.
- OpenRouter masking: on 500, `message` is replaced with a generic string and `provider_code`/`openrouter_metadata` are omitted, but `error_type` remains `server`. So a 500 cannot fingerprint the lab. Source: same.
- Z.ai bad parameter: HTTP 400, body `{"error":{"code":"1214","message":"Parameter ... is invalid..."}}`. This is lab prose and matches Z.ai docs. Source: docs.z.ai/api-reference/api-code.
- Z.ai content filter: code 1301, HTTP 400. This is the code that exposed ox-alpha's Z.ai lineage. Source: docs.z.ai/api-reference/api-code; implicator.ai ox-alpha coverage.
- Cloudflare front layer: HTTP 403 with `server: cloudflare`, `cf-ray: ...-POP`, and an HTML body containing `Error code 1020` plus a `cf-error-type`/`cf-error-origin` pair on Cloudflare-generated pages. Those headers are absent on origin-forwarded errors. Source: developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-error-headers.
- AWS front layer: `x-amzn-errortype` such as `MissingAuthenticationTokenException`, body `{"message":"Missing Authentication Token"}`, plus `x-amzn-requestid`. Source: AWS re:Post API Gateway 403 guide.
- modelprint's own handling: err-temperature unwraps `metadata.raw` before scrubbing; err-maxtokens labels a router-only limit as `router-reported limit`; err-code-family records `router-validated (no upstream signal)` when there is no upstream body. Source: github.com/unclecode/modelprint probes/err-*.js.

Practical rule for probes: send the bad parameter, parse the response, prefer `metadata.raw` when present, label the result `router-reported` or `router-validated` otherwise, and never let a router's generic envelope count as a lab match. Combine with header family and status code before reporting a family match.
