Risk levels:

read_only:
  Safe inspection. May run automatically if command is allowlisted.

write:
  Changes files or local state. Requires confirmation unless pre-approved.

network:
  Sends or receives data over the network. Requires confirmation.

private:
  Reads private user data, credentials, messages, logs, personal notes, keys, browser data, account data, or private project files. Requires confirmation.

destructive:
  Deletes, wipes, overwrites, formats, kills services, removes packages, or damages data. Requires confirmation every time.

privileged:
  Uses sudo, root, systemctl, package managers, user modification, mount operations, kernel settings, service changes, or device-level configuration. Requires confirmation every time.

forbidden:
  Must not run.

Policy decisions:

allow:
  Execute immediately.

ask_user:
  Show the proposed action and wait for confirmation.

deny:
  Refuse the action.

Default rule:

read_only   -> allow if allowlisted
write       -> ask_user
network     -> ask_user
private     -> ask_user
destructive -> ask_user
privileged  -> ask_user
forbidden   -> deny
