# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this integration, please report it privately by creating a [security advisory](https://github.com/cyberjunky/home-assistant-omnik_inverter/security/advisories) on GitHub.

**Please do NOT open a public issue for security vulnerabilities.** This allows us to address the issue before it becomes public knowledge.

## Security Considerations

### Network Communication

This integration communicates with your Omnik Inverter over your local network (TCP):

- Ensure your Omnik Inverter is only accessible from trusted networks
- Keep your Home Assistant instance on a secure network
- Consider using firewall rules to restrict access to your Omnik Inverter

### Credential Storage

Omnik Inverter connection details (IP, port, Serialnumber) are stored in Home Assistant's configuration:

- Keep your Home Assistant configuration secure
- Do not share your Home Assistant backups without sanitizing sensitive data

### Best Practices

1. **Keep Home Assistant updated** - Security patches are released regularly
2. **Install from official sources** - Use HACS or official GitHub releases
3. **Review the code** - As an open-source project, you can audit the code before use
4. **Secure your network** - Restrict access to your Home Assistant instance
5. **Use strong authentication** - Enable Home Assistant's user authentication

## Disclosure Timeline

When a vulnerability is confirmed:

1. We will assess the severity and impact
2. A fix will be prepared for the latest version
3. A new release will be published
4. A security advisory will be published on GitHub (with credit to the reporter if desired)

Thank you for helping keep this project secure!
