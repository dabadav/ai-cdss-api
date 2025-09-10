## AI-CDSS API package.

### Installation

Install directly from GitHub:

- Lastest release:

```bash
pip install "git+https://github.com/dabadav/ai-cdss-api.git@v0.1.3"
```

- Lastest commit in `main` branch:

```bash
pip install "git+https://github.com/dabadav/ai-cdss-api.git@main"
```

### Usage - CLI Entrypoint

After installation, run the CLI tool with:

```bash
ai-cdss
```
This will start the FastAPI Server

#### Customize how the API server runs:
```bash
ai-cdss --host 0.0.0.0 --port 8080 --reload --env-file .env.prod
```

##### Available Options

Option | Description | Default
-- | -- | --
--host | Host IP address to bind | 127.0.0.1
--port | Port number to bind | 8000
--reload / --no-reload | Enable or disable auto-reload | --reload
--reload-dir / -rd | Additional directories to watch for reload | None
--env-file / -e | Path to the .env file (Optional) | None

Once started, visit:
```
http://<host>:<port>/docs
```
to access the interactive Swagger API docs.

##### Example .env file

```
# CDSS Parameters
WEIGHTS=[1,1,1]
ALPHA=0.5
N=12
DAYS=7
PROTOCOLS_PER_DAY=5

# DB Credentials
DB_HOST=prod-db.internal
DB_USER=app
DB_PASS=supersecret
DB_NAME=ai
```

### Set up Daemon (Linux)

```bash
sudo nano /etc/systemd/system/cdss.service
```

Example `cdss.service`

```
[Unit]
Description=AI CDSS FastAPI Service
After=network.target

[Service]
User=dav
ExecStart=/home/dav/miniforge3/envs/cdss-test/bin/ai-cdss --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start the daemon

```bash
sudo systemctl daemon-reload
sudo systemctl enable cdss
sudo systemctl start cdss
```

To monitor the output (real-time)

```bash
sudo journalctl -u cdss -f
```



