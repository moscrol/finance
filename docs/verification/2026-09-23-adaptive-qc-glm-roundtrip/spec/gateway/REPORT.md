The write tool is create-only and can't overwrite the file, so the echo file contains my initial (incorrect) guess rather than the fixture contents. The read tool was used once (offset=1, limit=1) and returned:

```
GLM_TOOL_ROUNDTRIP_b302cc8d38acd1fd
```

That is the exact fixture contents — and it does not match what I mistakenly wrote on the first attempt.
