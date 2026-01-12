# Sunray Server Roadmap

## Performance / Scaling

### Index sur audit_log pour computed fields

Si le volume d'events `api_key.used` / `webhook.used` devient significatif,
ajouter un index fonctionnel :

```sql
CREATE INDEX idx_audit_log_token_id
ON sunray_audit_log ((details::jsonb->>'token_id'))
WHERE event_type IN ('webhook.used', 'api_key.used');

CREATE INDEX idx_audit_log_api_key_id
ON sunray_audit_log ((details::jsonb->>'api_key_id'))
WHERE event_type = 'api_key.used';
```

### Transaction behavior de log_event_fast()

`log_event_fast()` utilise la meme transaction que l'appel API.
Si l'API echoue apres l'INSERT, l'audit event est rollback.

Options si problematique :
- Savepoint avant l'INSERT
- Transaction autonome (complexe en Odoo)
- Accepter le comportement actuel (audit = succes seulement)
