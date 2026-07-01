-- Patch ruoyi-classic bridge seed for Docker networking and auth body secrets.
-- Idempotent: safe to re-run.

UPDATE projects
SET base_url = 'http://host.docker.internal:8080'
WHERE code = 'ruoyi-classic';

UPDATE interface_configs
SET yaml_text = 'version: 1
kind: auth
request:
  method: POST
  path: /api/agent-bridge/auth
  contentType: application/json
  body:
    clientId: "{secret.clientId}"
    clientSecret: "{secret.clientSecret}"
response:
  headerNamePath: headerName
  headerValuePath: headerValue
  expiresInPath: expiresIn
',
    parsed_json = '{"version":1,"kind":"auth","request":{"method":"POST","path":"/api/agent-bridge/auth","contentType":"application/json","body":{"clientId":"{secret.clientId}","clientSecret":"{secret.clientSecret}"}},"response":{"headerNamePath":"headerName","headerValuePath":"headerValue","expiresInPath":"expiresIn"}}',
    updated_at = CURRENT_TIMESTAMP
WHERE interface_id IN (
    SELECT ai.id
    FROM app_interfaces ai
    JOIN projects p ON p.id = ai.project_id
    WHERE p.code = 'ruoyi-classic' AND ai.code = 'get_agent_token'
);

UPDATE interface_configs
SET yaml_text = 'version: 1
kind: api
readOnly: true
request:
  method: POST
  path: /system/user/list
  contentType: application/x-www-form-urlencoded
  body:
    pageNum: "{pageNum}"
    pageSize: "10"
response:
  dataPath: rows
auth:
  useProjectAuth: true
',
    parsed_json = '{"version":1,"kind":"api","readOnly":true,"request":{"method":"POST","path":"/system/user/list","contentType":"application/x-www-form-urlencoded","body":{"pageNum":"{pageNum}","pageSize":"10"}},"response":{"dataPath":"rows"},"auth":{"useProjectAuth":true}}',
    updated_at = CURRENT_TIMESTAMP
WHERE interface_id IN (
    SELECT ai.id
    FROM app_interfaces ai
    JOIN projects p ON p.id = ai.project_id
    WHERE p.code = 'ruoyi-classic' AND ai.code = 'user_list'
);
