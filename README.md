# maubot-llmplus
-------
maubot plugin: llm plus

order:
- !ai info
> View the configuration information currently in official use.
- !ai platform list
> list platforms.
- !ai platform current
> query current platform in use.
- !ai model list
> list models on current platform.
- !ai model current
> query current model in use.
- !ai use [model_name]
> switch model in platform, you can use `!ai model list` command query model list.
- !ai switch [platform_name]
> switch platform
> support platforms:
> - local_ai#ollama
> - local_ai#lmstudio
> - openai
> - anthropic

