package com.ruoyi.web.controller.agent;

import java.util.HashMap;
import java.util.Map;
import org.apache.shiro.SecurityUtils;
import org.apache.shiro.authc.AuthenticationException;
import org.apache.shiro.authc.UsernamePasswordToken;
import org.apache.shiro.subject.Subject;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import com.ruoyi.common.annotation.Anonymous;

/**
 * Agent bridge: exchange client credentials for a Shiro session cookie header.
 * Used by ruoyi-ai Agent execute_interface (kind: auth).
 */
@RestController
@RequestMapping("/api/agent-bridge")
public class AgentBridgeController
{
    @Value("${ruoyi.agent-bridge.client-id:}")
    private String clientId;

    @Value("${ruoyi.agent-bridge.client-secret:}")
    private String clientSecret;

    @Value("${ruoyi.agent-bridge.service-username:admin}")
    private String serviceUsername;

    @Value("${ruoyi.agent-bridge.service-password:admin123}")
    private String servicePassword;

    @Value("${ruoyi.agent-bridge.session-ttl-seconds:7200}")
    private int sessionTtlSeconds;

    @Anonymous
    @PostMapping("/auth")
    public ResponseEntity<Map<String, Object>> auth(@RequestBody Map<String, String> body)
    {
        if (clientId == null || clientId.isEmpty() || clientSecret == null || clientSecret.isEmpty())
        {
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(
                errorBody("Agent bridge is not configured on RuoYi"));
        }

        String reqClientId = body != null ? body.getOrDefault("clientId", "") : "";
        String reqClientSecret = body != null ? body.getOrDefault("clientSecret", "") : "";
        if (!clientId.equals(reqClientId) || !clientSecret.equals(reqClientSecret))
        {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(
                errorBody("Invalid bridge credentials"));
        }

        Subject subject = SecurityUtils.getSubject();
        try
        {
            UsernamePasswordToken token = new UsernamePasswordToken(
                serviceUsername, servicePassword, false);
            subject.login(token);
        }
        catch (AuthenticationException ex)
        {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(
                errorBody("Service account login failed"));
        }

        String sessionId = String.valueOf(subject.getSession().getId());
        Map<String, Object> payload = new HashMap<>();
        payload.put("headerName", "Cookie");
        payload.put("headerValue", "JSESSIONID=" + sessionId);
        payload.put("expiresIn", sessionTtlSeconds);
        return ResponseEntity.ok(payload);
    }

    private static Map<String, Object> errorBody(String message)
    {
        Map<String, Object> body = new HashMap<>();
        body.put("msg", message);
        return body;
    }
}
