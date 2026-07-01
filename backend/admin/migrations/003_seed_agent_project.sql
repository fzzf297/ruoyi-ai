-- Seed ruoyi-ai Agent admin project: pages + interface metadata for agent tools.
-- Idempotent: safe to re-run on existing databases.

INSERT INTO projects (code, name, description, status)
SELECT 'ruoyi-ai-agent', 'Agent 智能助手', 'ruoyi-ai Agent 会话服务与后台配置元数据', 'enabled'
WHERE NOT EXISTS (SELECT 1 FROM projects WHERE code = 'ruoyi-ai-agent');

INSERT INTO admin_pages (project_id, code, name, route, sort_order, status, config_json)
SELECT p.id, 'chat', '对话', '/agent/chat', 10, 'enabled',
       '{"title":"Agent 对话","layout":"chat","streaming":true,"apiBase":"/api/agent"}'
FROM projects p
WHERE p.code = 'ruoyi-ai-agent'
  AND NOT EXISTS (
      SELECT 1 FROM admin_pages ap WHERE ap.project_id = p.id AND ap.code = 'chat'
  );

INSERT INTO admin_pages (project_id, code, name, route, sort_order, status, config_json)
SELECT p.id, 'sessions', '会话管理', '/agent/sessions', 20, 'enabled',
       '{"title":"会话列表","layout":"table","apiBase":"/api/agent"}'
FROM projects p
WHERE p.code = 'ruoyi-ai-agent'
  AND NOT EXISTS (
      SELECT 1 FROM admin_pages ap WHERE ap.project_id = p.id AND ap.code = 'sessions'
  );

INSERT INTO admin_pages (project_id, code, name, route, sort_order, status, config_json)
SELECT p.id, 'config', '配置浏览', '/agent/config', 30, 'enabled',
       '{"title":"后台配置","layout":"explorer","readApi":"/api/app"}'
FROM projects p
WHERE p.code = 'ruoyi-ai-agent'
  AND NOT EXISTS (
      SELECT 1 FROM admin_pages ap WHERE ap.project_id = p.id AND ap.code = 'config'
  );

INSERT INTO admin_pages (project_id, code, name, route, sort_order, status, config_json)
SELECT p.id, 'settings', '模型设置', '/agent/settings', 40, 'enabled',
       '{"title":"LLM 配置","provider":"deepseek","model":"deepseek-chat","note":"密钥由部署环境变量 AGENT_LLM_API_KEY 注入"}'
FROM projects p
WHERE p.code = 'ruoyi-ai-agent'
  AND NOT EXISTS (
      SELECT 1 FROM admin_pages ap WHERE ap.project_id = p.id AND ap.code = 'settings'
  );

INSERT INTO app_interfaces (project_id, code, name, method, path, auth_mode, status, description)
SELECT p.id, 'create_session', '创建会话', 'POST', '/api/agent/sessions', 'none', 'enabled',
       '创建新的 Agent 对话会话'
FROM projects p
WHERE p.code = 'ruoyi-ai-agent'
  AND NOT EXISTS (
      SELECT 1 FROM app_interfaces ai WHERE ai.project_id = p.id AND ai.code = 'create_session'
  );

INSERT INTO app_interfaces (project_id, code, name, method, path, auth_mode, status, description)
SELECT p.id, 'session_history', '会话历史', 'GET', '/api/agent/sessions/{session_id}/history', 'none', 'enabled',
       '获取指定会话的消息历史'
FROM projects p
WHERE p.code = 'ruoyi-ai-agent'
  AND NOT EXISTS (
      SELECT 1 FROM app_interfaces ai WHERE ai.project_id = p.id AND ai.code = 'session_history'
  );

INSERT INTO app_interfaces (project_id, code, name, method, path, auth_mode, status, description)
SELECT p.id, 'send_message', '发送消息', 'POST', '/api/agent/sessions/{session_id}/messages', 'none', 'enabled',
       '向会话发送用户消息，SSE 流式返回'
FROM projects p
WHERE p.code = 'ruoyi-ai-agent'
  AND NOT EXISTS (
      SELECT 1 FROM app_interfaces ai WHERE ai.project_id = p.id AND ai.code = 'send_message'
  );

INSERT INTO app_interfaces (project_id, code, name, method, path, auth_mode, status, description)
SELECT p.id, 'list_projects', '项目列表', 'GET', '/api/app/projects', 'none', 'enabled',
       'Agent 只读：列出后台已启用项目'
FROM projects p
WHERE p.code = 'ruoyi-ai-agent'
  AND NOT EXISTS (
      SELECT 1 FROM app_interfaces ai WHERE ai.project_id = p.id AND ai.code = 'list_projects'
  );

INSERT INTO app_interfaces (project_id, code, name, method, path, auth_mode, status, description)
SELECT p.id, 'list_pages', '页面列表', 'GET', '/api/app/projects/{project_code}/pages', 'none', 'enabled',
       'Agent 只读：列出项目下页面配置'
FROM projects p
WHERE p.code = 'ruoyi-ai-agent'
  AND NOT EXISTS (
      SELECT 1 FROM app_interfaces ai WHERE ai.project_id = p.id AND ai.code = 'list_pages'
  );

INSERT INTO app_interfaces (project_id, code, name, method, path, auth_mode, status, description)
SELECT p.id, 'list_interfaces', '接口列表', 'GET', '/api/app/projects/{project_code}/interfaces', 'none', 'enabled',
       'Agent 只读：列出项目下接口定义'
FROM projects p
WHERE p.code = 'ruoyi-ai-agent'
  AND NOT EXISTS (
      SELECT 1 FROM app_interfaces ai WHERE ai.project_id = p.id AND ai.code = 'list_interfaces'
  );

INSERT INTO interface_configs (interface_id, yaml_text, parsed_json)
SELECT ai.id,
       'version: 1
kind: api
readOnly: false
request:
  method: POST
  path: /api/agent/sessions
response:
  dataPath: .
',
       '{"version":1,"kind":"api","readOnly":false,"request":{"method":"POST","path":"/api/agent/sessions"},"response":{"dataPath":"."}}'
FROM app_interfaces ai
JOIN projects p ON p.id = ai.project_id
WHERE p.code = 'ruoyi-ai-agent' AND ai.code = 'create_session'
  AND NOT EXISTS (SELECT 1 FROM interface_configs ic WHERE ic.interface_id = ai.id);

INSERT INTO interface_configs (interface_id, yaml_text, parsed_json)
SELECT ai.id,
       'version: 1
kind: api
readOnly: true
request:
  method: GET
  path: /api/agent/sessions/{session_id}/history
response:
  dataPath: messages
',
       '{"version":1,"kind":"api","readOnly":true,"request":{"method":"GET","path":"/api/agent/sessions/{session_id}/history"},"response":{"dataPath":"messages"}}'
FROM app_interfaces ai
JOIN projects p ON p.id = ai.project_id
WHERE p.code = 'ruoyi-ai-agent' AND ai.code = 'session_history'
  AND NOT EXISTS (SELECT 1 FROM interface_configs ic WHERE ic.interface_id = ai.id);

INSERT INTO interface_configs (interface_id, yaml_text, parsed_json)
SELECT ai.id,
       'version: 1
kind: api
readOnly: false
request:
  method: POST
  path: /api/agent/sessions/{session_id}/messages
response:
  dataPath: .
  streaming: true
',
       '{"version":1,"kind":"api","readOnly":false,"request":{"method":"POST","path":"/api/agent/sessions/{session_id}/messages"},"response":{"dataPath":".","streaming":true}}'
FROM app_interfaces ai
JOIN projects p ON p.id = ai.project_id
WHERE p.code = 'ruoyi-ai-agent' AND ai.code = 'send_message'
  AND NOT EXISTS (SELECT 1 FROM interface_configs ic WHERE ic.interface_id = ai.id);

INSERT INTO interface_configs (interface_id, yaml_text, parsed_json)
SELECT ai.id,
       'version: 1
kind: api
readOnly: true
request:
  method: GET
  path: /api/app/projects
response:
  dataPath: items
',
       '{"version":1,"kind":"api","readOnly":true,"request":{"method":"GET","path":"/api/app/projects"},"response":{"dataPath":"items"}}'
FROM app_interfaces ai
JOIN projects p ON p.id = ai.project_id
WHERE p.code = 'ruoyi-ai-agent' AND ai.code = 'list_projects'
  AND NOT EXISTS (SELECT 1 FROM interface_configs ic WHERE ic.interface_id = ai.id);

INSERT INTO interface_configs (interface_id, yaml_text, parsed_json)
SELECT ai.id,
       'version: 1
kind: api
readOnly: true
request:
  method: GET
  path: /api/app/projects/{project_code}/pages
response:
  dataPath: items
',
       '{"version":1,"kind":"api","readOnly":true,"request":{"method":"GET","path":"/api/app/projects/{project_code}/pages"},"response":{"dataPath":"items"}}'
FROM app_interfaces ai
JOIN projects p ON p.id = ai.project_id
WHERE p.code = 'ruoyi-ai-agent' AND ai.code = 'list_pages'
  AND NOT EXISTS (SELECT 1 FROM interface_configs ic WHERE ic.interface_id = ai.id);

INSERT INTO interface_configs (interface_id, yaml_text, parsed_json)
SELECT ai.id,
       'version: 1
kind: api
readOnly: true
request:
  method: GET
  path: /api/app/projects/{project_code}/interfaces
response:
  dataPath: items
',
       '{"version":1,"kind":"api","readOnly":true,"request":{"method":"GET","path":"/api/app/projects/{project_code}/interfaces"},"response":{"dataPath":"items"}}'
FROM app_interfaces ai
JOIN projects p ON p.id = ai.project_id
WHERE p.code = 'ruoyi-ai-agent' AND ai.code = 'list_interfaces'
  AND NOT EXISTS (SELECT 1 FROM interface_configs ic WHERE ic.interface_id = ai.id);
