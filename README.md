## AI-CDSS API package.

### Installation

Install directly from GitHub:

```bash
pip install "git+https://github.com/dabadav/ai-cdss-api.git@v0.1.0"
```

### Usage - CLI Entrypoint

After installation, run the CLI tool with:

```bash
ai-cdss
```
This will start the FastAPI Server

#### Customize how the API server runs:
```bash
ai-cdss --host 0.0.0.0 --port 8080 --reload
```

##### Available Options

Option | Description | Default
-- | -- | --
--host | Host IP address to bind | 127.0.0.1
--port | Port number to bind | 8000
--reload / --no-reload | Enable or disable auto-reload | --reload


Once started, visit:
```
http://<host>:<port>/docs
```
to access the interactive Swagger API docs.
