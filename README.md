# four.meme Agentic Mode — Autonomous Token Launcher

An AI agent that autonomously creates and launches meme tokens on [four.meme](https://four.meme) (BSC).

Inspired by four.meme's upcoming **Agentic Mode** — where memes are created and operated by AI agents.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Agent Loop                         │
│                                                      │
│  MarketAnalyzer ──► AgentBrain ──► LaunchStrategy   │
│       │                 │                            │
│  four.meme API    TokenConcept ──► ImageGenerator    │
│       │                 │                │           │
│  upload_image     create_token      PIL/DALL-E/SD    │
│       │                 │                            │
│       └────────► BSCChain.submit ──► TokenManager2   │
│                         │                            │
│                    AgentMemory (JSON)                │
└─────────────────────────────────────────────────────┘
```

### Modules

| Module | Description |
|--------|-------------|
| `src/four_meme/auth.py` | Nonce + wallet-signed login |
| `src/four_meme/api.py` | Full four.meme REST client |
| `src/four_meme/onchain.py` | BSC Web3 — calls `TokenManager2.createToken()` |
| `src/agent/brain.py` | LLM-powered concept generation + ranking |
| `src/agent/memory.py` | Persistent launch history + learnings |
| `src/agent/strategy.py` | Launch timing + market analysis |
| `src/image/generator.py` | DALL-E / Stable Diffusion / Pillow image gen |

---

## Setup

```bash
git clone https://github.com/alenfour/four-meme-agent
cd four-meme-agent
pip install -r requirements.txt
cp .env.example .env
# Fill in your .env values
```

---

## Usage

### Autonomous agent mode
```bash
python scripts/run_agent.py
```

### Single launch (dry run — no real tx)
```bash
python scripts/run_agent.py --once --dry-run
```

### Force a theme
```bash
python scripts/run_agent.py --once --theme "AI cat taking over BSC"
```

### Manual token launch
```bash
python scripts/create_token.py \
  --name "My Token" \
  --symbol "MTK" \
  --description "The most based token on BSC" \
  --image path/to/logo.png \
  --raise-bnb 0.5
```

---

## four.meme API Flow

```
1. GET  /meme-api/v1/public/user/login/nonce
        → { nonce }

2. Sign "You are sign in Meme {nonce}" with wallet private key

3. POST /meme-api/v1/public/user/login
        → { accessToken }

4. POST /meme-api/v1/private/tool/upload   (multipart image)
        → { url: "https://..." }

5. POST /meme-api/v1/private/token/create
        → { createArg: "0x...", signature: "0x..." }

6. BSC:  TokenManager2.createToken(createArg, signature)
        → token deployed on-chain
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WALLET_PRIVATE_KEY` | BSC wallet private key | required |
| `LLM_API_KEY` | OpenAI (or compatible) API key | required |
| `LLM_API_BASE` | LLM API base URL | `https://api.openai.com/v1` |
| `LLM_MODEL` | Model to use | `gpt-4o` |
| `IMAGE_BACKEND` | `dalle` / `stable_diffusion` / `pillow` | `dalle` |
| `BSC_RPC_URL` | BSC RPC endpoint | public BSC node |
| `LOOP_INTERVAL_SECONDS` | Seconds between agent cycles | `600` |

---

## Warning

- Never commit your `.env` file or private key
- Always test with `--dry-run` first
- Launching tokens costs gas + optional BNB seed raise
- This project is for educational/research purposes

---

Built by [@alenfour](https://github.com/alenfour) | four.meme Solidity & Backend Engineer
