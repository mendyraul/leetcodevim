# Editor protocol v1

Start `leetcodevim serve --stdio` as a child process. It listens only on stdin/stdout; no network listener is created. Every request/response is one JSON line. Stdout contains protocol messages only.

```json
{"v":1,"id":1,"method":"browse","params":{"search":"two sum","limit":50,"offset":0}}
{"v":1,"id":1,"event":"started"}
{"v":1,"id":1,"result":{"data":{"total":1,"questions":[]},"cached":false,"stale":false}}
```

Request IDs are strings or integers and must be unique among pending requests. Responses may arrive out of order. Maximum request size is one MiB; four workers process at most sixteen pending requests. Requests use `v:1`, `id`, `method`, and an optional object `params`. Errors use `{code,message}`. Editors discard responses belonging to a previous navigation generation.

Cancellation:

```json
{"v":1,"id":2,"method":"cancel","params":{"id":1}}
```

A cancellation acknowledgement reports whether a pending request was found. Local process groups are killed; an outstanding HTTP request may take up to its network timeout to return. Cancellation does not undo remote writes. Execution emits an `operation` event containing `remote_id` before verdict polling. Reconnect using `poll` with that ID. EOF cancels pending work and shuts down the worker.

## Methods

- `hello`, `doctor`: protocol/capabilities and environment diagnostics.
- `auth.login`, `auth.import {browser}`, `auth.set {session,csrf}`, `auth.status`, `auth.logout`: authentication. Send secrets only over the private pipe. Never log request bodies.
- `browse {search,difficulty,topic,status,offset,limit,refresh}`: catalog page. Difficulty uses Easy/Medium/Hard; solved filters use NOT_STARTED/TRIED/AC.
- `open {slug,language,refresh}`: solution path, description, hints, examples, and metadata. Languages are python/cpp.
- `daily`, `random`: selected question information.
- `local`, `status {slug?}`, `recent`, `mark {slug,status,notes?,tags?}`: local practice state.
- `cases`, `notes`, `compose`: `{slug,language?}` returns an editable file path.
- `test {slug,language,timeout?}`: bounded local cases and per-case results.
- `run {slug,language,input?}`, `submit {slug,language,confirmed:true}`: remote execution. Input defaults to cached/custom cases as newline-separated JSON arguments.
- `poll {remote_id}`: resume an operation recorded for the signed-in account.
- `submission {remote_id}` reads accessible source; `restore {remote_id,slug?,confirmed:true}` backs up the current file and restores it.
- `submissions {slug,offset,refresh}`, `editorial {slug,refresh}`, `profile {username?,refresh}`: account-aware reads.
- `contests`, `study`, `favorites`, `discuss {slug?}`, `settings`: native data where supported, otherwise `{mode:"browser",url,message}`.
- `favorite {slug,favorite:true}`: local favorite only; does not claim to change a website list.

Expected errors include config_required, auth_required, access_restricted, rate_limited, offline, invalid_request, invalid_response, auth_changed, unsupported_checker, operation_pending, confirmation_required, uncertain_write, cancelled, and execution_error. Internal exceptions return a generic message without exception details or credentials.

Consumers must distinguish cached/stale content, local tests from official verdicts, browser fallbacks from native actions, and pending operations from completed submissions. Unknown write outcomes are never retried automatically.
