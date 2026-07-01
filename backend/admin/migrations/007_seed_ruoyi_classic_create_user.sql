-- Seed write API example: create user on classic RuoYi.
-- Idempotent: safe to re-run.

INSERT INTO app_interfaces (project_id, code, name, method, path, auth_mode, status, description)
SELECT
    p.id,
    'create_user',
    '新增用户',
    'POST',
    '/system/user/add',
    'bearer',
    'enabled',
    '经典 RuoYi 新增用户（写操作示例）'
FROM projects p
WHERE p.code = 'ruoyi-classic'
  AND NOT EXISTS (
      SELECT 1 FROM app_interfaces ai
      WHERE ai.project_id = p.id AND ai.code = 'create_user'
  );

INSERT INTO interface_configs (interface_id, yaml_text, parsed_json)
SELECT ai.id,
       'version: 1
kind: api
readOnly: false
request:
  method: POST
  path: /system/user/add
  contentType: application/json
  body:
    userName: "{userName}"
    loginName: "{loginName}"
    password: "{password}"
    deptId: "{deptId}"
    roleIds: [2]
    postIds: [4]
    sex: "0"
    status: "0"
response:
  dataPath: .
auth:
  useProjectAuth: true
',
       '{"version":1,"kind":"api","readOnly":false,"request":{"method":"POST","path":"/system/user/add","contentType":"application/json","body":{"userName":"{userName}","loginName":"{loginName}","password":"{password}","deptId":"{deptId}","roleIds":[2],"postIds":[4],"sex":"0","status":"0"}},"response":{"dataPath":"."},"auth":{"useProjectAuth":true}}'
FROM app_interfaces ai
JOIN projects p ON p.id = ai.project_id
WHERE p.code = 'ruoyi-classic' AND ai.code = 'create_user'
  AND NOT EXISTS (SELECT 1 FROM interface_configs ic WHERE ic.interface_id = ai.id);

UPDATE interface_configs
SET yaml_text = 'version: 1
kind: api
readOnly: false
request:
  method: POST
  path: /system/user/add
  contentType: application/json
  body:
    userName: "{userName}"
    loginName: "{loginName}"
    password: "{password}"
    deptId: "{deptId}"
    roleIds: [2]
    postIds: [4]
    sex: "0"
    status: "0"
response:
  dataPath: .
auth:
  useProjectAuth: true
',
    parsed_json = '{"version":1,"kind":"api","readOnly":false,"request":{"method":"POST","path":"/system/user/add","contentType":"application/json","body":{"userName":"{userName}","loginName":"{loginName}","password":"{password}","deptId":"{deptId}","roleIds":[2],"postIds":[4],"sex":"0","status":"0"}},"response":{"dataPath":"."},"auth":{"useProjectAuth":true}}',
    updated_at = CURRENT_TIMESTAMP
WHERE interface_id IN (
    SELECT ai.id
    FROM app_interfaces ai
    JOIN projects p ON p.id = ai.project_id
    WHERE p.code = 'ruoyi-classic' AND ai.code = 'create_user'
);
