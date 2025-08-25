Let's review the sunray setup workflow to:
 - User receives a mail containing the Sunray Server URL, his admin username and credentials
 - User connects to Sunray Server
 - User creates a protected host (at that time Worker are unknown)
   - User setups Sunray User
 - User creates a Sunray API Key. He must plan the worker name creation (field help=used in cloudflare worker.dev URL. No need to add number since cloudflare auto scale the worker, one Key=1 worker):
   - worker_name
   - worker_type:  At that time he doesn't know the worker name) of type 
 - User git clone the Sunray Worker repo:
   - create a wrangler.toml file with:
     - worker name, 
     - worker id 
     - Sunray URL, 
     - Sunray API Key
   - deploy the worker
   - Create the Zone Worker Route to bind the worker to the protected host URL
 - User then tries to open the Protected Host. Sunray Worker calls the Sunray Server config endpoint. At that point we knows the worker and the API Key link. But we don't know the link with the protected host yet. 
 Let's plan the following modifications that will allow to manage the binding between Workers and Protected Hosts


New model: sunray.worker                                                        
  1. Fields:                                                                     
    - name (Char, required): Worker identifier                                   
    - worker_type (Selection): 'cloudflare', 'kubernetes' (future-proof)
    - worker_url (Char): The worker's URL endpoint                               
    - api_key_id (Many2one to sunray.api.key): The API key this worker uses      
    - last_seen_ts (Datetime): Last API call timestamp computed field other other audit log
    - first_seen_ts (Datetime): First registration timestamp                     
    - is_active (Boolean): Whether the worker is active                          
    - host_ids (Many2one to sunray.host->sunray_worker_id): Hosts this worker serves              
    - version (Char): Worker version (from headers if provided)                  
  2. Auto-registration logic:                                                    
    - When API calls are made with X-Worker-ID header                            
    - Automatically create/update worker record                                  
    - Link to the API key being used                                             
    - Update first_seen_ts on first request
  3. Views:                                                                      
    - List view showing workers with status                                      
    - Form view with details and statistics                                      
    - Search filters by type, active status, last seen                           

Adapt sunray.api.key model:
  1. api_key_type field (Selection):                                                  
    - 'worker': For Cloudflare Workers                                                
    - 'admin': For administrative access                                              
    - 'cli': For CLI tools                                                            
  2. owner_name field (Char):                                                         
    - For worker type: stores worker identifier (e.g., "xy-demo-worker-001")          
    - For admin type: stores admin username                                           
    - For cli type: stores CLI user identifier                                        
  3. worker_id field (Many2one to sunray.worker):                                     
    - Links to the worker that uses this API key (optional, populated when worker is auto-registered see New API below)

Adapt model: sunray.host
 1. Fields
    - Add a new sunray_woker_id many2one(sunray.worker) field:
      - required=False
      - help= Worker that protects this host. A host can be protected by only one host. But a worker can protect several hosts.
    - Remove existing field worker_name (and replace it's usage by sunray_worker_id)
 2. 'Force Cache Refresh' logic
  - Modify 'Force Cache Refresh' button method to use protected host URL {protected_host}/sunray-wrkr/v1/cache/invalidate. We now longer use the worker.dev direct URL for that call. Returns an error if button is clicked and host is not yet bound to it's worker. Because in that case, we don't know yet the Worker API key to use to call the Host.

Adapt model: sunray.user:
 1. 'Force Cache Refresh' logic
  - Modify 'Force Cache Refresh' button method to use protected hosts URL (iterate other all hosts this user is allowed to). We now longer use the worker.dev direct URL for that call. Returns an error if button is clicked and host is not yet bound to it's worker. Because in that case, we don't know yet the Worker API key to use to call the Host.

New API: POST 'sunray-wrkr/v1/config/register'. Requires 'hostname' parameter. the hostname of a protected host.
 1. Logic
  - This API will:
   - Look for the worker:
   - If not found: returns an error and (Audit Log the call)
   - Look for the hostname in protected hosts.
   - If not found: returns an error and (Audit Log the call)
   - Bind worker to host by update host's sunray_worker_id field 
  - Return configuration data but only for the host (slight improvement over data volume generated)
  - Audit log the binding (Ensure an event type exist)
 2. Update API_CONTRACT.md

srctl CLI
 1. Create a new worker sub command with options (list, get, but no create and no delete) get will return cache info actually returned by cli 'cache' sub commande 
 2. update host commands to show sunray_worker_id, add a force-cache-refresh sub command
 3. update user commands to add a force-cache-refresh sub command
 4. remove cli cache command (if you think we replaced it with new host and user sub commands)

API:
 - Ensure each API call is audit logged to track worker activity. Store the workers IP 

Dont plan any migration ! Just setup the new fields and remove those defined as removed without deprecation. We are still in development.

Scan all existing documentation and plan for documentation update to integrate these new changes.
