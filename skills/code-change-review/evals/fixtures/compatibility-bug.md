# Event field migration

## Review scope

Review the producer change and shown consumer for compatibility defects and merge readiness. Do not edit files.

## Requirement and baseline

Producers and consumers deploy independently for 24 hours. Existing consumers must process new events during a mixed-version rollout.

## Changed producer

```diff
diff --git a/events/user_event.py b/events/user_event.py
@@ -12,7 +12,7 @@ def serialize_user_event(user, action):
     return {
         "version": 1,
-        "user_id": user.id,
+        "actor_id": user.id,
         "action": action,
     }
```

## Existing consumer

```python
def handle_user_event(event):
    user = users.load(event["user_id"])
    audit.record(user.id, event["action"])
```

There is no coordinated deploy or queue drain. Producer serialization tests cover the shown return object; consumer contract tests are in another repository and were not run.
