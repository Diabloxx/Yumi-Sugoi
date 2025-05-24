# Yumi Sugoi Changelog

## [v1.4.1] - 2025-05-24
### Fixed
- Fixed `!yumi_lockdown` command that was incorrectly changing channel permissions. Now it correctly only restricts Yumi to respond in the locked channel without preventing users from speaking.
- Fixed issue with lockdown settings not persisting after bot restart.
- Updated documentation for lockdown feature to clarify its intended behavior.

## [v1.4.0] - 2025-05-24
### Added
- **Ollama Integration:** Replaced OpenAI with local network Ollama for LLM capabilities.
- **Configurable LLM Settings:** Added support for environment variables to customize the Ollama model, temperature, and other parameters.
- **Enhanced Error Handling:** Better error messages for LLM communication issues.
- **Prompt Logging:** Optional logging of all prompts and responses to help with fine-tuning.
- **Modern White UI:** Redesigned dashboard with cleaner, modern white UI for better usability.

### Changed
- Removed OpenAI dependency in favor of Ollama for better privacy and cost control.
- Updated environment configuration to use Ollama-specific settings.
- Improved compatibility layer to ensure seamless transition from previous OpenAI implementation.
- Restyled dashboard with a modern white UI theme.

### Fixed
- Fixed Live Chat UI rendering in the dashboard.
- Fixed User Management tab UI issues.
- Fixed syntax error in user context handling.
- Added missing `load_hf_model()` function in llm.py for backward compatibility.

## [v1.3.0] - 2025-05-23
### Added
- Major web dashboard upgrade: modern UI with Bootstrap and Font Awesome.
- **Live Chat Console:** Send messages as Yumi to any server/channel, real-time message feed.
- **User Management:** Search users, view profiles (XP, level, facts, infractions, join date), kick/ban/unban users.
- **Scheduled Tasks:** View, add, and delete scheduled announcements/reminders.
- **Persona Management:** Add and delete custom personas from the dashboard.
- **Server Controls:** Change persona mode, lockdown channels, and toggle lockdown for the official server.
- **Moderation Logs:** Real-time log panel (placeholder, ready for real data).
- **API Scaffolding:** Endpoints for all major dashboard features (live chat, users, scheduled tasks, analytics, moderation, audit log).
- **UI Placeholders:** Analytics, moderation, and audit log panels for future expansion.

### Changed
- Refactored dashboard JS for modularity and extensibility.
- Improved dashboard interactivity and responsiveness.

### Notes
- This release lays the foundation for advanced analytics, moderation, and custom command management in future updates.

## [v1.2.3] - 2025-05-23
### Added
- Yumi now displays a typing indicator and random delay before replying, simulating human-like conversation.
- Persona management is fully dynamic: new custom personas are available instantly after creation, and all persona commands use the latest built-in and custom personas without restart.
- Refactored persona commands (`list`, `activate`, `channel persona`) to always use the latest persona list.
- Improved modularity and extensibility for future features.

### Fixed
- Fixed OpenAI API error in `llm.py` by ensuring `qa_pairs` is always a dict.
- Fixed circular import issues between persona and LLM modules.
- Fixed type errors and infinite recursion in message handling.
- Fixed syntax errors and improved error handling in all major features.

### Changed
- Yumi's responses are now more human-like and natural.
- Persona and context switching is now seamless and does not require a bot restart.
- All persistent data and persona changes are reflected instantly in commands and bot behavior.

## [v1.2.2] - 2025-05-23
### Fixed
- Fixed a crash on startup when loading conversation history with new per-user/channel context keys (mixed int and string keys).
- Now gracefully handles both old and new context key formats in `convo_history.json`.

## [v1.2.1] - 2025-05-23
### Added
- Persistent lockdown: Yumi now remembers which channel(s) are locked down in each server, even after a bot restart.
- Lockdown status is saved to `datasets/lockdown_channels.json` and restored on startup.

### Fixed
- Minor bug fixes and reliability improvements for lockdown and changelog posting.

## [v1.2.0] - 2025-05-22
### Added
- Per-user, per-channel context logic: Yumi now keeps conversation context separate for each user in servers.
- Changelog auto-posting: Only new changelog entries are posted to the changelog channel (ID: 1375129643925114973) using `!yumi_post_changelog`.
- `CHANGELOG.md` file for tracking all updates and fixes.
- Improved admin tools: lockdown, unlock, purge, say, and admin help commands.
- Lockdown now means Yumi only replies in the specified channel, but everyone can talk.
- Persona mode display and feedback improvements.

### Changed
- 'Normal' mode is now a friendly, caring AI companion (not flirty by default).
- Updated README.md for clarity and new features.

### Fixed
- Commands now work in all channels, even when lockdown is active.
- Yumi no longer mixes up user prompts in servers.
- Lockdown feedback and error handling improved.

## [v1.1.0] - 2024-12-10
### Added
- Image captioning with BLIP.
- Web search fallback for unknown questions.
- Persistent per-user name memory.
- Rotating Discord status and random DM reminders.

## [v1.0.0] - 2024-06-01
### Added
- Initial release: Multi-persona Discord AI chatbot with OpenAI support, self-learning Q&A, and basic admin tools.
