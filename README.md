<p align="center">
  <h1 align="center">🤖 MRAgent</h1>
  <p align="center">
    <strong>A lightweight, open-source AI Agent powered by free APIs</strong>
  </p>
  <p align="center">
    <a href="#features">Features</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#getting-started">Getting Started</a> •
    <a href="#api-providers">API Providers</a> •
    <a href="#roadmap">Roadmap</a>
  </p>
</p>

---

## ✨ Overview

**MRAgent** is a lightweight AI agent that connects to **free-tier LLM and multimodal APIs** to deliver a powerful, personal assistant experience — without expensive subscriptions. It combines text generation, image generation, text-to-speech, speech-to-text, screen monitoring, web browsing, code execution, terminal access, and file management into a single, extensible agent.

> **Philosophy:** Leverage the best free APIs available (primarily from NVIDIA and other open-source providers) to build an agent that rivals commercial solutions.

---

## 🚀 Features

| Capability               | Description                                                           | Status         |
| ------------------------ | --------------------------------------------------------------------- | -------------- |
| 💬 **LLM Chat**          | Multi-model text generation (Kimi K2.5, GLM-5, Gemma 3N, Qwen3 Coder) | 🟡 In Progress |
| 🎨 **Image Generation**  | Text-to-image via Stable Diffusion 3.5 Large & FLUX Dev               | 🟡 In Progress |
| 🗣️ **Text-to-Speech**    | Natural voice synthesis via Magpie TTS                                | 🟡 In Progress |
| 👂 **Speech-to-Text**    | Audio transcription via Whisper Large v3                              | 🟡 In Progress |
| 🖥️ **Screen Monitoring** | Capture and analyze screen content in real-time                       | 📋 Planned     |
| 🌐 **Web Browsing**      | Autonomous internet surfing and information gathering                 | 📋 Planned     |
| 💻 **Code Execution**    | Write, run, and debug code in multiple languages                      | 📋 Planned     |
| 🔧 **Terminal Access**   | Execute shell commands and system operations                          | 📋 Planned     |
| 📁 **File Management**   | Navigate, create, move, and organize files                            | 📋 Planned     |
| 🔍 **Web Search**        | Search the internet via Brave Search API                              | 🟡 In Progress |

---

## 🏗️ Architecture

```
MRAgent/
├── README.md
├── .env.example          # Template for API keys
├── .gitignore
├── requirements.txt      # Python dependencies
├── main.py               # Entry point
├── config/
│   └── settings.py       # Configuration & API key management
├── agents/
│   ├── core.py           # Core agent orchestration loop
│   ├── planner.py        # Task planning & decomposition
│   └── executor.py       # Action execution engine
├── providers/
│   ├── base.py           # Base API provider interface
│   ├── nvidia_llm.py     # NVIDIA LLM provider (Kimi, GLM, Gemma, Qwen)
│   ├── nvidia_image.py   # NVIDIA image generation (SD 3.5, FLUX)
│   ├── nvidia_tts.py     # NVIDIA text-to-speech (Magpie)
│   ├── nvidia_stt.py     # NVIDIA speech-to-text (Whisper)
│   └── brave_search.py   # Brave Search API
├── tools/
│   ├── browser.py        # Web browsing automation
│   ├── terminal.py       # Shell command execution
│   ├── file_manager.py   # File system operations
│   ├── screen.py         # Screen capture & analysis
│   └── code_runner.py    # Code execution sandbox
├── ui/
│   ├── cli.py            # Command-line interface
│   └── telegram_bot.py   # Telegram bot interface
└── utils/
    ├── logger.py         # Logging utilities
    └── helpers.py        # Shared helper functions
```

---

## 🛠️ Getting Started

### Prerequisites

- **Python 3.10+**
- Free API keys (see [API Providers](#api-providers))

### Installation

```bash
# Clone the repository
git clone git@github.com:bonzainsights/MRAgent.git
cd MRAgent

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up your environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Quick Start

```bash
# Run the agent (CLI mode)
python main.py

# Run as Telegram bot
python main.py --mode telegram
```

---

## 🔑 API Providers

MRAgent is built around **free-tier APIs** to keep costs at zero. Here are the current providers:

### NVIDIA NIM (Primary)

| Model                      | Purpose               | API        |
| -------------------------- | --------------------- | ---------- |
| Kimi K2.5                  | General-purpose LLM   | NVIDIA NIM |
| GLM-5                      | Reasoning & code      | NVIDIA NIM |
| Gemma 3N                   | Lightweight inference | NVIDIA NIM |
| Qwen3 Coder                | Code generation       | NVIDIA NIM |
| Stable Diffusion 3.5 Large | Image generation      | NVIDIA NIM |
| FLUX Dev                   | Image generation      | NVIDIA NIM |
| Magpie TTS                 | Text-to-speech        | NVIDIA NIM |
| Whisper Large v3           | Speech-to-text        | NVIDIA NIM |

### Other Providers

| Provider         | Purpose             |
| ---------------- | ------------------- |
| Brave Search     | Web search API      |
| Telegram Bot API | Messaging interface |

> 💡 **Adding new providers?** Implement the base interface in `providers/base.py` and register your provider in the config.

---

## 🗺️ Roadmap

- [x] Project setup & repository initialization
- [ ] Core agent loop with task planning
- [ ] NVIDIA LLM integration (multi-model)
- [ ] Image generation pipeline
- [ ] Text-to-speech & speech-to-text
- [ ] Brave Search integration
- [ ] Terminal & code execution tools
- [ ] File management system
- [ ] Screen monitoring & analysis
- [ ] Web browsing automation
- [ ] Telegram bot interface
- [ ] CLI interface with rich output
- [ ] Plugin system for community extensions

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is open source. See the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

MRAgent uses free-tier API keys which may have rate limits and usage quotas. The agent is designed to work within these constraints. Never commit your `.env` file or expose API keys publicly.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/bonzainsights">Bonza Insights</a>
</p>
