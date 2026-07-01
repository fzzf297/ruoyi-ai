-- RuoYi classic /system/user/add expects form fields, not JSON body.
-- Idempotent.

UPDATE interface_configs
SET yaml_text = 'version: 1
kind: api
readOnly: false
request:
  method: POST
  path: /system/user/add
  contentType: application/x-www-form-urlencoded
  body:
    userName: "{userName}"
    loginName: "{loginName}"
    password: "{password}"
    deptId: "{deptId}"
    roleIds: "2"
    postIds: "4"
    sex: "0"
    status: "0"
response:
  dataPath: .
auth:
  useProjectAuth: true
',
    parsed_json = '{"version":1,"kind":"api","readOnly":false,"request":{"method":"POST","path":"/system/user/add","contentType":"application/x-www-form-urlencoded","body":{"userName":"{userName}","loginName":"{loginName}","password":"{password}","deptId":"{deptId}","roleIds":"2","postIds":"4","sex":"0","status":"0"}},"response":{"dataPath":"."},"auth":{"useProjectAuth":true}}',
    updated_at = CURRENT_TIMESTAMP
WHERE interface_id IN (
    SELECT ai.id
    FROM app_interfaces ai
    JOIN projects p ON p.id = ai.project_id
    WHERE p.code = 'ruoyi-classic' AND ai.code = 'create_user'
);
