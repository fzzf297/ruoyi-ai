-- Seed a classic RuoYi bridge example. No credentials or tokens are stored here.
-- Idempotent: safe to re-run on existing databases.

INSERT INTO projects (code, name, description, base_url, status)
SELECT
    'ruoyi-classic',
    '经典 RuoYi 示例',
    '通过 agent bridge 暴露统一取 Token 接口的经典 RuoYi 示例',
    'http://host.docker.internal:8080',
    'enabled'
WHERE NOT EXISTS (SELECT 1 FROM projects WHERE code = 'ruoyi-classic');

INSERT INTO app_interfaces (project_id, code, name, method, path, auth_mode, status, description)
SELECT
    p.id,
    'get_agent_token',
    'Agent Bridge 取 Token',
    'POST',
    '/api/agent-bridge/auth',
    'none',
    'enabled',
    '由三方 bridge 返回 headerName/headerValue'
FROM projects p
WHERE p.code = 'ruoyi-classic'
  AND NOT EXISTS (
      SELECT 1 FROM app_interfaces ai
      WHERE ai.project_id = p.id AND ai.code = 'get_agent_token'
  );

INSERT INTO app_interfaces (project_id, code, name, method, path, auth_mode, status, description)
SELECT
    p.id,
    'user_list',
    '用户列表',
    'POST',
    '/system/user/list',
    'bearer',
    'enabled',
    '经典 RuoYi 只读用户列表查询'
FROM projects p
WHERE p.code = 'ruoyi-classic'
  AND NOT EXISTS (
      SELECT 1 FROM app_interfaces ai
      WHERE ai.project_id = p.id AND ai.code = 'user_list'
  );

INSERT INTO interface_configs (interface_id, yaml_text, parsed_json)
SELECT ai.id,
       'version: 1
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
       '{"version":1,"kind":"auth","request":{"method":"POST","path":"/api/agent-bridge/auth","contentType":"application/json","body":{"clientId":"{secret.clientId}","clientSecret":"{secret.clientSecret}"}},"response":{"headerNamePath":"headerName","headerValuePath":"headerValue","expiresInPath":"expiresIn"}}'
FROM app_interfaces ai
JOIN projects p ON p.id = ai.project_id
WHERE p.code = 'ruoyi-classic' AND ai.code = 'get_agent_token'
  AND NOT EXISTS (SELECT 1 FROM interface_configs ic WHERE ic.interface_id = ai.id);

INSERT INTO interface_configs (interface_id, yaml_text, parsed_json)
SELECT ai.id,
       'version: 1
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
       '{"version":1,"kind":"api","readOnly":true,"request":{"method":"POST","path":"/system/user/list","contentType":"application/x-www-form-urlencoded","body":{"pageNum":"{pageNum}","pageSize":"10"}},"response":{"dataPath":"rows"},"auth":{"useProjectAuth":true}}'
FROM app_interfaces ai
JOIN projects p ON p.id = ai.project_id
WHERE p.code = 'ruoyi-classic' AND ai.code = 'user_list'
  AND NOT EXISTS (SELECT 1 FROM interface_configs ic WHERE ic.interface_id = ai.id);
